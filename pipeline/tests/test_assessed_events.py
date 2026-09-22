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
            first = publication.cached_assessment(src).payload
            self.assertEqual(first, publication.cached_assessment(src).payload)
            self.assertEqual(1, model.call_count)
            with patch.object(semantic, "VERSION", semantic.VERSION+1):
                self.assertEqual(first, publication.cached_assessment(src).payload)
            self.assertEqual(1, model.call_count)
            with patch.object(semantic, "MODEL", "changed-model"):
                self.assertEqual(first, publication.cached_assessment(src).payload)
            self.assertEqual(1, model.call_count)
            changed = copy.deepcopy(src)
            changed["texts"]["ocr_text"] += " Bring a notebook."
            publication.cached_assessment(changed).payload
            self.assertEqual(2, model.call_count)
            publication.cached_assessment(changed, refresh=True).payload
            self.assertEqual(3, model.call_count)

    def test_live_provenance_is_per_invocation_and_not_saved_in_payload(self):
        src = source()
        with patch.object(semantic, "assess", return_value=decision(src)):
            fresh = publication.cached_assessment(src)
            reused = publication.cached_assessment(src)
        self.assertTrue(fresh.produced_live)
        self.assertFalse(reused.produced_live)
        self.assertEqual(fresh.payload, reused.payload)
        saved = json.loads(publication._cache_path(src["source_key"]).read_text())
        self.assertEqual(fresh.payload, saved)
        self.assertNotIn("produced_live", saved)

    def test_reviewed_notices_replace_cached_activity_and_produce_no_rows(self):
        cases = json.loads((Path(__file__).parent / "fixtures/content_assessment_cases.json").read_text())
        keys = {"instagram:post:3989062746896826756", "instagram:post:3989718067656891303"}
        for case in (case for case in cases if case["source"]["source_key"] in keys):
            src = case["source"]
            evidence = [{"field": field, "quote": text} for field, text in src["texts"].items() if text]
            prior = {"status": "complete", "source": src, "source_hash": semantic.fingerprint(src),
                     "assessed_at": "2026-09-19T18:30:00+00:00", "result": {"kind": "activity"}}
            publication._save_assessment(prior)
            result = {"kind": "announcement", "date_role": "notice_period",
                      "reason": "Source advertises a release or opening notice without an occasion.",
                      "activity_evidence": evidence, "date_evidence": evidence,
                      "occurrences": [], "schedule": None, "use_source_occurrences": False}
            reviewed = publication.record_review(src, result, reviewer="regression review")
            with self.subTest(source_key=src["source_key"]), patch.object(semantic, "assess") as model:
                payload = publication.cached_assessment(src, prior).payload
                self.assertEqual(reviewed, payload)
                self.assertEqual(([], set()), publication.post_rows({}, {}, payload, {}, "2026-09-19T19:00:00Z"))
                model.assert_not_called()

    def test_rule_validation_changes_do_not_reassess_previously_accepted_sources(self):
        src = source()
        prior = {"status":"complete", "model":semantic.MODEL, "version":semantic.VERSION,
                 "source_hash":semantic.fingerprint(src), "source":src, "result":decision(src)}
        with patch.object(semantic, "assess") as model, \
             patch.object(semantic, "validate", side_effect=ValueError("New stricter rule")):
            self.assertEqual(prior, publication.cached_assessment(src, prior).payload)
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
            self.assertEqual(corrected, publication.cached_assessment(src, corrected).payload)
            model.assert_not_called()


    def test_failure_is_not_a_negative_decision_and_retries(self):
        src = source()
        with patch.object(semantic, "assess", side_effect=[RuntimeError("unavailable"), decision(src)]) as model:
            failure = publication.cached_assessment(src).payload
            self.assertEqual("error", failure["status"])
            self.assertNotIn("result", failure)
            self.assertEqual("complete", publication.cached_assessment(src).payload["status"])
            self.assertEqual(2, model.call_count)

    def test_a_refused_assessment_is_not_paid_for_again_until_something_changes(self):
        src = source()
        refusal = semantic.GroundingRejected("Evidence quote 'x' is absent from field 'ocr_text'")
        with patch.object(semantic, "assess", side_effect=refusal) as model:
            first = publication.cached_assessment(src).payload
            self.assertEqual("error", first["status"])
            self.assertIs(False, first["retryable"])
            stats = {}
            self.assertEqual(first, publication.cached_assessment(src, stats=stats).payload)
            self.assertEqual(1, model.call_count)
            self.assertEqual({"rejections_skipped": 1}, stats)
            # Policy/model edits no longer reopen all refusals automatically.
            with patch.object(semantic, "VERSION", semantic.VERSION + 1):
                publication.cached_assessment(src).payload
            self.assertEqual(1, model.call_count)
            with patch.object(semantic, "MODEL", "changed-model"):
                publication.cached_assessment(src).payload
            self.assertEqual(1, model.call_count)
            changed = copy.deepcopy(src)
            changed["texts"]["ocr_text"] += " Bring a notebook."
            publication.cached_assessment(changed).payload
            self.assertEqual(2, model.call_count)
            publication.cached_assessment(changed, refresh=True).payload
            self.assertEqual(3, model.call_count)

    def test_an_outage_stays_retryable_and_is_never_cached_as_a_refusal(self):
        src = source()
        with patch.object(semantic, "assess", side_effect=RuntimeError("unavailable")) as model:
            failure = publication.cached_assessment(src).payload
            self.assertIs(True, failure["retryable"])
            publication.cached_assessment(src).payload
            self.assertEqual(2, model.call_count)

    def test_validation_diagnostics_survive_cache_round_trip(self):
        src = source()
        attempts = [{"response": {"kind": "activity"}, "error": "Missing source evidence"}]
        refusal = semantic.GroundingRejected("rejected", attempts=attempts)
        with patch.object(semantic, "assess", side_effect=refusal) as model:
            saved = publication.cached_assessment(src).payload
            self.assertEqual(attempts, saved["validation_attempts"])
            self.assertEqual(saved, publication.cached_assessment(src).payload)
            self.assertEqual(1, model.call_count)

    def test_reviewed_sources_survive_policy_changes_until_explicit_refresh(self):
        src = source()
        reviewed = publication.record_review(src, decision(src), reviewer="fixture review")
        with patch.object(semantic, "assess", return_value=decision(src)) as model:
            self.assertEqual(reviewed, publication.cached_assessment(src).payload)
            model.assert_not_called()
            with patch.object(semantic, "VERSION", semantic.VERSION+1):
                self.assertEqual(reviewed, publication.cached_assessment(src).payload)
            model.assert_not_called()
            publication.cached_assessment(src, refresh=True).payload
            model.assert_called_once()

    def negative_payload(self):
        src = source("Club news")
        return {"status": "complete", "source": src, "source_hash": semantic.fingerprint(src),
                "assessed_at": "2026-09-11T00:00:00Z",
                "result": {**decision(src, "announcement", "none"), "occurrences": []}}

    def update(self, payload, prior, **kwargs):
        return publication.make_update(payload["source"], {}, {}, prior, {},
                                       "2026-09-12T00:00:00Z", **kwargs).update

    def test_persisted_identical_negative_never_reaches_publication_rpc(self):
        payload = self.negative_payload()
        prior = {"assessment": payload, "event_ids": [], "known_event_ids": []}
        stats = {}
        with patch.object(semantic, "assess") as model, patch("db.client") as database:
            update = self.update(payload, prior, stats=stats)
            self.assertIsNone(update)
            publication.publish([] if update is None else [update])
        model.assert_not_called()
        database.assert_not_called()
        self.assertEqual(1, stats["unchanged_decisions_skipped"])

    def test_local_negative_still_needs_first_publication_and_ownership_cleanup(self):
        payload = publication._save_assessment(self.negative_payload())
        for prior in (None, {"assessment": {"status": "error"}, "event_ids": []},
                      {"assessment": payload, "event_ids": ["old"], "known_event_ids": ["old"]},
                      {"assessment": payload, "event_ids": [], "known_event_ids": ["locked"]}):
            with self.subTest(prior=prior), patch.object(semantic, "assess") as model:
                update = self.update(payload, prior)
                self.assertEqual(payload, update["assessment"])
                self.assertEqual([], update["rows"])
                model.assert_not_called()

    def test_newer_negative_correction_and_explicit_refresh_are_published(self):
        old = self.negative_payload()
        newer = {**old, "assessed_at": "2026-09-12T00:00:00Z"}
        publication._save_assessment(newer)
        prior = {"assessment": old, "event_ids": [], "known_event_ids": []}
        self.assertEqual(newer, self.update(newer, prior)["assessment"])
        prior["assessment"] = newer
        with patch.object(semantic, "assess", return_value=old["result"]) as model:
            self.assertIsNotNone(self.update(newer, prior, refresh=True))
            model.assert_called_once()

    def test_changed_source_is_assessed_and_negative_result_published(self):
        old = self.negative_payload()
        changed = copy.deepcopy(old)
        changed["source"]["texts"]["ocr_text"] += " New announcement."
        prior = {"assessment": old, "event_ids": [], "known_event_ids": []}
        with patch.object(semantic, "assess", return_value=changed["result"]) as model:
            self.assertIsNotNone(self.update(changed, prior))
            model.assert_called_once()

    def test_persisted_refusal_preserves_support_without_rewriting_but_outages_retry(self):
        payload = {**self.negative_payload(), "status": "error", "retryable": False}
        payload.pop("result")
        prior = {"assessment": payload, "event_ids": ["supported"], "known_event_ids": ["supported"]}
        with patch.object(semantic, "assess") as model:
            self.assertIsNone(self.update(payload, prior))
            model.assert_not_called()
        payload["retryable"] = True
        with patch.object(semantic, "assess", side_effect=RuntimeError("unavailable")) as model:
            update = self.update(payload, prior)
            self.assertTrue(update["assessment"]["retryable"])
            model.assert_called_once()


