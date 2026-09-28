"""Official Flower SecAgg+ over isolated local processes for public-data demos.

This transport is a local deployment simulation, not a malicious-host boundary.
No custom masking or replacement cryptography is implemented here.
"""
import multiprocessing as mp
from multiprocessing.reduction import ForkingPickler
import time
import uuid
from pathlib import Path

import torch
from flwr.client import ClientApp, NumPyClient
from flwr.client.mod import secaggplus_mod
from flwr.common import ConfigRecord, Context, Message, Metadata, RecordDict
from flwr.common import ndarrays_to_parameters, parameters_to_ndarrays
from flwr.compat.common import recorddict_compat as compat
from flwr.server import LegacyContext, ServerConfig
from flwr.server.compat.grid_client_proxy import GridClientProxy
from flwr.server.strategy import FedAvg
from flwr.server.workflow import SecAggPlusWorkflow
from flwr.server.workflow.secure_aggregation.secaggplus_workflow import WorkflowState

from .contracts import Plan
from .accounting import epsilon
from .data import SCHEMA_HASH
from .datasets import public_split
from .evaluation import private_confusion
from .ledger import PrivacyLedger
from .security import atomic_json, digest, load_key, public_key, sign, verify
from .training import Detector, array_hash, arrays, predict, set_arrays, train_private


def institution_process(connection, institution, index, directory, plan_envelope, coordinator_key, sigma):
    try:
        torch.set_num_threads(1)
        approved = verify(plan_envelope, coordinator_key)
        if approved["schema_hash"] != SCHEMA_HASH:
            raise ValueError("Approved feature contract differs from the installed implementation")
        plan = Plan.model_validate(approved["plan"])
        if approved["sigma"] != sigma or epsilon([
            {"kind": "training", "q": plan.sample_rate, "sigma": sigma,
             "steps": plan.rounds * plan.local_steps},
            {"kind": "validation", "epsilon": plan.evaluation_epsilon}
        ], plan.delta) > plan.epsilon_cap:
            raise ValueError("Training mechanism does not match approved privacy budget")
        directory = Path(directory)
        key = load_key(directory / "identity.key")
        lineage = {"public_fixture": "fixture-v1", "public_paysim": "public-paysim-v1",
                   "confidential": "confidential-v1"}[plan.mode]
        ledger = PrivacyLedger(directory / "privacy.db", lineage, 8.0, plan.delta)
        proposed = [(f'{approved["run_id"]}:round:{r}', {
            "kind": "training", "sigma": sigma, "q": plan.sample_rate, "steps": plan.local_steps})
            for r in range(1, plan.rounds + 1)]
        proposed.append((approved["run_id"] + ":validation", {"kind": "validation", "epsilon": plan.evaluation_epsilon}))
        ledger.preflight(proposed)
        x, y = public_split(plan, index, "train", directory / "dataset")
        model = Detector()

        class Client(NumPyClient):
            def fit(self, parameters, config):
                nonlocal model
                if not 1 <= config["server_round"] <= plan.rounds:
                    raise ValueError("Round outside approved plan")
                if config["approved_hash"] != digest(approved) or config["schema_hash"] != SCHEMA_HASH:
                    raise ValueError("Unapproved training configuration")
                if array_hash(parameters) != config["input_hash"]:
                    raise ValueError("Global model hash mismatch")
                set_arrays(model, parameters)
                reservation = f'{approved["run_id"]}:round:{config["server_round"]}'
                model, _ = train_private(model, x, y, plan, sigma, ledger, reservation, directory / "checkpoints")
                return arrays(model), 1, {}

            def get_parameters(self, config):
                raise ValueError("Unprotected parameter retrieval disabled")

            def evaluate(self, parameters, config):
                raise ValueError("Raw private evaluation disabled")

        app = ClientApp(client_fn=lambda context: Client().to_client(), mods=[secaggplus_mod])
        context = Context(run_id=1, node_id=index + 1, node_config={}, state=RecordDict(), run_config={})
        connection.send({"ready": True, "institution": institution, "public_key": public_key(key)})
        while True:
            command, payload = connection.recv()
            if command == "close":
                break
            if command == "flower":
                result = app(payload, context)
                if result.has_content() and any(len(record) for record in result.content.array_records.values()):
                    raise RuntimeError("Raw parameter record escaped the secure aggregation client")
                connection.send(result)
            elif command == "receipt":
                summary = ledger.summary()
                connection.send(sign({"institution": institution, "run_id": approved["run_id"],
                                      "plan_hash": digest(approved), **summary}, key))
            elif command == "validate":
                values, threshold = payload
                set_arrays(model, values)
                query = {"model_hash": array_hash(values), "threshold": threshold, "run_id": approved["run_id"]}
                qid = approved["run_id"] + ":validation"
                reserved = ledger.reserve(qid, query, {"kind": "validation", "epsilon": plan.evaluation_epsilon})
                cache = directory / "validation" / (digest(query) + ".json")
                if reserved["cached"]:
                    import json
                    if not cache.exists() or not reserved.get("output"):
                        raise ValueError("Validation attempt already charged; cannot regenerate its noise")
                    release = json.loads(cache.read_text())
                    if digest(release) != reserved["output"]:
                        raise ValueError("Validation cache integrity failure")
                else:
                    vx, vy = public_split(plan, index, "validation", directory / "dataset")
                    release = {**query, **private_confusion(vy, predict(model, vx), threshold, plan.evaluation_epsilon)}
                    atomic_json(cache, release)
                    ledger.complete(qid, digest(release))
                connection.send(sign({"institution": institution, **release}, key))
            else:
                raise ValueError("Unknown worker command")
    except EOFError:
        pass
    except Exception as error:
        # Explicit allowlisted errors; never return records or local tracebacks to coordinator.
        connection.send({"error": type(error).__name__, "detail": str(error)[:250]})
    finally:
        connection.close()


