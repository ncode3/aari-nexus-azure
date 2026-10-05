from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, date, datetime
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from app.bot import TelegramBotRunner
from app.cohort import CohortClient, CohortUnavailable, handle_cohort, summarize
from app.config import get_settings

BASE = get_settings()


def item(item_id="1", **overrides):
    fields = dict(Cohort="Fall", Track="Robotics", Stage="New", IsTest=False,
                  RegistrationComplete=False, ScheduleConfirmed=False,
                  TransportConfirmed=False, GuardianConsent="Pending")
    fields.update(overrides)
    return {"id": item_id, "fields": fields}


class CohortSummaryTests(unittest.TestCase):
    def test_readiness_queue_and_test_exclusion(self):
        rows = [
            item("1", RegistrationComplete=True, ScheduleConfirmed=True,
                 TransportConfirmed=True, GuardianConsent="Received"),
            item("2", NextFollowUp="2026-10-04T07:00:00Z", FollowUpOwnerLookupId="3"),
            item("3", NextFollowUp="2026-10-05T07:00:00Z"),
            item("4"), item("5", Stage="Active"), item("6", Stage="Completed"),
            item("7", Stage="Withdrawn"), item("8", IsTest=True),
        ]
        result = summarize(rows, date(2026, 10, 5))
        self.assertEqual((result.registrations, result.ready, result.followups), (7, 1, 3))
        self.assertEqual((result.overdue, result.due_today, result.undated, result.unassigned), (1, 1, 1, 2))
        self.assertEqual((result.active, result.completed, result.withdrawn), (1, 1, 1))

    def test_not_required_consent_and_string_flags(self):
        result = summarize([item(RegistrationComplete="Yes", ScheduleConfirmed=1,
                                TransportConfirmed="true", GuardianConsent="Not required", IsTest="No")], date.today())
        self.assertEqual(result.ready, 1)

    def test_missing_or_invalid_schema_is_not_zero_registrations(self):
        for rows in [[{"id": "1", "fields": {}}], [item(IsTest=None)],
                     [item(TransportConfirmed="unknown")], [item(NextFollowUp="bad-date")]]:
            with self.subTest(rows=rows), self.assertRaises(CohortUnavailable):
                summarize(rows, date.today())

    def test_empty_list_has_true_zero_count(self):
        self.assertEqual(summarize([], date.today()).registrations, 0)

    def test_groups_and_future_followup(self):
        result = summarize([item(Cohort="Fall\n2026", NextFollowUp="2026-10-10"),
                            item("2", Cohort="Spring", Track="Data center")], date(2026, 10, 5))
        self.assertEqual(result.overdue + result.due_today, 0)
        self.assertEqual(result.groups, (("Fall 2026", "Robotics", 1, 0), ("Spring", "Data center", 1, 0)))


class CohortGraphTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.settings = replace(BASE, cohort_site_id="site-id", cohort_graph_enabled=True)
        self.credential = SimpleNamespace(get_token=AsyncMock(return_value=SimpleNamespace(token="test-token")))
        self.client = CohortClient(self.settings)

    async def read(self, handler):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await self.client.read_items(client, self.credential)

    async def test_pagination_deduplication_and_minimal_fields(self):
        requests = []
        def handler(request):
            requests.append(request)
            self.assertEqual(request.method, "GET")
            self.assertEqual(request.headers["Authorization"], "Bearer test-token")
            if len(requests) == 1:
                self.assertNotIn("Title", request.url.params["$expand"])
                self.assertNotIn("FollowUpNotes", request.url.params["$expand"])
                return httpx.Response(200, json={"value": [item()], "@odata.nextLink":
                    f"https://graph.microsoft.com/v1.0/sites/site-id/lists/{BASE.cohort_list_id}/items?$skiptoken=next"})
            self.assertNotIn("$expand", request.url.params)
            return httpx.Response(200, json={"value": [item(), item("2")]})
        rows = await self.read(handler)
        self.assertEqual(len(rows), 2)
        self.credential.get_token.assert_awaited_with("https://graph.microsoft.com/.default")

    async def test_site_resolution(self):
        self.client = CohortClient(replace(self.settings, cohort_site_id=""))
        requests = []
        def handler(request):
            requests.append(request)
            if len(requests) == 1:
                self.assertIn("aari.sharepoint.com:/sites/AARICohortDesk", request.url.path)
                return httpx.Response(200, json={"id": "resolved-site"})
            self.assertIn("/sites/resolved-site/lists/", request.url.path)
            return httpx.Response(200, json={"value": []})
        self.assertEqual(await self.read(handler), [])

    async def test_upstream_errors_redact_bodies(self):
        for status in (401, 403, 404, 500, 302):
            with self.subTest(status=status), self.assertRaises(CohortUnavailable) as ctx:
                await self.read(lambda _: httpx.Response(status, text="secret-token student-name"))
            self.assertNotIn("secret-token", str(ctx.exception))
            self.assertNotIn("student-name", str(ctx.exception))

    async def test_invalid_page(self):
        for data in ({}, {"value": None}, {"value": [{}]}, [], {"value": [], "@odata.nextLink": 1}):
            with self.subTest(data=data), self.assertRaises(CohortUnavailable):
                await self.read(lambda _: httpx.Response(200, json=data))

    async def test_rejects_untrusted_next_page_without_forwarding_token(self):
        for url in ("https://evil.example/items", "https://graph.microsoft.com.evil.example/v1.0/sites/x",
                    "http://graph.microsoft.com/v1.0/sites/x", "https://user@graph.microsoft.com/v1.0/sites/x"):
            count = 0
            def handler(_):
                nonlocal count
                count += 1
                return httpx.Response(200, json={"value": [item()], "@odata.nextLink": url})
            with self.subTest(url=url), self.assertRaises(CohortUnavailable):
                await self.read(handler)
            self.assertEqual(count, 1)

    async def test_page_limit_never_reports_partial_totals(self):
        self.client = CohortClient(replace(self.settings, cohort_max_pages=1))
        with self.assertRaisesRegex(CohortUnavailable, "No partial totals"):
            await self.read(lambda _: httpx.Response(200, json={"value": [item()],
                "@odata.nextLink": "https://graph.microsoft.com/v1.0/sites/site-id/lists/list/items?next=2"}))

    async def test_repeated_pagination_fails(self):
        next_url = "https://graph.microsoft.com/v1.0/sites/site-id/lists/list/items?next=2"
        with self.assertRaisesRegex(CohortUnavailable, "repeated page"):
            await self.read(lambda _: httpx.Response(200, json={"value": [item()], "@odata.nextLink": next_url}))

    async def test_throttle_retries_bounded(self):
        calls = 0
        def handler(_):
            nonlocal calls
            calls += 1
            return httpx.Response(429, headers={"Retry-After": "0"})
        with self.assertRaises(CohortUnavailable):
            await self.read(handler)
        self.assertEqual(calls, 3)


class CohortCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_desk_requires_no_graph(self):
        client = SimpleNamespace(summary=AsyncMock(side_effect=AssertionError("Graph must not run")))
        result = await handle_cohort("desk", BASE, client)
        self.assertIn("apps.powerapps.com", result)
        self.assertIn("Follow-up queue", result)
        client.summary.assert_not_awaited()

    async def test_disabled_is_not_zero(self):
        result = await handle_cohort("", replace(BASE, cohort_graph_enabled=False))
        self.assertIn("No counts reported", result)
        self.assertNotIn("Registrations: 0", result)

    async def test_invalid_command_makes_no_request(self):
        client = SimpleNamespace(summary=AsyncMock())
        self.assertEqual(await handle_cohort("delete", BASE, client), "Usage: /cohort [summary|followups|impact|desk]")
        client.summary.assert_not_awaited()

    async def test_report_excludes_names_and_notes(self):
        summary = summarize([item(Title="Private Student", FollowUpNotes="Private notes")], date.today())
        result = await handle_cohort("summary", BASE, SimpleNamespace(summary=AsyncMock(return_value=summary)))
        self.assertIn("Registrations: 1", result)
        self.assertIn("not verified attendance or placements", result)
        self.assertNotIn("Private", result)

    async def test_followups_omits_group_table(self):
        summary = summarize([item()], date.today())
        result = await handle_cohort("followups", BASE, SimpleNamespace(summary=AsyncMock(return_value=summary)))
        self.assertIn("No date: 1 | No owner: 1", result)
        self.assertNotIn("Cohort / track", result)

    async def test_impact_denominator_excludes_closed_and_test_records(self):
        ready = dict(RegistrationComplete=True, ScheduleConfirmed=True,
                     TransportConfirmed=True, GuardianConsent="Received")
        rows = [item("1", **ready), item("2", Stage="Active"),
                item("3", Stage="Completed", **ready),
                item("4", Stage="Withdrawn", **ready), item("5", IsTest=True, **ready)]
        result = await handle_cohort("impact", BASE, SimpleNamespace(
            summary=AsyncMock(return_value=summarize(rows, date.today()))))
        self.assertIn("Current pipeline (New + Active): 2", result)
        self.assertIn("Readiness rate: 50.0%", result)
        self.assertIn("Missing registration: 1", result)
        self.assertIn("Missing schedule: 1 | Missing transport: 1", result)
        self.assertIn("Missing consent: 1", result)
        self.assertIn("Staff time saved: not measured", result)
        self.assertIn("Blocker counts overlap", result)

    async def test_empty_impact_has_no_misleading_rate(self):
        result = await handle_cohort("impact", BASE, SimpleNamespace(
            summary=AsyncMock(return_value=summarize([], date.today()))))
        self.assertIn("Not measurable: no New/Active records", result)
        self.assertNotIn("0.0%", result)

    async def test_measurement_event_has_numeric_counts_and_no_free_text(self):
        summary = summarize([item(Title="Private Student", Cohort="Private Group",
                                  Track="Private Track", FollowUpNotes="Private notes")], date.today())
        with patch("app.cohort.log_event") as log:
            await handle_cohort("impact", BASE, SimpleNamespace(summary=AsyncMock(return_value=summary)))
        event, = log.call_args.args
        fields = log.call_args.kwargs
        self.assertEqual(event, "cohort.measurement")
        self.assertEqual(fields["registrations"], 1)
        self.assertEqual(fields["status"], "available")
        self.assertIsNotNone(datetime.fromisoformat(fields["observed_at"]).tzinfo)
        self.assertNotIn("Private", str(fields))
        self.assertNotIn("groups", fields)
        self.assertNotIn(BASE.cohort_site_url, str(fields))

    async def test_unavailable_event_never_logs_counts_or_exception_details(self):
        client = SimpleNamespace(summary=AsyncMock(side_effect=CohortUnavailable("Safe reason")))
        with patch("app.cohort.log_event") as log:
            await handle_cohort("impact", BASE, client)
        self.assertEqual(log.call_args.kwargs["status"], "unavailable")
        self.assertNotIn("registrations", log.call_args.kwargs)
        self.assertNotIn("Safe reason", str(log.call_args))

    async def test_different_sources_do_not_share_measurement_scope(self):
        client = SimpleNamespace(summary=AsyncMock(return_value=summarize([], date.today())))
        keys = []
        for settings in (BASE, replace(BASE, cohort_list_id="another-list"), replace(BASE, app_env="prod")):
            with patch("app.cohort.log_event") as log:
                await handle_cohort("impact", settings, client)
            keys.append(log.call_args.kwargs["source_key"])
        self.assertEqual(len(set(keys)), 3)

    async def test_unknown_stage_cannot_silently_change_denominator(self):
        with self.assertRaisesRegex(CohortUnavailable, "invalid stage"):
            summarize([item(Stage="unknown")], date.today())

    async def test_large_summary_fits_telegram_limit(self):
        rows = [item(str(i), Cohort=str(i) * 100, Track="R" * 100) for i in range(100)]
        summary = summarize(rows, date.today())
        result = await handle_cohort("", BASE, SimpleNamespace(summary=AsyncMock(return_value=summary)))
        self.assertLess(len(result), 4096)
        self.assertIn("more groups", result)

    async def test_allowlist_and_routing(self):
        for command, mode in [("/cohort summary", "summary"), ("/today", "followups"), ("/metrics", "impact")]:
            await self.check_allowlist_and_routing(command, mode)

    async def check_allowlist_and_routing(self, command, mode):
        for allowed, chat_id, accepted in [(set(), 42, False), ({42}, 43, False), ({42}, 42, True)]:
            with self.subTest(command=command, allowed=allowed, chat_id=chat_id), TemporaryDirectory() as tmp:
                settings = replace(BASE, bot_allowed_chat_ids=allowed, nexus_memory_path=tmp + "/memory.db")
                runner = TelegramBotRunner(settings, None, None, datetime.now(UTC))
                runner._send_message = AsyncMock()
                with patch("app.bot.handle_cohort", new=AsyncMock(return_value="cohort result")) as handler:
                    await runner._handle_update(None, {"message": {"chat": {"id": chat_id}, "text": command}})
                    self.assertEqual(handler.await_count, int(accepted))
                    if accepted:
                        handler.assert_awaited_once_with(mode, settings)
                        runner._send_message.assert_awaited_once_with(None, chat_id, "cohort result")


if __name__ == "__main__":
    unittest.main()
