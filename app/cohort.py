"""Read-only Cohort Desk reporting. No participant names or model calls."""
from __future__ import annotations

import asyncio
import hashlib
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo

import httpx
from azure.identity.aio import DefaultAzureCredential

from app.config import Settings
from app.telemetry import log_event

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"
# Deliberately exclude Title, notes, attachments, contact details and consent documents.
REPORT_FIELDS = (
    "Cohort", "Track", "Stage", "IsTest", "RegistrationComplete",
    "ScheduleConfirmed", "TransportConfirmed", "GuardianConsent",
    "NextFollowUp", "FollowUpOwnerLookupId",
)
REQUIRED_FIELDS = {
    "IsTest", "Stage", "RegistrationComplete", "ScheduleConfirmed",
    "TransportConfirmed", "GuardianConsent",
}


class CohortUnavailable(Exception):
    """Safe reason suitable for a user response; never includes upstream bodies."""


def _flag(value: object) -> bool:
    if value is True or value == 1 or str(value).strip().lower() in {"true", "yes"}:
        return True
    if value is False or value == 0 or str(value).strip().lower() in {"false", "no"}:
        return False
    raise CohortUnavailable("The registration list contains an invalid readiness or test flag.")


def _label(value: object, default: str = "Unassigned") -> str:
    return " ".join(str(value or default).split())[:80]


@dataclass(frozen=True)
class CohortSummary:
    registrations: int
    ready: int
    active: int
    completed: int
    withdrawn: int
    followups: int
    overdue: int
    due_today: int
    undated: int
    unassigned: int
    pipeline: int
    pipeline_ready: int
    missing_registration: int
    missing_schedule: int
    missing_transport: int
    missing_consent: int
    groups: tuple[tuple[str, str, int, int], ...]


def summarize(items: list[dict], today: date) -> CohortSummary:
    rows = []
    for item in items:
        fields = item.get("fields")
        if not isinstance(fields, dict) or not REQUIRED_FIELDS <= fields.keys():
            raise CohortUnavailable("The registration list schema is incomplete. Check the Cohort Desk field mapping.")
        if _flag(fields["IsTest"]):
            continue
        if fields["Stage"] not in {"New", "Active", "Completed", "Withdrawn"}:
            raise CohortUnavailable("The registration list contains an invalid stage.")
        flags = [_flag(fields[name]) for name in ("RegistrationComplete", "ScheduleConfirmed", "TransportConfirmed")]
        ready = all(flags) and fields["GuardianConsent"] in {"Received", "Not required"}
        rows.append((fields, ready))

    stages = Counter(row["Stage"] for row, _ in rows)
    pending = [row for row, ready in rows if row["Stage"] == "New" and not ready]
    pipeline = [(row, ready) for row, ready in rows if row["Stage"] in {"New", "Active"}]
    overdue = due_today = undated = unassigned = 0
    for row in pending:
        value = row.get("NextFollowUp")
        if not value:
            undated += 1
        else:
            try:
                # SharePoint date-only column: retain the stored calendar date.
                due = date.fromisoformat(str(value)[:10])
            except ValueError as exc:
                raise CohortUnavailable("A follow-up date is invalid. Review dates in Cohort Desk.") from exc
            overdue += due < today
            due_today += due == today
        unassigned += not bool(row.get("FollowUpOwnerLookupId"))
    groups: dict[tuple[str, str], list[int]] = {}
    for row, ready in rows:
        key = (_label(row.get("Cohort")), _label(row.get("Track")))
        counts = groups.setdefault(key, [0, 0])
        counts[0] += 1
        counts[1] += ready
    return CohortSummary(
        registrations=len(rows), ready=sum(ready for _, ready in rows),
        active=stages["Active"], completed=stages["Completed"], withdrawn=stages["Withdrawn"],
        followups=len(pending), overdue=overdue, due_today=due_today,
        undated=undated, unassigned=unassigned,
        pipeline=len(pipeline), pipeline_ready=sum(ready for _, ready in pipeline),
        missing_registration=sum(not _flag(row["RegistrationComplete"]) for row, _ in pipeline),
        missing_schedule=sum(not _flag(row["ScheduleConfirmed"]) for row, _ in pipeline),
        missing_transport=sum(not _flag(row["TransportConfirmed"]) for row, _ in pipeline),
        missing_consent=sum(row["GuardianConsent"] not in {"Received", "Not required"} for row, _ in pipeline),
        groups=tuple((cohort, track, *counts) for (cohort, track), counts in sorted(groups.items())),
    )


class CohortClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def _get(self, client: httpx.AsyncClient, credential, url: str, params: dict | None = None) -> dict:
        parsed = urlparse(url)
        if (parsed.scheme != "https" or parsed.netloc != "graph.microsoft.com"
                or not parsed.path.startswith("/v1.0/sites/") or parsed.fragment):
            raise CohortUnavailable("Microsoft returned an unexpected pagination link.")
        for attempt in range(3):
            token = await credential.get_token(GRAPH_SCOPE)
            response = await client.get(url, params=params, headers={"Authorization": f"Bearer {token.token}"})
            if response.status_code in {429, 503, 504} and attempt < 2:
                try:
                    delay = min(3.0, max(0.0, float(response.headers.get("Retry-After", "1"))))
                except ValueError:
                    delay = 1.0
                await asyncio.sleep(delay)
                continue
            if response.status_code in {401, 403}:
                raise CohortUnavailable("Nexus does not have read access to the Cohort Desk list.")
            if response.status_code == 404:
                raise CohortUnavailable("The configured Cohort Desk site or list was not found.")
            if response.status_code >= 400 or response.is_redirect:
                raise CohortUnavailable("Microsoft Graph is unavailable. Try again shortly.")
            try:
                data = response.json()
            except ValueError as exc:
                raise CohortUnavailable("Microsoft returned an invalid response.") from exc
            if not isinstance(data, dict):
                raise CohortUnavailable("Microsoft returned an invalid response.")
            return data
        raise CohortUnavailable("Microsoft Graph is unavailable. Try again shortly.")

    async def read_items(self, client: httpx.AsyncClient, credential) -> list[dict]:
        site_id = self.settings.cohort_site_id
        if not site_id:
            site = urlparse(self.settings.cohort_site_url)
            if site.scheme != "https" or not site.hostname or not site.hostname.endswith(".sharepoint.com"):
                raise CohortUnavailable("The configured Cohort Desk site URL is invalid.")
            resolved = await self._get(client, credential,
                f"{GRAPH_ROOT}/sites/{quote(site.hostname, safe='')}:{quote(site.path.rstrip('/'), safe='/')}",
                {"$select": "id"})
            site_id = resolved.get("id")
            if not isinstance(site_id, str) or not site_id:
                raise CohortUnavailable("Microsoft did not return a SharePoint site ID.")
        url = f"{GRAPH_ROOT}/sites/{quote(site_id, safe=',')}/lists/{quote(self.settings.cohort_list_id, safe='')}/items"
        params = {"$expand": f"fields($select={','.join(REPORT_FIELDS)})", "$top": "200"}
        items: dict[str, dict] = {}
        visited: set[str] = set()
        for _ in range(self.settings.cohort_max_pages):
            if url in visited:
                raise CohortUnavailable("Microsoft returned a repeated page. No partial totals were reported.")
            visited.add(url)
            body = await self._get(client, credential, url, params)
            page = body.get("value")
            if not isinstance(page, list):
                raise CohortUnavailable("Microsoft returned an incomplete registration page.")
            for item in page:
                if not isinstance(item, dict) or not item.get("id"):
                    raise CohortUnavailable("Microsoft returned an invalid registration record.")
                items[str(item["id"])] = item
            next_url = body.get("@odata.nextLink")
            if not next_url:
                return list(items.values())
            if not isinstance(next_url, str):
                raise CohortUnavailable("Microsoft returned an invalid pagination link.")
            url, params = next_url, None
        raise CohortUnavailable("The registration list exceeds the configured page limit. No partial totals were reported.")

    async def summary(self) -> CohortSummary:
        if not self.settings.cohort_graph_enabled:
            raise CohortUnavailable("Live reporting is not enabled on this Nexus deployment.")
        try:
            async with asyncio.timeout(30):
                async with DefaultAzureCredential(
                    managed_identity_client_id=self.settings.azure_client_id,
                    exclude_interactive_browser_credential=True,
                ) as credential, httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                    items = await self.read_items(client, credential)
            return summarize(items, datetime.now(ZoneInfo("America/New_York")).date())
        except CohortUnavailable:
            raise
        except Exception as exc:
            # Credentials, tenant errors, headers and response bodies must not reach chat/logs.
            raise CohortUnavailable("The live SharePoint connection could not be verified. Check Nexus identity and connectivity.") from exc