class ProcessGrid:
    def __init__(self, workers):
        self.workers = workers
        self.bytes_sent = 0
        self.bytes_received = 0
        self.trace = []

    def get_node_ids(self):
        return list(self.workers)

    def send_and_receive(self, messages, timeout=None):
        messages = list(messages)
        if {m.metadata.dst_node_id for m in messages} != set(self.workers):
            raise RuntimeError("Every protocol stage requires all three institutions")
        for message in messages:
            meta = message.metadata
            prepared = Message(content=message.content, metadata=Metadata(
                run_id=1, message_id=str(uuid.uuid4()), src_node_id=0, dst_node_id=meta.dst_node_id,
                reply_to_message_id="", group_id=meta.group_id, created_at=time.time(), ttl=600,
                message_type=meta.message_type))
            # Match this local IPC transport's serialization, including its four-byte frame header.
            connection = self.workers[meta.dst_node_id][0]
            before = getattr(connection, "sent", 0)
            connection.send(("flower", prepared))
            self.bytes_sent += (connection.sent - before if hasattr(connection, "sent")
                                else len(ForkingPickler.dumps(("flower", prepared))) + 4)
        replies = []
        for message in messages:
            conn, _ = self.workers[message.metadata.dst_node_id]
            if not conn.poll(timeout or 180):
                raise TimeoutError("Institution did not complete protocol stage; round aborted")
            before = getattr(conn, "received", 0)
            reply = conn.recv()
            if not isinstance(reply, Message):
                raise RuntimeError(f'Institution failed: {reply.get("error", "unknown")}: {reply.get("detail", "")}')
            if reply.has_error() or any(len(record) for record in reply.content.array_records.values()):
                raise RuntimeError("Failed or unprotected secure-aggregation response")
            self.bytes_received += (conn.received - before if hasattr(conn, "received")
                                    else len(ForkingPickler.dumps(reply)) + 4)
            self.trace.append({"round": message.metadata.group_id, "institution": message.metadata.dst_node_id,
                               "array_records": 0, "record_names": list(reply.content.keys())})
            replies.append(reply)
        return replies


