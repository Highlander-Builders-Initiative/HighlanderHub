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

    def test_policy_and_model_changes_reuse_cache_but_source_edits_reassess(self):
        src = source()
        with patch.object(semantic, "assess", side_effect=lambda item: decision(item)) as model:
            first = publication.cached_assessment(src)
            self.assertEqual(first, publication.cached_assessment(src))
            self.assertEqual(1, model.call_count)
            with patch.object(semantic, "VERSION", semantic.VERSION+1):
                self.assertEqual(first, publication.cached_assessment(src))
            self.assertEqual(1, model.call_count)
            with patch.object(semantic, "MODEL", "changed-model"):
                self.assertEqual(first, publication.cached_assessment(src))
            self.assertEqual(1, model.call_count)
            changed = copy.deepcopy(src)
            changed["texts"]["ocr_text"] += " Bring a notebook."
            publication.cached_assessment(changed)
            self.assertEqual(2, model.call_count)
            publication.cached_assessment(changed, refresh=True)
            self.assertEqual(3, model.call_count)

    def test_rule_validation_changes_do_not_reassess_previously_accepted_sources(self):
        src = source()
        prior = {"status":"complete", "model":semantic.MODEL, "version":semantic.VERSION,
                 "source_hash":semantic.fingerprint(src), "source":src, "result":decision(src)}
        with patch.object(semantic, "assess") as model, \
             patch.object(semantic, "validate", side_effect=ValueError("New stricter rule")):
            self.assertEqual(prior, publication.cached_assessment(src, prior))
            model.assert_not_called()

    def test_newer_remote_correction_wins_over_older_local_cache(self):
        src = source()
        old = {"status": "complete", "version": 3, "model": semantic.MODEL,
               "source_hash": semantic.fingerprint(src), "source": src, "result": decision(src),
               "assessed_at": "2026-09-11T23:00:00+00:00"}
        publication._save_assessment(old)
        corrected = {**old, "version": 4, "assessed_at": "2026-09-12T01:00:00+00:00",
                     "result": {**old["result"], "kind": "application", "date_role": "none", "occurrences": []}}
        with patch.object(semantic, "assess") as model:
            self.assertEqual(corrected, publication.cached_assessment(src, corrected))
            model.assert_not_called()

    def test_hesa_reassesses_old_activity_and_retires_its_production_listing(self):
        cases = json.loads((Path(__file__).parent / "fixtures/content_assessment_cases.json").read_text())
        case = next(case for case in cases if case["name"] == "HESA program recruitment")
        src = publication.story_source(case["raw"], case["cached"])
        self.assertEqual(case["source"], src)
        legacy_id = case["expected_known_event_ids"][0]
        old = decision(src)
        old["occurrences"][0].update(title="HIGHLANDER EARLY START ACADEMY (HESA)", all_day=True,
            starts_at="2026-07-27T00:00:00-07:00", ends_at="2026-09-13T00:00:00-07:00")
        prior = {"status": "complete", "model": semantic.MODEL, "version": 3,
                 "source_hash": semantic.fingerprint(src), "source": src, "result": old}
        # Reproduce the old publication before testing its retirement. The
        # legacy classifier test alone never exercised this assessed path.
        old_rows, _ = publication.story_rows(case["raw"], case["cached"], prior, {}, src["posted_at"])
        self.assertEqual([(legacy_id, "student_event")], [(r["id"], r["content_kind"]) for r in old_rows])
        publication._save_assessment(prior)
        corrected = {**old, "kind": "application", "date_role": "program_duration", "occurrences": [],
                     "reason": "Recruitment for a credit-bearing curriculum; the dates describe its term."}
        semantic.validate(corrected, src)
        extraction_before = copy.deepcopy(case["cached"])
        with patch.object(semantic, "assess", return_value=corrected) as model, \
             patch("extract_stories._gemini_extract", side_effect=AssertionError("Must reuse saved extraction")):
            update = publication.make_update(src, case["raw"], case["cached"],
                {"assessment": prior, "event_ids": [legacy_id]}, {}, "2026-09-12T12:00:00Z", refresh=True)
            model.assert_called_once_with(src)
            self.assertEqual("complete", update["assessment"]["status"])
            self.assertEqual("application", update["assessment"]["result"]["kind"])
            self.assertGreater(update["assessment"]["version"], 3)
            self.assertEqual([], update["rows"])
            self.assertIn(legacy_id, update["known_event_ids"])
            self.assertEqual(update["assessment"], publication.cached_assessment(src, prior))
            model.assert_called_once()
        self.assertEqual(extraction_before, case["cached"])

    def test_failure_is_not_a_negative_decision_and_retries(self):
        src = source()
        with patch.object(semantic, "assess", side_effect=[RuntimeError("unavailable"), decision(src)]) as model:
            failure = publication.cached_assessment(src)
            self.assertEqual("error", failure["status"])
            self.assertNotIn("result", failure)
            self.assertEqual("complete", publication.cached_assessment(src)["status"])
            self.assertEqual(2, model.call_count)

    def test_a_refused_assessment_is_not_paid_for_again_until_something_changes(self):
        src = source()
        refusal = semantic.GroundingRejected("Evidence quote 'x' is absent from field 'ocr_text'")
        with patch.object(semantic, "assess", side_effect=refusal) as model:
            first = publication.cached_assessment(src)
            self.assertEqual("error", first["status"])
            self.assertIs(False, first["retryable"])
            stats = {}
            self.assertEqual(first, publication.cached_assessment(src, stats=stats))
            self.assertEqual(1, model.call_count)
            self.assertEqual({"rejections_skipped": 1}, stats)
            # Policy/model edits no longer reopen all refusals automatically.
            with patch.object(semantic, "VERSION", semantic.VERSION + 1):
                publication.cached_assessment(src)
            self.assertEqual(1, model.call_count)
            with patch.object(semantic, "MODEL", "changed-model"):
                publication.cached_assessment(src)
            self.assertEqual(1, model.call_count)
            changed = copy.deepcopy(src)
            changed["texts"]["ocr_text"] += " Bring a notebook."
            publication.cached_assessment(changed)
            self.assertEqual(2, model.call_count)
            publication.cached_assessment(changed, refresh=True)
            self.assertEqual(3, model.call_count)

    def test_an_outage_stays_retryable_and_is_never_cached_as_a_refusal(self):
        src = source()
        with patch.object(semantic, "assess", side_effect=RuntimeError("unavailable")) as model:
            failure = publication.cached_assessment(src)
            self.assertIs(True, failure["retryable"])
            publication.cached_assessment(src)
            self.assertEqual(2, model.call_count)

    def test_reviewed_sources_survive_policy_changes_until_explicit_refresh(self):
        src = source()
        reviewed = publication.record_review(src, decision(src), reviewer="fixture review")
        with patch.object(semantic, "assess", return_value=decision(src)) as model:
            self.assertEqual(reviewed, publication.cached_assessment(src))
            model.assert_not_called()
            with patch.object(semantic, "VERSION", semantic.VERSION+1):
                self.assertEqual(reviewed, publication.cached_assessment(src))
            model.assert_not_called()
            publication.cached_assessment(src, refresh=True)
            model.assert_called_once()


