# Cohort Desk integration

Cohort Desk is the staff entry and editing interface. SharePoint remains the
source of truth. Nexus reads current records on request and returns deterministic
counts, with links to the staff app and SharePoint views. There is no second
student database, scheduled synchronization, or model-generated enrollment count.

## Commands

| Command | Result |
| --- | --- |
| `/cohort desk` | Open the published staff app, follow-up queue, and cohort summary. No Graph request. |
| `/cohort` or `/cohort summary` | Registration and readiness totals, stage counts, and cohort/track groups. |
| `/cohort impact` | Current pipeline readiness, overlapping blocker counts, and explicitly unmeasured business outcomes. |
| `/cohort followups` | New registrations with pending readiness: overdue, due today, undated, and unassigned counts. |

Every command requires an explicitly allowed Telegram chat. An empty
`BOT_ALLOWED_CHAT_IDS` does not authorize Cohort Desk commands. Existing commands
retain their existing behavior.

## Source contract

Default source: `https://aari.sharepoint.com/sites/AARICohortDesk`, list
`Cohort Registrations`. Its list ID and published app/view URLs are supplied as
non-secret defaults in `app/config.py` and can be overridden through environment
variables or Pulumi configuration.

- `IsTest=true` records are excluded, regardless of the active SharePoint view.
- Ready means RegistrationComplete, ScheduleConfirmed, and TransportConfirmed
  are true, and GuardianConsent is Received or Not required. This matches the
  list's Readiness calculation.
- The follow-up queue is Stage=New and readiness Pending, matching the saved view.
- Date-only follow-up values retain their calendar date. Today's date is evaluated
  in America/New_York. An empty due date is counted separately, not as overdue.
- Counts are registration records, not unique people, attendance, certifications,
  placements, or confirmed enrollment. Stage counts reflect the staff-entered field.
- Missing required fields, invalid booleans/dates, denied access, failed requests,
  repeated pages and page limits return **unavailable**, never invented zero totals.
- All pages are read, duplicate item IDs are counted once, and partial totals are
  never presented as complete. The default cap is 100 pages of 200 items.

Only reporting fields are requested. Participant names, contact details, free-text
notes, files and consent documents are not requested. Record data is not sent to Azure
OpenAI, placed in memory, or written to Blob storage. Numeric aggregate snapshots
are logged to the existing telemetry pipeline; free-text group labels and
participant details are excluded. See [business measurement](business-measurement.md).
No public HTTP endpoint is added. The Graph client only issues GET requests and
will not forward its bearer token to a pagination URL outside Microsoft Graph.

## Activate on the existing deployment

Merging the code does **not** activate Azure or grant SharePoint access. Deploy to
the existing Nexus Container App using its existing Pulumi stack and identity.
Do not initialize a replacement stack or create another service.

1. Use an authorized administrator to grant the existing Nexus managed identity
   Microsoft Graph application permission `Sites.Selected`, with **read** access
   to the Cohort Desk site only. Do not grant tenant-wide `Sites.Read.All` or
   `Sites.ReadWrite.All`. This is a separate approval and permission action.
   Alternatively use `Lists.SelectedOperations.Selected` with read access to
   the registration list; with list-only permission, set `cohortSiteId` to the
   composite Graph site ID so no site discovery request is needed.
2. Confirm the identity belongs to the SharePoint tenant. The app uses
   `DefaultAzureCredential` with the deployed `AZURE_CLIENT_ID`; no stored Graph
   password, delegated token, or shared storage key is required.
3. From an authenticated deployment workstation, use the existing stack:

   ```bash
   cd infra
   pulumi stack select dev
   pulumi config set botAllowedChatIds '<existing approved Telegram chat IDs>'
   pulumi config set cohortGraphEnabled true
   # For list-only access, or to skip site resolution:
   # pulumi config set cohortSiteId '<hostname,site-collection-guid,site-guid>'
   ```

4. Build and push an immutable image tag from the merged source using the
   existing registry. Set both `containerImageTag` and `appVersion` to that tag,
   run `pulumi preview`, review changes, then `pulumi up`. See
   [deployment.md](deployment.md). Preserve all existing stack secrets and runtime
   settings. Import any out-of-band changes before applying the stack.
5. The current stack permits scaling to zero. A Telegram polling bot cannot wake
   itself from zero replicas. Check the actual runtime and approve the operating
   cost before making it continuously available. This change does not modify
   replica counts or start a paid service.
6. In the approved chat, run `/cohort desk`, `/cohort summary`, and
   `/cohort followups`. With an empty production roster the verified totals must
   be zero, and test records must stay excluded. Mark a test record ready in
   Cohort Desk to validate the formula without including it in production counts.

`COHORT_GRAPH_ENABLED=false` is the safe default. Until enabled and authorized,
Nexus states that live reporting is unavailable and provides the workspace links.
A successful `/healthz` response alone does not prove SharePoint connectivity.
The `/cohort summary` live response is the integration check.

## Configuration

| Environment variable | Pulumi key | Default |
| --- | --- | --- |
| `COHORT_GRAPH_ENABLED` | `cohortGraphEnabled` | false |
| `BOT_ALLOWED_CHAT_IDS` | `botAllowedChatIds` | empty; cohort commands denied |
| `COHORT_SITE_ID` | `cohortSiteId` | resolve from site URL |
| `COHORT_SITE_URL` | `cohortSiteUrl` | AARI Cohort Desk site |
| `COHORT_LIST_ID` | `cohortListId` | Cohort Registrations list |
| `COHORT_APP_URL` | `cohortAppUrl` | published Power Apps launch URL |
| `COHORT_QUEUE_URL` | `cohortQueueUrl` | SharePoint Follow-up Queue |
| `COHORT_SUMMARY_URL` | `cohortSummaryUrl` | SharePoint Cohort Summary |
| `COHORT_MAX_PAGES` | n/a | 100 |

## Verification and rollback

```bash
python -m unittest discover -s tests -v
python -m compileall -q app infra
git diff --check
```

Tests cover readiness, test exclusion, date buckets, pagination, throttling,
unauthorized chat rejection, unavailable data and minimal output. GitHub Actions
runs the same suite without cloud credentials or production data.

To disable reporting, set `cohortGraphEnabled=false` and deploy the existing stack.
Workspace shortcuts remain available to authorized chats. To roll back the app,
restore the prior immutable image tag through Pulumi. No SharePoint records are
changed by Nexus; revoking the selected permission independently stops access.

## Microsoft reference

- [List items](https://learn.microsoft.com/en-us/graph/api/listitem-list?view=graph-rest-1.0)
- [Selected permissions](https://learn.microsoft.com/en-us/graph/permissions-selected-overview)