class Federation:
    def __init__(self, plan, run_id, root: Path, sigma, signing_key):
        self.plan, self.run_id, self.root, self.sigma = plan, run_id, root, sigma
        self.approved = {"plan": plan.model_dump(), "run_id": run_id, "schema_hash": SCHEMA_HASH, "sigma": sigma}
        self.envelope = sign(self.approved, signing_key)
        self.coordinator_key = public_key(signing_key)
        self.workers, self.keys = {}, {}
        self.grid = ProcessGrid(self.workers)

    def start(self):
        if self.plan.mode == "confidential":
            raise ValueError("Confidential data requires the institution-operated TLS transport")
        ctx = mp.get_context("spawn")
        for index, institution in enumerate(self.plan.participants):
            parent, child = ctx.Pipe()
            process = ctx.Process(target=institution_process, args=(
                child, institution, index, str(self.root / institution), self.envelope, self.coordinator_key, self.sigma))
            process.start()
            child.close()
            self.workers[index + 1] = (parent, process)
        for node_id, (conn, _) in self.workers.items():
            if not conn.poll(120):
                raise TimeoutError("Worker enrollment timeout")
            result = conn.recv()
            if not result.get("ready"):
                raise RuntimeError(str(result))
            self.keys[result["institution"]] = result["public_key"]

    def train(self, on_round, cancelled=lambda: False):
        torch.manual_seed(self.plan.seed)
        initial = arrays(Detector())
        strategy = FedAvg(fraction_fit=1.0, fraction_evaluate=0.0, min_fit_clients=3,
                          min_available_clients=3, accept_failures=False,
                          initial_parameters=ndarrays_to_parameters(initial),
                          fit_metrics_aggregation_fn=lambda results: {})
        context = LegacyContext(Context(1, 0, {}, RecordDict(), {}), config=ServerConfig(num_rounds=self.plan.rounds),
                                strategy=strategy)
        for node_id in self.workers:
            context.client_manager.register(GridClientProxy(node_id, self.grid, 1))
        context.state.array_records["parameters"] = compat.parameters_to_arrayrecord(
            ndarrays_to_parameters(initial), keep_input=True)
        config = ConfigRecord({"current_round": 0})
        context.state.config_records["config"] = config
        # Flower's fractional threshold 1.0 resolves to all three shares; integer equality is rejected.
        workflow = SecAggPlusWorkflow(num_shares=3, reconstruction_threshold=1.0, max_weight=1.0,
                                     clipping_range=8.0, quantization_range=2**22, modulus_range=2**32, timeout=180)
        for round_number in range(1, self.plan.rounds + 1):
            if cancelled():
                raise InterruptedError("Run cancelled before next round")
            values = parameters_to_ndarrays(compat.arrayrecord_to_parameters(
                context.state.array_records["parameters"], keep_input=True))
            config["current_round"] = round_number
            strategy.on_fit_config_fn = lambda _, r=round_number, h=array_hash(values): {
                "server_round": r, "input_hash": h, "approved_hash": digest(self.approved), "schema_hash": SCHEMA_HASH}
            state = WorkflowState()
            for step in (workflow.setup_stage, workflow.share_keys_stage,
                         workflow.collect_masked_vectors_stage, workflow.unmask_stage):
                if not step(self.grid, context, state):
                    raise RuntimeError("Secure aggregation aborted; plaintext fallback is prohibited")
            receipts = self.receipts()
            on_round(round_number, receipts, self.grid.bytes_sent + self.grid.bytes_received)
        # The model contract is float32; quantization arithmetic may return float64.
        return [value.astype("float32") for value in parameters_to_ndarrays(compat.arrayrecord_to_parameters(
            context.state.array_records["parameters"], keep_input=True))]

    def command_all(self, command, payload=None):
        for conn, _ in self.workers.values():
            conn.send((command, payload))
        results = []
        for index, institution in enumerate(self.plan.participants):
            conn = self.workers[index + 1][0]
            if not conn.poll(120):
                raise TimeoutError("Institution response timeout")
            envelope = conn.recv()
            if "error" in envelope:
                raise RuntimeError(envelope["detail"])
            value = verify(envelope, self.keys[institution])
            if value["institution"] != institution:
                raise ValueError("Receipt institution mismatch")
            results.append(envelope)
        return results

    def receipts(self):
        return self.command_all("receipt")

    def validate(self, values, threshold):
        return self.command_all("validate", (values, threshold))

    def close(self):
        for conn, process in self.workers.values():
            try:
                conn.send(("close", None))
            except (BrokenPipeError, EOFError, OSError):
                pass
            process.join(3)
            if process.is_alive():
                process.terminate()
                process.join(3)
            conn.close()
