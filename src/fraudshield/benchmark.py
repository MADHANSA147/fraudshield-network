"""Ablations are deliberately restricted to already-public benchmark arrays."""
from pathlib import Path

import numpy as np
import torch

from .contracts import Plan
from .ledger import PrivacyLedger
from .training import Detector, SlotDataset, array_hash, arrays, set_arrays, train_private


def public_federated_ablation(datasets, plan: Plan, *, sigma=None, directory: Path | None = None):
    if plan.mode == "confidential":
        raise ValueError("Plaintext ablations cannot access confidential datasets")
    if sigma is not None and directory is None:
        raise ValueError("Private-mechanism ablation requires durable local ledgers")
    torch.manual_seed(plan.seed)
    model = Detector()
    trace = []
    for round_number in range(1, plan.rounds + 1):
        start = arrays(model)
        updates = []
        for index, (x, y) in enumerate(datasets):
            local = Detector()
            set_arrays(local, start)
            if sigma is not None:
                home = directory / str(index)
                ledger = PrivacyLedger(home / "privacy.db", "independent-public-ablation", 8, plan.delta)
                local, _ = train_private(local, x, y, plan, sigma, ledger,
                                         str(round_number), home / "checkpoints")
            else:
                data = SlotDataset(x, y, plan.capacity)
                generator = torch.Generator().manual_seed(plan.seed + index + 1000 * round_number)
                optimizer = torch.optim.SGD(local.parameters(), lr=plan.learning_rate)
                loss_fn = torch.nn.BCEWithLogitsLoss(reduction="none", pos_weight=torch.tensor(plan.positive_weight))
                for _ in range(plan.local_steps):
                    chosen = torch.rand(plan.capacity, generator=generator) < plan.sample_rate
                    optimizer.zero_grad()
                    # Normalize by public expected batch size, as DPOptimizer does.
                    loss = (loss_fn(local(data.x[chosen]), data.y[chosen]) * data.valid[chosen]).sum() / plan.batch_size
                    loss.backward()
                    optimizer.step()
            updates.append(arrays(local))
        # Match Flower's post-training clipping range in the comparison.
        result = [np.mean([np.clip(u[k], -8, 8) for u in updates], axis=0) for k in range(len(start))]
        set_arrays(model, result)
        trace.append({"round": round_number, "aggregate_hash": array_hash(result),
                      "coordinator_observes": "individual model arrays",
                      "individual_update_l2": [float(np.sqrt(sum(np.sum((a - b)**2) for a, b in zip(u, start))))
                                               for u in updates]})
    return model, {"source": "public_benchmark_only", "secure_aggregation": False,
                   "differential_privacy_mechanism": sigma is not None, "trace": trace}
