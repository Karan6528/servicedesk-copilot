# ServiceNow: urgent tickets become Incidents

When a ticket is **critical** or **high**, the app calls the ServiceNow **Table API** (`POST /api/now/table/incident`). It saves the returned incident number (e.g. `INC0010023`) on the ticket and shows it in the queue.

| Ticket urgency | ServiceNow urgency | ServiceNow impact |
|---|---|---|
| critical | 1 – High | 1 – High |
| high | 1 – High | 2 – Medium |

The ticket reference goes into `correlation_id`, so you can search for it in ServiceNow.

## 1. Get a free instance (about 10 minutes)

1. Register at https://developer.servicenow.com (free).
2. Click **Request Instance** and pick the latest release. You get a URL like `https://dev12345.service-now.com`, user `admin` and a password. You can reset the password in the developer portal under *Manage instance password*.
3. Note: a developer instance **hibernates** when unused and is **deleted after about 10 days of no activity**. Log in from time to time, and wake it up before a demo.

## 2. Test the API by hand

```bash
curl -u 'admin:<password>' -H 'Accept: application/json' -H 'Content-Type: application/json' \
  -X POST https://dev12345.service-now.com/api/now/table/incident \
  -d '{"short_description":"API test","urgency":"2","impact":"2"}'
```

The response contains `"number": "INC00100xx"`.

> Good practice: create a dedicated integration user (*User Administration → Users → New*, role `itil`) instead of using `admin`, and put its credentials in the app.

## 3. Connect the app

`.env` (local), or Azure secrets (see `docs/azure.md`):

```
SERVICENOW_INSTANCE=dev12345.service-now.com
SERVICENOW_USER=admin
SERVICENOW_PASSWORD=<password>
```

Restart the app. `GET /readyz` should now show `"servicenow": true`.

## 4. Demo

1. In the web UI, click the **breakdown** example → **Create ticket**.
2. Reload the queue after 2–3 seconds. The *ServiceNow* column shows `INC00100xx`.
3. In ServiceNow: *Incident → All*, then search for the number. The description holds the customer message, and `correlation_id` holds `SDC-0000xx`.

## Ideas for a next step

- **Two-way sync:** a ServiceNow *Business Rule* or *Flow Designer* flow calls `PATCH /api/tickets/{reference}` when the incident is resolved.
- Map categories to ServiceNow *assignment groups* (e.g. Roadside → "Mobility Service").
