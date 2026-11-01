import csv
import io
import os
import tempfile

# isolated DB per test run, no integrations, no LLM
_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_db.name}"
for var in ("OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "SERVICENOW_INSTANCE", "POWER_AUTOMATE_WEBHOOK_URL"):
    os.environ.pop(var, None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/healthz").json()["status"] == "ok"
    ready = client.get("/readyz").json()
    assert ready["status"] == "ready" and ready["engine"] == "rules"


def test_ui_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "ServiceDesk Copilot" in r.text


def test_triage_dry_run_does_not_store(client):
    before = client.get("/api/stats").json()["total"]
    r = client.post("/api/triage", json={"message": "My wallbox is not charging"})
    assert r.status_code == 200 and r.json()["category"] == "charging_ev"
    assert client.get("/api/stats").json()["total"] == before


def test_ticket_lifecycle(client):
    r = client.post(
        "/api/tickets",
        json={
            "message": "My car broke down and won't start, I'm stranded on the highway",
            "customer_name": "Max",
            "customer_email": "max@example.com",
            "channel": "phone",
        },
    )
    assert r.status_code == 201
    t = r.json()
    assert t["reference"].startswith("SDC-")
    assert t["urgency"] == "high" and t["category"] == "roadside_assistance"
    assert "Max" in t["suggested_reply"] and t["reference"] in t["suggested_reply"]

    ref = t["reference"]
    assert client.get(f"/api/tickets/{ref}").json()["status"] == "new"
    assert client.patch(f"/api/tickets/{ref}", json={"status": "resolved"}).json()["status"] == "resolved"
    assert client.get("/api/tickets", params={"status": "resolved"}).json()[0]["reference"] == ref


def test_validation(client):
    assert client.post("/api/tickets", json={"message": "hi"}).status_code == 422
    assert client.post("/api/tickets", json={"message": "hello world", "customer_email": "nope"}).status_code == 422
    assert client.patch("/api/tickets/SDC-999999", json={"status": "resolved"}).status_code == 404


def test_stats_and_csv(client):
    client.post("/api/tickets", json={"message": "Rechnung doppelt abgebucht, bitte Erstattung"})
    s = client.get("/api/stats").json()
    assert s["total"] >= 2 and s["by_language"].get("de", 0) >= 1
    rows = list(csv.DictReader(io.StringIO(client.get("/api/export.csv").text)))
    assert len(rows) == s["total"]
    assert rows[0]["reference"].startswith("SDC-")


def test_contact_details_and_lookup_by_number(client):
    t = client.post(
        "/api/tickets",
        json={
            "message": "My car broke down and won't start",
            "customer_name": "Siya",
            "customer_email": "siya@example.com",
            "customer_phone": "+49 30 1234567",
        },
    ).json()
    assert t["customer_phone"] == "+49 30 1234567"
    number = int(t["reference"].split("-")[1])
    for ref in (t["reference"], t["reference"].lower(), str(number), f"SDC{number}"):
        got = client.get(f"/api/tickets/{ref}")
        assert got.status_code == 200, ref
        assert got.json()["customer_email"] == "siya@example.com"
    assert client.get("/api/tickets/abc").status_code == 404
    assert client.get("/api/tickets/999999").status_code == 404


def test_invalid_phone_rejected(client):
    r = client.post("/api/tickets", json={"message": "hello world", "customer_phone": "call me maybe"})
    assert r.status_code == 422