class SourcePublicationTests(unittest.TestCase):
    def test_shared_builder_returns_classification_without_publication_gating(self):
        from instagram_rows import build_instagram_row
        raw = {"id": "123", "handle": "club"}
        occurrence = {"title": "Bake sale fundraiser", "starts_at": "2026-09-15T15:00:00-07:00"}
        for kind in (None, "activity"):
            with self.subTest(kind=kind):
                row = build_instagram_row(raw, occurrence, identity_handle="club", host_handle="club",
                    account_meta={}, text="Bake sale fundraiser", image_url=None, qr_urls=[],
                    scraped_at="2026-09-11T20:00:00Z", assessed_kind=kind)
                self.assertEqual("fundraiser", row["content_kind"])

    def test_assessed_story_does_not_call_the_legacy_row_mapper(self):
        src = source()
        raw = {"id": "123", "handle": "club", "posted_at": src["posted_at"]}
        cached = {"status": "not_event", "ocr_text": src["texts"]["ocr_text"], "result": {}}
        with patch("extract_stories._to_event_row", side_effect=AssertionError("Legacy mapper called")):
            rows, _ = publication.story_rows(raw, cached,
                {"status": "complete", "source": src, "result": decision(src)}, {}, "2026-09-11T20:00:00Z")
        self.assertEqual(["Workshop"], [row["title"] for row in rows])

    def test_old_extraction_text_cannot_suppress_or_enrich_assessed_story(self):
        src = source()
        raw = {"id": "123", "handle": "club", "posted_at": src["posted_at"]}
        cached = {"status": "ok", "ocr_text": src["texts"]["ocr_text"], "result": {
            "is_event": True, "title": "Obsolete fundraiser", "description": "Bake sale with free pizza",
            "category": "social", "tags": ["free food"], "is_free": False,
            "rsvp_required": True, "rsvp_url": "https://lu.ma/obsolete"}}
        rows, _ = publication.story_rows(raw, cached,
            {"status": "complete", "source": src, "result": decision(src)}, {}, "2026-09-11T20:00:00Z")
        self.assertEqual(1, len(rows))
        self.assertEqual("career", rows[0]["category"])
        self.assertEqual([], rows[0]["tags"])
        self.assertTrue(rows[0]["is_free"])
        self.assertFalse(rows[0]["has_free_food"])
        self.assertFalse(rows[0]["rsvp_required"])
        self.assertIsNone(rows[0]["rsvp_url"])
        self.assertNotIn("Bake sale", rows[0]["description"])

    def test_reshare_chrome_is_stripped_from_an_assessed_story_title(self):
        src = source("bluejadeandjoel and ucr_dance\n"
                     "bluejadeandjoel Joel Mejia Smith: it's been a while\n"
                     "Workshop September 15, 2026, 3-5 PM")
        raw = {"id": "123", "handle": "ucr_dance", "posted_at": src["posted_at"],
               "caption": "Spring showcase this Friday. Come through!"}
        cached = {"status": "ok", "ocr_text": src["texts"]["ocr_text"], "result": {}}
        for title, expected in (("bluejadeandjoel Workshop", "Workshop"),
                                ("bluejadeandjoel and ucr_dance", "Spring showcase this Friday"),
                                ("Workshop", "Workshop")):
            with self.subTest(title=title):
                result = decision(src)
                result["occurrences"][0]["title"] = title
                rows, _ = publication.story_rows(raw, cached,
                    {"status": "complete", "source": src, "result": result}, {}, "2026-09-11T20:00:00Z")
                self.assertEqual([expected], [row["title"] for row in rows])

    def test_assessed_story_location_stays_blank_or_uses_supplied_location(self):
        src = source()
        raw = {"id": "123", "handle": "club", "posted_at": src["posted_at"]}
        cached = {"status": "ok", "ocr_text": src["texts"]["ocr_text"], "result": {}}
        for location, expected in (("", ""), ("  ", ""), (" HUB 302 ", "HUB 302")):
            with self.subTest(location=location):
                result = decision(src)
                result["occurrences"][0]["location"] = location
                rows, _ = publication.story_rows(raw, cached,
                    {"status": "complete", "source": src, "result": result}, {}, "2026-09-11T20:00:00Z")
                self.assertEqual([expected], [row["location"] for row in rows])

    def test_structured_occurrences_preserve_source_location_when_assessment_is_blank(self):
        for origin in ("localist", "highlander_link"):
            raw = {"id": 1, "title": "Workshop", "name": "Workshop",
                   "filters": {"event_audience": [{"name": "Students"}]},
                   "first_date": "2026-09-15T15:00:00-07:00", "startsOn": "2026-09-15T15:00:00-07:00",
                   "location_name": "HUB 302", "location": "HUB 302"}
            src = publication.structured_source(raw, origin)
            for mode in ("occurrences", "schedule", "source"):
                for location, expected in (("", "HUB 302"), ("  ", "HUB 302"), (" Library ", "Library")):
                    with self.subTest(origin=origin, mode=mode, location=location):
                        result = decision(source())
                        result["occurrences"][0]["location"] = location
                        if mode == "schedule":
                            src["texts"]["description"] = "Workshop September 15, 2026 Tuesday 3-5 PM"
                            result["date_evidence"] = [{"field": "description", "quote": src["texts"]["description"]}]
                            result["occurrences"] = []
                            result["schedule"] = {"title": "Workshop", "location": location,
                                "first_day": "2026-09-15", "last_day": "2026-09-15",
                                "weekdays": [1], "windows": [{"start": "15:00", "end": "17:00"}]}
                        elif mode == "source":
                            result["use_source_occurrences"] = True
                            result["occurrences"] = []
                            expected = "HUB 302"
                        rows, _ = publication.structured_rows(raw, origin,
                            {"status": "complete", "source": src, "result": result}, "2026-09-11T20:00:00Z")
                        self.assertEqual([expected], [row["location"] for row in rows])

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

    def test_notifications_use_only_rows_that_exist_after_publication(self):
        requested = {"id":"ig_suppressed", "title":"Candidate", "has_free_food":True}
        published = {"id":"ig_published", "title":"Stored", "has_free_food":True}
        updates = [{"source_key":"instagram:a", "assessment":{"status":"complete"},
                    "rows":[requested, published]}]
        with patch.object(publication, "publish", return_value={"written":1}), \
             patch("db.get_event_rows_by_ids", return_value=[published]) as resolve, \
             patch("discord_notify.notify_free_food_events") as notify:
            publication._complete(updates, notify=True)
        resolve.assert_called_once_with(["ig_suppressed", "ig_published"])
        notify.assert_called_once_with([published])

    def test_notification_lookup_failure_does_not_fail_publication(self):
        updates = [{"source_key":"instagram:a", "assessment":{"status":"complete"},
                    "rows":[{"id":"ig_a"}]}]
        with patch.object(publication, "publish", return_value={"written":1}), \
             patch("db.get_event_rows_by_ids", side_effect=RuntimeError("unavailable")), \
             patch("discord_notify.notify_free_food_events") as notify, \
             self.assertLogs("pipeline.assessed_events", level="WARNING"):
            publication._complete(updates, notify=True)
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
