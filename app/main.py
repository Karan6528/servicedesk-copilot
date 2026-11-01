"""ServiceDesk Copilot – FastAPI application."""

from __future__ import annotations

import csv
import io
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from . import __version__
from .config import get_settings
from .db import Ticket, engine, get_session, init_db, iso_utc
from .integrations import escalate, ticket_payload
from .llm import llm_classify
from .triage import CATEGORY_LABELS, TriageResult, classify, draft_reply

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()
STATIC = Path(__file__).parent / "static"

Urgency = Literal["critical", "high", "normal", "low"]
Category = Literal["roadside_assistance", "workshop_repair", "charging_ev", "billing_invoice", "complaint", "general_inquiry"]
Status = Literal["new", "in_progress", "waiting_for_customer", "resolved"]


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="ServiceDesk Copilot",
    version=__version__,
    description="AI-assisted triage for customer-service requests (EN/DE).",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


# ------------------------------------------------------------------ schemas
class TicketIn(BaseModel):
    message: str = Field(min_length=5, max_length=5000)
    customer_name: str | None = Field(default=None, max_length=120)
    customer_email: EmailStr | None = None
    customer_phone: str | None = Field(default=None, max_length=40, pattern=r"^\+?[0-9 ()/-]{5,40}$")
    channel: Literal["web", "email", "phone", "chat"] = "web"


class TriageOut(BaseModel):
    language: str
    category: str
    category_label: str
    urgency: Urgency
    confidence: float
    engine: str
    matched: list[str]
    entities: dict[str, str]


class TicketOut(BaseModel):
    id: int
    reference: str
    created_at: str
    customer_name: str | None
    customer_email: str | None
    customer_phone: str | None
    channel: str
    message: str
    language: str
    category: str
    category_label: str
    urgency: str
    confidence: float
    engine: str
    suggested_reply: str
    status: str
    servicenow_number: str | None
    power_automate_notified: bool

    @classmethod
    def of(cls, t: Ticket) -> TicketOut:
        return cls(
            id=t.id,
            reference=t.reference,
            created_at=iso_utc(t.created_at),
            customer_name=t.customer_name,
            customer_email=t.customer_email,
            customer_phone=t.customer_phone,
            channel=t.channel,
            message=t.message,
            language=t.language,
            category=t.category,
            category_label=CATEGORY_LABELS.get(t.category, t.category),
            urgency=t.urgency,
            confidence=t.confidence,
            engine=t.engine,
            suggested_reply=t.suggested_reply,
            status=t.status,
            servicenow_number=t.servicenow_number,
            power_automate_notified=t.power_automate_notified,
        )


class StatusUpdate(BaseModel):
    status: Status


# ------------------------------------------------------------------ helpers
def run_triage(message: str) -> TriageResult:
    rules = classify(message)
    llm = llm_classify(settings, message)
    if llm is None:
        return rules
    # keep the rule engine's entity extraction; never let the LLM *lower* a
    # safety-critical urgency the rules detected
    llm.entities = rules.entities
    llm.matched = rules.matched
    if rules.urgency == "critical":
        llm.urgency = "critical"
    return llm


def triage_out(r: TriageResult) -> TriageOut:
    return TriageOut(
        language=r.language,
        category=r.category,
        category_label=r.category_label,
        urgency=r.urgency,
        confidence=r.confidence,
        engine=r.engine,
        matched=r.matched,
        entities=r.entities,
    )


# ------------------------------------------------------------------ routes
@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/healthz", tags=["ops"])
def healthz() -> dict:
    """Liveness probe: the process is up."""
    return {"status": "ok", "version": __version__}


