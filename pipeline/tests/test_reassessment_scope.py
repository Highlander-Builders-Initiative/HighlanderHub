"""Keep paid reassessment scoped to today's/future event dates."""
import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import assessed_events as publication
import content_assessment as semantic
from test_content_assessment import source, decision

NOW = "2026-09-12T20:00:00+00:00"


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls.fromisoformat(NOW).astimezone(tz or timezone.utc)


class ReassessmentScopeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        cache = patch.object(publication, "CACHE_DIR", self.root / "assessments")
        cache.start()
        self.addCleanup(cache.stop)

    def test_campus_date_uses_end_date_and_exclusive_midnight(self):
        for row, expected in (
            ({"starts_at": "2026-09-11T23:00:00-07:00"}, False),
            ({"starts_at": "2026-09-12T00:00:00-07:00"}, True),
            ({"starts_at": "2026-09-12T09:00:00-07:00", "ends_at": "2026-09-12T10:00:00-07:00"}, True),
            ({"starts_at": "2026-09-01T00:00:00-07:00", "ends_at": "2026-09-13T00:00:00-07:00"}, True),
            ({"starts_at": "2026-09-11T00:00:00-07:00", "ends_at": "2026-09-12T00:00:00-07:00"}, False),
            ({"starts_at": "2026-09-12T06:30:00Z"}, False),
            ({"starts_at": "2026-09-13T00:30:00Z"}, True),
            ({"starts_at": "2026-10-01T09:00:00-07:00", "ends_at": None}, True),
            ({"starts_at": "invalid"}, None),
            ({}, None),
        ):
            with self.subTest(row=row):
                self.assertIs(expected, publication._event_relevance(row, NOW))

    def test_finished_stories_and_posts_do_not_call_model_even_on_refresh(self):
        src = source("Workshop September 11, 2026, 3-5 PM")
        old = decision(src)
        old["occurrences"][0].update(starts_at="2026-09-11T15:00:00-07:00", ends_at="2026-09-11T17:00:00-07:00")
        for key in ("instagram:past", "instagram:post:past"):
            for refresh in (False, True):
                with self.subTest(key=key, refresh=refresh):
                    src["source_key"] = key
                    prior = {"assessment": {"status": "error", "retryable": True},
                             "last_complete_assessment": {"status": "complete", "result": old}}
                    before = copy.deepcopy(prior)
                    with patch.object(semantic, "assess") as model:
                        stats = {}
                        self.assertIsNone(publication.make_update(src, {}, {}, prior, {}, NOW, stats, refresh=refresh))
                        model.assert_not_called()
                    self.assertEqual({"past_sources_skipped": 1}, stats)
                    self.assertEqual(before, prior)

    def test_legacy_dates_and_finished_schedules_are_skipped(self):
        src = source()
        self.assertTrue(publication._source_is_past(src, {"result": {"starts_at": "2026-09-11T15:00:00-07:00"}}, None, NOW))
        prior = {"assessment": {"result": {"schedule": {"last_day": "2026-09-11"}}}}
        self.assertTrue(publication._source_is_past(src, None, prior, NOW))
        prior["assessment"]["result"]["schedule"]["last_day"] = "2026-09-12"
        self.assertFalse(publication._source_is_past(src, None, prior, NOW))

    def test_new_structured_dates_override_an_old_finished_assessment(self):
        src = source()
        src["source_occurrences"] = [{"starts_at": "2026-09-15T15:00:00-07:00"}]
        prior = {"assessment": {"result": {"occurrences": [{"starts_at": "2026-09-11T15:00:00-07:00"}]}}}
        self.assertFalse(publication._source_is_past(src, None, prior, NOW))
        src["source_occurrences"].append({"starts_at": "2026-09-10T15:00:00-07:00"})
        self.assertFalse(publication._source_is_past(src, None, prior, NOW))

    def test_old_upload_date_does_not_suppress_first_assessment_of_new_source(self):
        src = source()
        src["posted_at"] = "2026-06-01T12:00:00Z"
        with patch.object(semantic, "assess", return_value=decision(src)) as model:
            update = publication.make_update(src, {"id": "new", "handle": "club", "posted_at": src["posted_at"]},
                                             {"status": "ok", "ocr_text": src["texts"]["ocr_text"]}, None, {}, NOW)
        model.assert_called_once_with(src)
        self.assertEqual(1, len(update["rows"]))

    def test_skipped_structured_source_is_present_not_a_withdrawal(self):
        raw = {"id": 1, "title": "Old workshop", "first_date": "2026-09-11T15:00:00-07:00"}
        registry = {"localist:1": {"origin": "localist", "event_ids": ["ucr_events_1"]}}
        with patch.object(publication, "load_registry", return_value=registry), \
             patch("db.get_imported_events", return_value=[{"id": "ucr_events_1"}]), \
             patch.object(publication, "_complete") as complete, \
             patch.object(semantic, "assess") as model:
            publication.publish_structured([("localist", raw)], {"ucr_events_"}, NOW, notify=False)
        model.assert_not_called()
        complete.assert_called_once_with([], notify=False)

    def run_backfill(self, *flags):
        import extract_stories as stories
        import normalize_events as structured
        raw = [{"id": number, "title": "Workshop", "description_text": "Student workshop",
                "first_date": start, "last_date": end, "filters": {"event_audience": [{"name": "Students"}]}}
               for number, start, end in (
                   (1, "2026-09-11T15:00:00-07:00", None),
                   (2, "2026-09-12T09:00:00-07:00", None),
                   (3, "2026-09-01T00:00:00-07:00", "2026-09-13T00:00:00-07:00"),
                   (4, "2026-09-15T15:00:00-07:00", None))]
        events = [{"id": f"ucr_events_{r['id']}", "starts_at": r["first_date"], "ends_at": r["last_date"]} for r in raw]
        report = self.root / "report.json"
        # Use the real source mapper, cache boundary and row builder. No model
        # or database access is needed to verify which sources reach them.
        def assess(src):
            return {"kind": "activity", "date_role": "occurrence", "reason": "Student workshop",
                    "activity_evidence": [{"field": "description", "quote": "Student workshop"}],
                    "date_evidence": [{"field": "dates", "quote": src["texts"]["dates"]}],
                    "use_source_occurrences": True, "occurrences": [], "schedule": None}
        with patch.object(publication, "datetime", FixedDatetime), \
             patch.object(publication, "load_registry", return_value={}), \
             patch("db.get_imported_events", return_value=events), \
             patch.object(stories, "RAW_DIR", self.root / "empty"), \
             patch.object(stories, "_load_account_meta", return_value={}), \
             patch("post_archive.hydrate_local_posts"), \
             patch("post_archive.iter_local_posts", return_value=[]), \
             patch.object(structured, "_collect_raw", side_effect=[raw, []]), \
             patch.object(semantic, "assess", side_effect=assess) as model, \
             patch.object(publication, "_complete") as complete, \
             patch.object(sys, "argv", ["assessed_events.py", "--report", str(report), *flags]):
            publication.main()
        return json.loads(report.read_text()), model, complete

    def test_backfill_defaults_to_today_ongoing_and_future_without_active_flag(self):
        updates, model, _ = self.run_backfill("--refresh")
        self.assertEqual(["localist:2", "localist:3", "localist:4"], [u["source_key"] for u in updates])
        self.assertEqual(3, model.call_count)

    def test_explicit_source_refresh_cannot_bypass_past_date_limit(self):
        updates, model, complete = self.run_backfill("--source", "localist:1", "--refresh", "--apply")
        self.assertEqual([], updates)
        model.assert_not_called()
        complete.assert_called_once_with([], notify=False)


if __name__ == "__main__":
    unittest.main()
