import base64
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_key(path: Path) -> Ed25519PrivateKey:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as f:
            key = Ed25519PrivateKey.generate()
            f.write(key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()))
            f.flush()
            os.fsync(f.fileno())
        if os.name != "nt":
            path.chmod(0o600)
    except FileExistsError:
        pass
    # A simultaneous first request may observe the exclusive file before the
    # creator finishes writing it. Never replace an existing identity.
    for _ in range(20):
        raw = path.read_bytes()
        if len(raw) == 32:
            return Ed25519PrivateKey.from_private_bytes(raw)
        time.sleep(.05)
    raise ValueError("Signing key file is incomplete or corrupt")


def public_key(key) -> str:
    return base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()


def sign(payload: dict, key) -> dict:
    return {"payload": payload, "signature": base64.b64encode(key.sign(canonical(payload))).decode()}


def verify(envelope: dict, trusted_public_key: str) -> dict:
    key = Ed25519PublicKey.from_public_bytes(base64.b64decode(trusted_public_key, validate=True))
    key.verify(base64.b64decode(envelope["signature"], validate=True), canonical(envelope["payload"]))
    return envelope["payload"]


def atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix="." + path.name + ".", delete=False) as f:
        tmp = Path(f.name)
        f.write(canonical(data))
        f.flush()
        os.fsync(f.fileno())
    try:
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