class SourcePublicationTests(unittest.TestCase):
    def test_shared_builder_returns_classification_without_publication_gating(self):
        from instagram_rows import build_instagram_row
        raw = {"media_id": "123", "handle": "club"}
        occurrence = {"title": "Bake sale fundraiser", "starts_at": "2026-09-15T15:00:00-07:00"}
        for kind in (None, "activity"):
            with self.subTest(kind=kind):
                row = build_instagram_row(raw, occurrence, identity_handle="club", host_handle="club",
                    account_meta={}, text="Bake sale fundraiser", image_url=None, qr_urls=[],
                    scraped_at="2026-09-11T20:00:00Z", assessed_kind=kind)
                self.assertEqual("fundraiser", row["content_kind"])


    def test_successes_publish_before_partial_failure_is_reported_without_notifications(self):
        updates = [{"source_key":"instagram:a", "assessment":{"status":"complete"}, "rows":[{"id":"ig_a"}]},
                   {"source_key":"instagram:b", "assessment":{"status":"error"}, "rows":[]}]
        with patch.object(publication, "publish", return_value={"written":1}) as publish, \
             patch("discord_notify.notify_free_food_events") as notify:
            with self.assertRaisesRegex(RuntimeError, "1 source assessment"):
                publication._complete(updates, notify=False)
            publish.assert_called_once_with(updates)
            notify.assert_not_called()

    def test_a_refused_source_does_not_fail_publication_forever(self):
        # A refusal carries no occurrence dates, so `_source_is_past` can never
        # age it out. Failing the run on one would mean every later run is red.
        updates = [{"source_key":"instagram:a", "assessment":{"status":"complete"}, "rows":[{"id":"ig_a"}]},
                   {"source_key":"instagram:b",
                    "assessment":{"status":"error", "retryable":False, "error":"GroundingRejected: no printed date"},
                    "rows":[]}]
        with patch.object(publication, "publish", return_value={"written":1}) as publish, \
             self.assertLogs("pipeline.assessed_events", level="INFO") as logged:
            publication._complete(updates, notify=False)
        publish.assert_called_once_with(updates)
        self.assertIn("instagram:b", "\n".join(logged.output))

    def test_a_retryable_failure_still_fails_publication_beside_a_refusal(self):
        updates = [{"source_key":"instagram:refused",
                    "assessment":{"status":"error", "retryable":False, "error":"GroundingRejected: no printed date"},
                    "rows":[]},
                   {"source_key":"instagram:outage",
                    "assessment":{"status":"error", "retryable":True, "error":"RuntimeError: unavailable"},
                    "rows":[]}]
        with patch.object(publication, "publish", return_value={"written":0}):
            with self.assertRaises(RuntimeError) as raised:
                publication._complete(updates, notify=False)
        # Only the failure a rerun could clear is counted, named, and reported.
        self.assertIn("1 source assessment(s) failed", str(raised.exception))
        self.assertIn("instagram:outage", str(raised.exception))
        self.assertNotIn("instagram:refused", str(raised.exception))
        self.assertIn("RuntimeError: unavailable", str(raised.exception))

    def test_an_error_without_a_verdict_is_treated_as_retryable(self):
        # Extraction failures and mapping failures carry no `retryable` key.
        updates = [{"source_key":"instagram:a", "assessment":{"status":"error", "error":"Post extraction failed"},
                    "rows":[]}]
        with patch.object(publication, "publish", return_value={"written":0}):
            with self.assertRaisesRegex(RuntimeError, "1 source assessment"):
                publication._complete(updates, notify=False)

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


if __name__ == "__main__":
    unittest.main()
