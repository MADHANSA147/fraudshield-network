# Blueprint implementation register

The source specification is `FRAUDSHIELD-COMPLETE-BLUEPRINT.md` in the parent workspace.
No prior private-project implementation is copied into this repository.

| Phase | Implemented and checked | Remaining acceptance work |
|---|---|---|
| 1. Data | Fixed features; heterogeneous fixtures; PaySim loader, sender/time purge, manifests and baselines | Actual PaySim dataset run, terms and final partition verification |
| 2. Privacy | Opacus; clipping; zero slots; empty batches; PRV/RDP; reservations; retries | Compatible secure RNG and confidential execution on the institution target environment |
| 3. Collaboration | Official SecAgg+; three processes; three mutual-TLS endpoints; pinned identities; signed local approval; quantization and abort checks | Separate physical hosts, institutional PKI and recovery drills |
| 4. Evidence | Public metrics; OpenDP validation; baselines/ablations; limited membership attacks with controls and bootstrap intervals; exposure/poisoning diagnostics; sweeps | Actual PaySim utility, stronger institution/time-matched attacks and larger low-FPR samples |
| 5. Governance | Hash-bound approvals; gate; signed bundles; tamper/ZIP tests; activation/scoring | No qualifying measured candidate; standalone remote private candidates are not integrated into web release review |
| 6. SaaS | Eight workflow surfaces; roles; enrollment; durable jobs; local workers; RQ configuration; usage; Stripe/S3 adapters | Actual Stripe/S3 account tests; production authentication and operational hardening |
| 7. Delivery | TypeScript build; Python lint/tests; browser check; dependency locks; Docker/CI configuration; documentation/demo script | Docker/clean Linux verification; public deployment; remote CI; recording/submission |

Public fixture results are never labeled PaySim results. Missing private-mode prerequisites
block execution. Formal guarantee claims require the actual mechanism and trust assumptions.
External services (deployment, payment provider, object storage) must be configured and tested
before being described as operational.

## Verified locally

- Full Python suite: 31 automated tests passed at this checkpoint.
- TypeScript compilation and Vite production build passed.
- pip check reported no broken requirements.
- Browser: workspace creation -> training job -> completed evidence displayed.
- Three-process and three-TLS-institution secure aggregation both passed.
- Aggregate error against the clipped plaintext test reference was below 3e-5.
- Release/activation/scoring passed with fabricated test-only evidence. This is
  not a measured benchmark qualification.

## External/environment constraints

The Docker daemon was unavailable. No deployment host, Stripe test account,
S3 configuration or public PaySim CSV was supplied. A compatible secure-RNG
package is absent from this Windows runtime. Confidential execution refuses
that missing prerequisite.

The Windows environment reused installed scientific libraries to avoid duplicating
large packages on a nearly full system drive. The dependency lock describes that
tested environment, not a successful clean-container installation.

## Interpreting the model evidence

The default short configuration is an integration/smoke run. A larger public
development pilot is recorded separately, with its final-test partition unopened
during configuration selection. Independent research runs use the frozen research
plan and separate seeds.

A candidate below the recall/FPR/non-inferiority policy remains blocked.
The interface does not fabricate success, weaken policy after seeing results,
or call an inconclusive attack a proof of privacy.
