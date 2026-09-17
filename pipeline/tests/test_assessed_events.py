"""Assessment caching, source adaptation, and publication-boundary regressions."""
import copy
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

    def test_validation_diagnostics_survive_cache_round_trip(self):
        src = source()
        attempts = [{"response": {"kind": "activity"}, "error": "Missing source evidence"}]
        refusal = semantic.GroundingRejected("rejected", attempts=attempts)
        with patch.object(semantic, "assess", side_effect=refusal) as model:
            saved = publication.cached_assessment(src)
            self.assertEqual(attempts, saved["validation_attempts"])
            self.assertEqual(saved, publication.cached_assessment(src))
            self.assertEqual(1, model.call_count)

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


if __name__ == "__main__":
    unittest.main()
