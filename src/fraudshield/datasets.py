import json
from pathlib import Path

import numpy as np

from .data import FEATURES, SCHEMA_HASH, fixture
from .security import file_hash


def public_split(plan, index, split, directory: Path | None = None):
    if plan.mode == "public_fixture":
        offsets = {"train": 0, "development": 10000, "validation": 20000, "test": 30000}
        size = plan.capacity * 3 // 4 if split == "train" else 4096
        return fixture(size, plan.seed + offsets[split] + index * 101, index)
    if plan.mode not in ("public_paysim", "confidential") or directory is None:
        raise ValueError("Institution dataset path is required")
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("schema_hash") != SCHEMA_HASH:
        raise ValueError("Institution feature schema mismatch")
    path = directory / (split + ".npz")
    if file_hash(path) != manifest["files"][path.name]:
        raise ValueError("Prepared dataset integrity failure")
    with np.load(path, allow_pickle=False) as data:
        x, y = data["x"], data["y"]
    if x.ndim != 2 or x.shape[1] != len(FEATURES) or len(x) != len(y) or y.ndim != 1:
        raise ValueError("Prepared dataset shape mismatch")
    if not len(y) or not np.isfinite(x).all() or not np.isin(y, [0, 1]).all():
        raise ValueError("Prepared dataset contains empty or invalid records")
    if split == "train" and len(y) > plan.capacity:
        if plan.mode == "confidential":
            raise ValueError("Confidential records exceed approved slot capacity")
        # Declared public-only chronological prefix; never silently truncate confidential data.
        x, y = x[:plan.capacity], y[:plan.capacity]
    return x.astype(np.float32), y.astype(np.float32)
