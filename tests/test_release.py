import copy
import zipfile

import pytest
from safetensors.torch import save_file

from fraudshield.contracts import Plan
from fraudshield.data import SCHEMA
from fraudshield.evaluation import private_rates
from fraudshield.governance import BUNDLE_FILES, evaluate_gate, release_manifest, verify_bundle
from fraudshield.inference import LocalDetector, unpack_verified
from fraudshield.security import atomic_json, digest, file_hash, load_key, public_key, sign
from fraudshield.training import Detector, array_hash, arrays


def candidate(directory):
    """Fabricated unit-test evidence, never exposed as a benchmark result."""
    plan = Plan()
    model = Detector()
    save_file(model.state_dict(), str(directory / "model.safetensors"))
    model_hash = array_hash(arrays(model))
    evidence = {"run_id": "test-only", "approved_plan_hash": "test-plan", "model_array_hash": model_hash,
                "plan_hash": digest(plan.model_dump()),
                "threshold": .5, "receipts": [], "institution_keys": {}, "validation_receipts": [],
                "secagg": {"complete": True}, "public_evaluation": {"institutions": {}},
                "baselines": {"local": {}}, "attacks": {"membership": {"positive_control": {"passed": True}}}}
    for institution in plan.participants:
        key = load_key(directory / (institution + ".key"))
        evidence["institution_keys"][institution] = public_key(key)
        evidence["receipts"].append(sign({"institution": institution, "run_id": "test-only",
            "plan_hash": "test-plan", "epsilon": .5, "delta": plan.delta, "cap": 8,
            "events": [{"kind": "validation", "epsilon": .5}]}, key))
        evidence["validation_receipts"].append(sign({"institution": institution, "run_id": "test-only",
            "model_hash": model_hash, "threshold": .5, "epsilon": .5, "sensitivity": 1,
            "noisy_counts": [9900, 0, 999000, 100]}, key))
        evidence["public_evaluation"]["institutions"][institution] = {
            "fpr_interval": [0, .001], "recall_interval": [.9, .99]}
        evidence["baselines"]["local"][institution] = {"recall_interval": [.8, .9]}
    evidence["private_validation"] = private_rates([v["payload"] for v in evidence["validation_receipts"]])
    atomic_json(directory / "feature_schema.json", SCHEMA)
    atomic_json(directory / "threshold.json", {"threshold": .5})
    for name in ("privacy_statement.json", "evaluation.json", "attack_report.json"):
        atomic_json(directory / name, {"test_only": True})
    evidence["artifact_hashes"] = {name: file_hash(directory / name) for name in BUNDLE_FILES}
    return plan, evidence, load_key(directory / "coordinator.key")


def test_full_signed_release_activation_and_local_scoring(tmp_path):
    plan, evidence, key = candidate(tmp_path)
    manifest = release_manifest(tmp_path, evidence, plan, plan.participants, key)
    assert verify_bundle(tmp_path, public_key(key)) == manifest
    archive = tmp_path / "release.zip"
    with zipfile.ZipFile(archive, "w") as output:
        for name in [*BUNDLE_FILES, "manifest.json", "manifest.signature.json"]:
            output.write(tmp_path / name, name)
    activated = tmp_path / "activated"
    unpack_verified(archive, activated, public_key(key))
    score = LocalDetector(activated, public_key(key)).score([{"amount": 10, "type": "PAYMENT", "step": 1}])
    assert 0 <= score["predictions"][0]["score"] <= 1
    assert (activated / "activation.json").exists()
    (activated / "threshold.json").write_text('{"threshold": 0}')
    with pytest.raises(ValueError, match="hash"):
        LocalDetector(activated, public_key(key))


def test_gate_rejects_tampered_validation_budget_and_artifacts(tmp_path):
    plan, evidence, key = candidate(tmp_path)
    assert evaluate_gate(evidence, plan, plan.participants)["status"] == "PASS"
    changed = copy.deepcopy(evidence)
    changed["validation_receipts"][0]["payload"]["threshold"] = .1
    assert evaluate_gate(changed, plan, plan.participants)["status"] == "BLOCKED"
    changed = copy.deepcopy(evidence)
    changed["private_validation"]["fpr_interval"] = [0, 0]
    assert evaluate_gate(changed, plan, plan.participants)["status"] == "BLOCKED"
    assert evaluate_gate(evidence, plan)["status"] == "BLOCKED"
    (tmp_path / "threshold.json").write_text('{"threshold":0.4}')
    with pytest.raises(ValueError, match="changed"):
        release_manifest(tmp_path, evidence, plan, plan.participants, key)


def test_bundle_rejects_path_traversal_before_extraction(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../outside.json", "{}")
    with pytest.raises(ValueError, match="paths"):
        unpack_verified(archive, tmp_path / "activation", "invalid-key")
    assert not (tmp_path / "outside.json").exists()
