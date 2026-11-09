# Local autonomous student assessments

Start the existing local runtime with `python -m app.local` or
`scripts/start_local.ps1`. Its lifespan starts a one-second folder polling worker
under the existing runtime OS lease. No chat prompt, browser session, Telegram,
internet, cloud account, paid inference, or external scheduler is required.
The machine must stay awake and the runtime must remain running; this does not
install an operating-system login task.

## Storage and intake

All workflow files are under `NEXUS_LOCAL_ARTIFACT_PATH/assessments/`:

| Path | Purpose |
| --- | --- |
| `intake/` | Drop UTF-8 JSON or CSV assessment exports here |
| `config/roster.json` | Explicit local student/cohort membership |
| `config/keys/<assessment_id>@<version>.json` | Versioned, approved answer keys and foundation work |
| `sources/<SHA-256>.blob` | Original admitted bytes, archived before enqueue |
| `outputs/<job SHA-256>/job.json` | Job evidence, accepted rows, duplicates, specific review issues and report paths |
| `outputs/<job SHA-256>/cohort-*.json` / `.html` | Report snapshots for that execution |
| `outputs/cohort-*.json` / `.html` | Latest cohort reports |

Queue, student results, pinned configuration, key hashes and audit events share
the existing `nexus_memory.sqlite3`, using `assessment_*` tables. Existing bot
memory and action packages remain intact. The workflow reuses `MemoryStore`,
the runtime `FileLease`, intake/document-flow helpers, the agent model contract,
the loopback-only Ollama adapter and authenticated local API. It does not depend
on the unmerged PR #1 business ingestion/storage platform.

Write files outside intake, then rename them into it, or copy as `.part` and
rename when complete. Dotfiles, `.tmp`, `.part`, directories and symlinks are
ignored. Other files must have unchanged size and modification time across two
scans before admission. Maximum file size is 5 MiB and 10,000 submissions.
Oversized files produce a failed job with metadata; their full content is not
archived. Intake files are retained, not deleted or moved.

## Real-data dependency

**The repository does not contain the approved real assessment export schema,
answer key, cohort roster, or foundation curriculum mapping.** The supplied
fixtures are synthetic examples only. No Jotform question labels or student IDs
are guessed. Before real use, supply the approved roster and versioned key,
and map the real export explicitly to the canonical fields below. Missing
configuration produces review jobs with the exact dependency and zero invented
results. The dashboard also displays the missing dependency.

Roster format (no names or fuzzy matching):

```json
{"students": [{"student_id": "S001", "cohort": "COHORT-1"}]}
```

Each row needs exactly these five fields:

```json
{
  "submissions": [{
    "student_id": "S001",
    "cohort": "COHORT-1",
    "stage": "baseline",
    "answer_key": "foundations@v1",
    "answers": {"q1": "4"}
  }]
}
```

CSV uses `student_id,cohort,stage,answer_key,q1,...` headers. IDs, cohort,
assessment ID and key version allow letters, digits, dot, underscore and dash,
up to 80 characters. Stage must be `baseline`, `midpoint` or `final`. All question
fields in the selected key are required. Unknown fields, duplicate JSON keys,
duplicate CSV headers, blank answers, unmatched roster membership and answers
outside approved choices are flagged for review. There is no fuzzy identity
resolution, inferred stage, default answer key or silent field mapping.

`config/keys/foundations@v1.json` example:

```json
{
  "assessment_id": "foundations",
  "version": "v1",
  "items": [{
    "id": "q1", "kind": "objective", "accepted": ["4"],
    "choices": ["2", "3", "4"], "points": 2,
    "skill": "numeracy", "foundation": "Practice addition with counters."
  }]
}
```

Scoring compares exact strings against approved answers. Any permitted aliases
belong in the key. Points are positive bounded integers. Scores, question
evidence, maximum points and key hash are verified before persistence. Keys are
pinned per job and the same ID/version cannot change in place. Publish a new
version instead. Restart recovery uses the pinned key and roster.

For a qualitative item, set `kind` to `interpretation`, `points` to zero, and
`accepted` and `choices` to empty arrays. The assessment agent may use the
existing local Ollama adapter to suggest foundation work, bounded to 45 seconds.
Its response is stored as **unverified staff-review evidence**. The row is held
for review and never inserted as a verified student result. Model failure leaves
a specific review issue; objective-only jobs continue without any model request.
This first version does not approve qualitative answers or overwrite scores.

## Reports and dashboard

Unlock the existing browser workspace to see the assessment dashboard. It
refreshes every five seconds and shows pending, running, completed, failed and
review jobs, attempt counts, watcher health, actual-output downloads and recent
audit events. The worker continues when the workspace is locked or closed.
Authentication and same-origin protections cover all assessment APIs:

- `GET /local/assessments`: paths, dependencies, counts, latest 200 jobs, recent
  100 audit entries, report names. SQLite keeps the full audit history.
- `GET /local/assessment-outputs/<relative path>`: authenticated file download.
- `POST /local/assessments/<job SHA-256>/retry`: explicit staff retry after correction.

JSON and printable HTML reports show per-student scores, mean percentages,
stage-specific skill totals, missing IDs per stage, latest verified question
gaps and foundation work drawn directly from the key. Missing means no verified
submission; it does not imply overdue work. Matching uses explicit cohort,
student and assessment IDs. Baseline/midpoint/final changes are percentage points
and require identical key hashes. Incompatible versions are explicitly listed,
and no comparison is invented for an unmatched stage. Stages can arrive in any
order. Historical students outside the pinned roster are listed as excluded.

## Queue, corrections and recovery

