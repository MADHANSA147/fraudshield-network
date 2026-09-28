# Verification record — 28 September 2026

Dark-theme revision: all seven navigation pages opened in the real browser;
completed-run detail, evidence and blocked release review displayed real data.
The 390px release-review layout and mobile navigation were checked. Dialog
Escape dismissal was checked. TypeScript/Vite build and Ruff passed again.
The complete Python suite passed again: **31 passed, 8 warnings, 87.08 seconds**.
The historical workflow and benchmark checks below remain separately recorded.

## Executed

| Check | Observed result |
|---|---|
| Full Python suite | 31 passed, 0 failed; latest run 87.08 seconds |
| Python lint | Ruff passed |
| Dependency consistency | pip check: no broken requirements |
| Frontend | TypeScript and Vite production build passed |
| Docker Compose configuration | Parsed successfully; local Docker configuration access warnings |
| Real browser | Created workspace; launched quick and research runs; both reached EVIDENCE_READY |
| Mobile browser | 390px viewport checked; navigation and evidence layout worked; viewport restored |
| Secure aggregation | Local IPC and mutual-TLS three-institution integration tests passed |
| Signed release | Successful activation/scoring and rejection tests passed using test-only evidence |
| Public study | Nine research runs, seeds 242/243/244, epsilon profiles 2/4/8, all completed |

The research study used the configuration frozen after the separate public
development pilot. It produced PR-AUC 0.177–0.209 and recall about 5.3–7.6% at
the development-selected operating threshold. All candidates remained BLOCKED.
The 60% recall release floor was not relaxed.

The final browser research run showed a cumulative epsilon of approximately 4.67
after a prior run on the same local ledger, demonstrating retained expenditure.
Its new-run allowance was 2; the lifetime institution cap remained 8.

The membership diagnostic retains an INCONCLUSIVE outcome when its overfit
control cannot meet the predeclared low-FPR attack requirement. The final code
uses stable logit-space loss scores and includes a regression test for saturated
confidence ordering. Earlier recorded reports preserve their original source
hashes and results; they are not silently rewritten after implementation changes.

## Warnings and unexecuted checks

The test run emitted expected public-mode Opacus RNG warnings, PyTorch backward
hook notices and a Starlette/httpx deprecation notice. No test failure was hidden.

Docker daemon execution, clean Linux installation, hosted deployment, actual
Stripe checkout, S3 integration, actual PaySim evaluation, secure-RNG confidential
training and separate physical institution hosts were not verified here.

Passing these checks establishes the tested behavior. It is not an unrestricted
security, performance, regulatory or error-free certification.
