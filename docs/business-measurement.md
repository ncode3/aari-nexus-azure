# Cohort Desk business measurement

The business question is whether staff spend less time managing registrations
while more participants become ready and fewer follow-ups are missed. Software
installation, licenses claimed, test passes and fast API responses do not prove
those outcomes.

## What the implementation measures

`/cohort impact` reads the same live SharePoint list as `/cohort summary` and emits
one `cohort.measurement` event per report attempt through the existing application
logging pipeline. There is no scheduled collection or new cloud resource.

| Measure | Definition | Interpretation |
| --- | --- | --- |
| Pipeline | Non-test records in New or Active stage | Current registration workload, not unique people |
| Pipeline readiness | Ready pipeline records / pipeline records | Null when the pipeline is empty |
| Blockers | Missing registration, schedule, transport, or consent within the pipeline | Overlapping counts; do not add them into a participant total |
| Overdue follow-ups | New + Pending readiness with a due date before today in America/New_York | Undated items are reported separately |
| Unassigned follow-ups | New + Pending readiness without an owner | Work without a responsible staff member |
| Completed / withdrawn | Current staff-entered stage counts | Not independently verified attendance or placement |
| Read duration | Elapsed Graph read and summary computation | Technical performance only |

Events contain numeric aggregate counts, UTC observation time, schema version,
status, and a hash identifying the environment/site/list combination. They exclude
participant names, contacts, IDs, notes, cohort/track labels, upstream errors and
chat content. Failed reads emit `status=unavailable` without counts. Desk links and
invalid commands do not emit a measurement. Test records never enter the totals.

## Activation and history verification

Deploy the merged code and authorize the existing Graph connection using
[the activation steps](cohort-desk.md). The existing Application Insights
connection must collect INFO logs for durable history; local console output alone
does not prove persistence. Confirm two successful `/cohort impact` requests appear
in the existing Azure Logs workspace as `cohort.measurement` events. Confirm an
unavailable read has no count fields. Verify retention and sampling before using
logs as evidence: this instrumentation is not an immutable audit ledger.

Run [cohort-measurements.kql](cohort-measurements.kql) in that workspace. The query
compares the earliest and latest valid observations within its 30-day window,
keeps source scopes separate, shows the latest read status and timestamps, and
leaves change values null when only one observation exists. The daily view uses
the last observation, never the sum of repeated snapshots. No rows means no
recorded evidence, not zero registrations. Query syntax follows Microsoft's
[AppTraces schema](https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/apptraces)
and [arg_max reference](https://learn.microsoft.com/en-us/kusto/query/arg-max-aggregation-function).
The query still requires validation against the deployed workspace.

Record a baseline after real registrations are reconciled with the intake source.
Compare the same cohort, eligibility rules and workload over a defined period.
The current aggregate stream covers the whole configured list. It cannot isolate
cohorts or prove a fixed population: additions, deletions, stage changes and
withdrawals can move the ratios. Lower overdue counts alone do not prove staff
resolved more cases. Confirm explanations in the source records before attributing
changes to this tool. Snapshot history also cannot reconstruct every transition.

## Measuring staff time and financial benefit

For comparable registration tasks, record manual processing seconds, tool-assisted
processing seconds, human review/correction seconds, records handled, and errors
requiring rework. Compare per-record time using matched tasks and report the
sample sizes and measurement dates. Include all staff handling time in both
methods; do not substitute Graph latency or estimated clicks for a timed task.

Measured capacity hours = (manual seconds per record minus assisted seconds per
record, including review and corrections) times comparable completed records / 3600.
This may be negative. Capacity value = measured hours times an agreed fully loaded
hourly rate. It is not cash savings unless spending actually falls.

Net financial benefit requires measured cash savings or attributable additional
contribution margin, less actual incremental cloud, license, implementation,
training and support costs for the same period. Azure budgets are not actual
spend or hard caps. Credits and free licenses are not savings unless they replace
an expense the organization would otherwise incur. Keep dollar results unmeasured
until the required evidence is available.

## Validation and limits

Automated tests validate denominators, test exclusion, overlapping blockers,
unavailable states, private-field exclusion, source isolation and command access.
They use synthetic fixtures. Passing tests is not a live Graph connection test,
proof of telemetry ingestion, a measured time study, or a demonstrated business gain.
