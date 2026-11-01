# Jira: run the project as a real agile project

`backlog.csv` holds 1 epic, 12 user stories with acceptance criteria and 2 tasks. Each item has labels for its topic and its sprint (`sprint-1` … `sprint-3`).

## 1. Create the project (free plan, up to 10 users)

1. Sign up at https://www.atlassian.com/software/jira/free. You get Jira **and** Confluence on `https://<you>.atlassian.net`.
2. **Create project → Software development → Scrum → Team-managed**
   - Name: `ServiceDesk Copilot` · Key: **`SDCP`**

## 2. Import the backlog

1. Click the **⚙ gear (top right) → System → External system import → CSV**. On team-managed projects you can also use **Project → ⋯ → Import issues**.
2. Upload `docs/jira/backlog.csv` and choose project `SDCP`.
3. Map the columns: Summary → *Summary*, Issue Type → *Issue Type*, Priority → *Priority*, each Labels column → *Labels*, Description → *Description*.
4. Run the import, then open the **Backlog**.
5. Link the stories to the epic: select them all in the backlog → *Parent* → `ServiceDesk Copilot MVP`.

## 3. Plan the sprints (to show how you work)

- **Sprint 1, "Triage MVP":** filter label `sprint-1` → move into Sprint 1 → Start sprint (2 weeks)
- **Sprint 2, "Docker, K8s, Azure":** label `sprint-2`
- **Sprint 3, "Integrations & reporting":** label `sprint-3`

Add story points (1, 2, 3, 5, 8) and move cards across the board as you work: *To Do → In Progress → Done*. When a sprint ends, use **Complete sprint**. Jira then builds the **Burnup / Sprint report**, which is a nice screenshot for the README.

## 4. Connect GitHub (commits show up on the issues)

1. In Jira, go to **Apps → Explore more apps → "GitHub for Jira"** (free), then connect your GitHub account and select the `servicedesk-copilot` repo.
2. Put the issue key in branch names and commit messages:
   ```
   git checkout -b SDCP-7-kubernetes
   git commit -m "SDCP-7 add HPA and readiness probe"
   ```
   The issue now shows the branch, commits, PR and CI status.

## 5. Accepting a story

Before you move a story to **Done**, test it against its acceptance criteria. Then add a short comment: *"Tested on Azure revision xyz, all AC met"*, plus a screenshot. Reviewers see that you test and accept user stories, not only write code.
