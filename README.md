# FraudShield Network

Privacy-governed collaborative fraud detection for three institutions.

This repository contains a working public-data application: a React workspace,
FastAPI service, real Opacus DP-SGD, Flower SecAgg+, durable institution privacy
ledgers, OpenDP validation, measured attack diagnostics, release gates, signed
bundles, and institution-local inference. The TLS institution connector uses the
same training and aggregation implementation.

**Current results:** the recorded generated-fixture benchmarks complete but do
not meet the fraud-detection release policy. No real-bank performance, production
security certification, or error-free guarantee is claimed. See
[implementation status](docs/IMPLEMENTATION.md) and [research results](docs/research-benchmark/RESULTS.md).
The earlier [short smoke study](docs/benchmark/RESULTS.md) is retained separately.

The interface uses a responsive dark theme. The [complete blueprint audit](docs/BLUEPRINT-AUDIT.md)
maps all 22 planning sections to implementation evidence and outstanding acceptance work.

For a temporary public hackathon URL, use the [Render deployment guide](docs/RENDER_DEMO.md).
It describes the generated-fixture-only deployment and its free-plan constraints.

## Open the application

In the prepared Windows workspace:

    .\start.ps1

Open http://127.0.0.1:8000 and choose **Open demo workspace**.
This creates an isolated public sandbox. A small training run usually completes
in under a minute on the tested machine; runtime depends on the settings and host.
The Evidence lab also shows the recorded nine-run public comparison.

Do not enter private records into the hosted demo. Its local child processes
share a trusted host; they are an engineering simulation of institution boundaries.

## Clean installation

Python 3.13 and Node 22 were used locally. The Windows test environment reused
installed scientific packages; an entirely clean Linux/container installation
has not yet been executed on this machine.

    python -m venv .venv
    .venv/Scripts/python -m pip install torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu
    .venv/Scripts/python -m pip install -r requirements.lock
    .venv/Scripts/python -m pip install --no-deps -e .
    cd apps/web
    npm ci
    npm run build
    cd ../..
    .venv/Scripts/python -m fraudshield.cli serve

On Linux replace .venv/Scripts/python with .venv/bin/python. For frontend
development use npm run dev in apps/web with the API running on port 8000.

## What is implemented

- Workspace overview, institution enrollment, plan form, live jobs, evidence,
  privacy/utility plots, release review, registry, and usage/billing screens.
- Cookie or bearer-token authentication, tenant filtering, owner/admin/auditor
  controls, one-time enrollment, idempotent jobs, and one active job per workspace.
- Three persistent institution processes; official Flower SecAgg+ masking;
  equal public weights, all-three participation, and no plaintext fallback.
- Optional institution listeners with mutual TLS, certificate hostname checks,
  pinned Ed25519 identities, locally approved signed plans, bounded JSON/protobuf
  messages, and no network pickle deserialization.
- Fixed public feature transforms; pre-transaction inputs; fixed-capacity slots;
  actual Poisson sampling, per-example clipping/noise, empty-batch handling,
  PRV accounting and an RDP diagnostic.
- Full-plan budget preflight, transactional conservative reservations, no crash
  refunds, immutable result hashes, restart composition, and cached validation.
- Public exact metrics plus one fixed-threshold OpenDP confusion-vector release.
  Protected intervals account for noise and finite-sample uncertainty.
- Local, pooled, logistic, nonprivate federated and DP-without-SecAgg public
  baselines; membership attacks with an overfit control and bootstrap intervals;
  a labeled gradient exposure diagnostic and separate one-of-three scaling stress test.
- Policy checks, evidence-bound owner approvals, artifact hashes, Ed25519
  manifests, verified ZIP activation, and network-free local scoring.
- Subprocess jobs locally; Redis/RQ and PostgreSQL configuration for containers;
  optional S3 archive mirroring; Stripe test-mode integration.

## Core commands

Create a public workspace; keep the returned bearer token private:

    fraudshield workspace --name "Research consortium"
    fraudshield run --workspace WORKSPACE_ID --plan examples/plan.json

