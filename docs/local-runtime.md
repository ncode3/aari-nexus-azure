# Local Nexus runtime and cloud retirement

Implements #34 and the model-routing part of #26, reusing #28's loopback
Ollama adapter. This is the current Telegram bot, Arbiter, agents and SQLite
memory running locally. The separate PostgreSQL/MinIO platform in PR #1 is
not merged or migrated by this change. No cloud resources are changed.

## Start on the existing Ollama machine

Use Python 3.11 or newer. Run these commands from the repository root:

```sh
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell instead:
# .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy `.env.local.example` to `.env.local`. Generate a private API token of at least
32 characters, set your explicitly authorized chat ID(s), and choose the exact
installed model name from `ollama list`. The default starts no Telegram poller.
Keep Ollama listening on loopback. Do not expose port 11434 to the network.
Use a separate test bot token during the pilot: two polling instances cannot
share the production token. No model download or paid fallback occurs.

```sh
python -m app.local
```

For the permanent Windows checkout, use these poller-free service commands:

```powershell
cd C:\Users\NolanCode\Projects\aari-nexus-azure
.\scripts\start_local.ps1
.\scripts\stop_local.ps1
```

They use `%LOCALAPPDATA%\AARI\Nexus\.env.local`, record and verify process
identity, and stop the Windows launcher plus child interpreter. State is in
`%LOCALAPPDATA%\AARI\Nexus\state`; backup and acceptance evidence remain outside
the checkout. They neither change Azure nor enable Telegram. Keep the host awake;
no automatic Windows startup task is installed.

One-time synthetic acceptance and initial state installation (refuses existing
state or configuration):

```powershell
.\.venv\Scripts\python.exe scripts/validate_local.py --model qwen2.5:3b --state-root "$env:LOCALAPPDATA\AARI\Nexus" --install
```

This entry point binds HTTP to 127.0.0.1:8765, forces Ollama, disables
Azure Key Vault, Blob, Application Insights and live Graph reporting even when
cloud settings are inherited. Telegram still requires internet. Power Apps links
remain available; live Cohort Desk counts are disabled in this local profile.
Azure SDK packages remain installed for compatibility, but the profile disables
their configured services. This is not a network sandbox.

For permanent operation put `NEXUS_MEMORY_PATH` and `NEXUS_LOCAL_ARTIFACT_PATH`
under a private, durable directory outside the source checkout, for example
`%LOCALAPPDATA%/AARI/Nexus/state/nexus_memory.sqlite3` and its sibling `artifacts/`.
Both must share this recovery directory. `NEXUS_LOCAL_ENV_FILE` may point to a
private configuration file outside the repository. Keep private files under a
user-only Windows ACL or Unix mode 0700; chmod alone does not establish a Windows ACL.

Development state defaults to `data/nexus_memory.sqlite3`; local artifacts go to
`data/artifacts`. Both are gitignored. Existing operational action packages are
stored in SQLite; the artifact helper stores JSON locally when invoked. This is
not a migration of existing Azure blobs, business databases, or a vector index.
Protect the host account and disk, including backups. The host must remain awake
for the bot to respond. Review logs and model failures locally.

## Acceptance and backup

All `/local/*` routes require `Authorization: Bearer <NEXUS_LOCAL_API_TOKEN>`.
`POST /local/command` accepts `{"chat_id": <allowed-id>, "text": "/find topic"}`.
Its command path reuses the existing memory, agents, Arbiter and Cohort Desk links.
Invalid tokens return 401; unlisted chats, browser-origin requests and unexpected
Host headers are rejected. `/healthz` contains no records and is public on loopback.
There is no CORS grant, public tunnel, model-download endpoint or cloud-job endpoint.
Small operator attachments use `PUT /local/documents/<simple-name>`, filename
search uses `GET /local/documents?query=...`, and downloads use the returned hash ID.
This is not PR #1's business document-ingestion API.

Run the actual-machine synthetic drill without any Telegram token:

```powershell
.\.venv\Scripts\python.exe scripts/validate_local.py --model qwen2.5:3b --leave-running
```

It writes private evidence under `data/acceptance-*/`: a configuration, process
IDs, logs, SQLite snapshot, checksummed attachments, restored state and
`acceptance.json`. It verifies real inference/retrieval, rejected access, process
restart, offline backup and live restore, and a real refused Ollama connection
with memory still available. It never stops the shared Ollama service. On Windows
stop the saved launcher PID **and its child process tree**; killing just the venv
launcher is not a reliable restart. Check the port is closed before relaunch.

For the Telegram pilot, independently confirm a separate bot's identity, set its
token and allowed test chat in the private configuration, then explicitly set
`NEXUS_TELEGRAM_ENABLED=true` and `NEXUS_TEST_BOT_CONFIRMED=true`. A per-token OS
lease prevents two local pollers; it cannot detect a poller on Azure or another
machine. Production polling is not enabled by this validation. Never mark a
production token as a test token. Live Telegram acceptance remains separate.

1. On the test bot run `/ping`, `/status`, `/remember synthetic migration check`,
   `/find migration`, `/brief summarize the synthetic migration check`.
2. Restart the bot; verify `/find migration` still returns the saved record.
3. Stop Ollama; a model request must fail without any Azure request. Memory
   commands continue to work. Restart Ollama and repeat the brief.
4. Verify an unlisted chat is rejected and no Azure telemetry is configured.
5. Stop the bot before a matched database/artifact backup:

```sh
python scripts/backup_local.py backups/pilot.zip
```

The script uses SQLite's backup API, closes connections on Windows, checks
integrity, records table counts and hashes every file. An active local runtime
lease makes a matched offline backup fail closed. It refuses to overwrite.
For custom storage paths, consolidate a staged backup directory first; `--data`
expects `nexus_memory.sqlite3` and `artifacts/` beneath it. Copy backups to an
approved encrypted off-site destination; this tool does not upload them.
Restore a trusted backup into a NEW staging directory:

```sh
python scripts/restore_local.py backups/pilot.zip recovery/pilot
```

Restoration checks member paths, every SHA-256, SQLite integrity and table counts
before publishing the recovery directory. It refuses existing destinations,
traversal, linked files, extra members, and checksum changes. A checksum is an
integrity check, not authentication: use a trusted, access-controlled backup.
Then point the test runtime at the restored data and retrieve real sample bytes.
Never overwrite the only good database. Test recovery before production cutover.

## Cloud inventory and cutover gates

The optional read-only `python scripts/audit_azure.py --wsl` uses Azure CLI in
Ubuntu when Windows has no Azure CLI. It queries actual cost at subscription
scope without a region filter, follows cost pagination, compares prior-month
and month-to-date resource/location rows, inventories dependencies and reads
existing budgets. Private evidence is in `data/azure-audit/audit.json` and
`keep-retire.json`; raw account IDs, private configuration and budget contacts
must not be committed. Empty charge rows are not evidence of zero future cost.
The script never mutates Azure resources or budgets. Further audit work can be
deferred independently of the local runtime.

The Azure model adapter requires a fresh `PaidJobApproval` bound to the exact
request, output-token limit, deployment and expiry. Approval is consumed once,
before dispatch; SDK automatic retries are disabled. No model/Telegram/local API
route creates approvals or executes paid jobs. Missing or expired approval fails
closed. The status probe no longer makes a billable completion. This changes the
branch's legacy Azure inference behavior intentionally; do not redeploy it to
production without an approved migration. No paid job was run for acceptance.

Record live subscription charges and deployed dependencies as private evidence.
With authenticated Azure access, obtain month-to-date cost by resource and service
across all regions; distinguish Nexus charges from unrelated workloads. Inventory
Container Apps/revisions, registry, logs/retention, storage, Key Vault, model
deployments, Front Door, and all other billed resources. Budget alerts are not
spending caps. Preserve the previously approved $50/month ceiling pending a new
budget decision. Do not assume the earlier reported bill belongs to Nexus.

Before production cutover: export current application configuration securely,
record the active revision and poller count, back up existing SQLite and blobs,
verify restore counts and representative documents, and validate the local model
on authorized workflows. Preserve Power Apps/SharePoint ownership and permissions.
An Azure managed identity does not transfer to a local machine; live Graph needs
a separately approved authentication configuration. No inbound cloud-to-laptop
connection is added here.

Stop the cloud poller before starting the local bot with the production token.
Verify health, private access, drafts, memory persistence and recovery. Only then
retire individually verified unnecessary resources; retain data and rollback
artifacts until acceptance. Do not delete the resource group wholesale. Verify
cost accrual after the cutover and account for reporting lag.

Rollback: stop the local poller, retain its data, reconcile any new memory before
resuming writes, and restart the captured cloud revision/configuration. Do not
run both pollers with one token. Deployment, retirement and dollar savings are
not claimed until observed on the actual machines and subscription.
