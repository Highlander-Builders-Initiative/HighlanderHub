"""Deleted-post recheck: who is looked up, what counts as deleted, what is withdrawn."""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

import post_recheck as pr  # noqa: E402
import apify_posts as apify  # noqa: E402
from retire_apify_recheck import retire  # noqa: E402
from requests.exceptions import HTTPError  # noqa: E402

NOW = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)


def event(eid, days):
    return {"id": eid, "starts_at": (NOW + timedelta(days=days)).isoformat()}


def source(*ids, **assessment):
    return {"event_ids": list(ids), "assessment": {"status": "complete", **assessment}}


class DueSources(unittest.TestCase):
    def test_only_listings_starting_within_the_window_are_due(self):
        events = [event("soon", 2), event("later", 5), event("past", -1)]
        registry = {"instagram:post:1": source("soon"), "instagram:post:2": source("later"),
                    "instagram:post:3": source("past")}
        self.assertEqual({"instagram:post:1": ["soon"]}, pr.due_sources(events, registry, {}, NOW))

    def test_checked_withdrawn_and_cooling_posts_are_skipped(self):
        events = [event(i, 1) for i in "abcd"]
        registry = {"instagram:post:1": source("a"), "instagram:post:2": source("b", deleted=True),
                    "instagram:post:3": source("c"), "instagram:post:4": source("d")}
        state = {"1": {"status": "present"},
                 "3": {"status": "missing", "checked_at": (NOW - timedelta(hours=1)).isoformat()},
                 "4": {"status": "missing", "checked_at": (NOW - timedelta(hours=9)).isoformat()}}
        self.assertEqual(["instagram:post:4"], list(pr.due_sources(events, registry, state, NOW)))


class Classify(unittest.TestCase):
    def test_present_and_explicitly_deleted(self):
        rows = [{"kind": "post", "data": {"code": "AAA"}},
                {"kind": "post", "input": "https://www.instagram.com/p/BBB/",
                 "error": "Deleted or restricted post"}]
        self.assertEqual({"AAA": "present", "BBB": "missing"}, pr.classify(rows, {"AAA", "BBB"}))

    def test_unrecognised_failures_are_unknown_not_deleted(self):
        rows = [{"kind": "post", "input": "https://www.instagram.com/p/AAA/", "error": "Rate limited"},
                {"kind": "post", "data": None}]
        self.assertEqual({}, pr.classify(rows, {"AAA", "BBB"}))


class Withdrawal(unittest.TestCase):
    def test_publishes_nothing_and_marks_the_source_deleted(self):
        update = pr.withdrawal("instagram:post:9", source("ig_x_p9"), NOW)
        self.assertEqual([], update["rows"])
        self.assertEqual(["ig_x_p9"], update["known_event_ids"])
        self.assertTrue(update["assessment"]["deleted"])
        self.assertEqual("complete", update["assessment"]["status"])


