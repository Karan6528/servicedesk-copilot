from dataclasses import replace

import httpx

from app import integrations
from app.config import Settings
from app.db import Ticket


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return self

    def json(self):
        return self._data


def make_ticket(urgency="critical"):
    return Ticket(
        id=1,
        reference="SDC-000001",
        customer_name="Lea",
        customer_email="lea@example.com",
        channel="phone",
        message="Unfall, Rauch!",
        language="de",
        category="roadside_assistance",
        urgency=urgency,
        confidence=0.9,
        suggested_reply="...",
        status="new",
    )


def test_servicenow_incident_payload(monkeypatch):
    calls = []

    def fake_post(url, **kw):
        calls.append((url, kw))
        return FakeResponse({"result": {"number": "INC0010001"}})

    monkeypatch.setattr(httpx, "post", fake_post)
    s = replace(Settings(), servicenow_instance="dev123.service-now.com", servicenow_user="admin", servicenow_password="pw")
    assert integrations.create_servicenow_incident(s, make_ticket()) == "INC0010001"
    url, kw = calls[0]
    assert url == "https://dev123.service-now.com/api/now/table/incident"
    assert kw["json"]["urgency"] == "1" and kw["json"]["impact"] == "1"
    assert kw["json"]["correlation_id"] == "SDC-000001"
    assert kw["auth"] == ("admin", "pw")


def test_power_automate_posts_ticket(monkeypatch):
    sent = {}
    monkeypatch.setattr(httpx, "post", lambda url, **kw: sent.update(url=url, **kw) or FakeResponse({}))
    s = replace(Settings(), power_automate_webhook_url="https://prod-00.westeurope.logic.azure.com/flow")
    assert integrations.notify_power_automate(s, make_ticket()) is True
    assert sent["json"]["reference"] == "SDC-000001" and sent["json"]["urgency"] == "critical"


def test_integrations_off_by_default(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no call expected")))
    s = replace(Settings(), servicenow_instance="", power_automate_webhook_url="")
    assert integrations.create_servicenow_incident(s, make_ticket()) is None
    assert integrations.notify_power_automate(s, make_ticket()) is False


def test_failure_is_swallowed(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "post", boom)
    s = replace(Settings(), power_automate_webhook_url="https://x")
    assert integrations.notify_power_automate(s, make_ticket()) is False
