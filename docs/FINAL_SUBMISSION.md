# Galuxium Nexus V2 — final submission copy

Use this as the source of truth for the written Devpost fields. Replace every
`[bracketed value]` with the team's own information before submitting. Do not
claim a hosted deployment, payment integration, customer traction, real-bank
results, or a released fraud model until it has actually been completed.

## Project title

**FraudShield Network**

## Tagline / elevator pitch

**Privacy-governed collaborative AI for fraud detection: institutions train together without centralising transaction data.**

## Primary domain / track

**Autonomous AI & Intelligent Agents**

If the submission form offers a more specific **Enterprise SaaS**, **FinTech**,
or **Cybersecurity** category, select that category instead; it describes the
product more precisely than a generic agents category.

## Project banner / cover image

Use a 16:9 dark cover with the exact text:

```text
FraudShield Network
Privacy-governed collaborative fraud detection
Data stays local. Evidence decides release.
```

Visual direction: a deep navy background, three softly glowing institution nodes
at the bottom, a secure aggregation shield in the center, and thin mint-green
data paths that stop at the shield. Use mint, cyan and restrained violet accents.
Avoid bank logos, padlock stock photos, people, dollar signs, tiny unreadable
technical labels, and any claim that the model has already been approved.

## Team fields

| Form field | Value to enter |
|---|---|
| Team name | **[TEAM NAME]** |
| Primary contributor full name | **[YOUR FULL NAME]** |
| Primary contributor email | **[YOUR EMAIL]** |
| Discord username | **[YOUR DISCORD USERNAME]** |
| Total team size | **[NUMBER]** |
| Additional team members and emails | **[NAME — EMAIL; NAME — EMAIL]** |

## Executive briefing & problem statement

Financial institutions can improve fraud detection together, but cannot safely
centralise transaction records because data is sensitive, regulated and owned by
different organisations. Existing federated-learning demos often stop at model
training. They do not make privacy spend, evaluation leakage, evidence integrity
and model-release accountability visible to the people who must approve a model.

FraudShield Network is a governance-first collaborative AI SaaS for a
three-institution consortium. Each institution keeps its records in its local
worker and contributes clipped, differentially private model updates through
Flower SecAgg+. A persistent per-institution ledger composes privacy expenditure
across training and validation. The platform then records protected validation
evidence, attack diagnostics, signed receipts and release approvals against the
exact model, threshold and plan.

The workflow is a complete operational loop: create a signed training contract,
launch the three-party run, inspect evidence, review the release gate, register
only an approved signed bundle, and score transactions locally. The public demo
uses generated fixture data. Its recorded benchmark deliberately leaves models
that miss the recall and false-alert policy blocked, demonstrating that approvals
cannot override weak evidence. This is the product’s core promise: institutions
share learning, while custody, privacy budgets and release decisions remain
inspectable.

## Fiscal architecture & monetization engine

FraudShield is designed as a B2B consortium SaaS with a fixed workspace fee and
transparent infrastructure overages. The initial commercial hypothesis is a
**$499/month three-institution pilot** that includes the shared governance
workspace, three connector slots, training/evidence workflows and a signed model
registry. Metered worker time and secure-aggregation traffic provide the basis
for usage overages without collecting transaction volumes or charging per
transaction.

The prototype already records workspace usage from worker and protocol activity,
not private records, and includes a sandbox Stripe checkout/webhook path. The
checkout remains disabled until Stripe test credentials are configured. An
enterprise tier would price private deployment, dedicated support, additional
institutions and customer-managed operating boundaries separately. The $499
figure is an initial pricing hypothesis, not reported revenue or validated
customer demand.

## Primary tech stack used

**TypeScript, React, Vite, Python, FastAPI, PyTorch, Opacus, Flower SecAgg+,
OpenDP, SQLAlchemy, SQLite/PostgreSQL, Redis/RQ, Safetensors, Docker and GitHub
Actions.**

When the form offers multi-select choices, select **TypeScript / JavaScript / React**
and **Python / FastAPI**. Do not select Next.js: this project uses Vite, not Next.js.

## Public code repository link

**https://github.com/MADHANSA147/fraudshield-network**

