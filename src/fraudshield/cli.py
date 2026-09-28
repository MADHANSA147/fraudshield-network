"""Operator commands. Run with python -m fraudshield.cli or fraudshield."""
import argparse
import json
import os
import time
import uuid
from pathlib import Path

from .contracts import INSTITUTIONS, Plan
from .security import atomic_json, digest, file_hash, load_key, public_key


def new_workspace(name):
    from . import store
    store.init()
    tenant_id = str(uuid.uuid4())
    with store.session() as db:
        db.add(store.Tenant(id=tenant_id, name=name, created=time.time()))
        token = store.issue_token(db, tenant_id, "admin", days=7)
        for slug, info in INSTITUTIONS.items():
            db.add(store.Institution(id=str(uuid.uuid4()), tenant_id=tenant_id,
                                     slug=slug, name=info["name"], status="DEMO_READY"))
    return tenant_id, token


def run_local(plan, tenant_id):
    from . import store
    from .worker import execute
    run_id = str(uuid.uuid4())
    with store.session() as db:
        if not db.get(store.Tenant, tenant_id):
            raise ValueError("Unknown workspace")
        db.add(store.Run(id=run_id, tenant_id=tenant_id, idempotency=run_id,
                        plan_hash=digest(plan.model_dump()), plan=plan.model_dump(),
                        status="QUEUED", stage="CLI run queued", active_slot=tenant_id,
                        created=time.time(), updated=time.time()))
    execute(run_id)
    with store.session() as db:
        return store.run_view(db.get(store.Run, run_id), detail=True)


