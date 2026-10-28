# Deploy the public hackathon demo on Google Cloud Run

Google Cloud Run is the recommended host for the FraudShield public demo. The
application needs considerably more memory than the always-free 512 MB instances
available on Render and Koyeb. Cloud Run can run the existing Docker build with
2 GiB of memory, scale to zero when unused, and issue a public `run.app` HTTPS
URL.

This is a public-fixture demo only. It uses SQLite and an ephemeral `/data`
directory on one instance. A cold start, restart or revision deployment clears
workspaces, demo keys, ledgers and run history. Do not enter private records,
connect real institutions or describe this service as a confidential deployment.

## Before deploying

1. Sign in to a Google account and create a Google Cloud project.
2. Enable billing. Cloud Run has a monthly free allowance, but billing must be
   enabled. Create a low budget alert before deployment.
3. Open Cloud Shell in that project.

The official Cloud Run free tier includes 2 million requests, 180,000 vCPU
seconds and 360,000 GiB-seconds each month. A 2 GiB, 1-vCPU demo therefore has
about 50 request-active hours within those compute allowances. Keep the maximum
instance count at one and delete the service after judging.

## Deploy from the public repository

Run these commands in Cloud Shell. Replace `YOUR_PROJECT_ID` only if Cloud Shell
does not already select the project you created.

```bash
git clone https://github.com/MADHANSA147/fraudshield-network.git
cd fraudshield-network
git checkout codex/fraudshield
gcloud config set project YOUR_PROJECT_ID
gcloud run deploy fraudshield-network \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 1 \
  --concurrency 1 \
  --max-instances 1 \
  --timeout 900 \
  --set-env-vars FRAUDSHIELD_ALLOW_DEMO=1,FRAUDSHIELD_DEMO_INLINE=1,FRAUDSHIELD_SECURE_COOKIES=1
```

Cloud Run prints the public HTTPS URL when the deployment succeeds. Paste that
exact `https://…run.app` address into the hackathon **Live Working Demo URL**
field.

## Why demo-inline mode is enabled

The normal application dispatches a local worker process. Cloud Run's
request-based CPU allocation is not suitable for a detached background process.
`FRAUDSHIELD_DEMO_INLINE=1` keeps the public-fixture training operation inside
the active HTTP request. The short run may keep the browser waiting briefly, then
returns the completed evidence. It does not alter the DP mechanism, release gate
or public-data-only restriction.

## Judge-ready verification

1. Open the `run.app` URL in an incognito window.
2. Create a workspace and confirm the Overview page opens.
3. Start the quick public-fixture run once; wait for Evidence Ready.
4. Open Evidence Lab and Release Review. The candidate should remain blocked if
   it misses the policy—this is the intended governance behaviour.
5. Copy the URL only after these checks succeed.

## Cost and safety guardrails

- This service can become chargeable when usage exceeds Google Cloud's current
  free allowance. Monitor the Cloud Billing console and keep the instance limit
  at one.
- Never place credentials, Stripe keys, external storage credentials, real
  transaction data or institution certificates in Cloud Run environment values.
- Delete the Cloud Run service after the judging period.
