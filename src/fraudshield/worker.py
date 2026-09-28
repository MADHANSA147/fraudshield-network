import sys
import time

import numpy as np
import torch
from safetensors.torch import save_file

from . import store
from .accounting import calibrate
from .attacks import membership_report, poisoning_diagnostic, single_gradient_leakage
from .contracts import Plan
from .data import SCHEMA
from .datasets import public_split
from .benchmark import public_federated_ablation
from .evaluation import metrics, private_rates, threshold_from_public_development
from .federation import Federation
from .governance import evaluate_gate
from .ledger import BudgetExceeded
from .security import atomic_json, digest, file_hash, load_key
from .governance import BUNDLE_FILES
from .training import Detector, array_hash, predict, set_arrays, train_public
from .provenance import build_info


def execute(run_id):
    started = time.perf_counter()
    federation = None
    try:
        with store.session() as db:
            run = db.get(store.Run, run_id)
            if run is None or run.status != "QUEUED":
                return
            # Conditional claim prevents duplicate queue deliveries from executing twice.
            claimed = db.query(store.Run).filter(store.Run.id == run_id, store.Run.status == "QUEUED").update(
                {"status": "PREPARING", "stage": "Checking approved mechanism"})
            if claimed != 1:
                return
            plan, tenant_id = Plan.model_validate(run.plan), run.tenant_id
            already_cancelled = run.cancelled
        if already_cancelled:
            raise InterruptedError("Cancelled before mechanism execution")
        if plan.mode not in ("public_fixture", "public_paysim"):
            raise ValueError("This runner accepts public benchmarks only")
        torch.set_num_threads(1)
        directory = store.ROOT / "artifacts" / tenant_id / run_id
        directory.mkdir(parents=True, exist_ok=True)
        key = load_key(store.ROOT / "keys" / tenant_id / "coordinator.key")
        sigma = calibrate(plan)
        store.transition(run_id, "TRAINING", "Enrolling three isolated institution workers")
        federation = Federation(plan, run_id, store.ROOT / "institutions" / tenant_id, sigma, key)
        federation.start()

        def cancelled():
            with store.session() as db:
                return db.get(store.Run, run_id).cancelled

        def on_round(number, receipts, wire_bytes):
            store.transition(run_id, "TRAINING", f"Secure round {number} complete", round=number, wire_bytes=wire_bytes)
            with store.session() as db:
                store.event(db, tenant_id, run_id, "PRIVACY_RECEIPTS",
                            {"institutions": [{"institution": r["payload"]["institution"],
                                               "epsilon": r["payload"]["epsilon"], "delta": r["payload"]["delta"]}
                                              for r in receipts]})

        values = federation.train(on_round, cancelled)
        if cancelled():
            raise InterruptedError("Cancelled before evaluation")
        model = Detector()
        set_arrays(model, values)
        save_file(model.state_dict(), str(directory / "model.safetensors"))
        store.transition(run_id, "VALIDATING", "Selecting threshold on public development records")
        data_root = store.ROOT / "institutions" / tenant_id
        devs = [public_split(plan, i, "development", data_root / institution / "dataset")
                for i, institution in enumerate(plan.participants)]
        dev_x, dev_y = np.concatenate([x for x, _ in devs]), np.concatenate([y for _, y in devs])
        threshold = threshold_from_public_development(dev_y, predict(model, dev_x), plan.max_fpr)
        public_results, local_results = {}, {}
        pooled_x, pooled_y = [], []
        test_sets = []
        for i, institution in enumerate(plan.participants):
            x, y = public_split(plan, i, "train", data_root / institution / "dataset")
            tx, ty = public_split(plan, i, "test", data_root / institution / "dataset")
            pooled_x.append(x)
            pooled_y.append(y)
            test_sets.append((tx, ty))
            public_results[institution] = metrics(ty, predict(model, tx), threshold)
            baseline = train_public(x, y, seed=plan.seed, steps=plan.rounds * plan.local_steps,
                                    positive_weight=plan.positive_weight)
            bt = threshold_from_public_development(dev_y, predict(baseline, dev_x), plan.max_fpr)
            local_results[institution] = metrics(ty, predict(baseline, tx), bt)
        px, py = np.concatenate(pooled_x), np.concatenate(pooled_y)
        tx, ty = np.concatenate([x for x, _ in test_sets]), np.concatenate([y for _, y in test_sets])
        pooled = train_public(px, py, seed=plan.seed, steps=plan.rounds * plan.local_steps,
                              positive_weight=plan.positive_weight)
        pt = threshold_from_public_development(dev_y, predict(pooled, dev_x), plan.max_fpr)
        logistic = train_public(px, py, seed=plan.seed, steps=plan.rounds * plan.local_steps, linear=True,
                                positive_weight=plan.positive_weight)
        lt = threshold_from_public_development(dev_y, predict(logistic, dev_x), plan.max_fpr)
        ablations = {}
        for name, noise in (("federated_nonprivate", None), ("dp_without_secagg", sigma)):
            ablation, trace = public_federated_ablation(
                list(zip(pooled_x, pooled_y)), plan, sigma=noise, directory=directory / "public-ablations" / name)
            at = threshold_from_public_development(dev_y, predict(ablation, dev_x), plan.max_fpr)
            ablations[name] = {"metrics": metrics(ty, predict(ablation, tx), at), **trace}
        store.transition(run_id, "VALIDATING", "Releasing budgeted confusion counts")
        validation = federation.validate(values, threshold)
        receipts = federation.receipts()
        store.transition(run_id, "EVALUATING_ATTACKS", "Running public membership and exposure diagnostics")
        attacks = {"membership": membership_report(model, (px, py), (tx, ty), seed=plan.seed),
                   "gradient_exposure": single_gradient_leakage(plan.seed),
                   "poisoning": poisoning_diagnostic(model, tx[:512], ty[:512])}
        evaluation = {"aggregate": metrics(ty, predict(model, tx), threshold), "institutions": public_results}
        evidence = {"run_id": run_id, "approved_plan_hash": digest(federation.approved),
                    "build": build_info(), "evidence_schema_version": 2,
                    "plan_hash": digest(plan.model_dump()),
                    "source": "generated_public_fixture_not_paysim" if plan.mode == "public_fixture" else "user_supplied_public_paysim",
                    "model_hash": file_hash(directory / "model.safetensors"),
                    "model_array_hash": array_hash(values),
                    "threshold": threshold, "sigma": sigma, "receipts": receipts, "institution_keys": federation.keys,
                    "public_evaluation": evaluation,
                    "private_validation": private_rates([v["payload"] for v in validation]),
                    "validation_receipts": validation, "attacks": attacks,
                    "baselines": {"local": local_results, "pooled_public": metrics(ty, predict(pooled, tx), pt),
                                  "logistic_public": metrics(ty, predict(logistic, tx), lt), **ablations},
                    "secagg": {"complete": True, "implementation": "Flower SecAggPlusWorkflow 1.36.0",
                               "transport": "three local child processes; trusted host",
                               "participants": 3, "threshold": 3, "boundary_trace": federation.grid.trace},
                    "limitations": ["Generated engineering fixture; not real-bank validation" if plan.mode == "public_fixture"
                                    else "User-supplied synthetic PaySim benchmark; not real-bank validation",
                                    "Limited membership-attack sample; no universal resistance claim",
                                    "Local processes do not isolate against the host administrator",
                                    "Public RNG mode; not a confidential-data release"]}
        atomic_json(directory / "feature_schema.json", SCHEMA)
        atomic_json(directory / "threshold.json", {"threshold": threshold, "source": "public_development"})
        atomic_json(directory / "privacy_statement.json", {"receipts": receipts, "keys": federation.keys})
        atomic_json(directory / "evaluation.json", {"public": evaluation, "governed": evidence["private_validation"]})
        atomic_json(directory / "attack_report.json", attacks)
        evidence["artifact_hashes"] = {name: file_hash(directory / name) for name in BUNDLE_FILES}
        atomic_json(directory / "evidence.json", evidence)
        decision = evaluate_gate(evidence, plan)
        store.transition(run_id, "EVIDENCE_READY", "Evidence complete; review release requirements",
                         evidence=evidence, decision=decision, duration_seconds=time.perf_counter() - started,
                         wire_bytes=federation.grid.bytes_sent + federation.grid.bytes_received)
    except InterruptedError:
        store.transition(run_id, "ABORTED", "Cancelled; committed privacy spend retained")
    except Exception as error:
        status = "BUDGET_BLOCKED" if isinstance(error, BudgetExceeded) or "budget" in str(error).lower() else "FAILED"
        store.transition(run_id, status, "Run stopped without releasing a model",
                         error=f"{type(error).__name__}: {str(error)[:300]}",
                         duration_seconds=time.perf_counter() - started)
    finally:
        if federation:
            federation.close()


if __name__ == "__main__":
    store.init()
    execute(sys.argv[1])
