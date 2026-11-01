# ServiceDesk Copilot – Runbook

*Confluence page for operations: how to deploy, check, roll back and fix.*

## Health checks

| Endpoint | Meaning |
|---|---|
| `GET /healthz` | Process is running (liveness) |
| `GET /readyz` | Database reachable. Also shows the active engine and which integrations are configured |

## Deploy

| Where | How |
|---|---|
| Local | `uvicorn app.main:app --reload` |
| Docker | `docker compose up --build` |
| Kubernetes (kind) | see README → *Kubernetes* |
| Azure | GitHub → Actions → **deploy-azure** → Run workflow |

## Roll back (Azure)

Every deploy creates a new **revision**.

```bash
az containerapp revision list -n servicedesk-copilot -g rg-servicedesk-copilot -o table
az containerapp ingress traffic set -n servicedesk-copilot -g rg-servicedesk-copilot \
  --revision-weight <previous-revision-name>=100
```

## Roll back (Kubernetes)

```bash
kubectl -n servicedesk rollout undo deployment/servicedesk-api
kubectl -n servicedesk rollout status deployment/servicedesk-api
```

## Rotate a secret

1. Create the new password or URL in ServiceNow / Power Automate.
2. Azure: `az containerapp secret set ...` then `az containerapp update ...` (this creates a new revision).
   K8s: `kubectl -n servicedesk create secret generic servicedesk-secrets ... --dry-run=client -o yaml | kubectl apply -f -`, then `kubectl -n servicedesk rollout restart deployment/servicedesk-api`.
3. Check `/readyz`.

## Common problems

| Symptom | Likely cause | Fix |
|---|---|---|
| `/readyz` 503 | Database not reachable | K8s: `kubectl -n servicedesk get pods`, check the postgres pod and the `DATABASE_URL` secret |
| ServiceNow column stays "–" | Instance hibernating or wrong password | Wake the instance at developer.servicenow.com, then check the logs for `ServiceNow incident failed` |
| No Teams message | Flow URL changed or flow turned off | Power Automate → flow → run history; copy the new trigger URL into the secret |
| First request on Azure is slow | Scale-to-zero cold start | Expected (~10–30 s). Set `--min-replicas 1` before a demo |
| Pod `CrashLoopBackOff` | Missing secret | `kubectl -n servicedesk describe pod ...` → create `servicedesk-secrets` |

## Logs

```bash
docker compose logs -f api
kubectl -n servicedesk logs -l app=servicedesk-api -f
az containerapp logs show -n servicedesk-copilot -g rg-servicedesk-copilot --follow
```
