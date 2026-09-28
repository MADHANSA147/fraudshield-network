"""Institution-operated transport using the same tested Flower aggregation path."""
from .contracts import Plan
from .federation import Federation, ProcessGrid
from .security import public_key, verify
from .transport import connect_institution


class RemoteFederation(Federation):
    def __init__(self, contract, signing_key, config):
        approved = verify(contract, public_key(signing_key))
        self.plan = Plan.model_validate(approved["plan"])
        self.run_id, self.sigma = approved["run_id"], approved["sigma"]
        self.approved, self.envelope = approved, contract
        self.config = config
        self.workers, self.keys = {}, {}
        self.grid = ProcessGrid(self.workers)
        if {n["institution"] for n in config["nodes"]} != set(self.plan.participants) or len(config["nodes"]) != 3:
            raise ValueError("Exactly three pinned institution endpoints are required")

    def start(self):
        for index, institution in enumerate(self.plan.participants):
            node = next(n for n in self.config["nodes"] if n["institution"] == institution)
            conn = connect_institution(self.config, node, self.envelope)
            self.workers[index + 1] = (conn, None)
            if not conn.poll(120):
                raise TimeoutError("Institution enrollment timeout")
            hello = conn.recv()
            if not hello.get("ready") or hello.get("public_key") != node["signing_public_key"] or hello.get("institution") != institution:
                raise ValueError("Institution signing identity does not match pinned registry")
            self.keys[institution] = hello["public_key"]

    def close(self):
        for conn, _ in self.workers.values():
            try:
                conn.send(("close", None))
            except (OSError, EOFError):
                pass
            conn.close()
