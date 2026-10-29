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
   `render.yaml` creates the `fraudshield-network` web service on the Free plan.
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

## Free-plan constraints

Render Free currently provides 512 MB RAM and 0.1 CPU, sleeps after inactivity,
and has an ephemeral local filesystem. FraudShield's full three-institution
training simulation is compute-heavy, so the public interface and evidence
views are the most reliable free-tier demo. The quick training run can be slow
or exceed this plan's resources. If that happens, do not misrepresent it as a
successful run: use the recorded public evidence views for the submission or
move the same Docker image to a host with at least 2 GiB memory.

Every restart, redeploy, or free-plan recycle can erase workspaces, demo keys,
ledgers, and run history. The hosted URL is therefore a temporary public
demonstration, never a confidential or production deployment.

For Render Blueprint syntax and current free-plan limits, see the official
[Blueprint reference](https://render.com/docs/blueprint-spec) and
[Free-plan documentation](https://render.com/docs/free).
