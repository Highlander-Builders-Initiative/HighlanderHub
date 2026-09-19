"""Offline Following pagination, durability, normalization and runner tests."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from types import SimpleNamespace
import requests
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import following_feed as feed
import instagram_cooldown
import post_archive
import scrape_posts
from instaloader.exceptions import TooManyRequestsException

NOW = datetime(2026, 9, 16, 12, tzinfo=timezone.utc)
ACCOUNTS = [{"handle": "club", "instagram_user_id": 42},
            {"handle": "other", "instagram_user_id": 43}]
CHECKPOINTS = {a["handle"]: {"activated_at": "2026-09-01T00:00:00+00:00",
                            "scanned_through": "2026-09-15T00:00:00+00:00"} for a in ACCOUNTS}


def media(pk="100", day=16, owner=42, **changes):
    value = {"pk": pk, "code": "C" + pk, "taken_at": datetime(2026, 9, day, tzinfo=timezone.utc).timestamp(),
             "media_type": 1, "owner": {"pk": str(owner), "username": "author"},
             "caption": {"text": "Flyer @club"},
             "image_versions2": {"candidates": [{"url": f"https://cdn.example/{pk}_n.jpg"}]}}
    value.update(changes)
    return value


def page(items, more=False, cursor=None):
    return {"data": {feed.CONNECTION: {"edges": [{"node": {"media": m}} for m in items],
                                            "page_info": {"has_next_page": more, "end_cursor": cursor}}}}


class FollowingTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for module, name, value in (
            (feed, "FOLLOWING_CHECKPOINT_FILE", self.root / "following.json"),
            (post_archive, "POSTS_DIR", self.root / "posts"),
            (scrape_posts, "POST_CHECKPOINTS_FILE", self.root / "profiles.json"),
            (scrape_posts, "POST_BACKFILL_SINCE", ""),
            (instagram_cooldown, "INSTAGRAM_COOLDOWN_FILE", self.root / "cooldown.json"),
            (instagram_cooldown, "_UNSAVED", None),
        ):
            patcher = patch.object(module, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.remote = self.enterContext(patch.object(scrape_posts, "write_remote_posts"))
        self.loader = Mock()
        self.loader.context.username = "collector"
        self.checkpoints = copy.deepcopy(CHECKPOINTS)
        self.fetch = Mock()

    def collect(self, pages, **kwargs):
        self.fetch.side_effect = pages

        @contextmanager
        def browser(loader):
            yield self.fetch

        with patch.object(feed, "browser_pages", browser):
            return feed.collect(self.loader, ACCOUNTS, self.checkpoints, NOW, **kwargs)

    def test_replay_starts_at_head_and_keeps_observed_query_id(self):
        variables = {"after": "bootstrap-cursor", "data": {"pagination_source": "following"}}
        body = urlencode({"doc_id": "dynamic", "variables": json.dumps(variables)})
        template = feed.request_template("https://www.instagram.com/graphql/query", body)
        form = feed.page_form(template, None)
        self.assertEqual("dynamic", form["doc_id"])
        self.assertIsNone(json.loads(form["variables"])["after"])
        self.assertEqual("bootstrap-cursor", json.loads(template["variables"])["after"])
        self.assertIsNone(feed.request_template("https://example.com/graphql/query", body))
        variables["data"]["pagination_source"] = "feed_recs"
        self.assertIsNone(feed.request_template("https://www.instagram.com/graphql/query",
                                               urlencode({"doc_id": "1", "variables": json.dumps(variables)})))

    def test_multipage_dedup_and_independent_checkpoint(self):
        result = self.collect([page([media()], True, "a"), page([media(), media("101", 15)])])
        self.assertEqual([None, "a"], [c.args[0] for c in self.fetch.call_args_list])
        self.assertEqual(2, result["discovered"])
        self.assertEqual(CHECKPOINTS, self.checkpoints)
        self.assertEqual(NOW.isoformat(), feed.load_state()["observed_through"])
        self.assertEqual(2, self.remote.call_count)
        repeated = self.collect([page([media(), media("101", 15)])])
        self.assertEqual(0, repeated["discovered"])
        self.assertEqual(2, repeated["unchanged"])

    def test_does_not_stop_on_seen_post_or_single_old_item(self):
        self.collect([page([media()])])
        result = self.collect([page([media(), media("90", 2)], True, "a"), page([media("101", 15)])])
        self.assertEqual(1, result["discovered"])
        self.assertEqual(2, result["pages"])

    def test_two_old_pages_stop_only_when_timeline_order_was_consistent(self):
        result = self.collect([page([media()], True, "a"),
                               page([media("90", 7)], True, "b"),
                               page([media("89", 6)], True, "c")])
        self.assertEqual(3, result["pages"])
        unordered = [page([media("90", 7), media()], True, "a"),
                     page([media("89", 6)], True, "b"),
                     page([media("88", 5)], True, "c"), page([media("101", 15)])]
        result = self.collect(unordered)
        self.assertEqual(4, result["pages"])
        self.assertIn("101", result["media_ids"])

    def test_failures_keep_previous_watermark_and_saved_pages(self):
        self.collect([page([media()])])
        before = feed.load_state()
        for failure in (RuntimeError("network"), TooManyRequestsException("429")):
            with self.subTest(failure=failure):
                with self.assertRaises(type(failure)):
                    self.collect([page([media("101")], True, "a"), failure])
                self.assertEqual(before, feed.load_state())
                self.assertTrue(post_archive.post_path("club", "101").exists())
        self.remote.side_effect = RuntimeError("mirror down")
        with self.assertRaisesRegex(RuntimeError, "mirror down"):
            self.collect([page([media("102")])])
        self.assertEqual(before, feed.load_state())

    def test_budget_repeated_cursor_and_malformed_pages_cannot_claim_progress(self):
        cases = [([page([media()], True, "a")], {"max_pages": 1}),
                 ([page([media()], True, "a"), page([media("101")], True, "a")], {}),
                 ([page([media()], True, None)], {}), ([{"data": {}}], {}),
                 ([{"errors": [{"message": "bad"}], **page([])}], {})]
        for pages, kwargs in cases:
            with self.subTest(pages=pages), self.assertRaises(RuntimeError):
                self.collect(pages, **kwargs)
            self.assertFalse(feed.FOLLOWING_CHECKPOINT_FILE.exists())

    def test_activation_roster_and_collaborations(self):
        self.checkpoints["club"]["activated_at"] = "2026-09-15T12:00:00+00:00"
        result = self.collect([page([
            media("100", 16), media("101", 15), media("102", 15, 99),
            media("103", 15, 99, coauthor_producers=[{"pk": "43"}]),
            media("104", 15, 99, invited_coauthor_producers=[{"pk": "43"}]),
        ])])
        self.assertEqual(["100", "103"], result["media_ids"])
        record = post_archive.read_json(post_archive.post_path("other", "103"))
        self.assertEqual("99", record["owner_userid"])
        self.assertEqual("other", record["handle"])

    def test_lost_or_changed_scope_uses_profile_boundary_instead_of_now(self):
        self.collect([page([media()])])
        state = feed.load_state()
        state["scope"] = "different-account-or-roster"
        state["observed_through"] = "2026-09-30T00:00:00+00:00"
        post_archive.write_json(feed.FOLLOWING_CHECKPOINT_FILE, state)
        result = self.collect([page([media("80", 8)])])
        self.assertEqual(["80"], result["media_ids"])
        self.assertEqual("2026-09-08T00:00:00+00:00", result["boundary"])

    def test_carousel_and_video_cover_serialization_without_network(self):
        value = media(media_type=8, carousel_media=[media("1"), media("2", media_type=2)])
        with patch("requests.adapters.HTTPAdapter.send", side_effect=AssertionError("No HTTP")):
            record = feed.serialize_media(value, "club", NOW)
        self.assertEqual([0, 1], [m["index"] for m in record["media"]])
        self.assertEqual([False, True], [m["is_video"] for m in record["media"]])
        self.assertEqual(["club"], record["caption_mentions"])
        self.assertTrue(record["has_video"])
        value.pop("caption")
        with self.assertRaises(KeyError):
            feed.serialize_media(value, "club", NOW)

    def test_ads_suggestions_and_nested_recommendations_are_excluded(self):
        payload = page([media()])
        edges = payload["data"][feed.CONNECTION]["edges"]
        edges.extend({"node": node} for node in [
            {"ad": {"media": media("2")}}, {"explore_story": {"media": media("3")}},
            {"end_of_feed_demarcator": {"group_set": {"groups": [{"feed_items": [media("4")]}]}}},
            {"media": media("5", is_sponsored=True)},
        ])
        items, more, cursor = feed.parse_page(payload)
        self.assertEqual(["100"], [m["pk"] for m in items])

    def test_full_roster_rotation_including_failed_profiles(self):
        checkpoints = copy.deepcopy(CHECKPOINTS)
        self.assertEqual("club", feed.select_reconciliation(ACCOUNTS, checkpoints, 1)[0]["handle"])
        checkpoints["club"].update(last_scan_at=NOW.isoformat(), last_status="incomplete")
        self.assertEqual("other", feed.select_reconciliation(ACCOUNTS, checkpoints, 1)[0]["handle"])
        self.assertEqual(CHECKPOINTS["club"]["scanned_through"], checkpoints["club"]["scanned_through"])

    def test_rotation_restores_remote_attempts_after_local_cache_loss(self):
        remote = copy.deepcopy(CHECKPOINTS)
        remote["club"].update(last_scan_at=NOW.isoformat(), last_status="incomplete")
        with patch.object(scrape_posts, "_load_remote_checkpoints", return_value=remote), \
             patch.object(scrape_posts, "_claim_remote_activation", return_value={}):
            restored = scrape_posts.resolve_checkpoints(["club", "other"], NOW)
        self.assertEqual("other", feed.select_reconciliation(ACCOUNTS, restored, 1)[0]["handle"])
        self.assertEqual(CHECKPOINTS["club"]["scanned_through"], restored["club"]["scanned_through"])

    def run_main(self, *, failure=None):
        scrape_posts.write_local_checkpoints(copy.deepcopy(CHECKPOINTS))
        feed_result = {"media_ids": ["100"], "boundary": "2026-09-08T00:00:00+00:00",
                       "scanned": 1, "discovered": 1, "updated": 0, "unchanged": 0}
        with patch.object(scrape_posts.instaloader, "Instaloader", return_value=self.loader), \
             patch.object(scrape_posts, "_login"), patch.object(scrape_posts, "_attach_http_error_logger"), \
             patch.object(scrape_posts, "_persist_rotated_session"), \
             patch.object(scrape_posts, "load_accounts", return_value=ACCOUNTS), \
             patch.object(scrape_posts, "_load_scrape_accounts", side_effect=AssertionError("No roster HTTP")), \
             patch.object(scrape_posts, "_load_remote_checkpoints", return_value=copy.deepcopy(CHECKPOINTS)), \
             patch.object(scrape_posts, "_write_remote_checkpoints"), \
             patch.object(scrape_posts, "ensure_post_dirs"), patch.object(scrape_posts, "hydrate_local_posts"), \
             patch.object(scrape_posts, "_sleep_between_accounts"), \
             patch.object(feed, "collect", return_value=feed_result, side_effect=failure), \
             patch.object(scrape_posts, "scan_account", return_value=scrape_posts.AccountResult(
                 "club", 0, 0, 0, 0, True, [])) as scan, \
             patch.object(scrape_posts, "refresh_candidates", return_value={
                 "100": {"media_id": "100"}, "50": {"media_id": "50"}}), \
             patch.object(scrape_posts, "refresh_post") as refresh:
            self.scan, self.refresh = scan, refresh
            scrape_posts.main(discovery="following", reconcile_accounts=1)

    def test_main_limits_profiles_preserves_other_coverage_and_refreshes_old_posts(self):
        self.run_main()
        self.scan.assert_called_once()
        self.assertEqual("club", self.scan.call_args.args[1]["handle"])
        saved = scrape_posts.load_local_checkpoints()
        self.assertEqual(CHECKPOINTS["other"], saved["other"])
        self.assertNotEqual(CHECKPOINTS["club"]["scanned_through"], saved["club"]["scanned_through"])
        self.assertEqual(["50"], [c.args[1]["media_id"] for c in self.refresh.call_args_list])

    def test_main_feed_failure_stops_without_profile_fallback(self):
        with self.assertRaisesRegex(RuntimeError, "Following discovery stopped"):
            self.run_main(failure=RuntimeError("unknown feed format"))
        self.scan.assert_not_called()
        self.refresh.assert_not_called()

    def test_main_pushback_stops_without_profile_fallback_or_refresh(self):
        with self.assertRaises(instagram_cooldown.CollectionStopped):
            self.run_main(failure=TooManyRequestsException("429"))
        self.scan.assert_not_called()
        self.refresh.assert_not_called()
        self.assertEqual(CHECKPOINTS, scrape_posts.load_local_checkpoints())
        with self.assertRaises(instagram_cooldown.CollectionPaused):
            instagram_cooldown.ensure_collection_allowed("posts")


class BrowserTransportTests(unittest.TestCase):
    """Exercise the actual adapter with a fake browser and no Instagram traffic."""

    def setUp(self):
        self.loader = Mock()
        self.loader.context._session.cookies = requests.cookies.RequestsCookieJar()
        self.loader.context._session.cookies.set("sessionid", "original")
        self.loader.context._session.cookies.set("csrftoken", "original-csrf")
        self.context = Mock()
        self.page = self.context.new_page.return_value
        self.page.url = feed.URL
        self.context.cookies.return_value = [
            {"name": "sessionid", "value": "rotated"},
            {"name": "csrftoken", "value": "new-csrf"},
        ]
        self.response = self.context.request.post.return_value
        self.response.status = 200
        self.response.text.return_value = json.dumps(page([media()]))
        self.browser = Mock()
        self.browser.new_context.return_value = self.context
        playwright = Mock()
        playwright.chromium.launch.return_value = self.browser
        manager = Mock()
        manager.__enter__ = Mock(return_value=playwright)
        manager.__exit__ = Mock(return_value=False)
        self.enterContext(patch.dict(sys.modules, {
            "playwright.sync_api": SimpleNamespace(sync_playwright=lambda: manager,
                                                   Error=type("BrowserError", (Exception,), {})),
        }))
        self.route = Mock()
        self.route.request.url = "https://www.instagram.com/graphql/query"
        self.route.request.method = "POST"
        self.route.request.post_data = urlencode({
            "doc_id": "observed-id", "variables": json.dumps({
                "after": "bootstrap", "data": {"pagination_source": "following"}})})
        self.route.request.all_headers.return_value = {
            "cookie": "never-replay-stale-cookies", "x-csrftoken": "old-csrf",
            "x-ig-app-id": "observed-app", "x-fb-lsd": "observed-token",
        }
        self.page.goto.side_effect = lambda *a, **kw: self.page.route.call_args.args[1](self.route)

    def test_capture_restart_pacing_and_rotated_cookie_lifecycle(self):
        with feed.browser_pages(self.loader) as fetch:
            self.assertEqual(1, len(feed.parse_page(fetch(None))[0]))
            fetch("next")
        calls = self.context.request.post.call_args_list
        self.assertIsNone(json.loads(calls[0].kwargs["form"]["variables"])["after"])
        self.assertEqual("next", json.loads(calls[1].kwargs["form"]["variables"])["after"])
        self.assertEqual("observed-id", calls[0].kwargs["form"]["doc_id"])
        self.assertNotIn("cookie", calls[0].kwargs["headers"])
        self.assertEqual("new-csrf", calls[0].kwargs["headers"]["x-csrftoken"])
        self.assertEqual(0, calls[0].kwargs["max_redirects"])
        self.assertEqual(2, self.loader.context._rate_controller.wait_before_query.call_count)
        self.assertEqual("rotated", self.loader.context._session.cookies.get("sessionid"))
        self.route.abort.assert_called_once()
        self.page.close.assert_called_once()
        self.context.close.assert_called_once()
        self.browser.close.assert_called_once()

    def test_pushback_is_not_retried_and_closes_browser(self):
        self.response.status = 429
        with self.assertRaises(TooManyRequestsException):
            with feed.browser_pages(self.loader) as fetch:
                fetch(None)
        self.context.request.post.assert_called_once()
        self.response.dispose.assert_called_once()
        self.browser.close.assert_called_once()

    def test_binary_telemetry_does_not_get_decoded_as_a_query(self):
        class BinaryRequest:
            method = "POST"
            url = "https://www.instagram.com/ajax/bz"
            resource_type = "xhr"

            @property
            def post_data(self):
                raise AssertionError("Binary telemetry must not be decoded as UTF-8")

        binary_route = Mock()
        binary_route.request = BinaryRequest()

        def navigate(*args, **kwargs):
            intercept = self.page.route.call_args.args[1]
            intercept(binary_route)
            intercept(self.route)

        self.page.goto.side_effect = navigate
        with feed.browser_pages(self.loader) as fetch:
            fetch(None)
        binary_route.continue_.assert_called_once()
        self.context.request.post.assert_called_once()

    def test_browser_pushback_aborts_subsequent_requests_before_replay(self):
        def navigate(*args, **kwargs):
            response = Mock(url="https://www.instagram.com/graphql/query", status=429)
            self.page.on.call_args.args[1](response)
            self.page.route.call_args.args[1](self.route)

        self.page.goto.side_effect = navigate
        with self.assertRaises(TooManyRequestsException):
            with feed.browser_pages(self.loader):
                self.fail("rate limited browser must not yield")
        self.route.abort.assert_called_once()
        self.context.request.post.assert_not_called()

    def test_json_challenge_is_classified_as_shared_cooldown(self):
        self.response.text.return_value = '{"message":"challenge_required"}'
        try:
            with feed.browser_pages(self.loader) as fetch:
                fetch(None)
        except Exception as exc:
            self.assertIsNotNone(instagram_cooldown.classify(exc))
        else:
            self.fail("challenge accepted")
        self.context.request.post.assert_called_once()

    def test_missing_browser_query_fails_without_replaying_anything(self):
        self.page.goto.side_effect = None
        with patch.object(feed.time, "monotonic", side_effect=[0, 46]):
            with self.assertRaisesRegex(RuntimeError, "verifiable Following"):
                with feed.browser_pages(self.loader):
                    self.fail("unverified browser yielded a fetcher")
        self.context.request.post.assert_not_called()
        self.browser.close.assert_called_once()

    def test_transport_errors_do_not_leak_request_tokens(self):
        error = sys.modules["playwright.sync_api"].Error
        self.context.request.post.side_effect = error("x-csrftoken: private-token")
        with self.assertRaisesRegex(RuntimeError, "browser transport failed") as raised:
            with feed.browser_pages(self.loader) as fetch:
                fetch(None)
        self.assertNotIn("private-token", str(raised.exception))
        self.assertTrue(raised.exception.__suppress_context__)


if __name__ == "__main__":
    unittest.main()
