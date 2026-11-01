# ServiceDesk Copilot

![ci](https://github.com/Karan6528/servicedesk-copilot/actions/workflows/ci.yml/badge.svg)

A small tool that reads customer-service requests (in German or English), figures out what they're about and how urgent they are, and writes a first reply. If something is really urgent, like an accident or a car that won't start on the motorway, it opens a ServiceNow incident and pings the team through Power Automate.

This is what it looks like running on my laptop with about 30 demo tickets:

![ServiceDesk Copilot running locally](docs/images/queue-local.png)

Clicking a ticket (or typing its number in the search box) opens the details, with the customer's contact info and buttons to reply by e-mail, call them, or copy the suggested reply:

![Ticket details](docs/images/details.png)

## Why I built this

During my internship at ScikIQ I built RAG chatbots. What I noticed there: in a real service team, the chatbot is often not the part that saves the most time. The boring first step does. Someone has to read every message, decide "this is a billing question" or "this person is stuck on the Autobahn", and put it in the right queue. That decision should be fast, it should be easy to explain, and it should still work when some external API is down.

So I tried to build exactly that, and I used the project to learn the tools that enterprise IT teams actually use around such a service: Docker, Kubernetes, Azure, ServiceNow, Power Automate, Power BI, Jira and Confluence.

## How the triage works

I started with simple keyword rules instead of an LLM. Each category (roadside assistance, workshop, charging/EV, billing, complaint, general question) has a list of English and German keywords with weights. The category with the highest score wins, and the confidence is its share of all the points.

Urgency is separate:

- **critical**: someone could be in danger (accident, smoke, brakes failed)
- **high**: the car can't be driven, or the customer threatens a lawyer
- **low**: "no rush", opening hours
- everything else is **normal**

Every result shows which words decided it ("Why: autobahn, unfall, rauch"), so an agent can see immediately whether to trust it.

If you set an OpenAI or Azure OpenAI key, the app asks the model too. But the rules always run, and I added one hard rule: the LLM is never allowed to lower an urgency the rules marked as critical. If the LLM call fails or returns nonsense, the app just uses the rule result.

Testing with demo data also showed me where the rules were weak. For example, "Ich habe noch keine Gutschrift für die stornierte Reparatur erhalten" first landed in Workshop because "Reparatur" scored as high as "Gutschrift". I added cancellation words to the billing list and a test for that sentence. Most fixes went like this: find a wrong case, fix the rule, add a test.

## What's in the project

![Architecture](docs/images/architecture.png)

- **App:** Python 3.12, FastAPI, SQLAlchemy. The UI is one plain HTML file with a bit of JavaScript, no framework.
- **Database:** SQLite when you run it locally, PostgreSQL in Docker and Kubernetes.
- **Docker:** multi-stage image, runs as a non-root user, has a health check. `docker compose up` starts the app plus Postgres.
- **Kubernetes:** Deployment with health checks and autoscaling (2–5 pods), Postgres as a StatefulSet, secrets kept out of git.
- **CI (GitHub Actions):** on every push it lints, runs the tests, builds the image, starts it with Postgres for a quick check, and then deploys everything to a temporary Kubernetes cluster (kind) to make sure the manifests really work.
- **Azure:** a workflow that deploys to Azure Container Apps. The steps are in [docs/azure.md](docs/azure.md).
- **ServiceNow:** urgent tickets become incidents through the Table API ([docs/servicenow.md](docs/servicenow.md)).
- **Power Automate / Power BI:** a flow that posts urgent tickets to Teams, sends an e-mail for critical ones and logs them in Excel. There's also a CSV export for a Power BI report ([docs/power-platform](docs/power-platform/README.md)).
- **Jira / Confluence:** the backlog as an importable CSV with user stories and acceptance criteria, plus architecture, runbook and decision-log pages ([docs/jira](docs/jira/README.md), [docs/confluence](docs/confluence)).

## Run it yourself

You only need Python for this:

```bash
git clone https://github.com/Karan6528/servicedesk-copilot.git
cd servicedesk-copilot
python -m venv .venv
.venv\Scripts\activate          # on Mac/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000. To fill it with 30 demo requests, run this in a second terminal:

```bash
python scripts/seed_demo.py
```

All names, e-mails and phone numbers in the demo are made up.

With Docker (app + PostgreSQL):

```bash
docker compose up --build
```

On a local Kubernetes cluster with kind:

```bash
kind create cluster --name servicedesk --config k8s/kind-config.yaml
docker build -t servicedesk-copilot:local .
kind load docker-image servicedesk-copilot:local --name servicedesk
kubectl apply -f k8s/namespace.yaml
kubectl -n servicedesk create secret generic servicedesk-secrets \
  --from-literal=POSTGRES_PASSWORD=local-pass \
  --from-literal=DATABASE_URL=postgresql+psycopg://servicedesk:local-pass@postgres:5432/servicedesk
kubectl apply -k k8s/
kubectl -n servicedesk port-forward svc/servicedesk-api 8080:80
```

## API

The full docs are at `/docs` when the app is running. The main endpoints:

| Method | Path | What it does |
|---|---|---|
| POST | `/api/tickets` | Create a ticket (triage, save, suggested reply, escalation if urgent) |
| POST | `/api/triage` | Only classify a message, don't save it |
| GET | `/api/tickets` | The queue, filter with `?urgency=`, `?status=`, `?category=` |
| GET / PATCH | `/api/tickets/{number}` | Read a ticket or change its status. `SDC-000002`, `sdc-2` and `2` all work |
| GET | `/api/stats` | Counts per category, urgency, status, language |
| GET | `/api/export.csv` | Everything as CSV, for Power BI |
| GET | `/healthz`, `/readyz` | Health checks (readyz also shows which integrations are switched on) |

## Configuration

Without any settings it runs with SQLite and the rule engine. Everything else is optional. Copy [.env.example](.env.example) to `.env` and fill in what you have. The app reads `.env` from the project folder when it starts (the tests ignore it, so they never touch your real accounts):

| Variable | What it does |
|---|---|
| `DATABASE_URL` | e.g. `postgresql+psycopg://user:pass@host:5432/db` |
| `OPENAI_API_KEY` or `AZURE_OPENAI_*` | let an LLM help with triage |
| `SERVICENOW_INSTANCE`, `_USER`, `_PASSWORD` | create incidents for critical/high tickets |
| `POWER_AUTOMATE_WEBHOOK_URL` | send critical/high tickets to the alert flow |

## Tests

```bash
pytest -q
ruff check app tests
```

There are 36 tests: the triage rules (English and German examples), the API, the ServiceNow and Power Automate calls (with fake responses), the LLM fallback, and one that checks an older database gets upgraded without losing data.

## What I'd do next

- Keyword rules miss unusual wording. If agents correct categories in the UI, those corrections could train a small classifier later.
- The ServiceNow and Power Automate calls are "fire and forget" right now. A queue with retries (e.g. Azure Service Bus) would be more reliable.
- The demo has no login. In a real setup I'd put Microsoft Entra ID in front of it.

## License

MIT
