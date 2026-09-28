"""Bounded JSON/protobuf framing over mutually authenticated TLS.

Flower still owns all secure-aggregation cryptography. This transport never uses
pickle across a network. Certificate issuance is an institution operator task.
"""
import base64
import json
import math
import select
import socket
import ssl
import struct
from pathlib import Path

import numpy as np
from flwr.common import Message, serde

MAX_FRAME = 4 * 1024 * 1024


def encode(value):
    if isinstance(value, Message):
        return ["flower", base64.b64encode(serde.message_to_proto(value).SerializeToString()).decode()]
    if isinstance(value, np.ndarray):
        if value.dtype != np.float32 or value.size > 100000 or not np.isfinite(value).all():
            raise ValueError("Unexpected model array")
        return ["array", list(value.shape), base64.b64encode(value.tobytes()).decode()]
    if isinstance(value, dict):
        if not all(isinstance(k, str) for k in value):
            raise ValueError("Invalid message keys")
        return ["dict", {k: encode(v) for k, v in value.items()}]
    if isinstance(value, (tuple, list)):
        return ["tuple" if isinstance(value, tuple) else "list", [encode(v) for v in value]]
    if value is None or isinstance(value, (str, bool, int)) or isinstance(value, float) and math.isfinite(value):
        return ["scalar", value]
    raise ValueError("Unsupported wire value")


def decode(value, depth=0):
    if depth > 20 or not isinstance(value, list) or len(value) not in (2, 3):
        raise ValueError("Invalid wire structure")
    tag = value[0]
    if tag == "flower" and len(value) == 2:
        proto = serde.ProtoMessage()
        proto.ParseFromString(base64.b64decode(value[1], validate=True))
        return serde.message_from_proto(proto)
    if tag == "array" and len(value) == 3:
        shape = value[1]
        if not isinstance(shape, list) or not 1 <= len(shape) <= 2 or any(type(n) is not int or n <= 0 for n in shape):
            raise ValueError("Invalid array dimensions")
        size = math.prod(shape)
        if size > 100000:
            raise ValueError("Array exceeds model size")
        raw = base64.b64decode(value[2], validate=True)
        if len(raw) != size * 4:
            raise ValueError("Array size mismatch")
        result = np.frombuffer(raw, dtype=np.float32).reshape(shape).copy()
        if not np.isfinite(result).all():
            raise ValueError("Nonfinite array")
        return result
    if tag == "dict" and len(value) == 2 and isinstance(value[1], dict):
        return {k: decode(v, depth + 1) for k, v in value[1].items()}
    if tag in ("tuple", "list") and len(value) == 2 and isinstance(value[1], list):
        result = [decode(v, depth + 1) for v in value[1]]
        return tuple(result) if tag == "tuple" else result
    if tag == "scalar" and len(value) == 2:
        scalar = value[1]
        if scalar is None or isinstance(scalar, (str, bool, int)) or isinstance(scalar, float) and math.isfinite(scalar):
            return scalar
    raise ValueError("Invalid wire value")


class TLSConnection:
    def __init__(self, connection):
        self.socket = connection
        self.sent = self.received = 0

    def _read(self, size):
        data = bytearray()
        while len(data) < size:
            part = self.socket.recv(size - len(data))
            if not part:
                raise EOFError("Institution channel closed")
            data.extend(part)
        self.received += size
        return bytes(data)

    def send(self, value):
        payload = json.dumps(encode(value), allow_nan=False, separators=(",", ":")).encode()
        if len(payload) > MAX_FRAME:
            raise ValueError("Frame exceeds limit")
        self.socket.sendall(struct.pack("!I", len(payload)) + payload)
        self.sent += 4 + len(payload)

    def recv(self):
        size = struct.unpack("!I", self._read(4))[0]
        if not 0 < size <= MAX_FRAME:
            raise ValueError("Invalid frame length")
        return decode(json.loads(self._read(size)))

    def poll(self, timeout):
        return bool(self.socket.pending() or select.select([self.socket], [], [], timeout)[0])

    def close(self):
        self.socket.close()


def tls_context(config, server=False):
    purpose = ssl.Purpose.CLIENT_AUTH if server else ssl.Purpose.SERVER_AUTH
    context = ssl.create_default_context(purpose, cafile=config["ca"])
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(config["certificate"], config["private_key"])
    context.verify_mode = ssl.CERT_REQUIRED
    return context


def serve_institution(config_path: Path):
    from .contracts import Plan
    from .federation import institution_process
    from .security import digest, verify
    config = json.loads(config_path.read_text())
    context = tls_context(config, server=True)
    local = Path(config["directory"]).resolve()
    local.mkdir(parents=True, exist_ok=True)
    with socket.create_server((config.get("bind", "127.0.0.1"), config["port"])) as listener:
        print("Institution listener ready with mandatory client certificates", flush=True)
        while True:
            raw, _ = listener.accept()
            raw.settimeout(180)
            channel = None
            try:
                channel = TLSConnection(context.wrap_socket(raw, server_side=True))
                hello = channel.recv()
                approved = verify(hello["contract"], config["coordinator_public_key"])
                # The institution operator approves the exact signed contract locally.
                permitted = json.loads((local / "approved-plan.json").read_text())
                if digest(approved) != permitted["approved_hash"]:
                    raise ValueError("This training contract has not been locally approved")
                plan = Plan.model_validate(approved["plan"])
                institution = config["institution"]
                index = plan.participants.index(institution)
                institution_process(channel, institution, index, local, hello["contract"],
                                    config["coordinator_public_key"], approved["sigma"])
            except Exception as error:
                # Do not expose local paths, keys, records, or exception detail.
                print("Institution session stopped:", type(error).__name__, flush=True)
            finally:
                if channel:
                    channel.close()
                else:
                    raw.close()


def connect_institution(config, node, contract):
    context = tls_context(config)
    raw = socket.create_connection((node["host"], node["port"]), timeout=30)
    raw.settimeout(180)
    try:
        wrapped = context.wrap_socket(raw, server_hostname=node.get("server_name", node["host"]))
        channel = TLSConnection(wrapped)
        channel.send({"contract": contract})
        return channel
    except Exception:
        raw.close()
        raise
