# Blueprint audit — 28 September 2026

This is an implementation audit of all 22 sections of [the original plan](BLUEPRINT.md).
The repository is a working public-data engineering demonstration. It is not a
completed confidential production deployment. Passing software checks does not
mean a candidate meets the model release policy.

| Blueprint sections | Evidence in this repository | Outstanding work or deliberate implementation difference |
|---|---|---|
| 1–3: Product, originality, MVP | README, PROVENANCE, fixed three-institution fraud workflow | Public fixtures are used for measured results; no claim of winning, revenue or production readiness |
| 4–5: Workflow, architecture | API/workers, institution agent, mutual TLS, signed local plans, roles | Remote confidential candidates do not yet enter the web approval/registry workflow; physical-host validation remains |
| 6: Dataset and features | PaySim parser, fixed features, manifests, temporal splits and sender purging; data tests | Actual PaySim benchmark and terms review remain; no destination-entity isolation claim |
| 7–8: Model and privacy | Opacus DP-SGD, fixed padded slots, Poisson sampling, PRV/RDP, private validation | Compatible secure RNG is unavailable in this Windows environment; confidential execution fails closed |
| 9–10: Aggregation and budgets | Official Flower SecAgg+, three-process/TLS tests, durable ledger, cached retries and reservations | Institutional PKI deployment, host-loss recovery and backup/restore drills remain |
| 11–12: Evaluation and attacks | OpenDP counts, conservative intervals, public baselines, membership controls, reconstruction/poisoning diagnostics | Stronger institution/time-matched attacks and larger low-FPR samples remain; diagnostics are not universal attack resistance |
| 13: Release and inference | Hash-bound gate, owner approvals, signed bundle, ZIP/tamper checks, local activation/scoring | No measured candidate qualifies. Successful release-path tests use fabricated test-only evidence. Remote approval integration and operational rollback UI remain |
| 14: Interface | Seven navigation pages plus training dialog; dark responsive theme; charts and real API data | No confidential-data upload is exposed; hosted end-to-end acceptance remains |
| 15: Stack and storage | React/FastAPI, SQLAlchemy, SQLite/Postgres configuration, RQ, signed local artifacts | Source modules replace the proposed directory hierarchy; some evidence is JSON rather than separately normalized tables; database migrations remain |
| 16: Operations | Idempotent jobs, cancellation, tenant quotas, conservative accounting, sanitized errors | Public run lifecycle is simplified; deployment-enforced per-job CPU/GPU/memory limits, production identity, migration and recovery tests remain |
| 17: Monetization | Usage measurements, sandbox Stripe checkout/webhook implementation | Actual provider-account testing, measured infrastructure cost/margin and customer interviews remain; $499 is a hypothesis |
| 18: Experiments | Three epsilon profiles × three seeds; baselines, ablations, saved reports | Results are generated fixtures, not PaySim; current utility fails the predeclared release threshold |
| 19: Acceptance | Mechanism, empty batches, retries, concurrency, TLS aggregation, tenant boundaries and release-integrity tests | Clean institutional confidential end-to-end acceptance remains; see VERIFICATION.md |
| 20–22: Delivery and research | Build sequence, demo script, research citations, reproducible commands, CI/Docker files | Docker deployment, submission recording and actual hackathon submission remain |

## Scope of the dark-theme revision

The revision changes presentation, improves keyboard handling in the training
dialog, and clarifies that the selected epsilon is a new-run allowance. It does
not change DP mechanisms, relax release thresholds or relabel historical results.

The audit exposes incomplete work instead of treating missing external prerequisites
or failing quality gates as completed features. Detailed environment constraints
and test evidence are in [IMPLEMENTATION.md](IMPLEMENTATION.md) and
[VERIFICATION.md](VERIFICATION.md).
