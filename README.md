# ServiceDesk Copilot

![ci](https://github.com/Karan6528/servicedesk-copilot/actions/workflows/ci.yml/badge.svg)

**AI triage for customer-service requests in German and English.** A request comes in by web, e-mail, phone or chat. The service decides *what it is about* and *how urgent it is*, explains why, and drafts a reply in the customer's language. Urgent cases go straight to **ServiceNow** and to the team through **Power Automate** (Teams, Outlook, Excel). A **Power BI** report shows the queue.

Runs locally, in **Docker**, on **Kubernetes** and on **Microsoft Azure**. Planned and documented in **Jira** and **Confluence**.

![Web UI](docs/images/ui.png)

## Why I built this

In my data science internship I built RAG chatbots. I learned that the useful part of AI in a service team is often not a chatbot. It is the boring first step: reading every incoming message and putting it in the right queue with the right priority. That step has to be fast and explainable, and it has to keep working when an external API is down. So this project uses a transparent rule engine that always works, an optional LLM on top, and integrations that can fail without taking ticket creation down with them.

I also wanted one project where I use the tools an enterprise IT team actually works with, end to end: containers, Kubernetes, Azure, ITSM, low-code automation and agile tooling.

## Architecture

![Architecture](docs/images/architecture.png)

| Layer | Technology |
|---|---|
| API + UI | Python 3.12, FastAPI, SQLAlchemy 2, vanilla JS |
| AI | EN/DE rule engine (explainable) + optional OpenAI / Azure OpenAI with fallback |
| Data | PostgreSQL (Docker/K8s), SQLite (local) |
| Containers | Docker multi-stage, non-root, healthcheck · docker-compose |
| Orchestration | Kubernetes: Deployment, probes, HPA, Postgres StatefulSet, Kustomize |
| Cloud | Azure Container Apps + Azure Container Registry |
| CI/CD | GitHub Actions: lint → tests → image + compose smoke test → deploy to kind → (manual) Azure |
| ITSM | ServiceNow Table API (Incidents) |
| Low-code | Power Automate (Teams / Outlook / Excel), Power BI |
| Agile | Jira backlog (CSV import), Confluence pages |

## Quick start

### 1. Local (Python)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
# open http://localhost:8000   API docs: http://localhost:8000/docs
python scripts/seed_demo.py    # 12 demo requests (in a second terminal)
```

### 2. Docker (API + PostgreSQL)

```bash
docker compose up --build
```

### 3. Kubernetes (local with kind)

```bash
kind create cluster --name servicedesk --config k8s/kind-config.yaml
docker build -t servicedesk-copilot:local .
kind load docker-image servicedesk-copilot:local --name servicedesk

kubectl apply -f k8s/namespace.yaml
kubectl -n servicedesk create secret generic servicedesk-secrets \
  --from-literal=POSTGRES_PASSWORD=local-pass \
  --from-literal=DATABASE_URL=postgresql+psycopg://servicedesk:local-pass@postgres:5432/servicedesk
kubectl apply -k k8s/
kubectl -n servicedesk rollout status deployment/servicedesk-api
kubectl -n servicedesk port-forward svc/servicedesk-api 8080:80     # http://localhost:8080
```

### 4. Azure, ServiceNow, Power Platform, Jira

| Guide | What you get |
|---|---|
| [docs/azure.md](docs/azure.md) | Public HTTPS URL on Azure Container Apps, CD from GitHub Actions |
| [docs/servicenow.md](docs/servicenow.md) | Urgent tickets become ServiceNow incidents |
| [docs/power-platform/README.md](docs/power-platform/README.md) | Teams / Outlook / Excel alerts, Power BI report |
| [docs/jira/README.md](docs/jira/README.md) | Scrum project with 15 imported backlog items, GitHub integration |
| [docs/confluence/](docs/confluence) | Architecture, runbook, decision log |

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/tickets` | Create a ticket: triage, save, suggested reply, escalation |
| POST | `/api/triage` | Dry run: classify without saving |
| GET | `/api/tickets?urgency=&status=&category=` | Queue with filters |
| GET / PATCH | `/api/tickets/{reference}` | Read / change status |
| GET | `/api/stats` | Counts by category, urgency, status, language |
| GET | `/api/export.csv` | Flat export for Power BI |
| GET | `/healthz`, `/readyz` | Liveness / readiness (incl. active integrations) |

Example:

```bash
curl -X POST localhost:8000/api/tickets -H 'content-type: application/json' \
  -d '{"message":"Meine Wallbox lädt nicht mehr, das Ladekabel blinkt rot.","customer_name":"Anna"}'
```
```json
{ "reference": "SDC-000014", "language": "de", "category": "charging_ev", "urgency": "normal",
  "confidence": 1.0, "engine": "rules", "suggested_reply": "Hallo Anna,\n\nvielen Dank für Ihre Anfrage zum Laden. ..." }
```

## Configuration

Everything is optional. Without any variables the app runs with SQLite and the rule engine. See [.env.example](.env.example).

| Variable | Effect |
|---|---|
| `DATABASE_URL` | e.g. `postgresql+psycopg://user:pass@host:5432/db` |
| `OPENAI_API_KEY` or `AZURE_OPENAI_*` | Use an LLM for triage (falls back to rules on any error) |
| `SERVICENOW_INSTANCE/USER/PASSWORD` | Create incidents for critical/high tickets |
| `POWER_AUTOMATE_WEBHOOK_URL` | Call the alert flow for critical/high tickets |

## How triage works

- **Category:** weighted EN/DE keywords per category. The highest score wins, and confidence = winner's share of all matched weight. On a tie, roadside assistance wins (a stranded customer comes first).
- **Urgency:** ordered rules. *Critical* = danger to people (accident, smoke, brake failure). *High* = car can't be driven, or legal threat. *Low* = "no rush", opening hours.
- **Language:** stop-words, umlauts and German domain words, so even "Unfall! Rauch!" is detected as German.
- **Explainable:** the response lists the matched keywords (`"matched": ["wallbox", "laden"]`).
- **LLM safety rule:** if an LLM is configured, it can refine the category but **never lower a critical urgency** found by the rules.

## Tests

```bash
pytest -q          # 31 tests: triage, API, integrations (mocked), LLM fallback
ruff check app tests
```

CI also builds the Docker image, runs a smoke test against Postgres via docker-compose, and deploys to a real Kubernetes cluster (kind) inside GitHub Actions.

## Limitations and next steps

- Rule engine: unusual wording can land in "general inquiry". Next: collect agent corrections and train a small classifier on them.
- Integrations are fire-and-forget. Next: Azure Service Bus queue with retries.
- No authentication on the demo UI. Next: Microsoft Entra ID login.

## Licence

MIT
