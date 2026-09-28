import json
import math
from cryptography.exceptions import InvalidSignature
from pathlib import Path

from .security import atomic_json, digest, file_hash, public_key, sign, verify
from .accounting import epsilon
from .evaluation import private_rates


def evaluate_gate(evidence, plan, approvals=()):
    checks = []

    def check(name, passed, reason, status="BLOCKED"):
        checks.append({"name": name, "status": "PASS" if passed else status, "reason": reason})

    check("Approved policy", evidence.get("plan_hash") == digest(plan.model_dump()),
          "The release policy and training configuration must match the evaluated plan")
    receipts = evidence.get("receipts", [])
    keys = evidence.get("institution_keys", {})
    valid_receipts = []
    try:
        for envelope in receipts:
            institution = envelope["payload"]["institution"]
            receipt = verify(envelope, keys[institution])
            if receipt["run_id"] != evidence["run_id"] or receipt["plan_hash"] != evidence["approved_plan_hash"]:
                raise ValueError("Wrong receipt context")
            valid_receipts.append(receipt)
        okay = len(valid_receipts) == 3 and {r["institution"] for r in valid_receipts} == set(plan.participants)
        check("Privacy receipts", okay, "All three institution signatures and run bindings must verify")
    except Exception:
        check("Privacy receipts", False, "Receipt signature or context failed")
    try:
        budget_ok = len(valid_receipts) == 3 and all(
            math.isfinite(r["cap"]) and 0 < r["epsilon"] <= r["cap"] <= 8
            and r["delta"] == plan.delta
            and abs(epsilon(r["events"], r["delta"]) - r["epsilon"]) < 1e-7
            for r in valid_receipts)
    except (ValueError, KeyError, TypeError, OverflowError):
        budget_ok = False
    check("Cumulative budget", budget_ok, "Each local lifetime ledger must remain within its approved cap")
    check("Secure aggregation", evidence.get("secagg", {}).get("complete") is True,
          "Three participants; official Flower protocol; no plaintext fallback")
    evaluation = evidence.get("public_evaluation", {})
    institutions = evaluation.get("institutions", {})
    complete = set(institutions) == set(plan.participants)
    check("Utility evidence", complete, "Held-out evaluation required for every institution", "INCONCLUSIVE")
    if complete:
        check("False-alert limit", all(m["fpr_interval"][1] <= plan.max_fpr for m in institutions.values()),
              f"Upper confidence bound must be ≤ {plan.max_fpr:.1%}")
        check("Fraud recall", all(m["recall_interval"][0] >= plan.min_recall for m in institutions.values()),
              f"Lower confidence bound must be ≥ {plan.min_recall:.0%}")
        baselines = evidence.get("baselines", {}).get("local", {})
        noninferior = set(baselines) == set(plan.participants) and all(
            institutions[k]["recall_interval"][0] >= baselines[k]["recall_interval"][1] - plan.noninferiority_margin
            for k in plan.participants)
        check("Local non-inferiority", noninferior, "Compare each institution with its own local baseline")
    attack = evidence.get("attacks", {}).get("membership", {})
    check("Attack positive control", attack.get("positive_control", {}).get("passed") is True,
          "Membership evaluation needs a successful vulnerable-model control", "INCONCLUSIVE")
    try:
        releases = [verify(v, keys[v["payload"]["institution"]])
                    for v in evidence.get("validation_receipts", [])]
        validation_ok = len(releases) == 3 and {v["institution"] for v in releases} == set(plan.participants)
        validation_ok = validation_ok and all(
            v["run_id"] == evidence["run_id"] and v["model_hash"] == evidence["model_array_hash"]
            and v["threshold"] == evidence["threshold"] and v["epsilon"] == plan.evaluation_epsilon
            and v["sensitivity"] == 1 and len(v["noisy_counts"]) == 4
            and all(isinstance(c, int) for c in v["noisy_counts"]) for v in releases)
        protected = private_rates(releases) if validation_ok else {}
        validation_ok = validation_ok and digest(protected) == digest(evidence.get("private_validation"))
    except (ValueError, KeyError, TypeError, ZeroDivisionError, InvalidSignature):
        validation_ok, protected = False, {}
    check("Validation signatures", validation_ok, "Three signed counts must bind this candidate and threshold")
    check("Validation evidence", protected.get("denominators_supported") is True,
          "Protected validation counts must support denominators", "INCONCLUSIVE")
    check("Protected false-alert limit", protected.get("fpr_interval", [0, 1])[1] <= plan.max_fpr,
          "The governed validation upper bound must satisfy the false-alert policy")
    check("Protected fraud recall", protected.get("recall_interval", [0, 1])[0] >= plan.min_recall,
          "The governed validation lower bound must satisfy the recall policy")
    check("Owner approvals", set(approvals) == set(plan.participants),
          "All institution approvals must bind the current evidence digest")
    statuses = {c["status"] for c in checks}
    status = "BLOCKED" if "BLOCKED" in statuses else "INCONCLUSIVE" if "INCONCLUSIVE" in statuses else "PASS"
    return {"status": status, "checks": checks, "evidence_digest": digest(evidence)}


BUNDLE_FILES = ("model.safetensors", "feature_schema.json", "threshold.json", "privacy_statement.json",
                "evaluation.json", "attack_report.json")


def release_manifest(directory: Path, evidence: dict, plan, approvals, key):
    decision = evaluate_gate(evidence, plan, approvals)
    if decision["status"] != "PASS":
        raise ValueError("Release gate did not pass")
    hashes = {name: file_hash(directory / name) for name in BUNDLE_FILES}
    if hashes != evidence.get("artifact_hashes"):
        raise ValueError("Artifact files changed after evidence evaluation")
    manifest = {"version": 1, "run_id": evidence["run_id"], "files": hashes,
                "evidence_digest": digest(evidence), "plan": plan.model_dump(mode="json"),
                "approvals": sorted(approvals), "claim": "Public-data engineering demonstration",
                "trust": "Honest clients, honest-but-curious non-colluding coordinator; trusted institution hosts",
                "public_key": public_key(key)}
    manifest["build"] = evidence.get("build", {"revision": "test-or-legacy-evidence"})
    manifest["privacy_adjacency"] = "add_remove_one_transaction_in_fixed_slots"
    manifest["institution_privacy"] = [
        {name: r["payload"][name] for name in ("institution", "epsilon", "delta", "cap")} for r in evidence["receipts"]]
    envelope = sign(manifest, key)
    atomic_json(directory / "manifest.json", manifest)
    atomic_json(directory / "manifest.signature.json", envelope)
    return manifest


def verify_bundle(directory: Path, trusted_key: str):
    envelope = json.loads((directory / "manifest.signature.json").read_text())
    manifest = verify(envelope, trusted_key)
    if manifest != json.loads((directory / "manifest.json").read_text()):
        raise ValueError("Manifest contents differ")
    if set(manifest["files"]) != set(BUNDLE_FILES):
        raise ValueError("Unexpected artifact allowlist")
    for name, expected in manifest["files"].items():
        if file_hash(directory / name) != expected:
            raise ValueError("Artifact hash mismatch")
    return manifest