File bytes are content-addressed, so renaming or dropping an identical file
creates no new job. Canonical answers prevent a reformatted JSON/CSV export from
duplicating student results. The student/cohort/stage/assessment identity is
unique. Identical rows are duplicates; conflicting rows within an export are
all withheld, and conflicts with an existing result require staff reconciliation.
Valid rows in a partially invalid export can commit; job status is `review`.

Only transient filesystem and SQLite operational failures retry automatically,
with 2/4-second delays and at most three attempts. Malformed files fail once;
missing or ambiguous records go to review. Correct the source and drop a new
file, or fix a configuration dependency and select Retry. Explicit retry starts
a new bounded attempt cycle and revalidates current configuration. It cannot
overwrite a previously committed score. A correction to an already committed
conflicting score requires an explicit reconciliation process outside this MVP.

On restart, interrupted running jobs become pending unless their attempt budget
is exhausted. Committed rows replay idempotently. Reports are rebuilt and the
job becomes terminal only after its saved evidence has been read back and
verified. Per-job report snapshots preserve evidence; latest reports are
reproducible projections. A report filesystem error can leave verified rows
committed while its job waits for retry; it cannot duplicate them.

The existing offline backup/restore scripts include the queue database, roster,
keys, intake, source evidence and reports as one recovery unit, with hashes and
assessment table counts. Stop the runtime before backing up.

## Reproduce the real-process synthetic drill

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/validate_assessments.py --model qwen2.5:3b
```

This launches actual separate local runtime processes and drops files, using
authenticated read-only HTTP requests to inspect outputs. It never sends a chat
prompt. It repeats scoring, report accuracy, malformed input, record review,
renamed-file and semantic JSON/CSV duplicate checks with runtime internet access
blocked. An acceptance-only interpreter audit hook denies non-loopback sockets
and DNS, proves both denials, and permits loopback Ollama. It does not modify the
host firewall or claim the entire host is offline.

The drill also kills a real running job after a result commits, restarts the
runtime and verifies recovery; creates an actual filesystem output error to
prove bounded retries; verifies an explicit corrected retry; processes objective
work against a genuinely refused Ollama endpoint; and backs up/restores the
database and artifacts into a live runtime. Local-model suggestions are actual
Ollama calls and remain review-only. Unit tests use mocks for isolated error
cases; the drill does not use mocked workers or model responses.

Evidence stays in gitignored `data/assessment-acceptance-*/` by default.
`--state-root <private directory>` places evidence outside the checkout.
`--install --leave-running` restores the verified synthetic state to
`<state-root>/state` and leaves its runtime running on the chosen port (default
8876). It refuses existing state/configuration. The private `.env.local` contains
the token. Synthetic fixtures are installed only by explicit fixture/drill
commands, never automatically in the ordinary runtime.

## Demonstrated on 2026-11-09

The completed real-process drill is saved at:
`C:\Users\NolanCode\Projects\nexus-local-state\assessment-acceptance-20261109T151012256342Z\acceptance.json`.
It passed both ordinary and internet-blocked runs without chat prompts, using
the installed `qwen2.5:3b` for qualitative review only. The initial five verified
fixture results independently checked as follows:

| Measurement | Observed |
| --- | --- |
| S001 baseline / midpoint / final | 25% / 75% / 100% |
| S002 baseline / final | 75% / 75% |
| Cohort means baseline / midpoint / final | 50% / 75% / 87.5% |
| S001 baseline-to-final change | +75 percentage points |
| Missing final submission | S003 |
| S002 final foundation recommendation | Practice counting in pairs to ten. |

The later crash, output-error and model-unavailable drills added three S003
results, leaving **eight verified results and twelve jobs**: eight completed,
three needing review, one malformed-file failure. Original accuracy snapshots
remain in `online/verified-report.json` and `offline/verified-report.json` within
the evidence directory. Latest reports include the later drill results.

The evidence includes proof of denied external TCP/DNS, actual local model
suggestions, recovery after killing a partially committed running job (two
attempts, no duplicate result), a real filesystem error stopping after three
automatic attempts, successful explicit retry, objective processing with a
refused model endpoint, and a checksummed backup restored into a live runtime.
All 80 unit/regression tests passed. Installed Microsoft Edge also verified the
actual dashboard, report download, lock behavior and loopback-only browser
requests with zero JavaScript errors (`browser-verification.json` and
`assessment-dashboard.png`).

The durable synthetic pilot is running at **http://127.0.0.1:8876/**:

- Intake: `C:\Users\NolanCode\Projects\nexus-local-state\state\artifacts\assessments\intake`
- Outputs: `C:\Users\NolanCode\Projects\nexus-local-state\state\artifacts\assessments\outputs`
- Configuration: sibling `config/` directory; API token in
  `C:\Users\NolanCode\Projects\nexus-local-state\.env.local`.

The existing private `%LOCALAPPDATA%\AARI\Nexus` state is access-denied in this
recertified session, so it was not migrated or replaced. The older runtime on
8765 has not loaded the assessment worker; the pilot on 8876 has. Azure was not
queried, changed or deployed. No paid fallback is configured.

Managed stop/start was also demonstrated against this pilot, followed by another
automatic duplicate-file drop (`managed-restart-verification.json`). Commands:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts/stop_local.ps1 -StateRoot C:\Users\NolanCode\Projects\nexus-local-state
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts/start_local.ps1 -StateRoot C:\Users\NolanCode\Projects\nexus-local-state
```

`RemoteSigned` here applies only to the child PowerShell process; no machine or
user execution policy was changed. The managed restart uses the ordinary local
profile. The separate offline drill's network guard is an acceptance boundary,
not a global firewall installation.
