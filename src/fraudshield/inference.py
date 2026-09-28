"""Institution-local activation. No pickle model loading and no outbound requests."""
import json
import math
import tempfile
import zipfile
from pathlib import Path

import numpy as np
from safetensors.torch import load_file

from .contracts import Plan, Transaction
from .data import SCHEMA, features
from .governance import BUNDLE_FILES, verify_bundle
from .security import atomic_json, digest
from .training import Detector, predict


def unpack_verified(archive: Path, destination: Path, trusted_key: str):
    allowed = {*BUNDLE_FILES, "manifest.json", "manifest.signature.json"}
    if destination.exists():
        raise ValueError("Activation destination must be new")
    with tempfile.TemporaryDirectory(prefix="fraudshield-verify-") as temp:
        stage = Path(temp)
        with zipfile.ZipFile(archive) as bundle:
            entries = bundle.infolist()
            if len(entries) != len(allowed) or {i.filename for i in entries} != allowed:
                raise ValueError("Unexpected, missing, duplicate, or unsafe bundle paths")
            if sum(i.file_size for i in entries) > 16 * 1024 * 1024:
                raise ValueError("Bundle exceeds the detector size limit")
            for entry in entries:
                if entry.is_dir() or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("Directory or symlink in bundle")
                (stage / entry.filename).write_bytes(bundle.read(entry))
        manifest = verify_bundle(stage, trusted_key)
        # Validate the full inference contract before activation.
        LocalDetector(stage, trusted_key)
        destination.mkdir(parents=True)
        for name in allowed:
            (destination / name).write_bytes((stage / name).read_bytes())
        atomic_json(destination / "activation.json", {
            "run_id": manifest["run_id"], "manifest_digest": digest(manifest),
            "trusted_key": trusted_key, "execution": "institution_local",
        })
    return manifest


class LocalDetector:
    def __init__(self, directory: Path, trusted_key: str):
        self.manifest = verify_bundle(directory, trusted_key)
        Plan.model_validate(self.manifest["plan"])
        schema = json.loads((directory / "feature_schema.json").read_text())
        if digest(schema) != digest(SCHEMA):
            raise ValueError("Unsupported feature schema")
        self.threshold = json.loads((directory / "threshold.json").read_text())["threshold"]
        if not isinstance(self.threshold, (int, float)) or not math.isfinite(self.threshold) or not 0 <= self.threshold <= 1:
            raise ValueError("Invalid released threshold")
        self.model = Detector()
        self.model.load_state_dict(load_file(str(directory / "model.safetensors")), strict=True)
        if not all(np.isfinite(v.detach().numpy()).all() for v in self.model.state_dict().values()):
            raise ValueError("Nonfinite released model")

    def score(self, records: list[dict]):
        if not records or len(records) > 10000:
            raise ValueError("Provide between 1 and 10000 transactions")
        validated = [Transaction.model_validate(r).model_dump() for r in records]
        scores = predict(self.model, np.stack([features(r) for r in validated]))
        return {"run_id": self.manifest["run_id"], "threshold": self.threshold,
                "claim": self.manifest["claim"],
                "predictions": [{"score": float(s), "flag": bool(s >= self.threshold)} for s in scores],
                "execution": "local; no records transmitted"}
