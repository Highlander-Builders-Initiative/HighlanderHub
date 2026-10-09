"""Deleted-post recheck: who is looked up, what counts as deleted, what is withdrawn."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

import post_recheck as pr  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
