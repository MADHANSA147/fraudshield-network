"""Fail-closed, conservative, transactional dataset-lineage accounting."""
import json
import sqlite3
import time
from pathlib import Path

from .accounting import epsilon
from .security import canonical, digest


class BudgetExceeded(ValueError):
    pass


class PrivacyLedger:
    def __init__(self, path: Path, lineage: str, cap: float, delta: float):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.lineage, self.cap, self.delta = path, lineage, cap, delta
        with self.connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS policies(lineage TEXT PRIMARY KEY, cap REAL, delta REAL)")
            con.execute("CREATE TABLE IF NOT EXISTS events(lineage TEXT, reservation TEXT, spec_hash TEXT, "
                        "event TEXT, epsilon REAL, created REAL, output TEXT, PRIMARY KEY(lineage,reservation))")
            con.execute("INSERT OR IGNORE INTO policies VALUES(?,?,?)", (lineage, cap, delta))
            policy = con.execute("SELECT cap,delta FROM policies WHERE lineage=?", (lineage,)).fetchone()
            if tuple(policy) != (cap, delta):
                raise ValueError("Existing dataset privacy policy cannot be reset by a new job")

    def connect(self):
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=FULL")
        return con

    def preflight(self, proposed):
        """Advisory full-plan check; each execution still reserves atomically."""
        with self.connect() as con:
            rows = con.execute("SELECT reservation,event FROM events WHERE lineage=?", (self.lineage,)).fetchall()
        existing = {r["reservation"]: json.loads(r["event"]) for r in rows}
        pending = []
        for key, event in proposed:
            if key in existing:
                if canonical(existing[key]) != canonical(event):
                    raise ValueError("Approved mechanism differs from prior reservation")
            else:
                pending.append(event)
        total = epsilon([*existing.values(), *pending], self.delta)
        if total > self.cap:
            raise BudgetExceeded("Full approved plan would exceed the local lifetime budget")
        return total

    def reserve(self, key: str, spec: dict, event: dict) -> dict:
        event = json.loads(canonical(event))
        spec_hash = digest({"spec": spec, "event": event})
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            old = con.execute("SELECT * FROM events WHERE lineage=? AND reservation=?", (self.lineage, key)).fetchone()
            if old:
                if old["spec_hash"] != spec_hash:
                    raise ValueError("Idempotency key reused with different inputs")
                return {**dict(old), "cached": True}
            history = [json.loads(r[0]) for r in con.execute("SELECT event FROM events WHERE lineage=? ORDER BY created,reservation", (self.lineage,))]
            total = epsilon(history + [event], self.delta)
            if total > self.cap:
                raise BudgetExceeded(f"Operation would exceed the approved lifetime budget ({total:.4f} > {self.cap})")
            now = time.time()
            con.execute("INSERT INTO events VALUES(?,?,?,?,?,?,NULL)",
                        (self.lineage, key, spec_hash, canonical(event).decode(), total, now))
            return {"reservation": key, "epsilon": total, "cached": False, "spec_hash": spec_hash}

    def complete(self, key: str, output_digest: str):
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT output FROM events WHERE lineage=? AND reservation=?", (self.lineage, key)).fetchone()
            if row is None:
                raise ValueError("No reservation")
            if row[0] and row[0] != output_digest:
                raise ValueError("Reservation already has a different output")
            con.execute("UPDATE events SET output=? WHERE lineage=? AND reservation=?", (output_digest, self.lineage, key))

    def summary(self):
        with self.connect() as con:
            rows = con.execute("SELECT * FROM events WHERE lineage=? ORDER BY created,reservation", (self.lineage,)).fetchall()
            events = [json.loads(r["event"]) for r in rows]
        return {"epsilon": epsilon(events, self.delta), "rdp_upper_bound": epsilon(events, self.delta, True),
                "delta": self.delta, "cap": self.cap, "events": events,
                "reservations": [{"id": r["reservation"], "spec_hash": r["spec_hash"],
                                  "output_digest": r["output"], "state": "complete" if r["output"] else "charged"}
                                 for r in rows],
                "adjacency": "add_remove_one_transaction_in_fixed_slots", "accountant": "Opacus PRV",
                "reservation_policy": "charged_before_execution_no_refunds"}
