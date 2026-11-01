# ServiceDesk Copilot – Decision log

*Confluence page. One entry per important technical decision: what was decided, why, and what was given up.*

### D1 – Rule engine first, LLM optional
- **Decision:** classification works with weighted EN/DE keyword rules. An LLM (OpenAI / Azure OpenAI) is used only when a key is set.
- **Why:** it runs free and offline, it's fast, and every decision can be explained ("matched: wallbox, laden"). Ticket handling doesn't fail when an external API is down.
- **Trade-off:** rules miss unusual wording. Mitigation: an agent can change the category, and the LLM can be switched on.
- **Guard rail:** the LLM may never lower a *critical* urgency that the rules detected.

### D2 – Integrations as background tasks
- **Decision:** ServiceNow and Power Automate are called after the API has already answered.
- **Why:** the customer or agent gets a reference number in milliseconds, and slow or broken integrations don't block anything.
- **Trade-off:** no automatic retry yet. Next step: a queue (Azure Service Bus) with retries.

### D3 – Azure Container Apps instead of AKS for the cloud
- **Decision:** the cloud deployment runs on Container Apps. Kubernetes manifests exist and are tested on kind in CI.
- **Why:** Container Apps can scale to zero and doesn't need cluster management, which suits a student budget. The manifests show the app is ready for AKS.
- **Trade-off:** less control than AKS (no custom operators, for example).

### D4 – Power Automate for notifications
- **Decision:** Teams, Outlook and Excel are handled by a low-code flow, not by code in the app.
- **Why:** the business team can change who gets notified, and the wording, without a developer or a deployment.
- **Trade-off:** the HTTP trigger needs a premium licence (free in the Power Apps Developer Plan).

### D5 – SQLite locally, PostgreSQL in containers
- **Decision:** one `DATABASE_URL`, SQLAlchemy for both.
- **Why:** you can start without any setup, and the database behaves like production in Docker/K8s.
