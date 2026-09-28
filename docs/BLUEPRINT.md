# FraudShield Network: complete implementation blueprint

Version 1.0 · 27 September 2026 · Design specification, not a claim that implementation or benchmark results already exist.

This is the consolidated design. It incorporates the prior repository review and resolves the identified mechanism, accounting, telemetry, aggregation, and evaluation contradictions. No unbuilt software can be certified error-free and no proposal can guarantee a competition result; this specification makes correctness concrete through explicit invariants and acceptance checks.

## 1. Product and final problem statement

**FraudShield Network — Collaborative Fraud Detection with Enforced Privacy Budgets.**

**One sentence:** A consortium workspace where financial institutions jointly train a fraud detector while keeping records local, controlling cumulative privacy expenditure, and releasing only models with a verifiable evidence package.

Financial institutions have complementary fraud examples but cannot freely pool transaction records. Local-only models miss learning opportunities. Ordinary federated learning keeps raw data local but can expose information through updates, metrics, and released weights. Institutions also need to know whether repeated experiments have exhausted approved privacy budgets and whether a shared model is useful at an acceptable false-alert rate.

**Final problem statement:**

> Build a privacy-governed collaborative fraud-detection platform that enables three institutions to train a shared model without centralizing source records. The platform must protect individual training records with correctly accounted differential privacy, conceal individual model updates through established secure aggregation under explicit assumptions, and enforce durable privacy budgets across repeated training and evaluation. Demonstrate accuracy–privacy trade-offs and attack evaluations on public synthetic transaction data. Permit release only when the model, privacy ledger, evaluation evidence, and institutional approvals satisfy a predefined policy, and provide a signed manifest binding that evidence to the released artifact.

The first customer hypothesis is a payment processor or existing fintech consortium that can bring three participating institutions. It pays for collaboration orchestration, private training controls, model distribution, and evidence management. This avoids assuming three unrelated banks spontaneously join a new marketplace.

The MVP scores transaction risk for analyst review. It does not autonomously block payments or claim calibrated fraud probabilities without calibration evidence.

## 2. Competition fit and original implementation

