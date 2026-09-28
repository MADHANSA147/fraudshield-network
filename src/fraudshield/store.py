import os
import secrets
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import JSON, Boolean, Column, Float, Integer, String, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from .security import digest

ROOT = Path(os.environ.get("FRAUDSHIELD_HOME", "var")).resolve()
DATABASE_URL = os.environ.get("FRAUDSHIELD_DATABASE_URL", f"sqlite:///{ROOT / 'control.db'}")


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created = Column(Float, nullable=False)
    subscription = Column(String, default="sandbox_pilot")


class Membership(Base):
    __tablename__ = "memberships"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True, nullable=False)
    token_hash = Column(String, unique=True, nullable=False)
    role = Column(String, nullable=False)
    institution = Column(String, nullable=True)
    expires = Column(Float, nullable=False)


class Institution(Base):
    __tablename__ = "institutions"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True, nullable=False)
    slug = Column(String, nullable=False)
    name = Column(String, nullable=False)
    status = Column(String, default="NOT_ENROLLED")
    enrollment_hash = Column(String, nullable=True)
    enrollment_expires = Column(Float, nullable=True)
    public_key = Column(String, nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "slug"),)


class Run(Base):
    __tablename__ = "runs"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True, nullable=False)
    idempotency = Column(String, nullable=False)
    plan_hash = Column(String, nullable=False)
    plan = Column(JSON, nullable=False)
    status = Column(String, nullable=False)
    stage = Column(String, default="Waiting for worker")
    round = Column(Integer, default=0)
    created = Column(Float, nullable=False)
    updated = Column(Float, nullable=False)
    cancelled = Column(Boolean, default=False)
    evidence = Column(JSON, nullable=True)
    decision = Column(JSON, nullable=True)
    error = Column(String, nullable=True)
    duration_seconds = Column(Float, default=0)
    wire_bytes = Column(Integer, default=0)
    active_slot = Column(String, unique=True, nullable=True)
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency"),)


class Event(Base):
    __tablename__ = "audit_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, nullable=False, index=True)
    run_id = Column(String, nullable=True, index=True)
    kind = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    created = Column(Float, nullable=False)


class Approval(Base):
    __tablename__ = "approvals"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False)
    run_id = Column(String, nullable=False)
    institution = Column(String, nullable=False)
    evidence_hash = Column(String, nullable=False)
    actor = Column(String, nullable=False)
    created = Column(Float, nullable=False)
    __table_args__ = (UniqueConstraint("run_id", "institution", "evidence_hash"),)


class BillingEvent(Base):
    __tablename__ = "billing_events"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False)
    kind = Column(String, nullable=False)
    created = Column(Float, nullable=False)


def engine():
    ROOT.mkdir(parents=True, exist_ok=True)
    opts = {"connect_args": {"check_same_thread": False, "timeout": 30}} if DATABASE_URL.startswith("sqlite") else {}
    return create_engine(DATABASE_URL, **opts)


ENGINE = engine()


def init():
    Base.metadata.create_all(ENGINE)


@contextmanager
def session():
    with Session(ENGINE, expire_on_commit=False) as db:
        yield db
        db.commit()


def issue_token(db, tenant_id, role, institution=None, days=1):
    token = secrets.token_urlsafe(32)
    db.add(Membership(id=str(uuid.uuid4()), tenant_id=tenant_id, token_hash=digest(token.encode()),
                      role=role, institution=institution, expires=time.time() + days * 86400))
    return token


def event(db, tenant, run_id, kind, payload):
    db.add(Event(tenant_id=tenant, run_id=run_id, kind=kind, payload=payload, created=time.time()))


def transition(run_id, status, stage, **changes):
    with session() as db:
        run = db.get(Run, run_id)
        if run is None:
            raise ValueError("Run not found")
        run.status, run.stage, run.updated = status, stage, time.time()
        if status in ("FAILED", "ABORTED", "BUDGET_BLOCKED", "EVIDENCE_READY", "RELEASED"):
            run.active_slot = None
        for name, value in changes.items():
            setattr(run, name, value)
        event(db, run.tenant_id, run_id, status, {"stage": stage, **{k: v for k, v in changes.items()
                                                                  if k in ("round", "wire_bytes")}})


def run_view(run, detail=False):
    result = {k: getattr(run, k) for k in ("id", "status", "stage", "round", "created", "updated",
              "plan", "decision", "error", "duration_seconds", "wire_bytes")}
    if detail:
        result["evidence"] = run.evidence
    if run.evidence:
        result["comparison"] = {
            "metrics": run.evidence.get("public_evaluation", {}).get("aggregate"),
            "epsilon": max((r["payload"]["epsilon"] for r in run.evidence.get("receipts", [])), default=None),
            "source": run.evidence.get("source"),
        }
    return result
