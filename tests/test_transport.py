import datetime
import ipaddress
import multiprocessing as mp
import socket
import time

import numpy as np
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from safetensors.torch import load_file

from fraudshield.contracts import Plan
from fraudshield.data import SCHEMA_HASH
from fraudshield.remote import RemoteFederation
from fraudshield.security import atomic_json, digest, load_key, public_key, sign
from fraudshield.training import Detector, arrays
from fraudshield.transport import decode, encode, serve_institution


def certificates(directory):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "FraudShield test CA")])
    now = datetime.datetime.now(datetime.timezone.utc)
    ca = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=1))
          .not_valid_after(now + datetime.timedelta(days=1))
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
          .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, None, None), critical=True)
          .sign(key, hashes.SHA256()))
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
            .issuer_name(name).public_key(leaf_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=1)).not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(leaf_key.public_key()), critical=False)
            .add_extension(x509.KeyUsage(True, False, True, False, False, False, False, None, None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
            .sign(key, hashes.SHA256()))
    (directory / "ca.pem").write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    (directory / "leaf.pem").write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    (directory / "leaf.key").write_bytes(leaf_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return {"ca": str(directory / "ca.pem"), "certificate": str(directory / "leaf.pem"),
            "private_key": str(directory / "leaf.key")}


def test_codec_rejects_unbounded_or_nonfinite_arrays():
    value = ("validate", ([np.zeros((4, 2), dtype=np.float32)], .5))
    rebuilt = decode(encode(value))
    assert np.array_equal(rebuilt[1][0][0], value[1][0][0])
    with pytest.raises(ValueError):
        decode(["array", [10000000], ""])
    with pytest.raises(ValueError):
        encode(np.array([float("nan")], dtype=np.float32))
    with pytest.raises(ValueError):
        decode(["scalar", {"unexpected": "mapping"}])


def test_three_mutual_tls_institutions_and_quantized_aggregate(tmp_path):
    tls = certificates(tmp_path)
    key = load_key(tmp_path / "coordinator.key")
    plan = Plan(capacity=128, batch_size=16, rounds=1, local_steps=2)
    approved = {"plan": plan.model_dump(), "run_id": "tls-test", "sigma": 2., "schema_hash": SCHEMA_HASH}
    contract = sign(approved, key)
    processes, nodes = [], []
    federation = None
    try:
        for institution in plan.participants:
            directory = tmp_path / institution
            identity = load_key(directory / "identity.key")
            atomic_json(directory / "approved-plan.json", {"approved_hash": digest(approved)})
            with socket.socket() as reserve:
                reserve.bind(("127.0.0.1", 0))
                port = reserve.getsockname()[1]
            config = {**tls, "directory": str(directory), "port": port, "institution": institution,
                      "coordinator_public_key": public_key(key)}
            atomic_json(directory / "agent.json", config)
            process = mp.get_context("spawn").Process(target=serve_institution, args=(directory / "agent.json",))
            process.start()
            processes.append(process)
            nodes.append({"host": "127.0.0.1", "port": port, "institution": institution,
                          "signing_public_key": public_key(identity)})
        for node in nodes:
            deadline = time.monotonic() + 60
            while True:
                try:
                    with socket.create_connection((node["host"], node["port"]), timeout=.2):
                        break
                except OSError:
                    if time.monotonic() > deadline:
                        raise TimeoutError("Test institution failed to start")
                    time.sleep(.1)
        federation = RemoteFederation(contract, key, {**tls, "nodes": nodes})
        federation.start()
        result = federation.train(lambda *args: None)
        # Test harness only: compare private local files with the secure output.
        # Production coordinator never has these institution filesystem mounts.
        local = []
        for institution in plan.participants:
            path = next((tmp_path / institution / "checkpoints").glob("*.safetensors"))
            model = Detector()
            model.load_state_dict(load_file(str(path)))
            local.append(arrays(model))
        for index, aggregate in enumerate(result):
            expected = np.mean([np.clip(values[index], -8, 8) for values in local], axis=0)
            assert np.max(np.abs(aggregate - expected)) < 3e-5
        assert len(federation.validate(result, .5)) == 3
        assert all(item["array_records"] == 0 for item in federation.grid.trace)
    finally:
        if federation:
            federation.close()
        for process in processes:
            process.terminate()
            process.join(5)
