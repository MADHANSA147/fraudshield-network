# Four-minute demonstration

## Preparation

Start the local application. Use a public sandbox with a completed measured run.
Keep the benchmark report and CLI help available. State which services are local
and which external integrations have not been configured.

## 0:00–0:30 — The problem

Show the consortium overview and three institutions.

"FraudShield lets institutions collaborate on a fraud detector while retaining
their records locally. Privacy expenditure and measured performance determine
whether a model can be released."

Explain that this demonstration uses generated public records, not real banks.

## 0:30–1:15 — Training contract

Open New training run. Show epsilon/delta, rounds and local steps. Launch a small
run. Show actual stage events and completed secure rounds. The three-process
demo and the separate mutual-TLS route use the same Opacus/Flower implementation.

## 1:15–2:05 — Evidence

Show PR-AUC, recall, false alerts, per-institution results and privacy receipts.
Distinguish public exact metrics from noised validation intervals. Show the
baseline/ablation comparison and the attack positive-control status.

Use actual report numbers. Do not describe underfitting as a successful detector
or development metrics as held-out test performance.

## 2:05–2:55 — A gate that blocks

Read the actual Release review reasons. Owner approval cannot override quality
failures. The registry stays empty unless a real candidate passes every requirement.
The automated tampering/concurrency tests demonstrate additional failure paths.
Do not introduce fabricated test-only evidence into the measured registry.

## 2:55–3:30 — Local inference

Show the artifact contract and verify/activate/score commands. If no measured
candidate qualifies, say so. Explain that the successful bundle path is tested
with explicitly test-only evidence.

## 3:30–4:00 — Product and limits

Show actual usage and the pricing hypothesis. Stripe is test-mode only.
Do not claim revenue or customer validation. Close with data custody, record-level
accounting, inspected update boundaries and evidence-bound release.

## Submission checklist

- Confirm eligibility and provenance before publication.
- Publish only this fresh project; exclude var, keys, private references and data.
- Supply a public URL only after deployment is tested.
- Include benchmark provenance and BLOCKED/INCONCLUSIVE outcomes.
- Record the actual application; no simulated metrics.
