# Architecture and claim boundaries

## Public application

Browser -> authenticated FastAPI control plane -> subprocess or RQ job ->
three institution clients -> official Flower SecAgg+ -> candidate evidence ->
release gate -> signed artifact -> local inference.

The coordinator receives masked Flower messages, secure aggregates, signed
privacy receipts and already-noised validation vectors. Arbitrary evaluation
metrics are not attached to the secure fit result. The coordinator can read
public benchmark arrays for explicitly labeled baselines and attacks.

The local demonstration has a trusted-host assumption. Its child processes,
coordinator files and institution ledgers share one operating system.
The separate TLS listener path removes the need to mount institution data in
the coordinator process. Each institution operates its own files and ledger.

## Privacy contract

- Unit: one transaction; add/remove through a real record versus zero-contribution
  dummy slot in a fixed public capacity.
- One changed row affects only its own feature vector. Public transforms use
  fixed bounds and vocabularies.
- Uniform Poisson slot sampling, fixed expected-batch normalization, clipped
  per-example weighted BCE gradients, Gaussian noise and fixed optimizer steps.
- Per-institution epsilon is PRV(training history, delta) plus all pure-DP
  validation epsilon. RDP is a diagnostic bound, never silently substituted.
- Disjoint institution ownership permits a worst-record statement based on the
  maximum institution epsilon/delta. Duplicate ownership invalidates that
  parallel-composition assumption.
- SecAgg adds confidentiality of individual updates. No privacy amplification
  from secure aggregation or organization sampling is claimed.
- A frozen trained model is post-processing. A fresh private validation answer,
  adaptation or training step is not free.

Public benchmark mode uses standard experimental randomness. Confidential
training requires Opacus secure_mode and an actually functioning torchcsprng
installation. Agent approval fails before execution if that prerequisite is absent.

## Trust and threats

Assume honest institution clients, trusted institution host administrators,
and an honest-but-curious non-colluding coordinator. TLS authenticates endpoints;
Ed25519 pins signed plans, identities, receipts and releases. Signatures do not
prove that a dishonest institution executed the reported mechanism.

The host administrator must not roll back or alias away the authoritative
privacy ledger. Cross-host rollback resistance, hardware attestation, malicious
coordinator security, client collusion, side-channel resistance and Byzantine
robustness have not been established.

The coordinator may observe timing, protocol stage, enrolled identity and fixed
configuration. Confidential record counts, raw losses, optimizer state, record
membership and RNG state are not intentional protocol fields.

## Release

The policy requires privacy receipts, recomputed expenditure, matching plan and
candidate, full participation, public institution utility bounds, protected
validation bounds, a credible attack control, non-inferiority, and all owner
approvals. Owner approvals alone never override quality failures.

The public demonstration policy is a 1% false-positive ceiling and 60% recall
floor, using conservative confidence bounds. Current fixture candidates fail it.
Changing policy is not evidence that the old experiment succeeded.

The signature binds file hashes and evidence; it is not a compliance certificate.
Local activation rejects unknown files, duplicate ZIP entries, symlinks, path
traversal, excessive size, unsupported schema, nonfinite weights and wrong keys.

## Research basis

- Abadi et al.: https://arxiv.org/abs/1607.00133
- Opacus implementation: https://opacus.ai/api/privacy_engine.html
- Flower SecAgg+: https://flower.ai/docs/examples/flower-secure-aggregation.html
- Bonawitz et al.: https://research.google/pubs/practical-secure-aggregation-for-privacy-preserving-machine-learning/
- Cross-silo privacy: https://arxiv.org/abs/2206.07902
- Membership inference and LiRA: https://arxiv.org/abs/2112.03570
- OpenDP: https://docs.opendp.org/en/stable/api/python/opendp.measurements.html
- PaySim: https://github.com/EdgarLopezPhD/PaySim

The implemented four-shadow pooled likelihood diagnostic is not a reproduction
of full per-example LiRA. Its finite sample, temporal distribution mismatch and
low-FPR resolution limit conclusions, even when its positive control passes.
