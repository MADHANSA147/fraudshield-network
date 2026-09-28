"""Row-local, fixed public preprocessing. No fitted private-data statistics."""
import csv
import hashlib
import math
from pathlib import Path

import numpy as np

from .contracts import Transaction
from .security import digest, file_hash

TYPES = ("CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER", "UNKNOWN")
FEATURES = ("log_amount", "log_sender_balance", "amount_balance_ratio", "hour_sin", "hour_cos",
            "balance_missing", *(f"type_{t}" for t in TYPES))
SCHEMA = {"version": "1", "features": FEATURES, "amount_bound": 1e7, "balance_bound": 1e8,
          "prediction_time": "before_execution", "privacy_unit": "transaction",
          "excluded": ["newbalanceOrig", "newbalanceDest", "oldbalanceDest", "isFlaggedFraud",
                       "nameOrig", "nameDest", "isFraud"], "row_local": True}
SCHEMA_HASH = digest(SCHEMA)


def features(row: dict) -> np.ndarray:
    t = Transaction.model_validate({k: row[k] for k in Transaction.model_fields if k in row})
    amount = min(t.amount, 1e7)
    balance = min(t.oldbalanceOrg or 0, 1e8)
    phase = 2 * math.pi * (t.step % 24) / 24
    values = [math.log1p(amount) / math.log1p(1e7), math.log1p(balance) / math.log1p(1e8),
              min(amount / max(balance, 1), 10) / 10, math.sin(phase), math.cos(phase),
              float(t.oldbalanceOrg is None)]
    kind = t.type if t.type in TYPES else "UNKNOWN"
    return np.asarray(values + [float(kind == v) for v in TYPES], dtype=np.float32)


def fixture(n: int, seed: int, institution: int = 0):
    """Public synthetic engineering fixture, deliberately not labeled PaySim."""
    rng = np.random.default_rng(seed)
    rows, labels = [], []
    for i in range(n):
        kind = str(rng.choice(TYPES[:5], p=[.1, .15, .1, .4 - institution * .04, .25 + institution * .04]))
        amount = float(np.exp(rng.normal(7.5 + institution * .3, 1.8)))
        balance = float(np.exp(rng.normal(8.5, 1.8)))
        step = int(rng.integers(0, 720))
        row = {"amount": amount, "oldbalanceOrg": balance, "type": kind, "step": step}
        # Stochastic fixture labels allow useful smoke tests without asserting real-world utility.
        score = -6 + 2.3 * (kind in ("TRANSFER", "CASH_OUT")) + 2.4 * (amount > balance) + .5 * (step % 24 < 6)
        labels.append(float(rng.random() < 1 / (1 + np.exp(-score))))
        rows.append(features(row))
    return np.asarray(rows, dtype=np.float32), np.asarray(labels, dtype=np.float32)


def load_paysim(path: Path):
    required = {"step", "type", "amount", "oldbalanceOrg", "nameOrig", "isFraud"}
    records = []
    owners = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("PaySim schema is missing required fields")
        for row in reader:
            label = int(row["isFraud"])
            if label not in (0, 1):
                raise ValueError("Labels must be binary")
            account = row["nameOrig"]
            if account not in owners:
                # Public benchmark routing: mild label-independent type skew
                # with overlapping support, stable for every sender's records.
                value = int(hashlib.sha256(account.encode()).hexdigest()[:8], 16) / 2**32
                cuts = {"TRANSFER": (.45, .75), "CASH_OUT": (.25, .70),
                        "PAYMENT": (.30, .55)}.get(row["type"], (1 / 3, 2 / 3))
                owners[account] = int(value >= cuts[0]) + int(value >= cuts[1])
            partition = owners[account]
            clean = {"amount": float(row["amount"]), "oldbalanceOrg": float(row["oldbalanceOrg"]),
                     "step": int(row["step"]), "type": row["type"]}
            records.append((features(clean), label, int(row["step"]), account, partition))
    if not records:
        raise ValueError("Dataset is empty")
    return records, {"source": "user_supplied_paysim", "sha256": file_hash(path),
                     "schema_hash": SCHEMA_HASH, "rows": len(records)}


def temporal_group_split(records):
    """Public benchmark split. Purge sender groups spanning time boundaries."""
    times = np.array([r[2] for r in records])
    cuts = np.quantile(times, [.15, .65, .8])
    assignment = np.searchsorted(cuts, times, side="right")
    groups = {}
    for record, split in zip(records, assignment):
        groups.setdefault(record[3], set()).add(int(split))
    names = ("development", "train", "validation", "test")
    outputs = {name: {i: [] for i in range(3)} for name in names}
    dropped = 0
    for record, split in zip(records, assignment):
        if len(groups[record[3]]) != 1:
            dropped += 1
            continue
        outputs[names[split]][record[4]].append(record[:2])
    for name in names:
        for i in range(3):
            values = outputs[name][i]
            outputs[name][i] = (np.array([x for x, _ in values], dtype=np.float32).reshape(-1, len(FEATURES)),
                                np.array([y for _, y in values], dtype=np.float32))
    return outputs, {"cutoffs": cuts.tolist(), "purged_cross_time_senders_rows": dropped,
                     "destination_identity_separation": False}
