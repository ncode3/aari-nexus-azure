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

Copy `.env.local.example` to `.env.local`. Set the existing Telegram bot token,
your authorized chat ID(s), and the exact installed model name from `ollama list`.
Keep Ollama listening on loopback. Do not expose port 11434 to the network.
Use a separate test bot token during the pilot: two polling instances cannot
share the production token. No model download or paid fallback occurs.

```sh
python -m app.local
```

This entry point binds health HTTP to 127.0.0.1:8000, forces Ollama, disables
Azure Key Vault, Blob, Application Insights and live Graph reporting even when
cloud settings are inherited. Telegram still requires internet. Power Apps links
remain available; live Cohort Desk counts are disabled in this local profile.
Azure SDK packages remain installed for compatibility, but the profile disables
their configured services. This is not a network sandbox.

Persistent state defaults to `data/nexus_memory.sqlite3`; local artifacts go to
`data/artifacts`. Both are gitignored. Existing operational action packages are
stored in SQLite; the artifact helper stores JSON locally when invoked. This is
not a migration of existing Azure blobs, business databases, or a vector index.
Protect the host account and disk, including backups. The host must remain awake
for the bot to respond. Review logs and model failures locally.

## Acceptance and backup

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

The script uses SQLite's backup API, checks integrity, and refuses to overwrite.
For custom storage paths, consolidate a staged backup directory first; `--data`
expects `nexus_memory.sqlite3` and `artifacts/` beneath it. Copy backups to an
approved encrypted off-site destination; this tool does not upload them.
Restore into an empty staging directory using a trusted backup, check SQLite
integrity and record counts, then point the test runtime at the restored data.
Never overwrite the only good database. Test recovery before production cutover.

## Cloud inventory and cutover gates

Live subscription charges and deployed dependencies are unverified in this change.
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