def main():
    parser = argparse.ArgumentParser(description="FraudShield institution and benchmark tools")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Serve API and built React application")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    workspace = commands.add_parser("workspace", help="Create a public demonstration workspace")
    workspace.add_argument("--name", default="Local consortium")
    run = commands.add_parser("run", help="Execute an approved public-data plan")
    run.add_argument("--workspace", required=True)
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--dataset", type=Path, help="Prepared public PaySim directory")
    prepare = commands.add_parser("prepare-paysim", help="Prepare a user-supplied public PaySim CSV")
    prepare.add_argument("csv", type=Path)
    prepare.add_argument("output", type=Path)
    bench = commands.add_parser("benchmark", help="Run independent public-fixture studies; never resets a private ledger")
    bench.add_argument("--output", type=Path, default=Path("benchmark-results"))
    bench.add_argument("--seeds", default="42,43,44")
    bench.add_argument("--epsilons", default="2,4,8")
    bench.add_argument("--rounds", type=int, default=3)
    bench.add_argument("--steps", type=int, default=12)
    bench.add_argument("--plan", type=Path, help="Use a frozen full plan; seed and epsilon vary across the sweep")
    verify = commands.add_parser("verify", help="Verify an unpacked released bundle against a pinned key")
    verify.add_argument("directory", type=Path)
    verify.add_argument("--trusted-key", required=True)
    activate = commands.add_parser("activate", help="Verify and activate a released ZIP locally")
    activate.add_argument("archive", type=Path)
    activate.add_argument("destination", type=Path)
    activate.add_argument("--trusted-key", required=True)
    score = commands.add_parser("score", help="Score JSON transaction array locally; no network")
    score.add_argument("directory", type=Path)
    score.add_argument("records", type=Path)
    score.add_argument("--trusted-key", required=True)
    enroll = commands.add_parser("enroll", help="Enroll an institution signing identity")
    enroll.add_argument("--url", required=True)
    enroll.add_argument("--token", required=True)
    enroll.add_argument("--directory", type=Path, required=True)
    recover = commands.add_parser("recover", help="Mark an abandoned job aborted after stopping its worker")
    recover.add_argument("run_id")
    recover.add_argument("--worker-stopped", action="store_true", required=True)
    contract = commands.add_parser("remote-contract", help="Create a signed contract for institution review")
    contract.add_argument("--plan", type=Path, required=True)
    contract.add_argument("--key", type=Path, required=True)
    contract.add_argument("--output", type=Path, required=True)
    agent_approve = commands.add_parser("agent-approve", help="Locally authorize the exact signed training contract")
    agent_approve.add_argument("contract", type=Path)
    agent_approve.add_argument("--trusted-key", required=True)
    agent_approve.add_argument("--directory", type=Path, required=True)
    agent_serve = commands.add_parser("agent-serve", help="Run an institution listener with mutual TLS")
    agent_serve.add_argument("config", type=Path)
    agent_prepare = commands.add_parser("agent-prepare", help="Prepare training and validation records entirely on this institution host")
    agent_prepare.add_argument("--train", type=Path, required=True)
    agent_prepare.add_argument("--validation", type=Path, required=True)
    agent_prepare.add_argument("--directory", type=Path, required=True)
    remote = commands.add_parser("remote-run", help="Train a candidate on three TLS institution endpoints")
    remote.add_argument("contract", type=Path)
    remote.add_argument("--key", type=Path, required=True)
    remote.add_argument("--config", type=Path, required=True)
    remote.add_argument("--public-development", type=Path, required=True, help="Public NPZ x/y, never private records")
    remote.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn
        uvicorn.run("fraudshield.api:app", host=args.host, port=args.port)
        return
    if args.command == "workspace":
        tenant, token = new_workspace(args.name)
        print(json.dumps({"workspace": tenant, "admin_bearer_token": token,
                          "note": "Store securely; token expires in seven days"}))
    elif args.command == "run":
        from . import store
        store.init()
        plan = Plan.model_validate_json(args.plan.read_text())
        if plan.mode == "confidential":
            raise ValueError("Confidential mode is not deployed")
        if plan.mode == "public_paysim":
            import shutil
            if args.dataset is None:
                raise ValueError("Provide --dataset for a PaySim run")
            for institution in plan.participants:
                source = args.dataset / institution
                destination = store.ROOT / "institutions" / args.workspace / institution / "dataset"
                if destination.exists():
                    if file_hash(source / "manifest.json") != file_hash(destination / "manifest.json"):
                        raise ValueError("Cannot swap a workspace's registered dataset")
                else:
                    shutil.copytree(source, destination)
        result = run_local(plan, args.workspace)
        print(json.dumps({"run_id": result["id"], "status": result["status"], "decision": result["decision"]}))
        if result["status"] != "EVIDENCE_READY":
            raise SystemExit(1)
    elif args.command == "prepare-paysim":
        from .data import SCHEMA_HASH, load_paysim, temporal_group_split
        import numpy as np
        if args.output.exists():
            raise ValueError("Choose a new output directory; existing data is never overwritten")
        rows, provenance = load_paysim(args.csv)
        splits, partition = temporal_group_split(rows)
        args.output.mkdir(parents=True)
        for index, institution in enumerate(INSTITUTIONS):
            folder = args.output / institution
            folder.mkdir()
            for name, partitions in splits.items():
                x, y = partitions[index]
                np.savez_compressed(folder / (name + ".npz"), x=x, y=y)
            atomic_json(folder / "manifest.json", {"source": provenance, "partition": partition,
                        "schema_hash": SCHEMA_HASH,
                        "files": {p.name: file_hash(p) for p in folder.glob("*.npz")},
                        "capacity_policy": "First capacity training records in CSV order; public benchmark only"})
        atomic_json(args.output / "manifest.json", {**provenance, **partition,
                    "institution_assignment": "Sender ownership fixed by SHA-256 and first transaction type; overlapping type skew",
                    "warning": "Synthetic PaySim benchmark; partition is not a real bank consortium",
                    "splits": {k: {str(i): {"rows": len(y), "positives": int(y.sum())}
                                    for i, (_, y) in v.items()} for k, v in splits.items()}})
        print(str(args.output.resolve() / "manifest.json"))
    elif args.command == "benchmark":
        args.output.mkdir(parents=True, exist_ok=True)
        results = []
        for seed in map(int, args.seeds.split(",")):
            for budget in map(float, args.epsilons.split(",")):
                # Independently simulated public datasets only. No production budget bypass.
                tenant, _ = new_workspace("Public benchmark seed " + str(seed))
                config = (json.loads(args.plan.read_text()) if args.plan else
                          {"rounds": args.rounds, "local_steps": args.steps})
                config.update(name="Public fixture comparison", seed=seed, epsilon_cap=budget, mode="public_fixture")
                plan = Plan.model_validate(config)
                result = run_local(plan, tenant)
                atomic_json(args.output / (result["id"] + ".json"), result)
                ev = result.get("evidence") or {}
                results.append({"run_id": result["id"], "seed": seed, "planned_epsilon": budget,
                                "status": result["status"], "decision": (result.get("decision") or {}).get("status"),
                                "duration_seconds": result["duration_seconds"], "wire_bytes": result["wire_bytes"],
                                "metrics": ev.get("public_evaluation", {}).get("aggregate"),
                                "epsilon": max([r["payload"]["epsilon"] for r in ev.get("receipts", [])], default=None)})
                atomic_json(args.output / "summary.json", {"source": "generated_public_fixture_not_paysim",
                            "independent_public_studies": True,
                            "configuration": {k: v for k, v in plan.model_dump().items() if k not in ("seed", "epsilon_cap", "name")},
                            "results": results})
                print(json.dumps(results[-1]), flush=True)
    elif args.command == "verify":
        from .governance import verify_bundle
        print(json.dumps(verify_bundle(args.directory, args.trusted_key), indent=2))
    elif args.command == "activate":
        from .inference import unpack_verified
        print(json.dumps(unpack_verified(args.archive, args.destination, args.trusted_key), indent=2))
    elif args.command == "score":
        from .inference import LocalDetector
        print(json.dumps(LocalDetector(args.directory, args.trusted_key).score(json.loads(args.records.read_text())), indent=2))
    elif args.command == "enroll":
        import httpx
        from urllib.parse import urlparse
        parsed = urlparse(args.url)
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1")):
            raise ValueError("Enrollment requires HTTPS outside localhost")
        key = load_key(args.directory / "identity.key")
        response = httpx.post(args.url.rstrip("/") + "/api/connectors/enroll",
                              json={"token": args.token, "public_key": public_key(key)}, timeout=30)
        response.raise_for_status()
        path = args.directory / "connector.json"
        atomic_json(path, {"url": args.url, **response.json()})
        if os.name != "nt":
            path.chmod(0o600)
        print("Enrollment stored locally. This registers identity; it does not start confidential training.")
    elif args.command == "recover":
        from . import store
        store.init()
        with store.session() as db:
            job = db.get(store.Run, args.run_id)
            if not job or not job.active_slot:
                raise ValueError("No active job to recover")
        store.transition(args.run_id, "ABORTED", "Operator recovered abandoned job; privacy charges retained")
        print("Recovered. Local privacy ledgers were not altered.")
    elif args.command == "remote-contract":
        from .accounting import calibrate
        from .data import SCHEMA_HASH
        from .security import sign
        plan = Plan.model_validate_json(args.plan.read_text())
        approved = {"plan": plan.model_dump(), "run_id": str(uuid.uuid4()),
                    "schema_hash": SCHEMA_HASH, "sigma": calibrate(plan)}
        key = load_key(args.key)
        atomic_json(args.output, sign(approved, key))
        print(json.dumps({"approved_hash": digest(approved), "coordinator_public_key": public_key(key)}))
    elif args.command == "agent-approve":
        from .security import verify
        approved = verify(json.loads(args.contract.read_text()), args.trusted_key)
        plan = Plan.model_validate(approved["plan"])
        if plan.mode == "confidential":
            from opacus import PrivacyEngine
            PrivacyEngine(secure_mode=True)  # Approval itself fails if secure RNG is unavailable.
        atomic_json(args.directory / "approved-plan.json", {"approved_hash": digest(approved)})
        key = load_key(args.directory / "identity.key")
        print(json.dumps({"institution_public_key": public_key(key), "approved_hash": digest(approved)}))
    elif args.command == "agent-serve":
        from .transport import serve_institution
        serve_institution(args.config)
    elif args.command == "agent-prepare":
        import csv
        import numpy as np
        from .data import SCHEMA_HASH, features
        destination = args.directory / "dataset"
        if destination.exists():
            raise ValueError("A registered institution dataset cannot be replaced with this command")
        prepared = {}
        for split, path in (("train", args.train), ("validation", args.validation)):
            x, y = [], []
            with path.open(newline="", encoding="utf-8-sig") as file:
                for row in csv.DictReader(file):
                    label = int(row["isFraud"])
                    if label not in (0, 1):
                        raise ValueError("Institution labels must be binary")
                    clean = {"amount": float(row["amount"]), "type": row["type"], "step": int(row["step"]),
                             "oldbalanceOrg": float(row["oldbalanceOrg"]) if row.get("oldbalanceOrg") else None}
                    x.append(features(clean))
                    y.append(label)
            if not y:
                raise ValueError("Institution split cannot be empty")
            prepared[split] = (np.asarray(x, dtype=np.float32), np.asarray(y, dtype=np.float32))
        destination.mkdir(parents=True)
        for split, (x, y) in prepared.items():
            np.savez_compressed(destination / (split + ".npz"), x=x, y=y)
        atomic_json(destination / "manifest.json", {
            "schema_hash": SCHEMA_HASH, "source": "institution_owned_local_records",
            "files": {p.name: file_hash(p) for p in destination.glob("*.npz")}})
        if os.name != "nt":
            destination.chmod(0o700)
            for path in destination.iterdir():
                path.chmod(0o600)
        print("Institution dataset prepared locally. No records, counts, or paths sent to a coordinator.")
    elif args.command == "remote-run":
        import numpy as np
        from safetensors.torch import save_file
        from .remote import RemoteFederation
        from .evaluation import private_rates, threshold_from_public_development
        from .training import Detector, predict, set_arrays
        if args.output.exists():
            raise ValueError("Candidate output directory must be new")
        with np.load(args.public_development, allow_pickle=False) as development:
            dx, dy = development["x"], development["y"]
        config = json.loads(args.config.read_text())
        federation = RemoteFederation(json.loads(args.contract.read_text()), load_key(args.key), config)
        try:
            federation.start()
            values = federation.train(lambda r, receipts, size: print("Secure round", r, "complete", flush=True))
            model = Detector()
            set_arrays(model, values)
            threshold = threshold_from_public_development(dy, predict(model, dx), federation.plan.max_fpr)
            validation = federation.validate(values, threshold)
            args.output.mkdir(parents=True)
            save_file(model.state_dict(), str(args.output / "candidate.safetensors"))
            atomic_json(args.output / "candidate-evidence.json", {
                "run_id": federation.run_id, "approved_hash": digest(federation.approved),
                "model_hash": file_hash(args.output / "candidate.safetensors"),
                "public_development_hash": file_hash(args.public_development), "threshold": threshold,
                "receipts": federation.receipts(), "validation_receipts": validation,
                "private_validation": private_rates([r["payload"] for r in validation]),
                "transport": "mutual TLS; official Flower SecAgg+",
                "institution_keys": federation.keys, "status": "CANDIDATE_NOT_RELEASED",
                "limitation": "Remote candidate requires independent utility/attack review and owner release approvals"})
            print(str(args.output.resolve() / "candidate-evidence.json"))
        finally:
            federation.close()


if __name__ == "__main__":
    main()
