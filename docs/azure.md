# Deploy to Microsoft Azure (Azure Container Apps)

Goal: the app runs on a public HTTPS URL on Azure, and every redeploy goes through GitHub Actions.

**Cost:** with the **Azure for Students** offer (free credit, no credit card) this project costs only a few euros a month. Most of that is the container registry (Basic tier). The Container App scales to zero when nobody uses it. Delete the resource group when you are done: `az group delete -n rg-servicedesk-copilot`.

## 0. One-time: account and CLI

1. Activate **Azure for Students** with your Gisma e-mail: https://azure.microsoft.com/free/students
2. Install the Azure CLI: https://learn.microsoft.com/cli/azure/install-azure-cli
3. Log in and add the Container Apps extension:

```bash
az login
az extension add --name containerapp --upgrade
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
```

## 1. First deployment (one command)

Run this from the project folder. `az containerapp up` creates the resource group, a container registry, the Container Apps environment and the app. It builds the Dockerfile **in Azure**, so you don't need Docker on your laptop for this step.

```bash
az containerapp up \
  --name servicedesk-copilot \
  --resource-group rg-servicedesk-copilot \
  --location germanywestcentral \
  --source . \
  --ingress external \
  --target-port 8000 \
  --env-vars APP_ENV=azure
```

> If you get *"location not allowed"*: student subscriptions sometimes limit regions. Try `westeurope` or `northeurope`.

The command prints the URL (`https://servicedesk-copilot.<random>.germanywestcentral.azurecontainerapps.io`). Open it, then load the demo data:

```bash
python scripts/seed_demo.py https://<your-url>
```

Save money by letting it scale to zero:

```bash
az containerapp update -n servicedesk-copilot -g rg-servicedesk-copilot --min-replicas 0 --max-replicas 2
```

**About the database:** the cloud version uses SQLite inside the container, so the data resets when the container restarts. That is fine for a demo. For persistent data, create *Azure Database for PostgreSQL – Flexible Server* (Burstable B1ms) and set `DATABASE_URL` as a secret. Note that this costs noticeably more credit.

## 2. Secrets (optional integrations)

```bash
az containerapp secret set -n servicedesk-copilot -g rg-servicedesk-copilot \
  --secrets sn-pass=<servicenow-password> pa-url=<power-automate-url>

az containerapp update -n servicedesk-copilot -g rg-servicedesk-copilot \
  --set-env-vars SERVICENOW_INSTANCE=dev12345.service-now.com SERVICENOW_USER=admin \
                 SERVICENOW_PASSWORD=secretref:sn-pass POWER_AUTOMATE_WEBHOOK_URL=secretref:pa-url
```

## 3. Continuous deployment with GitHub Actions

The workflow `.github/workflows/deploy-azure.yml` builds a new image in your registry and rolls out a new revision.

1. Find the name of the registry that step 1 created:
   ```bash
   az acr list -g rg-servicedesk-copilot --query "[].name" -o tsv
   ```
2. Create a service principal that may deploy to **this resource group only**:
   ```bash
   SUB=$(az account show --query id -o tsv)
   az ad sp create-for-rbac --name gh-servicedesk-deploy --role contributor \
     --scopes /subscriptions/$SUB/resourceGroups/rg-servicedesk-copilot --json-auth
   ```
   Copy the JSON output.
   > If your university tenant does not allow creating service principals, skip CD. Redeploy by running the `az containerapp up ... --source .` command from step 1 again. It does the same job.
3. On GitHub, open **Settings → Secrets and variables → Actions** and add:
   - Secret `AZURE_CREDENTIALS` = the JSON from step 2
   - Variable `ACR_NAME` = the registry name from step 1
4. Create an environment called `azure` (Settings → Environments). You can require your own approval there before each deploy.
5. To deploy, go to **Actions → deploy-azure → Run workflow**.

## 4. What to show in an interview

- The live URL, plus `/docs` (the Swagger API docs) and `/readyz` (shows which engine and integrations are active)
- Azure Portal → Container App → **Revisions** (one revision per deploy) and **Log stream**
- The GitHub Actions run that built and deployed it
