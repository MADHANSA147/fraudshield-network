
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from fraudshield import api, store


@pytest.fixture
def client(monkeypatch, tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(store, "ENGINE", engine)
    monkeypatch.setattr(store, "ROOT", tmp_path)
    monkeypatch.setattr(api, "dispatch", lambda _: None)
    with TestClient(api.app) as client:
        yield client


def workspace(client):
    assert client.post("/api/demo/session", json={"name": "Test Consortium"}).status_code == 200


def test_auth_tenant_isolation_and_idempotency(client):
    assert client.get("/api/workspace").status_code == 401
    workspace(client)
    headers = {"Idempotency-Key": "a-stable-request-key"}
    first = client.post("/api/runs", json={"epsilon_cap": 2}, headers=headers)
    assert first.status_code == 202, first.text
    run_id = first.json()["id"]
    repeated = client.post("/api/runs", json={"epsilon_cap": 2}, headers=headers)
    assert repeated.json()["id"] == run_id
    assert client.post("/api/runs", json={"epsilon_cap": 4}, headers=headers).status_code == 409
    assert client.get("/api/runs/" + run_id).status_code == 200
    workspace(client)
    assert client.get("/api/runs/" + run_id).status_code == 404
    assert client.post("/api/runs/" + run_id + "/cancel").status_code == 404


def test_confidential_job_cannot_silently_use_demo(client):
    workspace(client)
    result = client.post("/api/runs", json={"mode": "confidential"}, headers={"Idempotency-Key": "not-a-demo"})
    assert result.status_code == 422


def test_readonly_cannot_train_and_unreleased_cannot_download(client):
    workspace(client)
    tenant = client.get("/api/workspace").json()["tenant"]["id"]
    with store.session() as db:
        token = store.issue_token(db, tenant, "auditor")
    result = client.post("/api/runs", json={}, headers={"Authorization": "Bearer " + token,
                                                       "Idempotency-Key": "auditor-request"})
    assert result.status_code == 403
    run = client.post("/api/runs", json={}, headers={"Idempotency-Key": "normal-request"}).json()
    assert client.get("/api/runs/" + run["id"] + "/bundle").status_code == 409
    assert client.post("/api/runs/" + run["id"] + "/release").status_code == 409


def test_unconfigured_billing_fails_explicitly(client, monkeypatch):
    workspace(client)
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    assert client.post("/api/billing/checkout").status_code == 503
    assert not client.get("/api/usage").json()["billing_configured"]


def test_cross_origin_post_rejected(client):
    assert client.post("/api/demo/session", json={"name": "Test"}, headers={"Origin": "https://attacker.invalid"}).status_code == 403


def test_enrollment_is_one_time_and_owner_cannot_approve_another_institution(client, tmp_path):
    from fraudshield.security import load_key, public_key
    workspace(client)
    enrollment = client.post("/api/institutions/atlas/enrollment", json={}).json()
    payload = {"token": enrollment["token"], "public_key": public_key(load_key(tmp_path / "owner.key"))}
    response = client.post("/api/connectors/enroll", json=payload)
    assert response.status_code == 200
    assert client.post("/api/connectors/enroll", json=payload).status_code == 403
    job = client.post("/api/runs", json={}, headers={"Idempotency-Key": "owner-check-job"}).json()
    with store.session() as db:
        row = db.get(store.Run, job["id"])
        row.status, row.evidence = "EVIDENCE_READY", {"test_only": True}
    owner = {"Authorization": "Bearer " + response.json()["token"]}
    assert client.post("/api/runs/" + job["id"] + "/approve/harbor", json={}, headers=owner).status_code == 403


def test_signed_sandbox_billing_is_idempotent(client, monkeypatch):
    import stripe
    workspace(client)
    tenant = client.get("/api/workspace").json()["tenant"]["id"]
    event = {"id": "evt_test_only", "livemode": False, "type": "checkout.session.completed",
             "data": {"object": {"client_reference_id": tenant}}}
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "test-only")
    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda *args: event)
    first = client.post("/api/billing/webhook", content=b"unit-test", headers={"Stripe-Signature": "test"})
    second = client.post("/api/billing/webhook", content=b"unit-test", headers={"Stripe-Signature": "test"})
    assert first.status_code == 200 and second.json()["duplicate"]
    assert client.get("/api/workspace").json()["tenant"]["subscription"] == "sandbox_subscribed"
    event["livemode"] = True
    assert client.post("/api/billing/webhook", content=b"unit-test", headers={"Stripe-Signature": "test"}).status_code == 400


def test_cancelled_queue_job_never_enters_training(client, monkeypatch):
    from fraudshield.worker import execute
    workspace(client)
    job = client.post("/api/runs", json={}, headers={"Idempotency-Key": "cancelled-job"}).json()
    assert client.post("/api/runs/" + job["id"] + "/cancel", json={}).status_code == 200
    execute(job["id"])
    result = client.get("/api/runs/" + job["id"]).json()
    assert result["status"] == "ABORTED"
    assert not (store.ROOT / "institutions").exists()