@app.get("/readyz", tags=["ops"])
def readyz() -> dict:
    """Readiness probe: the database answers."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"database not ready: {exc}") from exc
    return {
        "status": "ready",
        "environment": settings.environment,
        "engine": "llm" if settings.llm_enabled else "rules",
        "integrations": {
            "servicenow": settings.servicenow_enabled,
            "power_automate": settings.power_automate_enabled,
        },
    }


@app.post("/api/triage", response_model=TriageOut, tags=["triage"])
def triage_only(payload: TicketIn) -> TriageOut:
    """Classify a message without saving it (dry run)."""
    return triage_out(run_triage(payload.message))


@app.post("/api/tickets", response_model=TicketOut, status_code=201, tags=["tickets"])
def create_ticket(payload: TicketIn, background: BackgroundTasks, session: Session = Depends(get_session)) -> TicketOut:
    r = run_triage(payload.message)
    t = Ticket(
        customer_name=payload.customer_name,
        customer_email=payload.customer_email,
        customer_phone=payload.customer_phone,
        channel=payload.channel,
        message=payload.message,
        language=r.language,
        category=r.category,
        urgency=r.urgency,
        confidence=r.confidence,
        engine=r.engine,
        matched=", ".join(r.matched),
    )
    session.add(t)
    session.flush()  # get the id
    t.reference = f"SDC-{t.id:06d}"
    t.suggested_reply = draft_reply(r, payload.customer_name, t.reference)
    session.commit()
    if t.urgency in settings.escalate_urgencies:
        background.add_task(escalate, settings, t.id)
    return TicketOut.of(t)


@app.get("/api/tickets", response_model=list[TicketOut], tags=["tickets"])
def list_tickets(
    category: Category | None = None,
    urgency: Urgency | None = None,
    status: Status | None = None,
    limit: int = Query(50, ge=1, le=500),
    session: Session = Depends(get_session),
) -> list[TicketOut]:
    q = select(Ticket).order_by(Ticket.id.desc()).limit(limit)
    if category:
        q = q.where(Ticket.category == category)
    if urgency:
        q = q.where(Ticket.urgency == urgency)
    if status:
        q = q.where(Ticket.status == status)
    return [TicketOut.of(t) for t in session.scalars(q)]


def normalise_reference(raw: str) -> str:
    """Accept 'SDC-000002', 'sdc-2', 'SDC2' or just '2'."""
    digits = re.sub(r"\D", "", raw)
    if not digits:
        raise HTTPException(404, "ticket not found")
    return f"SDC-{int(digits):06d}"


@app.get("/api/tickets/{reference}", response_model=TicketOut, tags=["tickets"])
def get_ticket(reference: str, session: Session = Depends(get_session)) -> TicketOut:
    t = session.scalar(select(Ticket).where(Ticket.reference == normalise_reference(reference)))
    if t is None:
        raise HTTPException(404, "ticket not found")
    return TicketOut.of(t)


@app.patch("/api/tickets/{reference}", response_model=TicketOut, tags=["tickets"])
def update_status(reference: str, upd: StatusUpdate, session: Session = Depends(get_session)) -> TicketOut:
    t = session.scalar(select(Ticket).where(Ticket.reference == normalise_reference(reference)))
    if t is None:
        raise HTTPException(404, "ticket not found")
    t.status = upd.status
    session.commit()
    return TicketOut.of(t)


@app.get("/api/stats", tags=["reporting"])
def stats(session: Session = Depends(get_session)) -> dict:
    def grouped(col):
        return {k: v for k, v in session.execute(select(col, func.count()).group_by(col))}

    return {
        "total": session.scalar(select(func.count()).select_from(Ticket)) or 0,
        "by_category": grouped(Ticket.category),
        "by_urgency": grouped(Ticket.urgency),
        "by_status": grouped(Ticket.status),
        "by_language": grouped(Ticket.language),
    }


@app.get("/api/export.csv", response_class=PlainTextResponse, tags=["reporting"])
def export_csv(session: Session = Depends(get_session)):
    """Flat export for Power BI (Get data → Web → this URL)."""
    buf = io.StringIO()
    fields = list(ticket_payload(Ticket(created_at=None)).keys())
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    for t in session.scalars(select(Ticket).order_by(Ticket.id)):
        w.writerow(ticket_payload(t))
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tickets.csv"},
    )
