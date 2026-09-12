"""Assessment caching, source adaptation, and publication-boundary regressions."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import assessed_events as publication
import content_assessment as semantic
from test_content_assessment import source, decision


class AssessmentCacheTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.cache = patch.object(publication, "CACHE_DIR", Path(directory.name))
        self.cache.start()
        self.addCleanup(self.cache.stop)

    def test_version_source_and_model_invalidate_semantics_without_touching_ocr(self):
        src = source()
        with patch.object(semantic, "assess", side_effect=lambda item: decision(item)) as model:
            first = publication.cached_assessment(src)
            self.assertEqual(first, publication.cached_assessment(src))
            self.assertEqual(1, model.call_count)
            with patch.object(semantic, "VERSION", semantic.VERSION+1):
                publication.cached_assessment(src)
            self.assertEqual(2, model.call_count)
            with patch.object(semantic, "MODEL", "changed-model"):
                publication.cached_assessment(src)
            self.assertEqual(3, model.call_count)
            changed = copy.deepcopy(src)
            changed["texts"]["ocr_text"] += " Bring a notebook."
            publication.cached_assessment(changed)
            self.assertEqual(4, model.call_count)

    def test_remote_assessment_is_revalidated_and_reused(self):
        src = source()
        prior = {"status":"complete", "model":semantic.MODEL, "version":semantic.VERSION,
                 "source_hash":semantic.fingerprint(src), "source":src, "result":decision(src)}
        with patch.object(semantic, "assess") as model:
            self.assertEqual(prior, publication.cached_assessment(src, prior))
            model.assert_not_called()

    def test_failure_is_not_a_negative_decision_and_retries(self):
        src = source()
        with patch.object(semantic, "assess", side_effect=[RuntimeError("unavailable"), decision(src)]) as model:
            failure = publication.cached_assessment(src)
            self.assertEqual("error", failure["status"])
            self.assertNotIn("result", failure)
            self.assertEqual("complete", publication.cached_assessment(src)["status"])
            self.assertEqual(2, model.call_count)

    def test_reviewed_sources_never_call_model_and_expire_on_policy_change(self):
        src = source()
        reviewed = publication.record_review(src, decision(src), reviewer="fixture review")
        with patch.object(semantic, "assess", return_value=decision(src)) as model:
            self.assertEqual(reviewed, publication.cached_assessment(src))
            model.assert_not_called()
            with patch.object(semantic, "VERSION", semantic.VERSION+1):
                publication.cached_assessment(src)
            model.assert_called_once()


class SourcePublicationTests(unittest.TestCase):
    def test_actual_observances_retire_legacy_ids_from_reviewed_source_evidence(self):
        cases = json.loads((Path(__file__).parent / "fixtures/content_assessment_cases.json").read_text())
        for case in cases[:2]:
            src = case["source"]
            result = {"kind":"announcement", "date_role":"observance", "reason":"Source describes an awareness observance, with no attendable activity.",
                      "activity_evidence":[], "date_evidence":[{"field":"ocr_text", "quote":src["texts"]["ocr_text"]}],
                      "occurrences":[], "schedule":None, "use_source_occurrences":False}
            semantic.validate(result, src)
            rows, retired = publication.story_rows(case["raw"], case["cached"], {"status":"complete", "source":src, "result":result}, {}, "2026-09-11T20:00:00Z")
            self.assertEqual([], rows)
            expected = "ig_ucrwoof_20260901T0700Z" if "Dog" in case["name"] else "ig_ucr_caps_20260906T0700Z"
            self.assertIn(expected, retired)

    def test_campus_calendar_placement_does_not_promote_an_announcement(self):
        raw = {"id":1, "title":"National Service Dog Month", "description_text":"Celebrate service dogs this September.",
               "first_date":"2026-09-01T00:00:00-07:00", "last_date":"2026-10-01T00:00:00-07:00",
               "filters":{"event_audience":[{"name":"Students"}]}}
        src = publication.structured_source(raw, "localist")
        result = {"kind":"announcement", "date_role":"observance", "reason":"Observance only", "activity_evidence":[],
                  "date_evidence":[], "occurrences":[], "schedule":None, "use_source_occurrences":False}
        self.assertEqual(([], {"ucr_events_1"}), publication.structured_rows(raw, "localist", {"status":"complete", "source":src, "result":result}, "2026-09-11T20:00:00Z"))

    def test_successes_publish_before_partial_failure_is_reported_without_notifications(self):
        updates = [{"source_key":"instagram:a", "assessment":{"status":"complete"}, "rows":[{"id":"ig_a"}]},
                   {"source_key":"instagram:b", "assessment":{"status":"error"}, "rows":[]}]
        with patch.object(publication, "publish", return_value={"written":1}) as publish, \
             patch("discord_notify.notify_free_food_events") as notify:
            with self.assertRaisesRegex(RuntimeError, "1 source assessment"):
                publication._complete(updates, notify=False)
            publish.assert_called_once_with(updates)
            notify.assert_not_called()

    def test_unverified_missing_sources_are_not_retired(self):
        prior = {"localist:1":{"source_key":"localist:1", "origin":"localist", "event_ids":["ucr_events_1"]}}
        with patch.object(publication, "load_registry", return_value=prior), \
             patch("db.get_imported_events", return_value=[]), \
             patch.object(publication, "_complete") as complete:
            publication.publish_structured([], set(), "2026-09-11T20:00:00Z", notify=False)
            self.assertEqual([], complete.call_args.args[0])
            publication.publish_structured([], {"ucr_events_"}, "2026-09-11T20:00:00Z", notify=False)
            self.assertEqual("localist:1", complete.call_args.args[0][0]["source_key"])
            self.assertEqual([], complete.call_args.args[0][0]["rows"])

    def test_verified_snapshot_retires_vanished_legacy_source_without_a_registry_entry(self):
        with patch.object(publication, "load_registry", return_value={}), \
             patch("db.get_imported_events", return_value=[{"id":"ucr_events_123_456"}, {"id":"highlander_link_789"}]), \
             patch.object(publication, "_complete") as complete:
            publication.publish_structured([], {"ucr_events_"}, "2026-09-11T20:00:00Z", notify=False)
            updates = complete.call_args.args[0]
            self.assertEqual(1, len(updates))
            self.assertEqual("localist:123", updates[0]["source_key"])
            self.assertEqual(["ucr_events_123_456"], updates[0]["known_event_ids"])


if __name__ == "__main__":
    unittest.main()
