"""Actor contract, checkpoint safety, and billed-run recovery (no network)."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import apify_posts as apify

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)
ACCOUNTS = {"club": {"handle": "club", "instagram_user_id": 42}}
STATE = {"club": {"activated_at": "2026-09-01T00:00:00+00:00",
                  "scanned_through": "2026-09-19T00:00:00+00:00"}}


def item(**changes):
    return {"pk": "123", "code": "Ab_cd", "taken_at": 1789776000,
            "media_type": 1, "user": {"pk": "42", "username": "club"},
            "caption": {"text": "Meet us @club 📅"}, "scraped_username": "club",
            "image_versions2": {"candidates": [
                {"width": 320, "height": 320, "url": "https://cdn.example/small.jpg"},
                {"width": 1080, "height": 1080, "url": "https://cdn.example/large.jpg"}]},
            **changes}


class NormalizeTests(unittest.TestCase):
    def test_photo_uses_native_fields_and_largest_image(self):
        record = apify.normalize(item(), ACCOUNTS, NOW)
        self.assertEqual("123", record["media_id"])
        self.assertEqual("Meet us @club 📅", record["caption"])
        self.assertEqual(["club"], record["caption_mentions"])
        self.assertEqual("GraphImage", record["typename"])
        self.assertEqual("https://cdn.example/large.jpg", record["media"][0]["image_url"])
        self.assertEqual("https://www.instagram.com/p/Ab_cd/", record["permalink"])

    def test_carousel_preserves_first_slide_and_video_covers(self):
        raw = item(media_type=8, carousel_media=[item(), item(media_type=2)])
        record = apify.normalize(raw, ACCOUNTS, NOW)
        self.assertEqual("GraphSidecar", record["typename"])
        self.assertEqual([0, 1], [m["index"] for m in record["media"]])
        self.assertTrue(record["has_video"])
        self.assertFalse(record["media"][0]["is_video"])

    def test_accepted_collaborator_can_own_profile_post(self):
        raw = item(user={"pk": "55", "username": "partner"},
                   coauthor_producers=[{"pk": "42", "username": "club"}])
        record = apify.normalize(raw, ACCOUNTS, NOW)
        self.assertEqual("club", record["handle"])
        self.assertEqual("partner", record["owner_username"])

    def test_invited_or_wrong_id_is_not_ownership(self):
        for raw in [item(user={"pk": 55, "username": "club"}),
                    item(user={"pk": 55, "username": "partner"},
                         invited_coauthor_producers=[{"pk": 42, "username": "club"}])]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                apify.normalize(raw, ACCOUNTS, NOW)

    def test_malformed_identity_and_media_rejected(self):
        for changes in [{"pk": "../pwn"}, {"code": "../../x"}, {"scraped_username": "../x"},
                        {"taken_at": "yesterday"}, {"taken_at": 9999999999},
                        {"media_type": 8, "carousel_media": []}, {"caption": "wrong shape"},
                        {"image_versions2": {"candidates": []}}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                apify.normalize(item(**changes), ACCOUNTS, NOW)

    def test_id_fallback_and_no_numeric_roster_id(self):
        raw = item(pk=None, id="123_42", caption=None)
        record = apify.normalize(raw, {"club": {"handle": "club"}}, NOW)
        self.assertEqual("123", record["media_id"])
        self.assertIsNone(record["caption"])


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "run.json"
        self.enterContext(patch.object(apify, "RUN_FILE", self.path))
        self.api = apify.ApifyClient("test-token")
        self.input = {"username": ["club"], "resultsLimit": 100,
                      "onlyPostsNewerThan": "2026-09-12T00:00:00Z"}

    def test_start_poll_and_resume_without_second_paid_post(self):
        run = {"id": "run1", "status": "RUNNING", "startedAt": NOW.isoformat()}
        done = {**run, "status": "SUCCEEDED"}
        self.api.request = Mock(side_effect=[{"data": run}, {"data": done}, {"data": done}])
        with patch.object(apify.time, "sleep"):
            self.assertEqual(done, self.api.run(self.input, max_charge=2, timeout=60))
            self.assertEqual(done, self.api.run({**self.input, "onlyPostsNewerThan": "2026-09-13T00:00:00Z"},
                                                max_charge=2, timeout=60))
        self.assertEqual(["POST", "GET", "GET"], [call.args[0] for call in self.api.request.call_args_list])
        self.assertEqual(1.6, self.api.request.call_args_list[0].kwargs["params"]["maxTotalChargeUsd"])
        self.assertEqual("run1", json.loads(self.path.read_text())["id"])

    def test_dataset_pages_until_empty_not_only_first_thousand(self):
        self.api.request = Mock(side_effect=[[{"pk": i} for i in range(1000)], [{"pk": 1000}]])
        self.assertEqual(1001, len(list(self.api.items("dataset"))))
        self.assertEqual(1000, self.api.request.call_args.kwargs["params"]["offset"])

    def test_auth_token_is_header_only(self):
        self.api.session.request = Mock(return_value=Mock(json=Mock(return_value={"data": {}})))
        self.api.request("GET", "actor-runs/test")
        self.assertEqual("Bearer test-token", self.api.session.headers["Authorization"])
        self.assertNotIn("test-token", str(self.api.session.request.call_args))

    def test_no_retry_of_ambiguous_creation(self):
        self.api.request = Mock(side_effect=TimeoutError("unknown start status"))
        with self.assertRaises(TimeoutError):
            self.api.run(self.input, max_charge=1, timeout=60)
        with self.assertRaisesRegex(RuntimeError, "outcome unknown"):
            self.api.run(self.input, max_charge=1, timeout=60)
        self.api.request.assert_called_once()

    def test_timeout_leaves_run_available_for_resume(self):
        self.api.request = Mock(return_value={"data": {"id": "running", "status": "RUNNING", "startedAt": NOW.isoformat()}})
        with patch.object(apify.time, "monotonic", side_effect=[0, 181]), self.assertRaisesRegex(RuntimeError, "resume"):
            self.api.run(self.input, max_charge=1, timeout=60)
        self.assertFalse(json.loads(self.path.read_text())["consumed"])


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "run.json"
        self.enterContext(patch.object(apify, "RUN_FILE", self.path))
        self.enterContext(patch.object(apify, "POST_BACKFILL_SINCE", ""))
        self.known = self.enterContext(patch.object(apify, "known_post_ids", return_value=set()))
        self.mirror = self.enterContext(patch.object(apify, "mirror"))
        self.write = self.enterContext(patch.object(apify, "write_post"))
        self.upsert = self.enterContext(patch("db.upsert_batched"))
        self.api = Mock()
        self.api.run_file = self.path
        self.api.run.return_value = {"status": "SUCCEEDED", "defaultDatasetId": "dataset",
                                     "pricingInfo": {"pricingPerEvent": {"actorChargeEvents": {
                                         "apify-default-dataset-item": {"eventPriceUsd": .0003},
                                         "apify-actor-start": {"eventPriceUsd": .005}}}}}
        self.api.items.return_value = [item()]
        self.state = copy.deepcopy(STATE)
        self.path.write_text(json.dumps({"id": "run1", "posts_per_profile": 100,
                                         "started_at": NOW.isoformat(), "consumed": False}))

    def collect(self, **kwargs):
        apify.collect(self.api, ACCOUNTS, self.state, NOW, limit=100, max_charge=10,
                      timeout=60, **kwargs)

    def test_success_mirrors_before_advancing_progress(self):
        calls = []
        self.mirror.side_effect = lambda _: calls.append("mirror")
        self.write.side_effect = lambda _: calls.append("local")
        self.upsert.side_effect = lambda *a, **k: calls.append("checkpoint")
        self.collect()
        self.assertEqual(["mirror", "local", "checkpoint"], calls)
        self.assertEqual(NOW.isoformat(), self.upsert.call_args.args[1][0]["scanned_through"])
        self.assertTrue(json.loads(self.path.read_text())["consumed"])

    def test_actor_date_hint_is_strictly_filtered_locally(self):
        self.api.items.return_value = [item(taken_at=1704067200)]
        self.collect()
        self.mirror.assert_not_called()
        self.write.assert_not_called()

    def test_failed_run_keeps_partial_records_without_progress(self):
        self.api.run.return_value["status"] = "TIMED-OUT"
        with self.assertRaises(apify.PartialCollection):
            self.collect()
        self.mirror.assert_called_once()
        self.assertEqual(STATE["club"]["scanned_through"], self.upsert.call_args.args[1][0]["scanned_through"])

    def test_export_cap_and_empty_result_cannot_advance(self):
        for items in [[], [item(pk=str(i + 1)) for i in range(100)]]:
            with self.subTest(count=len(items)):
                self.api.items.return_value = items
                with self.assertRaises(apify.PartialCollection):
                    self.collect()
                self.assertEqual(STATE["club"]["scanned_through"], self.upsert.call_args.args[1][0]["scanned_through"])

    def test_malformed_item_keeps_valid_prefix_but_blocks_progress(self):
        self.api.items.return_value = [item(), item(pk="bad")]
        with self.assertRaises(apify.PartialCollection):
            self.collect()
        self.mirror.assert_called_once()
        self.assertEqual("incomplete", self.upsert.call_args.args[1][0]["last_status"])

    def test_mirror_failure_never_advances_and_dataset_can_be_replayed(self):
        self.mirror.side_effect = RuntimeError("database offline")
        with self.assertRaises(RuntimeError):
            self.collect()
        self.upsert.assert_not_called()
        self.write.assert_not_called()
        self.assertFalse(json.loads(self.path.read_text())["consumed"])

    def test_duplicate_dataset_records_deduplicate_by_media_id(self):
        self.api.items.return_value = [item(), item()]
        self.collect()
        self.mirror.assert_called_once()
        self.write.assert_called_once()

    def test_saved_post_with_edited_caption_is_not_overwritten(self):
        self.known.return_value = {"123"}
        self.api.items.return_value = [item(caption={"text": "Changed time"})]
        self.collect()
        self.mirror.assert_not_called()
        self.write.assert_not_called()
        # Seeing only known posts still proves a nonempty, uncapped scan.
        self.assertEqual(NOW.isoformat(), self.upsert.call_args.args[1][0]["scanned_through"])
        self.assertEqual(0, json.loads(self.path.read_text())["saved_posts"])

    def test_mixed_results_save_only_unseen_posts(self):
        self.known.return_value = {"123"}
        self.api.items.return_value = [item(), item(pk="456")]
        self.collect()
        self.assertEqual("456", self.write.call_args.args[0]["media_id"])
        self.write.assert_called_once()

    def test_unreadable_known_ids_stop_before_paid_creation(self):
        self.known.side_effect = RuntimeError("database unavailable")
        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            self.collect()
        self.api.run.assert_not_called()

    def test_known_posts_still_count_toward_export_cap(self):
        self.known.return_value = {str(i + 1) for i in range(100)}
        self.api.items.return_value = [item(pk=str(i + 1)) for i in range(100)]
        with self.assertRaises(apify.PartialCollection):
            self.collect()
        self.mirror.assert_not_called()
        self.assertEqual("incomplete", self.upsert.call_args.args[1][0]["last_status"])

    def test_dataset_transport_failure_retains_progress_and_run(self):
        def pages():
            yield item()
            raise RuntimeError("page two failed")
        self.api.items.side_effect = lambda _: pages()
        with self.assertRaises(RuntimeError):
            self.collect()
        self.mirror.assert_called_once()
        self.upsert.assert_not_called()
        self.assertFalse(json.loads(self.path.read_text())["consumed"])

    def test_resumed_run_cannot_claim_newly_requested_older_coverage(self):
        saved = json.loads(self.path.read_text())
        self.path.write_text(json.dumps({**saved, "newer_than": "2026-09-19T01:00:00+00:00"}))
        with self.assertRaisesRegex(apify.PartialCollection, "older cutoff"):
            self.collect()
        self.assertEqual(STATE["club"]["scanned_through"], self.upsert.call_args.args[1][0]["scanned_through"])

    def test_checkpoint_write_failure_keeps_run_unconsumed(self):
        self.upsert.side_effect = RuntimeError("checkpoint write failed")
        with self.assertRaises(RuntimeError):
            self.collect()
        self.assertFalse(json.loads(self.path.read_text())["consumed"])

    def test_actor_input_matches_documented_schema(self):
        self.collect()
        payload = self.api.run.call_args.args[0]
        self.assertEqual(["club"], payload["username"])
        self.assertEqual(100, payload["resultsLimit"])
        self.assertEqual("detailedData", payload["dataDetailLevel"])
        # Only this pairing drops pins older than the window; the cutoff alone
        # still exports and bills for pinned posts of any age.
        self.assertTrue(payload["skipPinnedPosts"])
        self.assertEqual("2026-09-18T23:54:59Z", payload["onlyPostsNewerThan"])

    def test_charge_capped_success_never_advances_checkpoints(self):
        self.api.run.return_value["options"] = {"maxTotalChargeUsd": .0053}
        with self.assertRaisesRegex(apify.PartialCollection, "charge ceiling"):
            self.collect()
        self.mirror.assert_called_once()
        self.assertEqual(STATE["club"]["scanned_through"], self.upsert.call_args.args[1][0]["scanned_through"])

    def test_missing_pricing_metadata_cannot_claim_complete_coverage(self):
        self.api.run.return_value.pop("pricingInfo")
        with self.assertRaisesRegex(apify.PartialCollection, "pricing metadata"):
            self.collect()
        self.assertEqual("incomplete", self.upsert.call_args.args[1][0]["last_status"])

    def test_activation_is_durable_and_existing_boundary_is_reused(self):
        db = Mock()
        db.rpc.return_value.execute.return_value.data = STATE
        with patch("db.client", return_value=db):
            self.assertEqual(STATE, apify.checkpoints(["club"], NOW))
            db.rpc.return_value.execute.return_value.data = {}
            with self.assertRaises(RuntimeError):
                apify.checkpoints(["club"], NOW)


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(apify, "POST_BACKFILL_SINCE", ""))
        self.accounts = {h: {"handle": h} for h in ["current", "stale", "other"]}
        self.state = {h: {"activated_at": "2026-01-01T00:00:00+00:00",
                          "scanned_through": "2026-09-19T16:00:00+00:00"} for h in self.accounts}
        self.state["stale"]["scanned_through"] = "2026-08-01T00:00:00+00:00"
    def jobs(self, **kwargs):
        return apify.plan_jobs(self.accounts, self.state, NOW,
                              limit=100, max_charge=kwargs.pop("max_charge", 10), **kwargs)

    def test_stale_account_and_old_event_do_not_widen_current_discovery(self):
        jobs = self.jobs()
        current = next(j for j in jobs if j["mode"] == "discovery" and "current" in j["handles"])
        self.assertEqual(["current", "other"], current["handles"])
        self.assertEqual("2026-09-19T15:54:59+00:00", current["cutoff"])
        stale = next(j for j in jobs if j["mode"] == "discovery" and "stale" in j["handles"])
        self.assertEqual(["stale"], stale["handles"])
        self.assertTrue(all(j["mode"] == "discovery" for j in jobs))
        self.assertTrue(all("refresh" not in j for j in jobs))

    def test_total_ceiling_is_entirely_available_for_discovery(self):
        jobs = self.jobs(max_charge=1.03)
        self.assertEqual(103, sum(round(j["max_charge"] * 100) for j in jobs))
        self.assertTrue(all(j["max_charge"] >= .01 for j in jobs))

    def test_fractional_cent_budget_rounds_down_never_above_ceiling(self):
        jobs = self.jobs(max_charge=1.009)
        self.assertEqual(100, sum(round(j["max_charge"] * 100) for j in jobs))

    def test_recent_incomplete_profile_waits_without_losing_progress(self):
        original = copy.deepcopy(self.state)
        self.state["stale"].update(last_scan_at="2026-09-19T17:00:00+00:00", last_status="incomplete")
        jobs = self.jobs()
        self.assertFalse(any("stale" in j["handles"] for j in jobs))
        self.assertEqual(original["stale"]["scanned_through"], self.state["stale"]["scanned_through"])
        self.state["stale"]["last_scan_at"] = "2026-09-19T16:00:00+00:00"
        self.assertTrue(any("stale" in j["handles"] for j in self.jobs()))

    def test_hour_grouping_adds_less_than_an_hour_to_any_account(self):
        self.state["other"]["scanned_through"] = "2026-09-19T15:30:00+00:00"
        for job in self.jobs():
            if job["mode"] != "discovery":
                continue
            for handle in job["handles"]:
                widened = apify.boundary(self.state[handle]) - apify.parse_instant(job["cutoff"])
                self.assertLessEqual(widened.total_seconds(), 3600)


class PlanResumeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.enterContext(patch.object(apify, "PLAN_FILE", self.root / "plan.json"))
        self.jobs = [{"mode": "discovery", "handles": ["club"], "cutoff": "2026-09-18T23:55:00+00:00",
                      "refresh": {}, "limit": 100, "max_charge": .5,
                      "file": str(self.root / f"{i}.json"), "done": False} for i in range(2)]
        self.plan = {"jobs": self.jobs, "complete": False}

    def execute(self):
        apify.execute_plan("test", ACCOUNTS, STATE, NOW, self.plan, 1800)

    def test_consumed_batch_is_not_rebilled_after_plan_write_interruption(self):
        apify.write_json(Path(self.jobs[0]["file"]), {"consumed": True, "errors": []})
        def finish(api, *args, **kwargs):
            apify.write_json(api.run_file, {"consumed": True, "errors": []})
        with patch.object(apify, "collect", side_effect=finish) as collect:
            self.execute()
        collect.assert_called_once()
        self.assertTrue(self.plan["complete"])

    def test_resume_only_unfinished_batch_after_transport_failure(self):
        def attempt(api, *args, **kwargs):
            if api.run_file.name == "1.json":
                raise RuntimeError("dataset disconnected")
            apify.write_json(api.run_file, {"consumed": True, "errors": []})
        with patch.object(apify, "collect", side_effect=attempt), self.assertRaises(RuntimeError):
            self.execute()
        self.assertTrue(self.jobs[0]["done"])
        def finish(api, *args, **kwargs):
            apify.write_json(api.run_file, {"consumed": True, "errors": []})
        with patch.object(apify, "collect", side_effect=finish) as collect:
            self.execute()
        collect.assert_called_once()
        self.assertEqual("1.json", collect.call_args.args[0].run_file.name)

    def test_prior_terminal_failure_is_still_reported_after_other_batches_resume(self):
        self.jobs[0].update(done=True, errors=["club incomplete"])
        apify.write_json(Path(self.jobs[1]["file"]), {"consumed": True, "errors": []})
        with self.assertRaisesRegex(apify.PartialCollection, "club incomplete"):
            self.execute()
        self.assertTrue(self.plan["complete"])

    def test_cached_refresh_job_never_starts_or_resumes_actor(self):
        for already_started in (False, True):
            with self.subTest(already_started=already_started):
                self.jobs[0].update(mode="refresh", done=False, handles=["removed_account"])
                self.jobs[1]["done"] = True
                if already_started:
                    apify.write_json(Path(self.jobs[0]["file"]), {"id": "paid-run", "consumed": False})
                with patch.object(apify, "ApifyClient") as client, patch.object(apify, "collect") as collect:
                    self.execute()
                collect.assert_not_called()
                client.assert_not_called()
                self.assertEqual("post rechecks disabled", self.jobs[0]["skipped"])
                self.assertTrue(self.plan["complete"])

    def test_legacy_incidental_refresh_targets_are_not_forwarded(self):
        self.jobs[0]["refresh"] = {"123": {"handle": "club", "posted_at": "2024-01-01"}}
        self.jobs[1]["done"] = True
        def finish(api, *args, **kwargs):
            self.assertNotIn("refresh", kwargs)
            apify.write_json(api.run_file, {"consumed": True, "errors": []})
        with patch.object(apify, "collect", side_effect=finish) as collect:
            self.execute()
        collect.assert_called_once()
        self.assertNotIn("refresh", self.jobs[0])

    def test_real_collection_replay_preserves_first_snapshot(self):
        jobs = apify.plan_jobs(ACCOUNTS, STATE, NOW, limit=100, max_charge=1)
        for i, job in enumerate(jobs):
            job["file"] = str(self.root / f"integration-{i}.json")
        plan = {"jobs": jobs, "complete": False}
        remote = {}
        def make_api(token, path):
            api = Mock(run_file=path)
            def run(payload, **kwargs):
                apify.write_json(path, {"consumed": False, "posts_per_profile": 100,
                                       "started_at": NOW.isoformat(),
                                       "newer_than": payload["onlyPostsNewerThan"]})
                return {"status": "SUCCEEDED", "defaultDatasetId": "test",
                        "pricingInfo": {"pricingPerEvent": {"actorChargeEvents": {
                            "apify-default-dataset-item": {"eventPriceUsd": .0003},
                            "apify-actor-start": {"eventPriceUsd": .005}}}}}
            api.run.side_effect = run
            api.items.return_value = [item(caption={"text": "Edited" if remote else "Original"})]
            return api
        def mirror(records):
            remote.update({record["media_id"]: record for record in records})
        with patch.object(apify, "ApifyClient", side_effect=make_api), \
             patch.object(apify, "mirror", side_effect=mirror) as mirrored, \
             patch.object(apify, "write_post"), patch("db.upsert_batched"), \
             patch.object(apify, "known_post_ids", side_effect=lambda: set(remote)):
            apify.execute_plan("test", ACCOUNTS, STATE, NOW, plan, 1800)
            jobs[0]["done"] = False
            Path(jobs[0]["file"]).unlink()
            apify.execute_plan("test", ACCOUNTS, STATE, NOW, plan, 1800)
        mirrored.assert_called_once()
        self.assertEqual("Original", remote["123"]["caption"])
        self.assertTrue(plan["complete"])


# Captured from real runs of apify/instagram-post-scraper build 0.0.599 and from
# the already-paid sones datasets, so the parsers are tested against the bytes
# each actor actually emits rather than against its README.
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "apify_actor_output.json").read_text())
OFFICIAL_ACCOUNTS = {
    "ucr_athletics": {"handle": "ucr_athletics", "instagram_user_id": 294586099},
    "thereachinitiative.ucr": {"handle": "thereachinitiative.ucr", "instagram_user_id": 80325881866},
    "careersinscrubs_": {"handle": "careersinscrubs_", "instagram_user_id": 76614406560},
    "officialhoucr": {"handle": "officialhoucr", "instagram_user_id": 6252059643},
}
SEEN = datetime(2026, 9, 21, tzinfo=timezone.utc)
OFFICIAL_STATE = {handle: {"activated_at": "2026-09-01T00:00:00+00:00",
                           "scanned_through": "2026-09-17T00:00:00+00:00"}
                  for handle in OFFICIAL_ACCOUNTS}
# Verbatim lines from runs 9jZq8UqNt2mK0QMdd, m3rA4ErWevfBdZuce and nCu5l2WShzhXTzjLI.
LOG = """2026-09-20T03:59:44.383Z INFO  No more posts within the wanted time range, finishing https://www.instagram.com/ucr_athletics
2026-09-20T03:59:48.631Z INFO  NO RESULTS: zero public posts for https://www.instagram.com/officialhoucr within the given requirements
2026-09-20T04:01:56.410Z INFO  [END-OF-RESULTS]: thereachinitiative.ucr confirmed end of results at pos 6
2026-09-20T04:00:06.669Z INFO  CheerioCrawler: Finished! Total 18 requests: 18 succeeded, 0 failed.
"""


class OfficialActorTests(unittest.TestCase):
    """Measured behaviour of the pinned build, not its documented behaviour."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "run.json"
        self.enterContext(patch.object(apify, "RUN_FILE", self.path))
        self.enterContext(patch.object(apify, "POST_BACKFILL_SINCE", ""))
        self.known = self.enterContext(patch.object(apify, "known_post_ids", return_value=set()))
        self.mirror = self.enterContext(patch.object(apify, "mirror"))
        self.write = self.enterContext(patch.object(apify, "write_post"))
        self.upsert = self.enterContext(patch("db.upsert_batched"))
        self.api = Mock(run_file=self.path)
        self.api.run.return_value = {
            "id": "run1", "status": "SUCCEEDED", "actId": apify.ACTOR_ID,
            "defaultDatasetId": "dataset", "options": {"maxTotalChargeUsd": 1.0},
            "chargedEventCounts": {"post": 2, "post-details": 2},
            "pricingInfo": {"pricingPerEvent": {"actorChargeEvents": {
                "post": {"eventPriceUsd": .0017}, "post-details": {"eventPriceUsd": .001}}}}}
        self.api.completed_profiles.return_value = set(OFFICIAL_ACCOUNTS)
        self.api.items.return_value = [FIXTURE["image"]]
        self.state = copy.deepcopy(OFFICIAL_STATE)
        self.path.write_text(json.dumps({"id": "run1", "posts_per_profile": 100,
                                         "actor_id": apify.ACTOR_ID, "consumed": False,
                                         "newer_than": "2026-09-16T23:54:59Z",
                                         "started_at": NOW.isoformat()}))

    def collect(self, **kwargs):
        apify.collect(self.api, OFFICIAL_ACCOUNTS, self.state, NOW, limit=100,
                      max_charge=10, timeout=60, cutoff="2026-09-16T23:54:59+00:00", **kwargs)

    def checkpoint(self, handle):
        rows = {row["handle"]: row for row in self.upsert.call_args.args[1]}
        return rows[handle]

    def test_verified_output_maps_to_the_archive_contract(self):
        record = apify.normalize(apify.official_item(FIXTURE["image"]), OFFICIAL_ACCOUNTS, SEEN)
        # The exact ID matters: the previous actor rounded pk past 2**53.
        self.assertEqual("3989905292304988880", record["media_id"])
        self.assertEqual("ucr_athletics", record["handle"])
        self.assertEqual("GraphImage", record["typename"])
        self.assertEqual(1350449562, record["owner_userid"])
        self.assertTrue(record["media"][0]["image_url"].startswith("https://"))

    def test_carousel_children_supply_every_slide(self):
        record = apify.normalize(apify.official_item(FIXTURE["collab_sidecar"]), OFFICIAL_ACCOUNTS, SEEN)
        self.assertEqual("GraphSidecar", record["typename"])
        self.assertEqual([0, 1], [media["index"] for media in record["media"]])
        self.assertEqual(2, len({media["image_url"] for media in record["media"]}))

    def test_collaboration_is_credited_to_the_requested_profile(self):
        record = apify.normalize(apify.official_item(FIXTURE["image"]), OFFICIAL_ACCOUNTS, SEEN)
        # Athletics posts arrive owned by the team account that published them.
        self.assertEqual("ucrvolleyball", record["owner_username"])
        self.assertEqual("ucr_athletics", record["handle"])

    def test_every_verified_completion_signal_advances_its_profile(self):
        self.assertEqual({"ucr_athletics", "officialhoucr", "thereachinitiative.ucr"},
                         apify.completed_profiles_from_log(LOG))

    def test_unrecognised_log_contract_advances_nothing(self):
        self.assertEqual(set(), apify.completed_profiles_from_log(
            "2026-09-20T03:59:44.383Z INFO  finished https://www.instagram.com/ucr_athletics"))

    def test_empty_window_is_coverage_not_failure(self):
        self.api.items.return_value = [FIXTURE["image"], FIXTURE["no_items"]]
        self.collect()
        self.assertEqual("ok", self.checkpoint("officialhoucr")["last_status"])
        self.assertEqual(NOW.isoformat(), self.checkpoint("officialhoucr")["scanned_through"])

    def test_unconfirmed_empty_result_keeps_its_checkpoint(self):
        self.api.items.return_value = [FIXTURE["no_items"]]
        self.api.completed_profiles.return_value = set()
        with self.assertRaises(apify.PartialCollection):
            self.collect()
        self.assertEqual("incomplete", self.checkpoint("officialhoucr")["last_status"])
        self.assertEqual(OFFICIAL_STATE["officialhoucr"]["scanned_through"],
                         self.checkpoint("officialhoucr")["scanned_through"])

    def test_completion_signal_cannot_override_a_profile_failure(self):
        for error in ("not_found", "blocked", "rate_limited", "unknown_error"):
            with self.subTest(error=error):
                self.api.items.return_value = [FIXTURE["image"],
                                              {**FIXTURE["no_items"], "error": error}]
                with self.assertRaises(apify.PartialCollection):
                    self.collect()
                self.assertEqual("incomplete", self.checkpoint("officialhoucr")["last_status"])
                self.assertEqual(OFFICIAL_STATE["officialhoucr"]["scanned_through"],
                                 self.checkpoint("officialhoucr")["scanned_through"])
                self.assertEqual("ok", self.checkpoint("ucr_athletics")["last_status"])

    def test_post_older_than_the_paid_cutoff_halts_the_plan(self):
        # The previous actor billed for 5,160 such posts before anyone noticed.
        self.api.items.return_value = [FIXTURE["image"], FIXTURE["out_of_window_pin"]]
        with self.assertRaisesRegex(apify.CollectionHalted, "date filter"):
            self.collect()
        self.assertEqual("incomplete", self.checkpoint("ucr_athletics")["last_status"])
        self.assertEqual("Actor violated the paid date filter; remaining paid batches stopped",
                         json.loads(self.path.read_text())["halt_reason"])

    def test_official_charge_ceiling_blocks_checkpoint_advance(self):
        self.api.run.return_value["options"] = {"maxTotalChargeUsd": .0055}
        with self.assertRaisesRegex(apify.PartialCollection, "charge ceiling"):
            self.collect()
        self.assertEqual("incomplete", self.checkpoint("ucr_athletics")["last_status"])

    def test_unpriced_events_cannot_claim_complete_coverage(self):
        self.api.run.return_value["pricingInfo"]["pricingPerEvent"]["actorChargeEvents"].pop("post-details")
        with self.assertRaisesRegex(apify.PartialCollection, "charge-limit coverage"):
            self.collect()


class LegacyDatasetTests(unittest.TestCase):
    """Datasets already paid for must still ingest after the actor swap."""

    def test_flattened_media_and_rounded_pk_still_ingest(self):
        accounts = {"careersinscrubs_": {"handle": "careersinscrubs_",
                                         "instagram_user_id": 76614406560}}
        record = apify.normalize(FIXTURE["legacy_image"], accounts, SEEN)
        # pk arrived as 3702683390001380000; the composite id holds the truth.
        self.assertEqual("3702683390001380073", record["media_id"])
        self.assertEqual(FIXTURE["legacy_image"]["image_url"], record["media"][0]["image_url"])

    def test_every_legacy_carousel_slide_resolves(self):
        accounts = {"careersinscrubs_": {"handle": "careersinscrubs_",
                                         "instagram_user_id": 76614406560}}
        record = apify.normalize(FIXTURE["legacy_sidecar"], accounts, SEEN)
        self.assertEqual("GraphSidecar", record["typename"])
        self.assertTrue(all(media["image_url"].startswith("https://") for media in record["media"]))



if __name__ == "__main__":
    unittest.main()
