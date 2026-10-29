# Deploy the public hackathon demo on Render

This Blueprint deploys the public FraudShield generated-fixture demo as one
Render web service. It does not use private financial, health, government, or
institutional data, and it does not include external credentials.

## Create the free deployment

1. Open [Render's Blueprint page](https://dashboard.render.com/blueprints) and
   sign in with GitHub.
2. Select **New Blueprint Instance**, then choose
   `MADHANSA147/fraudshield-network`.
3. Select the `codex/fraudshield` branch if Render asks. The repository's
   `render.yaml` creates the `fraudshield-network` web service on Render's
   `1c-2g` plan (1 CPU, 2 GB RAM).
4. Click **Apply** and wait for the Docker build and `/api/ready` health check.
5. Open the generated `https://fraudshield-network.onrender.com` URL from the
   service dashboard. Render adds a suffix if that name is already in use.

No environment variables need to be added manually. The service binds to
Render's assigned `PORT`, and demo-inline mode keeps the short public run in the
browser request instead of starting a detached worker.

## Verify before submitting

1. Open the URL in an incognito window (the free plan may cold-start after
   inactivity).
2. Select **Open demo workspace**, then verify that Overview and Evidence Lab
   load.
3. Start one quick generated-fixture run. Wait for its evidence view; do not
   enter real records or credentials.
4. Visit Release Review. A candidate that misses the stated policy remains
   blocked; that is an intentional governance control, not a successful
   production fraud-release claim.
5. Paste the exact Render HTTPS URL into the hackathon **Live Working Demo URL**
   field only after these checks succeed.

## Demo-service constraints

Render's `1c-2g` plan is a paid plan with 1 CPU and 2 GB RAM. This capacity is
configured because FraudShield runs three isolated Torch institution workers for
a genuine public-fixture DP-SGD + SecAgg+ experiment. It is still a temporary
demo service, not a production confidential deployment.

Every restart or redeploy can erase workspaces, demo keys, ledgers, and run
history because this single-service demo deliberately uses ephemeral SQLite
state. The hosted URL is therefore a temporary public
demonstration, never a confidential or production deployment.

For Render Blueprint syntax and current free-plan limits, see the official
[Blueprint reference](https://render.com/docs/blueprint-spec) and
[Free-plan documentation](https://render.com/docs/free).