class RecheckIntegration(unittest.TestCase):
    """Exercise real batching, paid-run recovery and durable check state."""

    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.state_file = Path(directory) / "state.json"
        self.run_file = Path(directory) / "recheck.json"
        self.details_file = Path(directory) / "recheck-details.json"
        self.enterContext(patch.object(pr, "STATE_FILE", self.state_file))
        self.enterContext(patch.object(pr, "RUN_FILE", self.run_file))
        self.enterContext(patch.dict(pr.os.environ, {"APIFY_TOKEN": "test"}))
        self.clock = self.enterContext(patch.object(pr, "datetime", wraps=datetime))
        self.clock.now.return_value = NOW
        self.events = []
        self.registry = {}
        self.codes = {}
        self.database = MagicMock()
        query = self.database.table.return_value.select.return_value.eq.return_value
        query.gte.return_value.lte.return_value.execute.return_value.data = self.events
        self.enterContext(patch("db.client", return_value=self.database))
        self.enterContext(patch("assessed_events.load_registry", return_value=self.registry))
        self.publish = self.enterContext(patch("assessed_events.publish"))
        self.enterContext(patch.object(pr, "shortcodes", side_effect=lambda ids: {
            key: self.codes[key] for key in ids if key in self.codes}))
        self.purchases = []
        self.runs = {}
        self.datasets = {}
        self.requests = []
        self.response_rows = None
        self.fail_purchase = None
        self.fail_dataset = None
        self.run_updates = {}
        self.enterContext(patch.object(apify.ApifyClient, "request", new=self.request))

    def add_posts(self, count, offset=0):
        for i in range(offset, offset + count):
            key = str(i)
            self.codes[key] = f"POST_{i:03d}"
            self.events.append(event(key, 2))
            self.registry[f"instagram:post:{key}"] = source(key)

    def request(self, method, path, **kwargs):
        self.requests.append((method, path))
        if method == "POST":
            if len(self.purchases) == self.fail_purchase:
                raise TimeoutError("ambiguous paid start")
            codes = [url.rsplit("/", 2)[1] for url in kwargs["json"]["posts"]]
            run_id = str(len(self.purchases))
            self.purchases.append(codes)
            self.datasets[run_id] = (self.response_rows if self.response_rows is not None else
                                     [{"kind": "post", "data": {"code": code}} for code in codes])
            run = {"id": run_id, "actId": apify.HPIX_ACTOR_ID, "status": "SUCCEEDED",
                   "startedAt": NOW.isoformat(), "defaultDatasetId": run_id,
                   "options": {"maxTotalChargeUsd": kwargs["params"]["maxTotalChargeUsd"]},
                   "chargedEventCounts": {"individual_post_scraped": len(codes), "apify-actor-start": 1},
                   "pricingInfo": {"pricingPerEvent": {"actorChargeEvents": {
                       "individual_post_scraped": {"eventPriceUsd": .00149},
                       "apify-actor-start": {"eventPriceUsd": .00005}}}}}
            run.update(self.run_updates)
            self.runs[run_id] = run
            return {"data": run}
        if path.startswith("actor-runs/"):
            return {"data": self.runs[path.split("/")[1]]}
        if path.startswith("datasets/"):
            if path.split("/")[1] == self.fail_dataset:
                raise RuntimeError("dataset temporarily unavailable")
            return self.datasets[path.split("/")[1]]
        raise AssertionError((method, path))

    def test_distinct_batches_and_later_cycle_do_not_recheck_present_posts(self):
        self.add_posts(60)
        pr.main()
        self.assertEqual([50, 10], [len(batch) for batch in self.purchases])
        self.assertEqual(60, len(set(code for batch in self.purchases for code in batch)))
        self.assertEqual(60, len(pr.read_json(self.state_file)))
        pr.main()
        self.assertEqual(2, len(self.purchases))
        self.add_posts(1, offset=60)
        pr.main()
        self.assertEqual(["POST_060"], self.purchases[-1])

    def test_completed_legacy_list_does_not_replace_new_work(self):
        pr.write_json(self.details_file, {"consumed": True, "usernames": ["EXPIRED"]})
        self.add_posts(1)
        pr.main()
        self.assertEqual([["POST_000"]], self.purchases)

    def test_account_switch_requires_explicit_retirement_before_replacement_purchase(self):
        self.add_posts(2)
        self.run_file = self.run_file.with_name("post_recheck_run.json")
        self.details_file = self.run_file.with_name("post_recheck_run-details.json")
        self.enterContext(patch.object(pr, "RUN_FILE", self.run_file))
        pr.write_json(self.details_file, {"id": "oldRun", "consumed": False,
                                        "usernames": ["POST_000"]})
        pr.write_json(self.state_file, {"1": {"status": "present", "run_id": "completed"}})

        def forbidden(method, path, **kwargs):
            if path == "actor-runs/oldRun":
                raise HTTPError("403 Forbidden")
            return self.request(method, path, **kwargs)

        with patch.object(apify.ApifyClient, "request", side_effect=forbidden):
            with self.assertRaisesRegex(HTTPError, "403 Forbidden"):
                pr.main()
        self.assertEqual([], self.purchases)
        self.publish.assert_not_called()
        backup = retire(self.run_file.parent, "oldRun")
        pr.main()
        self.assertEqual([["POST_000"]], self.purchases)
        state = pr.read_json(self.state_file)
        self.assertEqual("present", state["0"]["status"])
        self.assertEqual({"status": "present", "run_id": "completed"}, state["1"])
        self.assertEqual("oldRun", pr.read_json(backup)["id"])
        self.publish.assert_not_called()

    def test_state_write_failure_replays_paid_run_without_another_purchase(self):
        self.add_posts(1)
        write = pr.write_json
        def fail_state(path, value):
            if path == self.state_file:
                raise OSError("disk unavailable")
            write(path, value)
        with patch.object(pr, "write_json", side_effect=fail_state):
            with self.assertRaises(OSError):
                pr.main()
        self.assertFalse(pr.read_json(self.details_file)["consumed"])
        pr.main()
        self.assertEqual(1, len(self.purchases))
        self.assertEqual("present", pr.read_json(self.state_file)["0"]["status"])

    def test_later_batch_failure_keeps_completed_checks(self):
        self.add_posts(60)
        self.fail_purchase = 1
        with self.assertRaises(TimeoutError):
            pr.main()
        self.assertEqual(50, len(pr.read_json(self.state_file)))
        with self.assertRaisesRegex(RuntimeError, "outcome unknown"):
            pr.main()
        self.assertEqual(1, len(self.purchases))

    def test_pending_paid_run_is_consumed_even_when_its_events_expired(self):
        self.add_posts(1)
        with patch.object(pr, "write_json", side_effect=OSError("disk unavailable")):
            with self.assertRaises(OSError):
                pr.main()
        self.events.clear()
        pr.main()
        self.assertEqual(1, len(self.purchases))
        self.assertTrue(pr.read_json(self.details_file)["consumed"])

    def test_second_batch_resumes_original_list_after_due_work_changes(self):
        self.add_posts(60)
        self.fail_dataset = "1"
        with self.assertRaisesRegex(RuntimeError, "dataset temporarily unavailable"):
            pr.main()
        self.assertEqual(50, len(pr.read_json(self.state_file)))
        self.add_posts(1, offset=60)
        self.fail_dataset = None
        pr.main()
        self.assertEqual([50, 10, 1], [len(batch) for batch in self.purchases])
        self.assertEqual(["POST_060"], self.purchases[-1])
        self.assertEqual(61, len(pr.read_json(self.state_file)))

    def test_failed_or_charge_limited_run_is_not_consumed_or_rebought(self):
        self.add_posts(60)
        for changes in ({"status": "FAILED"}, {"options": {"maxTotalChargeUsd": .05}}):
            with self.subTest(changes=changes):
                self.run_updates = changes
                if self.details_file.exists():
                    self.details_file.unlink()
                before = len(self.purchases)
                with self.assertRaises(RuntimeError):
                    pr.main()
                self.assertFalse(pr.read_json(self.details_file)["consumed"])
                with self.assertRaises(RuntimeError):
                    pr.main()
                self.assertEqual(before + 1, len(self.purchases))
                self.assertFalse(self.state_file.exists())

    def test_withdrawal_failure_replays_paid_results_before_marking_withdrawn(self):
        self.add_posts(1)
        pr.write_json(self.state_file, {"0": {"status": "missing", "misses": 1,
                      "checked_at": (NOW - timedelta(hours=8)).isoformat(), "run_id": "old"}})
        self.response_rows = [{"kind": "post", "input": "https://www.instagram.com/p/POST_000/",
                               "error": "Post deleted"}]
        self.publish.side_effect = RuntimeError("database unavailable")
        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            pr.main()
        self.assertEqual("missing", pr.read_json(self.state_file)["0"]["status"])
        self.assertFalse(pr.read_json(self.details_file)["consumed"])
        self.publish.side_effect = None
        pr.main()
        self.assertEqual(1, len(self.purchases))
        self.assertEqual("withdrawn", pr.read_json(self.state_file)["0"]["status"])

    def test_matching_rate_limit_stays_unknown_without_withdrawing(self):
        self.add_posts(1)
        self.response_rows = [{"input": "https://www.instagram.com/p/POST_000/", "error": "Rate limited"}]
        pr.main()
        self.assertEqual({}, pr.read_json(self.state_file))
        self.assertTrue(pr.read_json(self.details_file)["consumed"])
        self.publish.assert_not_called()

    def test_unrelated_or_empty_output_stops_without_buying_more_batches(self):
        self.add_posts(60)
        for rows in ([{"kind": "post", "data": {"code": "UNRELATED"}}], []):
            with self.subTest(rows=rows):
                self.response_rows = rows
                if self.details_file.exists():
                    self.details_file.unlink()
                before = len(self.purchases)
                with self.assertRaisesRegex(RuntimeError, "output"):
                    pr.main()
                self.assertEqual(before + 1, len(self.purchases))
                with self.assertRaisesRegex(RuntimeError, "output"):
                    pr.main()
                self.assertEqual(before + 1, len(self.purchases))
                self.assertFalse(self.state_file.exists())

    def test_missing_confirmation_is_not_counted_twice_after_consumption_write_failure(self):
        self.add_posts(1)
        self.response_rows = [{"kind": "post", "input": "https://www.instagram.com/p/POST_000/",
                               "error": "Post deleted"}]
        write = pr.write_json
        def fail_consumption(path, value):
            if path == self.details_file and value.get("consumed"):
                raise OSError("disk unavailable")
            write(path, value)
        with patch.object(pr, "write_json", side_effect=fail_consumption):
            with self.assertRaises(OSError):
                pr.main()
        self.clock.now.return_value = NOW + timedelta(hours=8)
        pr.main()
        self.assertEqual(1, len(self.purchases))
        self.assertEqual(1, pr.read_json(self.state_file)["0"]["misses"])
        self.publish.assert_not_called()
        pr.main()
        self.assertEqual(2, len(self.purchases))
        self.assertEqual("withdrawn", pr.read_json(self.state_file)["0"]["status"])
        self.publish.assert_called_once()


if __name__ == "__main__":
    unittest.main()