The published Galuxium criteria allocate 20% each to architecture, governance, and market fit; 15% each to monetization and UI; and 10% to demo completeness. Requirements include a live deployment, public code repository, monetization explanation, and a 2–5 minute video. Therefore the deliverable is an operating SaaS workflow with an ML pipeline, not just a notebook. [Official event page](https://galuxium-nexus-v2-29411.devpost.com/).

Use a fresh repository and authentic commit history during the event. The previous private project remains a research reference. Record libraries, paper references, dataset provenance, AI assistance, and the distinction from previous work in `PROVENANCE.md`. The event permits public libraries but prohibits copying prior submissions or proprietary products. [Official rules](https://www.galuxium.com/rules).

## 3. Fixed MVP scope

| Decision | Specification |
|---|---|
| Task | Binary synthetic payment-fraud detection |
| Participants | Three institution workers, one consortium coordinator |
| Training | Horizontal federated learning; common feature schema; equal institution weights |
| Model | Small PyTorch MLP; logistic regression as diagnostic baseline |
| Training privacy | Record-level DP-SGD inside each institution using Opacus |
| Aggregation | Flower SecAgg+; all three participants required in the MVP |
| Validation | One fixed-threshold DP confusion-vector release per institution per approved candidate |
| Accounting | Durable local authority, central receipt mirror, conservative composition |
| Inference | Released model executes inside each institution |
| Data | Public PaySim transaction benchmark; clearly labeled synthetic |
| Product surfaces | Consortium setup, training, evidence comparison, release registry, usage/billing |
| Attack scope | Membership inference and update-exposure evaluation; separate poisoning stress test |
| Excluded | Arbitrary uploaded code, LLM access to records, custom cryptography, cross-bank entity matching, customer-level DP claims, Byzantine robustness claims |

Three organizations are the demonstration configuration, not evidence of scalability to thousands of nodes.

## 4. Users and complete workflow

The consortium administrator creates a workspace and invites three institution owners. Each owner registers a local worker with a short-lived enrollment token, approves the fixed training package, and sets the local privacy policy. A fraud analyst proposes a training run; each worker independently validates the signed run specification. A model approver reviews the evidence package and authorizes release. A read-only auditor can inspect the manifest and exported evidence without opening institution data.

The workflow is:

1. Create consortium and enroll workers.
2. Select the local dataset through the worker's local configuration, not a central upload form.
3. Validate schema locally; expose only allowlisted operational status.
4. Select an approved privacy profile and fixed training plan.
5. Obtain a budget reservation from every worker.
6. Run local DP training and secure aggregation.
7. Evaluate on the public benchmark and, separately, execute the governed validation demonstration.
8. Run the evidence checks and show PASS, BLOCKED, or INCONCLUSIVE with reasons.
9. Collect owner approvals tied to the candidate hash.
10. Sign the manifest and allow institution workers to download the approved model.
11. Run local inference and show metered platform usage.

## 5. Architecture and trust boundaries

```text
                           Consortium web application
                                     |
                         FastAPI control plane + worker
                         PostgreSQL / job queue / registry
                                     |
                           Flower coordinator
                            /        |        \
                     encrypted protocol messages
                         /           |           \
              Institution A   Institution B   Institution C
              local records   local records   local records
              local ledger    local ledger    local ledger
              Opacus trainer  Opacus trainer  Opacus trainer
              client keys     client keys     client keys
              local inference local inference local inference
```

Each worker has its own filesystem volume and process identity. The coordinator has no mount containing a worker's source records, private key, RNG state, optimizer state, or unprotected metrics. A single-machine Docker deployment demonstrates logical separation only; it does not protect against that machine's administrator. Institution-controlled hosts are the deployment trust boundary.

The coordinator is honest-but-curious for the formal SecAgg claim: it follows the configured protocol but inspects everything it legitimately receives. The clients correctly execute approved code. The MVP assumes no coordinator–client collusion and requires all three clients. Arbitrary malicious coordinators, compromised client hosts, traffic-analysis defenses, and Byzantine clients are outside its established guarantee.

All workers verify the same approved model/configuration hash, schema version, participant roster, and round number. Authenticated encrypted transport protects channels. These checks constrain accidental inconsistency and replay; they are not a claim of a malicious-secure protocol.

## 6. Dataset, institution partitions, and feature contract

Use the public synthetic transaction data associated with [PaySim](https://github.com/EdgarLopezPhD/PaySim). Keep simulator/software licensing separate from the downloaded dataset's terms. Record the exact dataset source, version/checksum, and redistribution conditions; distribute the loader rather than copying a large dataset into Git.

Define the prediction moment as **before executing a transaction**, using information available to the originating institution. Candidate features are transaction amount, transaction type, time features, and sender balance before execution where the dataset documents that meaning. Exclude post-transaction balances, the target, existing fraud flags, and destination balances unavailable to the sender. Account identifiers are partition/split metadata, never model inputs. No cross-record behavioral aggregates are computed for this MVP: one changed record must not silently change many other feature rows.

Use fixed, public feature rules: bounded `log1p` amount/balance transforms, a public categorical vocabulary with UNKNOWN, fixed missing-value treatment, and fixed time encodings. Do not fit a scaler, imputer, vocabulary, clipping threshold, or class weight on private data without accounting for it. Public-development data may be used to choose these constants before locking the configuration.

Use an explicitly labeled public development partition for hyperparameter decisions. Hold back the final benchmark test period. For evaluation, separate both time and sender groups where identifiers permit; purge repeated sender groups crossing split boundaries rather than claiming complete identity separation from row splitting alone. Report dropped rows and fraud counts using public benchmark data. Related destination identities can still cross groups; no customer-level guarantee is inferred.

Create three heterogeneous simulated institutions through fixed, label-independent routing by permitted transaction attributes and account ownership. Keep each record in exactly one institution. Use a mild, reproducible skew with overlapping feature support rather than assigning all positives to one client. A pooled/IID partition is a diagnostic comparison, not the sole experiment. The simulation is not a claim that PaySim supplies actual bank identifiers.

Preserve natural class imbalance in validation and test data. Do not balance the test set or use SMOTE/positive oversampling inside a pipeline accounted as uniform Poisson sampling. Weighted per-example loss is permitted only with a fixed public weight and clipping applied to the resulting per-example gradient.

## 7. Model and training contract

Use `Linear(d,32) -> ReLU -> Linear(32,16) -> ReLU -> Linear(16,1)` with `BCEWithLogitsLoss`; sigmoid is applied only to produce a risk score. Use SGD without momentum initially, no BatchNorm, no dropout, and a fixed learning rate chosen on public development data. This keeps per-record behavior and checkpoints simple.

Run a logistic-regression baseline to establish whether extra neural-network complexity helps. Neither the architecture nor the DP parameters are optimized against the final test set. The MLP is small for compute and sample-efficiency reasons, not because a small parameter count automatically lowers epsilon.

Initial public-benchmark engineering configuration: 10 rounds, 100 local optimizer steps per round, clipping norm C=1, Poisson sample rate around 1/1024 where capacity permits. These are starting experiment settings, not claimed optimal values. Freeze the final run plan after public pilots. Noise is calibrated against the entire approved plan, not separately to spend the full budget again each round.

Each worker uses only the model, optimizer and loader returned by `PrivacyEngine.make_private`. Every optimizer step uses per-example clipping and noise before parameters can leave the worker. Empty Poisson batches are handled by the supported DP path; never silently replace them with a different sampler or skip accountant events inconsistently. [Opacus API](https://opacus.ai/api/privacy_engine.html); [DP-SGD foundation](https://arxiv.org/abs/1607.00133).

## 8. Exact privacy unit, sampling and composition

The privacy unit is **one transaction row**, under an add/remove-one-real-record relation. Customer-level protection is not claimed when a person contributes multiple transactions.

For the confidential execution contract, each worker uses an approved fixed-capacity slot dataset. A slot contains either one real record or a dummy record contributing exactly zero loss and zero gradient. Neighbors differ by a real record becoming an empty slot. Capacity, sampling rate, number of steps and expected-batch normalization are fixed policy parameters independent of private occupancy. Dummy slots remain in the sampling population; the worker does not repack or drop them based on occupancy. This prevents sample count from silently changing both the sampling mechanism and its public transcript.

Use the actual configured Poisson slot-sampling probability in the accountant and Opacus's expected-batch normalization. Validate the padded zero-contribution behavior against per-example gradients and the accounted sampled-Gaussian mechanism. Public benchmark jobs may reveal true dataset sizes because their records are already public, but confidential mode follows the fixed-capacity contract.

Use Opacus PRV as the primary training accountant with recorded numerical tolerances; use RDP on the same event history as an independent diagnostic bound. Never average the two or silently substitute a heuristic after an error. An accountant failure blocks the run. Per-round entries store the actual q, sigma, step count and mechanism version; an integer number of epochs alone is insufficient.

For each institution, conservatively compose training with pure-DP validation:

`epsilon_total_i(delta_i) = epsilon_training_i(delta_i) + sum(epsilon_validation_queries_i)`.

With fixed disjoint institution datasets, report every institution's guarantee; a global worst-case record statement may use the maximum epsilon and maximum delta, not their average. If the same protected record is allowed in several institutions, compose its exposures instead; the MVP enrollment contract forbids duplicate ownership. Reusing a source dataset under a different job/model/dataset alias does not create a new privacy budget.

The demo exposes total-budget profiles of epsilon 2, 4 and 8 at delta 1e-6, with 0.5 reserved for one validation release and the remainder available for training. These are comparison points, not labels such as safe/unsafe. Check delta against the chosen population and threat model. Multiple real-private runs compose against the lifetime policy; public benchmark sweeps are clearly labeled separate public-data experiments.

A frozen DP model can be downloaded or used repeatedly without retraining spend, because those uses are post-processing. New training, private-data adaptation, or new private evaluation queries require accounting. A new inference input is not itself protected merely because the model was privately trained.

## 9. Secure aggregation integration

Start from the current official [Flower SecAgg+ example](https://flower.ai/docs/examples/flower-secure-aggregation.html) and integrate the private local training function into its client interface. Use the supported `SecAggPlusWorkflow` and `secaggplus_mod` route from that example. Do not assemble incompatible APIs from different Flower generations. Pin the complete tested environment and container digest after the integration test succeeds.

The MVP uses three full participants, three shares and a reconstruction threshold of three in a compatible full-neighborhood configuration. A missing participant aborts the round; there is no automatic plaintext fallback or smaller-cohort retry. Before deployment, assert these values against the pinned workflow and inspect its resulting participant/share configuration. [Workflow API](https://flower.ai/docs/framework/ref-api/flwr.server.workflow.SecAggPlusWorkflow.html).

The sequence is: approved weights -> local DP-SGD -> DP model serialization -> library clipping/quantization -> client-side masking -> network -> secure aggregate -> global model. The coordinator never receives unmasked per-client weights in the claimed secure path. Metrics fields are explicitly stripped: SecAgg does not automatically conceal arbitrary attached metrics.

Use equal institution weights of one, not private sample counts. Set encoding bounds on public pilots and record them in the run specification. Secure-aggregation range clipping is post-processing of a DP output, not a replacement for per-example gradient clipping. Verify modular bounds, finite values and quantization error on synthetic vectors. Compare secure output to plaintext aggregation of the same quantized vectors; compare quantized to full-precision output separately.

No extra central Gaussian mechanism is added in this design. Privacy is supplied by local record-DP training; SecAgg adds update confidentiality. Do not claim an amplification benefit from SecAgg or from sampling organizations when every organization participates.

## 10. Durable privacy-budget service

The institution's local SQLite ledger is authoritative; the coordinator stores signed receipts. The host administrator is trusted not to roll back its ledger. Cross-host rollback resistance is not claimed. Clients refuse training when their ledger is unavailable or inconsistent.

Before a round, the worker atomically reserves the full worst-case planned spend under a transaction lock, checks the resulting cumulative privacy bound, and persists the new accountant state. It charges the reservation conservatively even if the job crashes; the MVP makes no privacy refund after starting. This may waste budget but prevents crash/retry ambiguity from undercounting it.

Each reservation key includes institution, stable dataset lineage, policy version, job, round and attempt. A duplicate request returns the existing status. Retransmitting an already computed DP result does not spend again, but recomputing with fresh access/noise requires a fresh reservation. A crash with an uncertain output state cannot reset the ledger. Jobs sharing one dataset are serialized.

Receipts contain mechanism/configuration hashes, accountant version, planned and executed step metadata, committed spend, cumulative bounds, and output digest. They never contain RNG seeds, records, sample membership, raw losses, private counts or optimizer state. Bounds are recomputed from event history during recovery. Budget denial depends on policy/history, not unprotected data-dependent training metrics.

## 11. Evaluation without a telemetry leak

The **public benchmark lane** reports exact metrics because its dataset is public. It measures PR-AUC, recall at a predeclared 1% FPR operating target, precision, false alerts per 1,000 legitimate transactions, per-institution utility, runtime, memory, and communication. Lower-FPR points are displayed only when negative sample counts support useful uncertainty estimates.

The **governed validation lane** demonstrates the confidential-data contract on locally held synthetic records. Select one threshold using the public development data for that candidate, then freeze the model and threshold hashes before opening private validation. Do not search thresholds through repeated unbudgeted private queries.

For the fixed model and threshold, each validation row contributes to exactly one of four cells: TP, FP, TN, FN. Under add/remove adjacency this count vector has L1 sensitivity one. Each worker releases a vector with a verified Laplace/discrete-Laplace mechanism at epsilon_eval=0.5, using OpenDP's checked transformation/measurement composition. The implementation calls its privacy map/check rather than assuming nominal floating-point scale is exact. No raw count vector leaves the worker. [OpenDP measurements](https://docs.opendp.org/en/stable/api/python/opendp.measurements.html).

The server sums the three already-private vectors and derives rates as post-processing. Each local release is protected even before summation; no claim of noise cancellation or central-DP trust is needed. The model is fixed conditional on the prior DP training transcript, and training plus validation is conservatively composed even if record overlap is uncertain.

Display uncertainty from both finite validation samples and the known privacy noise. Use conservative simultaneous count intervals before deriving ratio bounds; never approve because a clipped negative noisy count artificially improves a rate. If denominator bounds include zero or evidence is too weak, return INCONCLUSIVE. Reopening the same cached release spends nothing; another model or newly drawn answer is a new query.

A private validation lane provides operating-point counts/rates, not an exact private PR-AUC curve. The curve shown in the hackathon dashboard belongs to the public benchmark lane and is labeled accordingly.

## 12. Attack evaluation

**Membership inference:** Run a loss/confidence attack and a shadow-model likelihood-ratio attack inspired by [LiRA](https://arxiv.org/abs/2112.03570). Keep members/nonmembers drawn from matched institution/time/class distributions, separate attack calibration from attack testing, and report class-stratified results where possible. Report ROC-AUC and TPR at 1% FPR with uncertainty. A deliberately overfit nonprivate model is the positive control. If the attack fails there, the protected-model result is INCONCLUSIVE. A reduced shadow-model budget is labeled a limited evaluation, not a full reproduction of the paper.

**Update exposure:** In a public-data diagnostic run, demonstrate gradient/update inference against an unprotected path. Record exactly what the attacker observes: a single-example gradient is not equivalent to a many-step federated delta. For the secure run, verify the coordinator's message boundary receives masked payloads and aggregates only. A denied observation is an access-control/protocol result, not a measured zero-success inversion attack.

**Poisoning stress test:** On public synthetic data, inject one malicious client update and measure degradation. Keep its report separate from privacy. The MVP does not advertise Byzantine robustness or claim honest-client clipping constrains a malicious participant.

All attack artifacts containing examples run on public data and carry that provenance. No private records are published merely to demonstrate attacks.

## 13. Model-release decision and evidence package

The gate evaluates immutable evidence, not dashboard booleans or a manually entered epsilon. It requires a verified current candidate hash, complete accountant receipts, sufficient budget, approved participation, known mechanism versions, model/threshold consistency, valid utility evidence, completed attack evaluation status, and required owner approvals.

The public-demo quality policy uses an FPR target of 1%, a declared recall floor of 60%, and a non-inferiority tolerance of five percentage points against the local benchmark at the same operating point. These are explicit demo acceptance targets, not predicted achievements. Define comparisons on each institution's own test records; distinguish an average improvement from a claim that every institution benefits. Private-mode release uses only privately released rates and a public/preapproved baseline, never raw private local-model metrics.

For a confident release, the relevant one-sided uncertainty bounds must satisfy policy. Positive-control failure yields INCONCLUSIVE, which blocks a release claiming completed attack evidence. A policy change creates a new version with visible rationale; it cannot retroactively turn a failed experiment into a predeclared success.

The released bundle contains `model.safetensors`, `feature_schema.json`, `threshold.json`, `privacy_statement.json`, `evaluation.json`, `attack_report.json`, `manifest.json`, and its signature. The manifest includes every file hash, code revision, dependency lock hash, run configuration hash, privacy adjacency, per-institution budget bounds, artifact provenance, assumptions and approval identities.

Serialize the manifest canonically and sign its exact bytes with a managed signing key; verify against a configured public key. No hard-coded demo secret in a claimed secure deployment. Use a standard signature implementation. The signature proves integrity/authorship of the record, not the truth of every institution's execution or regulatory compliance.

## 14. User interface

| Screen | User purpose |
|---|---|
| Workspace overview | See three members, connector readiness and current approved model |
| Institution setup | Enroll connector and review the public feature contract; source path stays local |
| Training plan | Choose an approved privacy cap; see plan cost, local approvals and reservation status |
| Live run | See stage, round, participant status and committed privacy spend; no raw private losses |
| Evidence comparison | Explore public accuracy–privacy curves and identify measured, not invented, trade-offs |
| Release review | Read exact PASS/BLOCKED/INCONCLUSIVE reasons and approve the hash-bound candidate |
| Registry | Verify bundle/signature, download approved version and record local activation |
| Usage and plan | See worker compute usage, included quota and sandbox subscription flow |

Never prepopulate charts with illustrative values that resemble measured results. Cached experiments are labeled with their timestamp, revision and run ID. Live smoke runs and full benchmark runs have visibly different labels. A slider selects approved profiles or existing results; it does not imply a full training experiment finished instantly.

## 15. Software stack and repository

Use Python, PyTorch, Opacus, Flower and OpenDP for the privacy/training components; FastAPI and Pydantic for control APIs; PostgreSQL for consortium state; a Redis-backed job queue for long jobs; SQLite with transactional locking for each local privacy ledger; React/TypeScript for the web client; and an S3-compatible store for released artifacts. Use Docker images and a tested Linux environment for the secure RNG dependency. Select exact versions through an integration smoke test, then commit the lockfile and image digest—no invented compatibility claim from independent latest versions.

```text
fraudshield/
  apps/web/
  services/control_api/
  services/job_worker/
  federation/server/
  institution_agent/
    enrollment/ data_contract/ training/ validation/ inference/
  privacy/
    accountant/ ledger/ reservations/ receipts/
  governance/
    release_policy/ manifests/ signatures/
  experiments/
    datasets/ splits/ baselines/ attacks/ reports/
  tests/
    mechanism/ integration/ privacy_boundaries/ governance/
  infra/
  docs/
  PROVENANCE.md
  README.md
```

Core APIs: create consortium; enroll worker; create immutable run specification; reserve/start/cancel run; fetch redacted events; read evidence; request and approve release; verify/download bundle; view usage. Starting a run requires an idempotency key. Use SSE for server-to-browser status. Do not accept arbitrary model paths, shell commands, Python code or pickle uploads.

Core central tables: tenants, memberships, institutions, connectors, policies, runs, rounds, receipts, evaluation_releases, attack_reports, artifacts, approvals, audit_events, usage_events and subscriptions. Every central resource is scoped to tenant and consortium. Local tables track dataset lineage, event history, reservations and output digests; sensitive manifests stay local. Application authorization is checked on every object access, not just on menu visibility.

## 16. Job lifecycle and operational behavior

```text
DRAFT -> APPROVAL_PENDING -> BUDGET_RESERVED -> QUEUED -> TRAINING
      -> VALIDATING -> EVIDENCE_READY -> RELEASE_REVIEW -> RELEASED
```

Terminal/exception states are BUDGET_BLOCKED, FAILED, ABORTED, and INCONCLUSIVE. A failed attempt keeps its ledger entries. A new attempt receives a distinct identity. Cancellation stops future steps/messages; it cannot undo a released update or previously consumed reservation.

Training runs in workers, never in an HTTP request handler. Each run has a CPU/GPU/memory limit and concurrency quota. Queue limits and public-demo rate limits prevent visitors from launching unbounded training. Secret values come from the deployment secret store. The public judge account accesses only synthetic demonstration data and cannot upload production records.

Record operational failures without echoing raw record values. Coarse stage telemetry is allowlisted; fixed-shape inputs and fixed scheduled steps reduce accidental data-dependent status leakage. Do not claim protection against all timing or hardware side channels.

A rollback changes the locally active approved model; it does not erase prior privacy expenditure. Migration/backup tests cover central state and local ledgers. A recorded demo is a presentation aid, not a substitute for the working hosted workflow.

## 17. Monetization and customer validation

Offer a consortium subscription with a fixed number of institution connectors and included managed training compute; charge transparent overage for additional compute and connectors. Local inference is not billed per transaction in the MVP because scoring occurs at institutions and transaction telemetry is unnecessary.

Illustrative test offer: USD 499/month for a three-institution pilot workspace, with a declared compute allowance and separately quoted deployment/support. This is a price hypothesis, not a researched market price or proof of willingness to pay. Validate it with payment-risk leaders and consortium operators before presenting revenue forecasts.

The product includes a sandbox billing checkout, plan limits, server-side verified and idempotently processed billing webhooks, and a usage page. Financial usage is metered from authorized worker resource/job records, never private transaction counts. No real payments are required for judging.

Track actual compute and storage cost for a full run. Show contribution margin assumptions explicitly: subscription plus overages less managed compute, storage and support. Customer interviews should establish who can coordinate institutions, existing fraud-model pain, acceptable deployment boundary, procurement owner, and which evidence is needed for approval. Record interviews and interest honestly; do not fabricate customers or letters of intent.

## 18. Experiment matrix and claim policy

Compare institution-only models, a pooled public-data reference, nonprivate FL, DP FL without SecAgg as a controlled diagnostic, and DP FL with SecAgg. Use the same feature contract, time/group splits and model family. Label DP-off and SecAgg-off runs as public research diagnostics; they are unavailable in confidential mode.

Train the three privacy profiles with at least three independent training seeds, increasing repetitions if time permits. Report every run, mean and variability. With only three seeds, do not advertise a precise normal-approximation confidence interval as strong evidence. Use held-out prediction/bootstrap or binomial methods appropriate to the metric and grouping, and keep training variability distinct from test-sample uncertainty.

Compare global versus local utility on each institution's own test set. Public pooled performance is a reference, not a guaranteed upper bound. An improvement claim appears only if supported by the predeclared comparison and uncertainty. A privacy/utility trade-off that fails a quality gate remains visible as a failed candidate.

The demo's formal privacy statement comes from a matched mechanism/accountant and explicit assumptions. Empirical attacks assess specific threats but never prove universal absence of leakage. Never display epsilon as a probability that a person's data leaks.

## 19. Acceptance checks

| Requirement | Testable acceptance |
|---|---|
| Per-example mechanism | Check individual gradient norms/clipping and accountant event increments on tiny synthetic inputs |
| Sampling contract | Verify configured q, fixed capacity, zero-contribution dummy slots, expected normalization, and empty-batch behavior |
| RNG | Confidential mode requires secure_mode and supported secure randomness; no public noise seed/state in outputs |
| Accountant failures | Missing, nonfinite, mismatched or errored accounting blocks training/release |
| Cumulative spend | Two runs on one lineage compose; restart/rename cannot reset budget |
| Concurrency and retries | Duplicate idempotency requests do not rerun; concurrent reservations cannot overspend |
| Crash handling | Started reservations remain charged after process termination |
| Aggregation | Correct quantized aggregate, fresh protocol state, three-participant requirement, no plaintext fallback |
| Boundary inspection | No raw data, local weights, private metrics, keys or RNG state in coordinator payloads/logs |
| Validation privacy | Count-vector sensitivity and privacy map verified; repeated cached query does not redraw noise |
| Evidence integrity | Changed model, threshold, schema, policy or report invalidates prior approvals/signature checks |
| Tenant isolation | Cross-tenant IDs/tokens cannot fetch runs, receipts, artifacts or events |
| Attack credibility | Positive-control result and observable attacker interface recorded; weak tests labeled inconclusive |
| End-to-end product | Enroll -> train -> evaluate -> approve -> download -> local score on clean environment |

Passing these tests establishes the tested properties; it is not an unrestricted security certification.

## 20. Build sequence and ownership

Use these milestones in order. A practical four-person split is ML/data, privacy/federation, backend/governance, and frontend/deployment; a smaller team executes the same milestones sequentially.

1. **Foundation:** Fresh repository, provenance, data schema, partition manifest, local baseline, public development/test separation.
2. **Private local training:** One institution, real Opacus path, fixed sampling contract, secure RNG environment, accountant checks and persistent ledger.
3. **Collaboration:** Three workers using the official SecAgg route, shared signed run plan, conservative reservations, no plaintext metrics.
4. **Evidence:** Fixed-threshold DP validation, experiment matrix, attacks with controls, machine-readable evidence.
5. **Governance:** Release policy, approvals, canonical manifest/signature, artifact registry and local inference.
6. **SaaS:** Tenant-aware UI/API, queued jobs, usage page and sandbox checkout, public synthetic demo.
7. **Submission:** Clean-environment reproduction, deployment checks, architecture/provenance documentation, full evidence and a four-minute video.

Allow approximately three to four weeks of focused work for a small team, with actual time driven by the first mechanism/SecAgg integration milestone. The public event currently lists 31 October 2026 at 5:00pm IST as its deadline. Keep the final week for evaluation, deployment and submission rather than adding another privacy technology. [Event page](https://galuxium-nexus-v2-29411.devpost.com/).

## 21. Four-minute demonstration

0:00–0:30: Show three institutions and explain why their data remains local.

0:30–1:05: Create an approved training plan, show local budget reservations, and launch a short live run.

1:05–1:40: Show participant messages, round progression and the absence of raw record uploads. Open clearly labeled completed benchmark results for the full experiment.

1:40–2:20: Compare local/nonprivate/private performance at the fraud operating point; show epsilon/delta and the privacy-cost curve.

2:20–3:05: Attempt an over-budget operation and a release with altered evidence. Both are blocked with specific reasons. Show a failed attack control as inconclusive if that is the actual result.

3:05–3:35: Approve a qualifying candidate if one exists, verify its signed manifest, and score a synthetic transaction through an institution's local endpoint. If no candidate meets policy, show the truthful blocked state and a separately identified previously qualified run only if real evidence exists.

3:35–4:00: Show the customer, subscription/usage model, measured operating cost and the boundary of the current guarantee.

Closing pitch: **“FraudShield lets institutions learn together while retaining their records locally—and makes every model release accountable to a privacy budget and measured fraud-detection performance.”**

## 22. Research basis

- [Abadi et al., Deep Learning with Differential Privacy](https://arxiv.org/abs/1607.00133): per-example private training.
- [Opacus PrivacyEngine API](https://opacus.ai/api/privacy_engine.html): actual implementation contract.
- [Flower Opacus example](https://flower.ai/docs/examples/opacus.html): federated private-client integration reference.
- [Flower SecAgg+ example](https://flower.ai/docs/examples/flower-secure-aggregation.html): supported aggregation workflow.
- [Bonawitz et al., Practical Secure Aggregation](https://research.google/pubs/practical-secure-aggregation-for-privacy-preserving-machine-learning/): protocol foundations.
- [Liu et al., On Privacy and Personalization in Cross-Silo FL](https://arxiv.org/abs/2206.07902): record privacy in heterogeneous institutions.
- [Carlini et al., Membership Inference Attacks From First Principles](https://arxiv.org/abs/2112.03570): strong empirical privacy evaluation.
- [OpenDP measurements](https://docs.opendp.org/en/stable/api/python/opendp.measurements.html): governed count releases.
- [Fed-RD](https://arxiv.org/abs/2408.01609): related financial collaborative-learning research; no claim of first invention.
- [PaySim](https://github.com/EdgarLopezPhD/PaySim): synthetic transaction benchmark provenance.
- Prior local report: `RESEARCH-AND-PROJECT-DECISION.md`; earlier repository and VaultAdapt material remain references, not a prebuilt submission.
