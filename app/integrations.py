"""Hand-offs to other systems for urgent tickets.

- ServiceNow: create an Incident through the Table API.
- Power Automate: POST the ticket to a flow's HTTP trigger (the flow then
  posts to Teams, sends an Outlook mail and adds an Excel row).

Both are optional and skip quietly when not configured.
"""

from __future__ import annotations

import logging

import httpx

from .config import Settings
from .db import SessionLocal, Ticket, iso_utc

log = logging.getLogger(__name__)

# ServiceNow uses 1 = high, 2 = medium, 3 = low for urgency and impact
SN_URGENCY = {"critical": "1", "high": "1", "normal": "2", "low": "3"}
SN_IMPACT = {"critical": "1", "high": "2", "normal": "3", "low": "3"}


def ticket_payload(t: Ticket) -> dict:
    return {
        "reference": t.reference,
        "created_at": iso_utc(t.created_at),
        "customer_name": t.customer_name,
        "customer_email": t.customer_email,
        "customer_phone": t.customer_phone,
        "channel": t.channel,
        "message": t.message,
        "language": t.language,
        "category": t.category,
        "urgency": t.urgency,
        "confidence": t.confidence,
        "suggested_reply": t.suggested_reply,
        "status": t.status,
        "servicenow_number": t.servicenow_number,
    }


def create_servicenow_incident(settings: Settings, t: Ticket) -> str | None:
    if not settings.servicenow_enabled:
        return None
    base = settings.servicenow_instance.rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = f"https://{base}"
    url = f"{base}/api/now/table/incident"
    body = {
        "short_description": f"[{t.urgency.upper()}] {t.category} – {t.reference}",
        "description": (
            f"Customer: {t.customer_name or '-'} <{t.customer_email or '-'}> phone: {t.customer_phone or '-'}\n\n{t.message}"
        ),
        "urgency": SN_URGENCY[t.urgency],
        "impact": SN_IMPACT[t.urgency],
        "category": "inquiry",
        "caller_id": t.customer_email or "",
        "correlation_id": t.reference,
    }
    try:
        resp = httpx.post(
            url,
            json=body,
            auth=(settings.servicenow_user, settings.servicenow_password),
            headers={"Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["result"]["number"]
    except Exception as exc:  # noqa: BLE001
        log.warning("ServiceNow incident failed for %s: %s", t.reference, exc)
        return None


def notify_power_automate(settings: Settings, t: Ticket) -> bool:
    if not settings.power_automate_enabled:
        return False
    try:
        resp = httpx.post(settings.power_automate_webhook_url, json=ticket_payload(t), timeout=15)
        resp.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Power Automate webhook failed for %s: %s", t.reference, exc)
        return False


def escalate(settings: Settings, ticket_id: int) -> None:
    """Runs as a background task after the API has already answered."""
    with SessionLocal() as session:
        t = session.get(Ticket, ticket_id)
        if t is None or t.urgency not in settings.escalate_urgencies:
            return
        number = create_servicenow_incident(settings, t)
        if number:
            t.servicenow_number = number
        t.power_automate_notified = notify_power_automate(settings, t)
        session.commit()
