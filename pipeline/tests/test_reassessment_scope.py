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

    def test_finished_posts_do_not_call_model_even_on_refresh(self):
        src = source("Workshop September 11, 2026, 3-5 PM")
        old = decision(src)
        old["occurrences"][0].update(starts_at="2026-09-11T15:00:00-07:00", ends_at="2026-09-11T17:00:00-07:00")
        for key in ("instagram:post:past",):
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

    def test_finished_schedules_are_skipped(self):
        src = source()
        prior = {"assessment": {"result": {"schedule": {"last_day": "2026-09-11"}}}}
        self.assertTrue(publication._source_is_past(src, prior, NOW))
        prior["assessment"]["result"]["schedule"]["last_day"] = "2026-09-12"
        self.assertFalse(publication._source_is_past(src, prior, NOW))


    def test_old_upload_date_does_not_suppress_first_assessment_of_new_source(self):
        src = source()
        src["posted_at"] = "2026-06-01T12:00:00Z"
        src["source_key"] = "instagram:post:new"
        with patch.object(semantic, "assess", return_value=decision(src)) as model:
            update = publication.make_update(src, {"media_id": "new", "handle": "club", "posted_at": src["posted_at"]},
                                             {"status": "ok", "ocr_text": src["texts"]["ocr_text"]}, None, {}, NOW)
        model.assert_called_once_with(src)
        self.assertEqual(1, len(update["rows"]))

    def run_backfill(self, *flags, failed=(), successful=()):
        import extract_posts as posts
        from test_post_events import record, post_decision

        raws, events, results = [], [], {}
        for number, start, end in (
            (1, "2026-09-11T15:00:00-07:00", None),
            (2, "2026-09-12T09:00:00-07:00", None),
            (3, "2026-09-01T00:00:00-07:00", "2026-09-13T00:00:00-07:00"),
            (4, "2026-09-15T15:00:00-07:00", None),
        ):
            raw = record(media_id=str(number), slides=1)
            raw.update(shortcode=f"Post{number}", permalink=f"https://www.instagram.com/p/Post{number}/")
            raw["caption"] = f"Study Jam {start} {end or ''}"
            cached = {"status": "ok", "images": []}
            src = publication.post_source(raw, cached)
            result = post_decision(src, field="caption")
            result["occurrences"][0].update(starts_at=start, ends_at=end, all_day=number == 3)
            results[src["source_key"]] = result
            if number in failed:
                publication._save_assessment({"source": src, "source_hash": semantic.fingerprint(src),
                                              "status": "error", "retryable": False})
            if number in successful:
                publication._save_assessment({"source": src, "source_hash": semantic.fingerprint(src),
                                              "status": "complete", "result": result})
            (self.root / f"{number}.json").write_text(json.dumps(cached))
            raws.append(raw)
            events.append({"id": f"ig_saved_{number}", "source_url": raw["permalink"],
                           "starts_at": start, "ends_at": end})
        # Failed sources never got a public listing.
        events = [row for row in events if int(row["id"].rsplit("_", 1)[1]) not in failed]
        report = self.root / "report.json"
        with patch.object(publication, "datetime", FixedDatetime), \
             patch.object(publication, "load_registry", return_value={}), \
             patch("db.get_imported_events", return_value=events), \
             patch.object(publication, "load_account_meta", return_value={}), \
             patch("post_archive.hydrate_local_posts"), \
             patch("post_archive.iter_local_posts", return_value=raws), \
             patch.object(posts, "_cache_path", side_effect=lambda key: self.root / f"{key}.json"), \
             patch.object(semantic, "assess", side_effect=lambda src: results[src["source_key"]]) as model, \
             patch.object(publication, "_complete") as complete, \
             patch.object(sys, "argv", ["assessed_events.py", "--report", str(report), *flags]):
            publication.main()
        return json.loads(report.read_text()), model, complete

    def test_backfill_defaults_to_today_ongoing_and_future_without_active_flag(self):
        updates, model, _ = self.run_backfill("--refresh")
        self.assertEqual(["instagram:post:2", "instagram:post:3", "instagram:post:4"],
                         [u["source_key"] for u in updates])
        self.assertEqual(3, model.call_count)
        self.assertTrue(all(u["assessment"]["status"] == "complete" for u in updates))

    def test_explicit_source_refresh_cannot_bypass_past_date_limit(self):
        updates, model, complete = self.run_backfill("--source", "instagram:post:1", "--refresh", "--apply")
        self.assertEqual([], updates)
        model.assert_not_called()
        complete.assert_called_once_with([], notify=False)

    def test_failed_retry_requires_explicit_source_selection_before_remote_reads(self):
        with patch.object(sys, "argv", ["assessed_events.py", "--retry-failed"]), \
             patch.object(publication, "load_registry") as registry, \
             self.assertRaises(SystemExit):
            publication.main()
        registry.assert_not_called()

    def test_failed_retry_recovers_only_named_failure_without_a_listing(self):
        updates, model, complete = self.run_backfill(
            "--retry-failed", "--source", "instagram:post:2", failed=(2, 4))
        self.assertEqual(["instagram:post:2"], [u["source_key"] for u in updates])
        self.assertEqual(1, model.call_count)
        self.assertEqual("complete", updates[0]["assessment"]["status"])
        self.assertEqual(1, len(updates[0]["rows"]))
        complete.assert_not_called()
        # A preview must leave the failure selectable for a subsequent apply.
        saved = json.loads(publication._cache_path("instagram:post:2").read_text())
        self.assertEqual("error", saved["status"])

    def test_failed_retry_apply_persists_and_publishes_without_notifications(self):
        updates, model, complete = self.run_backfill(
            "--retry-failed", "--source", "instagram:post:2", "--apply", failed=(2,))
        complete.assert_called_once_with(updates, notify=False)
        saved = json.loads(publication._cache_path("instagram:post:2").read_text())
        self.assertEqual("complete", saved["status"])

    def test_failed_retry_does_not_refresh_successful_assessments(self):
        updates, model, _ = self.run_backfill("--retry-failed", "--source", "instagram:post:2", successful=(2,))
        self.assertEqual([], updates)
        model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