## Live working demo URL

**[REQUIRED: paste the tested public HTTPS deployment URL here]**

The form requires a publicly hosted URL; `http://127.0.0.1:8000` is only a local
development address and must not be submitted. The repository currently includes
the deployment configuration and a passing clean-Ubuntu GitHub Actions workflow,
but no public deployment URL has been verified.

## Technical keynote / demo video link

**[PASTE YOUR 2–5 MINUTE YOUTUBE OR LOOM LINK]**

### Video story beats

1. **Problem (0:00–0:25):** Three institutions need better fraud detection but
   cannot centralise their records.
2. **Training contract (0:25–0:55):** Show the consortium dashboard, the signed
   plan, epsilon/delta allowance, rounds and local steps.
3. **Protected collaboration (0:55–1:35):** Show all three workers, DP-SGD and
   SecAgg+; say that the public demo uses generated fixtures, not bank data.
4. **Evidence (1:35–2:15):** Show the Evidence Lab with per-institution metrics,
   protected validation intervals, privacy receipts, comparison runs and attack
   diagnostic status.
5. **Governance moment (2:15–3:00):** Open Release Review. Emphasise that the
   model is blocked because it does not meet the policy; owner approvals cannot
   override evidence.
6. **Business model and close (3:00–3:30):** Show usage metering and the pilot
   pricing hypothesis. Close with: “FraudShield lets institutions learn together
   while data stays local and every release remains accountable.”

## Evidence for judges

| Judging focus | What to point to |
|---|---|
| Technical architecture & scalability | FastAPI control plane, durable SQLAlchemy state, local subprocess/RQ worker option, three-worker Flower workflow, protocol byte metering, Docker configuration and clean Ubuntu CI. |
| Enterprise governance & compliance | Opacus record-level DP-SGD, PRV/RDP accounting, persistent local ledgers, Flower SecAgg+, mTLS route, signed plans/receipts/bundles, OpenDP validation and tamper-resistant release checks. |
| Product innovation & market fit | A full governance workflow from enrolment and training contract to evidence, release review, signed registry and local inference—not a training notebook. |
| Monetization & fiscal design | Consortium pilot pricing, three connector slots, metered compute/protocol use, sandbox billing integration and no transaction-volume telemetry. |
| UI/UX | Responsive dark consortium workspace with Overview, Institutions, Training Runs, Evidence Lab, Release Review, Registry and Usage pages. |
| Demo completeness | Run the actual sandbox, show the recorded research evidence and explain the deliberately blocked release outcome honestly. |

## Verified implementation facts

- The public repository has a clean Ubuntu GitHub Actions pass for the backend
  suite and frontend build.
- The local verification suite reports 31 passing tests, with browser checks for
  all workflow pages and mobile release review.
- The recorded public engineering benchmark contains nine runs: three seeds at
  each planned epsilon value of 2, 4 and 8.
- Those results are generated fixtures, not PaySim, bank data or a claim of a
  production-quality detector. The current candidates do not meet the release
  policy and remain blocked.
- Confidential execution is fail-closed until secure randomness and institution
  deployment prerequisites are supplied.

## Required declarations — team action

Only tick each declaration after the person submitting has personally verified
it is true:

- **Originality & commit date:** The repository's provenance states that it is a
  fresh implementation and that no prior private-project implementation was
  copied. Confirm this statement and the hackathon's date rule yourself before
  ticking the form checkbox.
- **Code & asset ownership:** Tick only if the team owns, or has valid rights to,
  all code, assets, APIs and the final banner/video used in the submission.
- **Final evaluation terms:** Read the current rules and tick only if the team
  agrees to them.

## Final pre-submit checklist

- Replace all bracketed team, contact, demo and video values.
- Test the public HTTPS demo in an incognito window, including workspace creation,
  a short run and Evidence Lab.
- Make the video 2–5 minutes and show the actual product state.
- Upload a 16:9 cover image with the text and visual direction above.
- Confirm the repository link opens on the public default branch and the README
  is visible.
- Make only claims supported by the repository evidence; do not describe the
  generated-fixture benchmark as real banking validation.
