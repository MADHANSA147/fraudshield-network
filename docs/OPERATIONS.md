# Operations

## Local development

start.ps1 runs the prepared Windows installation on 127.0.0.1:8000. The default
database is var/control.db. Tenant keys, artifacts, logs and institution ledgers
are under var and excluded from Git. Never publish that directory.

The API starts public training as a background subprocess on Windows. It sets
CREATE_NO_WINDOW. SSE emits only allowlisted stage and budget events.
Cancellation prevents future work at round/evaluation boundaries and never
refunds a committed reservation.

If a host/process crashes, stop the abandoned worker before recovering its job:

    fraudshield recover RUN_ID --worker-stopped

This frees the workspace's active-job slot, retains local privacy expenditure
and marks the run aborted. It does not restart or refund an uncertain mechanism.

## Docker

Copy .env.example to .env, set a strong alphanumeric PostgreSQL password, then:

    docker compose config --quiet
    docker compose up --build

The composition contains PostgreSQL, Redis, API and an RQ worker. Only the API
is bound to host loopback. Databases and ledgers persist in named volumes.
Do not remove ledger volumes to recover a privacy budget.

The Dockerfile installs CPU PyTorch, builds the React app, and runs as a non-root
user. This machine had no running Docker daemon during development; the image,
clean Linux dependency resolution and service composition remain unexecuted here.
Use a host with sufficient image/build storage before claiming deployment success.

For external hosting, supply a domain and HTTPS reverse proxy, restrict allowed
origins, set FRAUDSHIELD_PUBLIC_URL and FRAUDSHIELD_SECURE_COOKIES=1. Public demo
creation is controlled by FRAUDSHIELD_ALLOW_DEMO. Its 20-workspace/hour and
20-run/workspace limits are demonstration quotas, not a production abuse solution.

## Optional services

Stripe accepts test-mode credentials only. Set STRIPE_SECRET_KEY, STRIPE_PRICE_ID,
STRIPE_WEBHOOK_SECRET and FRAUDSHIELD_PUBLIC_URL. The webhook checks the signature,
rejects live events, and deduplicates event IDs. The displayed $499 is a pricing
hypothesis, not proven willingness to pay or revenue. Actual checkout has not
been exercised without the user's Stripe test account.

An S3-compatible release mirror is available through FRAUDSHIELD_S3_BUCKET and
optional FRAUDSHIELD_S3_ENDPOINT plus the provider's standard credentials.
Only a verified, approved archive is mirrored. The bucket must remain private.
Server-side AES256 encryption is requested. A configured mirror failure blocks
the release transition. No cloud storage credentials were supplied or used.

## Durability and recovery limits

Local privacy ledgers use SQLite WAL, synchronous FULL and immediate write
transactions. Back up the control database, signing keys, artifacts and institution
ledgers as one documented operational set. Never restore an older privacy ledger
and resume private access without reconciling all later expenditure.

Initial schema creation uses SQLAlchemy metadata. Versioned production migrations,
multi-host disaster recovery and coordinated backups have not been validated.
Keep the demonstration database schema fixed; stage migrations and backup/restore
tests before operating with real institutions.

## Security-relevant configuration

HTTPS is required for nonlocal connector enrollment. Browser sessions are
HttpOnly, SameSite Strict cookies; bearer tokens are hashed in storage and expire.
Owner permissions are institution-specific. The public administrator can simulate
owner approvals only for public_fixture runs, with that fact recorded in audit events.

Review dependency updates against the mechanism and protocol integration tests.
requirements.lock records the locally tested versions, and package-lock.json
locks the frontend. The CI workflow is supplied but has not run on a remote
GitHub runner because the repository has not been published.
