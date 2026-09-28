import importlib.metadata as metadata
import os
from pathlib import Path
from .security import digest, file_hash


def build_info():
    package = Path(__file__).resolve().parent
    sources = {p.name: file_hash(p) for p in sorted(package.glob("*.py"))}
    lock = Path(os.environ.get("FRAUDSHIELD_DEPENDENCY_LOCK", str(package.parents[1] / "requirements.lock")))
    return {"source_tree_sha256": digest(sources),
            "revision": os.environ.get("FRAUDSHIELD_REVISION", "uncommitted-local-build"),
            "dependency_lock_sha256": file_hash(lock) if lock.exists() else None,
            "runtime": {name: metadata.version(name) for name in ("torch", "opacus", "opendp", "flwr")},
            "implementation": "original FraudShield implementation; no private reference code copied"}