def desk_links(settings: Settings) -> str:
    return "\n".join([
        "Cohort Desk: " + settings.cohort_app_url,
        "Follow-up queue: " + settings.cohort_queue_url,
        "Cohort summary: " + settings.cohort_summary_url,
    ])


async def handle_cohort(payload: str, settings: Settings, client: CohortClient | None = None) -> str:
    mode = payload.strip().lower()
    if mode not in {"", "summary", "followups", "impact", "desk"}:
        return "Usage: /cohort [summary|followups|impact|desk]"
    if mode == "desk":
        return desk_links(settings)
    source_key = hashlib.sha256("|".join((settings.app_env, settings.cohort_site_url.rstrip("/"),
                                        settings.cohort_list_id)).encode()).hexdigest()[:16]
    started = time.perf_counter()
    try:
        result = await (client or CohortClient(settings)).summary()
    except CohortUnavailable as exc:
        log_event("cohort.measurement", schema_version=1, source_key=source_key,
                  status="unavailable", read_seconds=round(time.perf_counter() - started, 3))
        return f"Cohort Desk reporting unavailable: {exc}\nNo counts reported.\n\n{desk_links(settings)}"
    observed_at = datetime.now(UTC).isoformat()
    # Explicit numeric allowlist: never serialize groups, raw rows, names or notes.
    measurements = {name: getattr(result, name) for name in (
        "registrations", "ready", "active", "completed", "withdrawn", "followups",
        "overdue", "due_today", "undated", "unassigned", "pipeline", "pipeline_ready",
        "missing_registration", "missing_schedule", "missing_transport", "missing_consent",
    )}
    log_event("cohort.measurement", schema_version=1, source_key=source_key,
              status="available", observed_at=observed_at,
              read_seconds=round(time.perf_counter() - started, 3), **measurements)
    lines = ["AARI Cohort Desk", "Source: live SharePoint registrations; test records excluded.",
             "Applications count after reaching SharePoint; enrollment still requires staff verification.",
             f"Observed: {observed_at}"]
    if mode == "impact":
        readiness = (f"{100 * result.pipeline_ready / result.pipeline:.1f}%"
                     if result.pipeline else "Not measurable: no New/Active records")
        lines += [f"Current pipeline (New + Active): {result.pipeline}",
                  f"Ready in pipeline: {result.pipeline_ready} | Readiness rate: {readiness}",
                  f"Missing registration: {result.missing_registration}",
                  f"Missing schedule: {result.missing_schedule} | Missing transport: {result.missing_transport}",
                  f"Missing consent: {result.missing_consent}",
                  "Blocker counts overlap; one registration can have several blockers.",
                  "Staff time saved: not measured. Added revenue: not measured.",
                  "Attendance/placements: not measured. Net financial benefit: not measured.",
                  "This snapshot alone does not establish improvement or causation."]
    elif mode != "followups":
        lines += [f"Registrations: {result.registrations} | Ready: {result.ready}",
                  f"Active: {result.active} | Completed: {result.completed} | Withdrawn: {result.withdrawn}",
                  "Counts are registration records, not verified attendance or placements."]
        if result.groups:
            lines.append("\nCohort / track: registrations, ready")
            for cohort, track, total, ready in result.groups[:10]:
                lines.append(f"{cohort} / {track}: {total}, {ready} ready")
            if len(result.groups) > 10:
                lines.append(f"{len(result.groups) - 10} more groups in Cohort summary.")
    lines += [f"\nFollow-up queue (New + Pending): {result.followups}",
              f"Overdue: {result.overdue} | Due today: {result.due_today}",
              f"No date: {result.undated} | No owner: {result.unassigned}",
              "Dates use America/New_York.", "", desk_links(settings)]
    return "\n".join(lines)
