# Power Platform: Power Automate alert flow + Power BI report

```
ServiceDesk Copilot ──(urgent ticket, JSON)──▶ Power Automate flow
                                                 ├─▶ Teams: post alert in a channel
                                                 ├─▶ Outlook: e-mail to the team lead (critical only)
                                                 └─▶ Excel: add a row to "Escalations" table
ServiceDesk Copilot ──/api/export.csv──▶ Power BI report
```

## Which licence do I need?

The trigger **"When an HTTP request is received"** is a *premium* connector. A normal student Microsoft 365 licence usually does not include it.

**Recommended:** sign up for the free **Power Apps Developer Plan** with your Gisma account: https://powerapps.microsoft.com/developerplan
You get a personal *developer environment* where premium connectors work for free, for learning and testing. Build the flow **in that environment**. Pick it in the environment switcher, top right of make.powerautomate.com.

Teams, Outlook and Excel Online are standard connectors and work with your Gisma account.

## Part 1: the alert flow (about 20 minutes)

1. Go to https://make.powerautomate.com, switch to your developer environment, then **Create → Instant cloud flow → skip**.
2. **Trigger:** *When an HTTP request is received* (the "Request" connector)
   - *Who can trigger the flow?* → **Anyone**. The URL contains a secret signature, so treat it like a password.
   - Click **Use sample payload to generate schema** and paste:
     ```json
     {
       "reference": "SDC-000006",
       "created_at": "2026-11-01T12:00:00+00:00",
       "customer_name": "Lea Fischer",
       "customer_email": "lea.fischer@example.com",
       "channel": "phone",
       "message": "Unfall auf der Autobahn, Rauch aus dem Motorraum!",
       "language": "de",
       "category": "roadside_assistance",
       "urgency": "critical",
       "confidence": 1.0,
       "suggested_reply": "Hallo Lea Fischer, ...",
       "status": "new",
       "servicenow_number": "INC0010001"
     }
     ```
3. **Action:** *Microsoft Teams → Post message in a chat or channel*
   - Post as: Flow bot · Post in: Channel · pick a team/channel (create a test team "ServiceDesk Demo")
   - Message: `🚨 <b>@{triggerBody()?['urgency']}</b> ticket @{triggerBody()?['reference']} – @{triggerBody()?['category']}<br>@{triggerBody()?['message']}<br>ServiceNow: @{triggerBody()?['servicenow_number']}`
     (In the editor you can also click the fields from the *Dynamic content* list instead of typing the expressions.)
4. **Condition:** `urgency` *is equal to* `critical`
   - **If yes:** *Office 365 Outlook → Send an email (V2)* to yourself. Subject: `CRITICAL: @{triggerBody()?['reference']}`, Body: message + suggested reply.
5. **Excel log:**
   - In OneDrive, create `ServiceDesk-Escalations.xlsx` with a table named `Escalations` (Insert → Table) and the columns: `Reference | Created | Urgency | Category | Language | Customer | ServiceNow`
   - Action: *Excel Online (Business) → Add a row into a table* → map the fields.
6. **Response** action (optional, good practice): status code `202`.
7. **Save.** Copy the **HTTP URL** shown in the trigger.
8. Give the URL to the app:
   - local: in `.env`: `POWER_AUTOMATE_WEBHOOK_URL=<url>`, then restart
   - Azure: see `docs/azure.md` step 2
9. **Test:** create the "Unfall (DE)" example in the web UI. Within a few seconds you should see the Teams message, the e-mail and a new Excel row. Check **My flows → the flow → Run history**.

**Fallback without the developer plan:** let the flow start with the standard trigger *"When a new email arrives (V3)"* in a mailbox, and have a colleague or the app send mails there. Same Teams, Outlook and Excel actions.

**Screenshots for the README:** the flow designer, a successful run, the Teams message.

## Part 2: Power BI report (about 30 minutes)

Data source, either:
- **File:** `docs/power-platform/sample_tickets.csv` (400 synthetic tickets over 90 days, made with `python -m scripts.make_powerbi_sample`), or
- **Live:** *Get data → Web →* `https://<your-app>/api/export.csv`

In Power Query, set `created_at` to *Date/Time*, `confidence` to *Decimal*, and add a column `Date = DateTime.Date([created_at])`.

Measures (DAX):

```DAX
Tickets = COUNTROWS(tickets)
Open Tickets = CALCULATE([Tickets], tickets[status] <> "resolved")
Critical + High = CALCULATE([Tickets], tickets[urgency] IN {"critical", "high"})
Escalation Rate = DIVIDE([Critical + High], [Tickets])
Escalated to ServiceNow = CALCULATE([Tickets], NOT ISBLANK(tickets[servicenow_number]))
German Share = DIVIDE(CALCULATE([Tickets], tickets[language] = "de"), [Tickets])
```

Suggested page "Service Desk Overview":
- KPI cards: Tickets · Open Tickets · Escalation Rate · German Share
- Bar chart: Tickets by `category`
- Stacked bar: `category` × `urgency`
- Donut: `status`
- Table: latest critical/high tickets (reference, category, message, status)
- Slicers: language, channel

Save as `docs/power-platform/servicedesk-overview.pbix` and add a screenshot to the README.

## Optional: Power Apps

Make a canvas app from the Excel `Escalations` table (*Create → Start from data → Excel*). That gives the team lead a mobile list of escalated tickets.
