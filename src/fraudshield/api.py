import asyncio
import json
import os
import secrets
import subprocess
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from . import store
from .contracts import INSTITUTIONS, Plan
from .data import SCHEMA
from .governance import evaluate_gate, release_manifest
from .security import digest, file_hash, load_key, public_key
from .artifacts import archive_bundle, mirror_release


@asynccontextmanager
async def lifespan(app):
    store.init()
    yield


app = FastAPI(title="FraudShield Network", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get(
    "FRAUDSHIELD_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(","),
    allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Idempotency-Key", "Authorization"])


@app.middleware("http")
async def security_headers(request, call_next):
    if request.method == "POST":
        origin = request.headers.get("origin")
        permitted = set(os.environ.get("FRAUDSHIELD_ORIGINS",
                        "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8000,http://localhost:8000").split(","))
        same_host = origin and urlsplit(origin).netloc == request.headers.get("host")
        if origin and origin not in permitted and not same_host and not request.url.path.startswith("/api/billing/webhook"):
            return Response("Origin not permitted", status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api") else "no-cache"
    return response


def identity(authorization: str | None = Header(None), fs_session: str | None = Cookie(None)):
    token = authorization.removeprefix("Bearer ") if authorization else fs_session
    if not token:
        raise HTTPException(401, "Sign in to your workspace")
    with store.session() as db:
        member = db.scalar(select(store.Membership).where(store.Membership.token_hash == digest(token.encode()),
                                                         store.Membership.expires > time.time()))
        if not member:
            raise HTTPException(401, "Session expired or invalid")
        return {"id": member.id, "tenant": member.tenant_id, "role": member.role, "institution": member.institution}


def require_write(user):
    if user["role"] not in ("admin", "analyst", "owner"):
        raise HTTPException(403, "Read-only membership")


def own_run(db, run_id, user):
    run = db.scalar(select(store.Run).where(store.Run.id == run_id, store.Run.tenant_id == user["tenant"]))
    if not run:
        raise HTTPException(404, "Run not found")
    return run


def approvals_for(db, run):
    if not run.evidence:
        return []
    return list(db.scalars(select(store.Approval.institution).where(
        store.Approval.run_id == run.id, store.Approval.tenant_id == run.tenant_id,
        store.Approval.evidence_hash == digest(run.evidence))))


class WorkspaceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(default="Northstar Consortium", min_length=3, max_length=80)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0", "confidential_execution": "requires institution deployment and secure RNG",
            "demo_source": "generated_public_fixture_not_paysim"}


@app.get("/api/ready")
def ready():
    from sqlalchemy import text
    try:
        with store.ENGINE.connect() as connection:
            connection.execute(text("SELECT 1"))
        if os.environ.get("FRAUDSHIELD_QUEUE") == "redis":
            from redis import Redis
            Redis.from_url(os.environ["REDIS_URL"], socket_timeout=3).ping()
    except Exception:
        raise HTTPException(503, "A required service is unavailable")
    return {"ready": True}


@app.post("/api/demo/session")
def demo_session(body: WorkspaceInput, response: Response):
    if os.environ.get("FRAUDSHIELD_ALLOW_DEMO", "1") != "1":
        raise HTTPException(403, "Demo enrollment disabled")
    with store.session() as db:
        recent = db.scalar(select(func.count()).select_from(store.Tenant).where(store.Tenant.created > time.time() - 3600))
        if recent >= 20:
            raise HTTPException(429, "Demo workspace limit reached; reuse an existing session")
        tenant_id = str(uuid.uuid4())
        db.add(store.Tenant(id=tenant_id, name=body.name, created=time.time()))
        token = store.issue_token(db, tenant_id, "admin")
        for slug, info in INSTITUTIONS.items():
            db.add(store.Institution(id=str(uuid.uuid4()), tenant_id=tenant_id, slug=slug, name=info["name"],
                                     status="DEMO_READY"))
        store.event(db, tenant_id, None, "WORKSPACE_CREATED", {"mode": "public_fixture"})
    response.set_cookie("fs_session", token, httponly=True, samesite="strict", max_age=86400,
                        secure=os.environ.get("FRAUDSHIELD_SECURE_COOKIES") == "1")
    return {"tenant_id": tenant_id, "name": body.name}


@app.post("/api/logout")
def logout(response: Response, user=Depends(identity)):
    with store.session() as db:
        db.get(store.Membership, user["id"]).expires = time.time()
    response.delete_cookie("fs_session")
    return {"logged_out": True}


@app.get("/api/workspace")
def workspace(user=Depends(identity)):
    with store.session() as db:
        tenant = db.get(store.Tenant, user["tenant"])
        institutions = db.scalars(select(store.Institution).where(store.Institution.tenant_id == tenant.id)).all()
        runs = db.scalars(select(store.Run).where(store.Run.tenant_id == tenant.id).order_by(store.Run.created.desc())).all()
        return {"tenant": {"id": tenant.id, "name": tenant.name, "subscription": tenant.subscription},
                "role": user["role"], "institutions": [{"slug": i.slug, "name": i.name, "status": i.status,
                                                       **INSTITUTIONS[i.slug]} for i in institutions],
                "runs": [store.run_view(r) for r in runs], "schema": SCHEMA,
                "public_demo": True, "signing_public_key": public_key(load_key(store.ROOT / "keys" / tenant.id / "coordinator.key"))}


@app.get("/api/reference-benchmark")
def reference_benchmark(user=Depends(identity)):
    path = Path(os.environ.get("FRAUDSHIELD_REFERENCE_BENCHMARK",
                str(Path(__file__).resolve().parents[2] / "benchmark-results" / "research" / "summary.json")))
    if not path.exists():
        return {"source": "not_configured", "results": []}
    report = json.loads(path.read_text())
    if report.get("source") != "generated_public_fixture_not_paysim":
        raise HTTPException(503, "Reference benchmark provenance is not approved")
    return report


@app.post("/api/institutions/{slug}/enrollment")
def enrollment(slug: str, user=Depends(identity)):
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator required")
    with store.session() as db:
        institution = db.scalar(select(store.Institution).where(store.Institution.tenant_id == user["tenant"],
                                                                store.Institution.slug == slug))
        if not institution:
            raise HTTPException(404, "Institution not found")
        token = secrets.token_urlsafe(32)
        institution.enrollment_hash = digest(token.encode())
        institution.enrollment_expires = time.time() + 600
        return {"token": token, "expires_in": 600, "institution": slug,
                "note": "Keep this one-time token with the institution operator"}


class EnrollmentInput(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    public_key: str = Field(min_length=40, max_length=60)


@app.post("/api/connectors/enroll")
def enroll(body: EnrollmentInput):
    import base64
    try:
        if len(base64.b64decode(body.public_key, validate=True)) != 32:
            raise ValueError()
    except ValueError:
        raise HTTPException(422, "Invalid Ed25519 public key")
    with store.session() as db:
        institution = db.scalar(select(store.Institution).where(
            store.Institution.enrollment_hash == digest(body.token.encode()),
            store.Institution.enrollment_expires > time.time()).with_for_update())
        if not institution:
            raise HTTPException(403, "Enrollment token expired or used")
        institution.public_key, institution.status = body.public_key, "ENROLLED"
        institution.enrollment_hash = None
        token = store.issue_token(db, institution.tenant_id, "owner", institution.slug, days=7)
        store.event(db, institution.tenant_id, None, "CONNECTOR_ENROLLED", {"institution": institution.slug})
        return {"token": token, "institution": institution.slug}


def dispatch(run_id):
    if os.environ.get("FRAUDSHIELD_DEMO_INLINE") == "1":
        # Cloud Run's request-based CPU is available for the active request only.
        # This bounded public-fixture mode keeps the demo run inside that request.
        from .worker import execute
        execute(run_id)
    elif os.environ.get("FRAUDSHIELD_QUEUE") == "redis":
        from redis import Redis
        from rq import Queue
        Queue(connection=Redis.from_url(os.environ["REDIS_URL"])).enqueue(
            "fraudshield.worker.execute", run_id, job_id=run_id, job_timeout=3600)
    else:
        log_dir = store.ROOT / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / f"{run_id}.log").open("ab") as log:
            subprocess.Popen([sys.executable, "-m", "fraudshield.worker", run_id], stdout=log, stderr=log,
                             env={**os.environ, "FRAUDSHIELD_HOME": str(store.ROOT),
                                  "FRAUDSHIELD_DATABASE_URL": store.DATABASE_URL},
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)


@app.post("/api/runs", status_code=202)
def create_run(plan: Plan, idempotency_key: str = Header(..., min_length=8, max_length=100), user=Depends(identity)):
    require_write(user)
    if plan.mode != "public_fixture":
        raise HTTPException(422, "Hosted demo only accepts the public fixture. Confidential runs require institution deployment.")
    with store.session() as db:
        existing = db.scalar(select(store.Run).where(store.Run.tenant_id == user["tenant"],
                                                      store.Run.idempotency == idempotency_key))
        if existing:
            if existing.plan_hash != digest(plan.model_dump()):
                raise HTTPException(409, "Idempotency key already used with another plan")
            return store.run_view(existing)
        active = db.scalar(select(func.count()).select_from(store.Run).where(
            store.Run.tenant_id == user["tenant"], store.Run.status.in_(
                ["QUEUED", "PREPARING", "TRAINING", "VALIDATING", "EVALUATING_ATTACKS"])))
        if active:
            raise HTTPException(409, "One active run per workspace; wait or cancel it")
        count = db.scalar(select(func.count()).select_from(store.Run).where(store.Run.tenant_id == user["tenant"]))
        if count >= 20:
            raise HTTPException(429, "Public demo run quota reached")
        run = store.Run(id=str(uuid.uuid4()), tenant_id=user["tenant"], idempotency=idempotency_key,
                        plan_hash=digest(plan.model_dump()), plan=plan.model_dump(), status="QUEUED",
                        stage="Queued for privacy preflight", created=time.time(), updated=time.time(),
                        active_slot=user["tenant"])
        db.add(run)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Another request already reserved this workspace")
        store.event(db, user["tenant"], run.id, "RUN_QUEUED", {"plan_hash": run.plan_hash})
        result = store.run_view(run)
        run_id = run.id
    try:
        dispatch(run_id)
    except Exception:
        store.transition(run_id, "FAILED", "Queue unavailable", error="Could not schedule worker")
        raise HTTPException(503, "Training queue unavailable")
    return result


@app.get("/api/runs/{run_id}")
def get_run(run_id: str, user=Depends(identity)):
    with store.session() as db:
        run = own_run(db, run_id, user)
        return {**store.run_view(run, detail=True), "approvals": approvals_for(db, run)}


@app.post("/api/runs/{run_id}/cancel")
def cancel(run_id: str, user=Depends(identity)):
    require_write(user)
    with store.session() as db:
        run = own_run(db, run_id, user)
        if run.status in ("RELEASED", "FAILED", "ABORTED", "BUDGET_BLOCKED", "EVIDENCE_READY"):
            raise HTTPException(409, "Run is no longer active")
        run.cancelled = True
        store.event(db, user["tenant"], run_id, "CANCELLATION_REQUESTED", {})
        return {"status": "cancellation_requested", "privacy_refund": False}


@app.get("/api/runs/{run_id}/events")
async def events(run_id: str, request: Request, user=Depends(identity)):
    with store.session() as db:
        own_run(db, run_id, user)
    async def stream():
        last = 0
        while not await request.is_disconnected():
            with store.session() as db:
                rows = db.scalars(select(store.Event).where(store.Event.tenant_id == user["tenant"],
                    store.Event.run_id == run_id, store.Event.id > last).order_by(store.Event.id)).all()
                for row in rows:
                    last = row.id
                    yield f"id: {row.id}\ndata: {json.dumps({'kind': row.kind, 'payload': row.payload, 'created': row.created})}\n\n"
                run = own_run(db, run_id, user)
                if run.status in ("EVIDENCE_READY", "FAILED", "ABORTED", "BUDGET_BLOCKED", "RELEASED"):
                    return
            yield ": heartbeat\n\n"
            await asyncio.sleep(2)
    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/runs/{run_id}/approve/{institution}")
def approve(run_id: str, institution: str, user=Depends(identity)):
    if institution not in INSTITUTIONS:
        raise HTTPException(404, "Institution not found")
    with store.session() as db:
        run = own_run(db, run_id, user)
        if not run.evidence or run.status != "EVIDENCE_READY":
            raise HTTPException(409, "Candidate is not ready for approval")
        is_demo_admin = user["role"] == "admin" and run.plan["mode"] == "public_fixture"
        if not is_demo_admin and not (user["role"] == "owner" and user["institution"] == institution):
            raise HTTPException(403, "Matching institution owner required")
        evidence_hash = digest(run.evidence)
        present = db.scalar(select(store.Approval).where(store.Approval.run_id == run_id,
                            store.Approval.institution == institution, store.Approval.evidence_hash == evidence_hash))
        if not present:
            db.add(store.Approval(id=str(uuid.uuid4()), tenant_id=user["tenant"], run_id=run_id,
                institution=institution, evidence_hash=evidence_hash, actor=user["id"], created=time.time()))
            db.flush()
        approved = approvals_for(db, run)
        run.decision = evaluate_gate(run.evidence, Plan.model_validate(run.plan), approved)
        store.event(db, user["tenant"], run_id, "OWNER_APPROVAL", {
            "institution": institution, "evidence_hash": evidence_hash, "simulated_owner": is_demo_admin})
        return {"decision": run.decision, "approvals": approved, "simulated_owner": is_demo_admin}


@app.post("/api/runs/{run_id}/release")
def release(run_id: str, user=Depends(identity)):
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator required")
    with store.session() as db:
        run = own_run(db, run_id, user)
        if run.status != "EVIDENCE_READY" or not run.evidence:
            raise HTTPException(409, "No release-ready candidate")
        directory = store.ROOT / "artifacts" / user["tenant"] / run_id
        if file_hash(directory / "model.safetensors") != run.evidence["model_hash"]:
            raise HTTPException(409, "Model integrity failure")
        key = load_key(store.ROOT / "keys" / user["tenant"] / "coordinator.key")
        try:
            manifest = release_manifest(directory, run.evidence, Plan.model_validate(run.plan), approvals_for(db, run), key)
        except ValueError as error:
            raise HTTPException(409, str(error))
        try:
            mirror_release(directory, public_key(key), user["tenant"], run_id)
        except Exception:
            raise HTTPException(503, "Configured archive storage is unavailable; release remains pending")
        run.status, run.stage, run.updated = "RELEASED", "Approved artifact available", time.time()
        store.event(db, user["tenant"], run_id, "MODEL_RELEASED", {"manifest_hash": digest(manifest)})
        return manifest


@app.get("/api/runs/{run_id}/bundle")
def bundle(run_id: str, user=Depends(identity)):
    with store.session() as db:
        run = own_run(db, run_id, user)
        if run.status != "RELEASED":
            raise HTTPException(409, "Model has not passed release")
    directory = store.ROOT / "artifacts" / user["tenant"] / run_id
    key = load_key(store.ROOT / "keys" / user["tenant"] / "coordinator.key")
    archive = archive_bundle(directory, public_key(key))
    return Response(archive, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="fraudshield-{run_id[:8]}.zip"'})


@app.get("/api/usage")
def usage(user=Depends(identity)):
    with store.session() as db:
        runs = db.scalars(select(store.Run).where(store.Run.tenant_id == user["tenant"])).all()
        return {"plan": "Pilot · sandbox", "price_hypothesis_usd": 499, "institutions": 3,
                "compute_seconds": sum(r.duration_seconds or 0 for r in runs),
                "wire_bytes": sum(r.wire_bytes or 0 for r in runs), "runs": len(runs), "run_quota": 20,
                "billing_configured": bool(os.environ.get("STRIPE_SECRET_KEY", "").startswith("sk_test_")
                                           and os.environ.get("STRIPE_PRICE_ID") and os.environ.get("FRAUDSHIELD_PUBLIC_URL")),
                "actual_revenue": None, "metering": "Compute usage; no transaction-count billing"}


@app.post("/api/billing/checkout")
def checkout(user=Depends(identity)):
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator required")
    key, price = os.environ.get("STRIPE_SECRET_KEY"), os.environ.get("STRIPE_PRICE_ID")
    if not key or not key.startswith("sk_test_") or not price:
        raise HTTPException(503, "Configure Stripe test-mode credentials and price to enable sandbox checkout")
    import stripe
    stripe.api_key = key
    origin = os.environ["FRAUDSHIELD_PUBLIC_URL"]
    checkout = stripe.checkout.Session.create(mode="subscription", line_items=[{"price": price, "quantity": 1}],
        client_reference_id=user["tenant"], success_url=origin + "/?checkout=success", cancel_url=origin + "/?checkout=cancelled",
        metadata={"tenant_id": user["tenant"]})
    return {"url": checkout.url}


@app.post("/api/billing/webhook")
async def webhook(request: Request, stripe_signature: str = Header(...)):
    import stripe
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(503, "Billing webhook not configured")
    try:
        billing_event = stripe.Webhook.construct_event(await request.body(), stripe_signature, secret)
    except Exception:
        raise HTTPException(400, "Invalid webhook signature")
    if billing_event.get("livemode"):
        raise HTTPException(400, "Only sandbox events accepted")
    if billing_event["type"] == "checkout.session.completed":
        obj = billing_event["data"]["object"]
        tenant_id = obj.get("client_reference_id")
        with store.session() as db:
            if db.get(store.BillingEvent, billing_event["id"]):
                return {"duplicate": True}
            tenant = db.get(store.Tenant, tenant_id)
            if not tenant:
                raise HTTPException(400, "Unknown billing tenant")
            db.add(store.BillingEvent(id=billing_event["id"], tenant_id=tenant_id,
                                     kind=billing_event["type"], created=time.time()))
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                return {"duplicate": True}
            tenant.subscription = "sandbox_subscribed"
    return {"received": True}


dist = Path(os.environ.get("FRAUDSHIELD_WEB_DIST", str(Path(__file__).resolve().parents[2] / "apps" / "web" / "dist")))
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="web")