Run the fixed public comparison protocol:

    fraudshield benchmark --output benchmark-results/new-study --seeds 42,43,44 --epsilons 2,4,8 --rounds 3 --steps 12

The longer frozen public-development configuration uses separate evaluation seeds:

    fraudshield benchmark --output benchmark-results/research-repeat --plan examples/research-plan.json --seeds 242,243,244 --epsilons 2,4,8

The new-run allowance is separate from each institution's cumulative lifetime
cap of epsilon 8. Previous expenditure is retained and can block a new plan.

These are independent PUBLIC studies. Creating another workspace is not a
permitted way to reset a real institution's privacy budget.

Prepare a locally supplied PaySim CSV:

    fraudshield prepare-paysim PATH_TO_PUBLIC_PAYSIM.csv prepared-paysim

Create a plan with mode public_paysim and a declared capacity, then:

    fraudshield run --workspace WORKSPACE_ID --plan paysim-plan.json --dataset prepared-paysim

Preparation records source checksum, row-local schema, temporal cutoffs,
purged cross-time senders, institution routing and public split counts. Training
uses the declared capacity-sized prefix when a PUBLIC training split exceeds
capacity. This selection is reported in the local manifest. Test and validation
keep their natural label distribution. The loader has been tested against a
small PaySim-format fixture; the real PaySim dataset has not been evaluated here.
The full CSV loader holds its parsed records in memory; provision memory for it.

After an actual qualifying release, pin the coordinator key through an
authenticated channel, then verify, activate and score:

    fraudshield verify UNPACKED_BUNDLE --trusted-key PINNED_PUBLIC_KEY
    fraudshield activate release.zip institution/active-model --trusted-key PINNED_PUBLIC_KEY
    fraudshield score institution/active-model examples/transactions.json --trusted-key PINNED_PUBLIC_KEY

The trusted key must not be taken solely from the bundle being verified.
No qualifying measured candidate currently exists. Unit tests exercise the
successful release path using explicitly fabricated test-only evidence.

## Verification

    python -m pytest -q
    python -m ruff check src tests scripts
    cd apps/web
    npm run build

The tests include real three-process and three-TLS-institution training,
quantization accuracy, dropout aborts, cached validation, clipping, empty
Poisson batches, accountant failures, concurrent budget reservations,
crash charges, tenant/role boundaries, webhook idempotency, manifest tampering,
ZIP traversal rejection, activation and local scoring.

To regenerate the research figure, install the optional reports dependencies
and run:

    python scripts/report_benchmark.py benchmark-results/research/summary.json --output docs/research-benchmark

## Repository map

| Path | Purpose |
|---|---|
| apps/web | React and TypeScript application |
| src/fraudshield/training.py | Fixed-slot Opacus mechanism |
| src/fraudshield/federation.py | Flower SecAgg+ workflow and client boundaries |
| src/fraudshield/transport.py | Mutual-TLS framing and institution listener |
| src/fraudshield/ledger.py | Authoritative institution accounting |
| src/fraudshield/evaluation.py | Public metrics and OpenDP validation |
| src/fraudshield/governance.py | Release decisions and signatures |
| src/fraudshield/inference.py | Verified local activation and scoring |
| src/fraudshield/api.py | Tenant API and service integrations |
| src/fraudshield/cli.py | Operator and benchmark commands |
| tests | Mechanism, integration, security-boundary and API tests |
| benchmark-results/research | Actual frozen-plan public study evidence |
| docs | Architecture, operations, limitations and submission script |

## Documentation

- [Original design specification](docs/BLUEPRINT.md)
- [Verification record](docs/VERIFICATION.md)
- [Architecture and privacy assumptions](docs/ARCHITECTURE.md)
- [Institution-operated deployment](docs/INSTITUTIONS.md)
- [Operations and service setup](docs/OPERATIONS.md)
- [Implementation and remaining acceptance work](docs/IMPLEMENTATION.md)
- [Four-minute demonstration](docs/DEMO.md)
- [Provenance](PROVENANCE.md)

The reference project was used for understanding only. No private reference
repository source, credentials or dataset is included.
