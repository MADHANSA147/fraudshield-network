# Institution-operated transport

This path uses real Flower SecAgg+ over a small mutually authenticated TLS
transport. It has been integration-tested with three local TLS endpoints and
public records. Separate machines, institutional PKI and real confidential
execution have not been tested in this workspace.

## Provision identities

Each institution owns its directory, signing key, data, TLS private key and
privacy.db. The coordinator must not mount those directories.

Use a consortium CA and distinct leaf certificates with appropriate server/client
usage and DNS/IP subject alternative names. The code requires trusted certificates
and hostname verification. It contains no insecure certificate bypass.
Example configuration files contain placeholders, not credentials.

Copy examples/agent.example.json onto each institution host and configure its
institution name, host-local directory, certificate paths, bind address and port.
Keep the default loopback binding for local testing; an operator must explicitly
choose the reachable interface for a cross-host deployment.

Create the signed plan at the coordinator:

    fraudshield remote-contract --plan examples/plan.json --key coordinator.key --output contract.json

Distribute the contract and pin the coordinator Ed25519 public key through an
authenticated operator channel. On each institution:

    fraudshield agent-approve contract.json --trusted-key COORDINATOR_KEY --directory LOCAL_INSTITUTION_DIRECTORY
    fraudshield agent-serve agent.json

Approval creates the institution signing identity if needed. Pin the returned
public keys in coordinator.example.json. The coordinator refuses any mismatch.
Local approval is required for every new contract hash.

## Datasets

Public fixture mode generates only public records. For PaySim, copy the prepared
institution folder into that institution's dataset directory.

For institution-owned CSV data, perform preparation only on its own host:

    fraudshield agent-prepare --train train.csv --validation validation.csv --directory LOCAL_INSTITUTION_DIRECTORY

Required fields: amount, type, step and isFraud; oldbalanceOrg may be missing.
Features are row-local and fixed. Preparation writes NPZ files and their hashes
locally; it makes no network request. Existing registered data is not overwritten.
Use filesystem access controls appropriate for the institution.

Confidential mode requires a compatible tested torchcsprng build. It is not
installed in the delivered Windows environment. agent-approve and training refuse
to silently fall back to nonsecure randomness. The loader checks the declared
capacity; it never truncates confidential records to make a job fit.

## Execute a candidate

Supply a genuinely public development NPZ containing x and y arrays. Do not
point this option at private records: this file is read at the coordinator to
select the operating threshold.

    fraudshield remote-run contract.json --key coordinator.key --config coordinator.json --public-development public-development.npz --output candidate

The command trains, validates with budgeted counts, and stores a clearly marked
CANDIDATE_NOT_RELEASED artifact. The standalone remote runner does not bypass
the product release policy and does not automatically place a candidate into
the web registry. Remote private release review and its full cross-host operating
procedure remain acceptance work, not a verified production feature.

A disconnect aborts the round. Reconnecting to retransmit a completed identical
operation uses cached DP outputs. Failed reservations remain spent. One validation
query is allowed for an approved run; changing its model or threshold requires
a newly approved run and sufficient remaining budget.
