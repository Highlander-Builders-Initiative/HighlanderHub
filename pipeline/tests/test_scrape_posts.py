"""Post collection: activation boundaries, pinned prefixes, and restart recovery."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from instaloader.exceptions import (
    ConnectionException,
    QueryReturnedBadRequestException,
    TooManyRequestsException,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import instagram_cooldown
import post_archive
import scrape_posts


def instant(text: str) -> datetime:
    return datetime.fromisoformat(text)


class FakePost:
    """The parts of instaloader's Post that the collector reads."""

    def __init__(self, media_id, posted_at, *, caption="Flyer", images=1,
                 video=False, shortcode=None, owner="acm.ucr"):
        self.mediaid = media_id
        self.date_utc = instant(posted_at).astimezone(timezone.utc).replace(tzinfo=None)
        self.caption = caption
        self.caption_mentions = []
        self.shortcode = shortcode or f"C{media_id}"
        self.owner_username = owner
        self.owner_id = 42
        self.is_video = video and images == 1
        self.typename = ("GraphVideo" if video and images == 1
                         else "GraphSidecar" if images > 1 else "GraphImage")
        self._images = images
        self._video = video
        self.url = f"https://cdn.example/v/t51/{media_id}_0_n.jpg?oh=sig&oe=1&stp=x"

    def get_sidecar_nodes(self):
        for index in range(self._images):
            is_video = self._video and index == self._images - 1
            yield SimpleNamespace(
                is_video=is_video,
                display_url=f"https://cdn.example/v/t51/{self.mediaid}_{index}_n.jpg?oh=s{index}&oe=9",
                video_url=None,
            )


class PostArchiveTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for module, target, value in (
            (post_archive, "POSTS_DIR", self.root / "posts"),
            (scrape_posts, "POST_CHECKPOINTS_FILE", self.root / "post_checkpoints.json"),
            (instagram_cooldown, "INSTAGRAM_COOLDOWN_FILE", self.root / "instagram_cooldown.json"),
            (instagram_cooldown, "_UNSAVED", None),
        ):
            patcher = patch.object(module, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        remote = patch.object(scrape_posts, "write_remote_posts", Mock())
        self.remote_writes = remote.start()
        self.addCleanup(remote.stop)

    def scan(self, posts, checkpoint, now="2026-09-11T12:00:00+00:00"):
        with patch.object(scrape_posts, "_graphql_feed_posts", return_value=iter(posts)):
            return scrape_posts.scan_account(
                Mock(), {"handle": "acm.ucr", "instagram_user_id": 42}, checkpoint, instant(now)
            )


class ProfileLookupTests(PostArchiveTests):
    def setUp(self):
        super().setUp()
        self.loader = scrape_posts.instaloader.Instaloader(
            quiet=True, rate_controller=scrape_posts.PacedRateController)
        self.addCleanup(self.loader.close)
        self.loader.context.username = "collector"
        self.loader.context._session.cookies.set("csrftoken", "offline-test")
        # Every test in this class is offline, even on unexpected fallback paths.
        no_http = patch("requests.adapters.HTTPAdapter.send",
                        side_effect=AssertionError("Live HTTP forbidden"))
        no_http.start()
        self.addCleanup(no_http.stop)

    @staticmethod
    def page(items, cursor=None):
        return {"status": "ok", "data": {
            "xdt_api__v1__feed__user_timeline_graphql_connection": {
                "edges": [{"node": item} for item in items],
                "page_info": {"has_next_page": cursor is not None, "end_cursor": cursor},
            },
        }}

    def graphql_scan(self):
        return scrape_posts.scan_account(
            self.loader, {"handle": "acm.ucr", "instagram_user_id": 42},
            {"activated_at": "2026-09-10T00:00:00+00:00"},
            instant("2026-09-11T12:00:00+00:00"))

    def test_real_transport_matches_upstream_feed_request_and_keeps_rate_control(self):
        import requests
        context = self.loader.context
        requests_seen = []
        metadata = {"status": "ok", "data": {"user": {
            "id": "42", "username": "acm.ucr", "media_count": 3}}}
        feed = self.page([iphone_post(str(n), media_type=t)
                          for n, t in [(700, 1), (701, 8), (702, 2)]])

        def respond(request, **kwargs):
            requests_seen.append((request.method, request.url,
                                  dict(request.headers), request.body))
            response = requests.Response()
            response.status_code = 200
            response.request = request
            response.url = request.url
            # The first request is the original Profile metadata fetch.
            response._content = json.dumps(metadata if len(requests_seen) == 1 else feed).encode()
            return response

        controller = context._rate_controller
        with patch("requests.adapters.HTTPAdapter.send", side_effect=respond), \
             patch.object(context, "do_sleep"), \
             patch.object(controller, "sleep"), \
             patch.object(controller, "wait_before_query", wraps=controller.wait_before_query) as pace:
            upstream = list(scrape_posts.instaloader.Profile(
                context, {"id": "42", "username": "acm.ucr"}).get_posts())
            self.assertEqual(2, len(requests_seen))
            pace.reset_mock()
            result = self.graphql_scan()
            self.assertEqual(3, len(requests_seen))
            self.assertEqual(requests_seen[1], requests_seen[2])
            pace.assert_called_once_with("7898261790222653")
        self.assertTrue(result.complete)
        self.assertEqual(3, result.discovered)
        self.assertEqual(
            [scrape_posts.serialize_post(post, "acm.ucr", seen_at=instant("2026-09-11T12:00:00+00:00"))
             for post in upstream], self.remote_writes.call_args.args[0])

    def test_pagination_preserves_pinned_prefix_and_date_boundary(self):
        old = [iphone_post(str(n), posted_at="2020-01-01T00:00:00+00:00") for n in range(3)]
        with patch.object(self.loader.context, "get_json", side_effect=[
                self.page(old, "next"), self.page([iphone_post(), old[0]], "unused")]) as request:
            result = self.graphql_scan()
        self.assertTrue(result.complete)
        self.assertEqual(["700"], result.media_ids)
        self.assertEqual(2, request.call_count)
        variables = json.loads(request.call_args.kwargs["params"]["variables"])
        self.assertEqual("next", variables["after"])
        self.assertEqual("acm.ucr", variables["username"])

    def test_wrong_or_missing_owner_rejects_entire_page_even_outside_window(self):
        for owner in ({"pk": "99"}, {}, None):
            bad = iphone_post("701", posted_at="2020-01-01T00:00:00+00:00")
            bad["user"] = owner
            with self.subTest(owner=owner), \
                 patch.object(self.loader.context, "get_json", return_value=self.page([iphone_post(), bad])):
                with self.assertRaisesRegex(RuntimeError, "owner ID"):
                    self.graphql_scan()
                self.remote_writes.assert_not_called()
                self.assertEqual([], list((self.root / "posts").glob("*/*.json")))

    def test_owner_validation_applies_to_later_pages(self):
        wrong = iphone_post("701")
        wrong["user"]["pk"] = "99"
        with patch.object(self.loader.context, "get_json", side_effect=[
                self.page([iphone_post()], "next"), self.page([wrong])]):
            with self.assertRaisesRegex(RuntimeError, "owner ID"):
                self.graphql_scan()
        self.assertTrue((self.root / "posts" / "acm.ucr" / "700.json").exists())
        self.assertFalse((self.root / "posts" / "acm.ucr" / "701.json").exists())
        self.remote_writes.assert_not_called()

    def test_empty_first_page_and_malformed_pagination_do_not_establish_coverage(self):
        malformed = self.page([iphone_post()])
        del malformed["data"]["xdt_api__v1__feed__user_timeline_graphql_connection"]["page_info"]
        for response in (self.page([]), malformed):
            with self.subTest(response=response), \
                 patch.object(self.loader.context, "get_json", return_value=response):
                with self.assertRaisesRegex(RuntimeError, "empty GraphQL|malformed GraphQL"):
                    self.graphql_scan()
                self.remote_writes.assert_not_called()

    def test_empty_final_page_after_verified_owner_can_complete(self):
        with patch.object(self.loader.context, "get_json", side_effect=[
                self.page([iphone_post()], "next"), self.page([])]):
            self.assertTrue(self.graphql_scan().complete)

    def test_logged_out_scan_fails_before_any_request(self):
        self.loader.context.username = None
        with patch.object(self.loader.context, "get_json") as request:
            with self.assertRaisesRegex(RuntimeError, "requires login"):
                self.graphql_scan()
            request.assert_not_called()

    def test_identity_failure_retains_persisted_checkpoint(self):
        before = {"activated_at": "2026-09-01T00:00:00+00:00",
                  "scanned_through": "2026-09-10T00:00:00+00:00"}
        wrong = iphone_post()
        wrong["user"]["pk"] = "99"
        for response in (self.page([wrong]), self.page([])):
            scrape_posts.write_local_checkpoints({"acm.ucr": before})
            with self.subTest(response=response), \
                 patch.object(scrape_posts.instaloader, "Instaloader", return_value=self.loader), \
                 patch.object(self.loader, "close"), \
                 patch.object(self.loader.context, "get_json", return_value=response), \
                 patch.object(scrape_posts, "_login"), \
                 patch.object(scrape_posts, "_attach_http_error_logger"), \
                 patch.object(scrape_posts, "_persist_rotated_session"), \
                 patch.object(scrape_posts, "_load_scrape_accounts", return_value=[
                     {"handle": "acm.ucr", "instagram_user_id": 42}]), \
                 patch.object(scrape_posts, "resolve_checkpoints", return_value={"acm.ucr": dict(before)}), \
                 patch.object(scrape_posts, "_write_remote_checkpoints") as remote_checkpoints, \
                 patch.object(scrape_posts, "refresh_candidates", return_value={}), \
                 patch.object(scrape_posts, "hydrate_local_posts"), \
                 patch.object(scrape_posts, "ensure_post_dirs"):
                with self.assertRaisesRegex(RuntimeError, "1 failure"):
                    scrape_posts.main()
                self.assertEqual(before, scrape_posts.load_local_checkpoints()["acm.ucr"])
                self.assertEqual(before, remote_checkpoints.call_args.args[0]["acm.ucr"])
                self.remote_writes.assert_not_called()

    def test_missing_id_fails_without_falling_back_to_username_lookup(self):
        loader = Mock()
        with patch.object(scrape_posts.instaloader, "Profile") as profile:
            with self.assertRaisesRegex(ValueError, "missing instagram_user_id"):
                scrape_posts.scan_account(
                    loader, {"handle": "acm.ucr"},
                    {"activated_at": "2026-09-10T00:00:00+00:00"},
                    instant("2026-09-11T12:00:00+00:00"),
                )
        profile.assert_not_called()
        profile.from_username.assert_not_called()
        self.remote_writes.assert_not_called()


def iphone_post(media_id="700", *, media_type=1, posted_at="2026-09-11T09:00:00+00:00"):
    """Representative v1 wire format consumed by the installed Instaloader."""
    photo = {"media_type": 1, "image_versions2": {"candidates": [
        {"url": "https://cdn.example/photo.jpg"}]}}
    video = {"media_type": 2, "image_versions2": {"candidates": [
        {"url": "https://cdn.example/cover.jpg"}]},
        "video_versions": [{"url": "https://cdn.example/video.mp4"}]}
    return {
        "pk": media_id, "code": f"C{media_id}", "media_type": media_type,
        "taken_at": int(instant(posted_at).timestamp()),
        "caption": {"text": "Meet @ieee.ucr"}, "has_liked": False, "like_count": 0,
        "user": {"pk": "42", "username": "renamed.ucr", "is_private": False,
                 "full_name": "Club", "profile_pic_url": "https://cdn.example/avatar.jpg"},
        "image_versions2": photo["image_versions2"],
        "carousel_media": [photo, video],
        "video_versions": video["video_versions"],
    }


class DirectFeedTests(PostArchiveTests):
    def setUp(self):
        super().setUp()
        self.loader = scrape_posts.instaloader.Instaloader(
            quiet=True, rate_controller=scrape_posts.PacedRateController)
        self.addCleanup(self.loader.close)
        self.loader.context.username = "collector"

    def direct_scan(self):
        return scrape_posts.scan_account(
            self.loader, {"handle": "acm.ucr", "instagram_user_id": 42},
            {"activated_at": "2026-09-10T00:00:00+00:00"},
            instant("2026-09-11T12:00:00+00:00"), direct_feed=True)

    def test_one_page_serializes_images_carousels_and_video_without_metadata_requests(self):
        items = [iphone_post(str(n), media_type=t) for n, t in [(700, 1), (701, 8), (702, 2)]]
        with patch.object(self.loader.context, "get_json", return_value={
                "status": "ok", "items": items, "more_available": False}) as request, \
             patch("requests.sessions.Session.request", side_effect=AssertionError("Live HTTP forbidden")):
            result = self.direct_scan()
        self.assertTrue(result.complete)
        self.assertEqual(3, result.discovered)
        request.assert_called_once_with("api/v1/feed/user/42/", params={"count": 12})
        records = self.remote_writes.call_args.args[0]
        self.assertEqual(["GraphImage", "GraphSidecar", "GraphVideo"], [r["typename"] for r in records])
        self.assertEqual([False, True], [m["is_video"] for m in records[1]["media"]])
        self.assertEqual(["photo", "cover"], [m["media_key"] for m in records[1]["media"]])
        self.assertEqual("renamed.ucr", records[0]["owner_username"])
        self.assertEqual(["ieee.ucr"], records[0]["caption_mentions"])

    def test_pagination_skips_pinned_prefix_and_stops_at_boundary(self):
        old = [iphone_post(str(n), posted_at="2020-01-01T00:00:00+00:00") for n in range(3)]
        pages = [
            {"status": "ok", "items": old, "more_available": True, "next_max_id": "next"},
            {"status": "ok", "items": [iphone_post(), old[0]],
             "more_available": True, "next_max_id": "unused"},
        ]
        with patch.object(self.loader.context, "get_json", side_effect=pages) as request:
            result = self.direct_scan()
        self.assertTrue(result.complete)
        self.assertEqual(["700"], result.media_ids)
        self.assertEqual(2, request.call_count)
        self.assertEqual({"count": 12, "max_id": "next"}, request.call_args.kwargs["params"])

    def test_budget_exhaustion_mirrors_partial_records_but_is_incomplete(self):
        pages = [{"status": "ok", "items": [iphone_post(str(700 + n))],
                  "more_available": True, "next_max_id": str(n)} for n in range(3)]
        with patch.object(self.loader.context, "get_json", side_effect=pages) as request:
            result = self.direct_scan()
        self.assertFalse(result.complete)
        self.assertEqual(3, request.call_count)
        self.assertEqual(3, len(self.remote_writes.call_args.args[0]))

    def test_malformed_or_repeating_pages_never_establish_coverage(self):
        for page in ({"status": "ok"}, {"status": "ok", "items": []},
                     {"status": "ok", "items": [], "more_available": True},
                     {"status": "ok", "items": [], "more_available": True, "next_max_id": "same"}):
            with self.subTest(page=page), \
                 patch.object(self.loader.context, "get_json", return_value=page) as request:
                with self.assertRaises(RuntimeError):
                    self.direct_scan()
                self.assertLessEqual(request.call_count, 2)
                self.remote_writes.assert_not_called()

    def test_real_transport_keeps_pacing_hooks_cookies_and_stops_pushback_without_retry(self):
        import requests
        context = self.loader.context
        session = context._session
        saved_headers = dict(session.headers)
        saved_attempts = context.max_connection_attempts
        saved_fatal = context.fatal_status_codes
        hook = Mock()
        session.hooks["response"].append(hook)
        for status, body, kind in (
            (200, {"status": "ok", "items": [], "more_available": False}, None),
            (429, {"status": "fail", "message": "Too many requests"}, instagram_cooldown.Kind.THROTTLED),
            (401, {"status": "fail"}, instagram_cooldown.Kind.CHALLENGED),
            (403, {"status": "fail"}, instagram_cooldown.Kind.CHALLENGED),
            (400, {"message": "challenge_required"}, instagram_cooldown.Kind.CHALLENGED),
            (400, {"message": "feedback_required", "spam": True,
                   "feedback_title": "Try Again Later", "status": "fail"},
             instagram_cooldown.Kind.THROTTLED),
            (200, {"status": "fail", "message": "Please wait a few minutes"}, instagram_cooldown.Kind.THROTTLED),
            (302, {}, instagram_cooldown.Kind.CHALLENGED),
        ):
            with self.subTest(status=status, body=body):
                response = requests.Response()
                response.status_code = status
                response.reason = "Test response"
                response._content = json.dumps(body).encode()
                response.headers["Content-Type"] = "application/json"
                if status == 302:
                    response.headers["location"] = "https://www.instagram.com/accounts/login/"
                hook.reset_mock()
                hook.return_value = response
                def respond(request, **kwargs):
                    self.assertEqual("https://www.instagram.com/api/v1/feed/user/42/?count=12", request.url)
                    self.assertEqual("936619743392459", request.headers["X-IG-App-ID"])
                    self.assertEqual("https://www.instagram.com/acm.ucr/", request.headers["Referer"])
                    response.request = request
                    response.url = request.url
                    session.cookies.set("sessionid", "rotated-offline")
                    return response
                controller = context._rate_controller
                with patch("requests.adapters.HTTPAdapter.send", side_effect=respond) as send, \
                     patch.object(context, "do_sleep"), \
                     patch.object(controller, "sleep") as sleep, \
                     patch.object(controller, "wait_before_query", wraps=controller.wait_before_query) as pace:
                    if kind is None:
                        self.assertTrue(self.direct_scan().complete)
                    else:
                        with self.assertRaises(BaseException) as raised:
                            self.direct_scan()
                        block = instagram_cooldown.classify(raised.exception, lone_400=True)
                        self.assertIsNotNone(block, repr(raised.exception))
                        self.assertEqual(kind, block.kind)
                    self.assertEqual(1, send.call_count)
                    pace.assert_called_once_with("other")
                    self.assertTrue(sleep.called)
                    hook.assert_called_once()
                self.assertEqual(saved_headers, dict(session.headers))
                self.assertEqual(saved_attempts, context.max_connection_attempts)
                self.assertIs(saved_fatal, context.fatal_status_codes)
                self.assertEqual("rotated-offline", session.cookies.get("sessionid"))

    def test_unbounded_pilot_is_rejected_before_any_side_effect(self):
        for handles in (None, [], [" "], [str(n) for n in range(6)]):
            with self.subTest(handles=handles), patch.object(scrape_posts, "ensure_post_dirs") as dirs:
                with self.assertRaisesRegex(ValueError, "requires"):
                    scrape_posts.main(handles, direct_feed=True)
                dirs.assert_not_called()


class MediaIdentityTests(unittest.TestCase):
    def test_signature_changes_do_not_change_media_identity(self):
        first = "https://cdn.example/v/t51/12345_0_n.jpg?stp=dst-jpg&oh=abc&oe=68F1&_nc_gid=x"
        second = "https://other.cdn.example/v/t51/12345_0_n.jpg?stp=other&oh=zzz&oe=9999"
        self.assertEqual(post_archive.media_key(first), post_archive.media_key(second))
        self.assertEqual("12345_0_n", post_archive.media_key(first))

    def test_different_media_keep_different_identities(self):
        self.assertNotEqual(
            post_archive.media_key("https://cdn.example/v/t51/12345_0_n.jpg?oh=a"),
            post_archive.media_key("https://cdn.example/v/t51/12345_1_n.jpg?oh=a"),
        )


class ActivationBoundaryTests(PostArchiveTests):
    def test_posts_published_before_activation_are_never_imported(self):
        checkpoint = {"activated_at": "2026-09-10T00:00:00+00:00"}
        result = self.scan([
            FakePost("300", "2026-09-11T09:00:00+00:00"),
            FakePost("200", "2026-09-09T09:00:00+00:00"),
        ], checkpoint)
        self.assertEqual(["300"], result.media_ids)
        self.assertFalse((self.root / "posts" / "acm.ucr" / "200.json").exists())

    def test_an_activated_account_never_looks_behind_its_activation(self):
        # The single invariant the whole feature rests on: whatever the
        # checkpoint says, a scan cannot reach back past activation.
        for through in (None, "2026-09-11T00:00:00+00:00", "2020-01-01T00:00:00+00:00"):
            checkpoint = {"activated_at": "2026-09-10T00:00:00+00:00"}
            if through:
                checkpoint["scanned_through"] = through
            with self.subTest(scanned_through=through):
                self.assertGreaterEqual(
                    scrape_posts.scan_boundary(checkpoint, instant("2026-09-11T12:00:00+00:00")),
                    instant("2026-09-10T00:00:00+00:00"),
                )

    def test_a_post_published_exactly_at_activation_is_collected(self):
        checkpoint = {"activated_at": "2026-09-10T00:00:00+00:00"}
        result = self.scan([FakePost("250", "2026-09-10T00:00:00+00:00")], checkpoint)
        self.assertEqual(["250"], result.media_ids)

    def test_an_old_post_pinned_above_new_ones_does_not_end_the_scan(self):
        # Instagram renders pinned posts first regardless of age, and
        # `Post.is_pinned` is unreliable — the first entries must not be read
        # as "the feed is now older than the boundary".
        checkpoint = {"activated_at": "2026-09-01T00:00:00+00:00",
                      "scanned_through": "2026-09-10T00:00:00+00:00"}
        result = self.scan([
            FakePost("100", "2026-01-04T09:00:00+00:00"),   # pinned, ancient
            FakePost("101", "2026-01-03T09:00:00+00:00"),   # pinned, ancient
            FakePost("900", "2026-09-11T09:00:00+00:00"),   # genuinely new
            FakePost("899", "2026-09-08T09:00:00+00:00"),   # inside the overlap
            FakePost("500", "2026-02-01T09:00:00+00:00"),   # older than boundary
        ], checkpoint)
        self.assertEqual(["900", "899"], result.media_ids)
        self.assertTrue(result.complete)

    def test_a_pinned_post_inside_the_overlap_is_collected_normally(self):
        # Being in the pinned prefix only stops an entry from ending the scan;
        # it never excludes the entry itself.
        checkpoint = {"activated_at": "2026-09-01T00:00:00+00:00",
                      "scanned_through": "2026-09-11T00:00:00+00:00"}
        result = self.scan([
            FakePost("100", "2026-09-06T09:00:00+00:00"),   # pinned, still in window
            FakePost("900", "2026-09-11T09:00:00+00:00"),
        ], checkpoint)
        self.assertEqual({"100", "900"}, set(result.media_ids))


class OverlapAndCheckpointTests(PostArchiveTests):
    def test_discovery_rewalks_a_seven_day_overlap_bounded_by_activation(self):
        boundary = scrape_posts.scan_boundary(
            {"activated_at": "2026-01-01T00:00:00+00:00",
             "scanned_through": "2026-09-11T00:00:00+00:00"},
            instant("2026-09-11T12:00:00+00:00"),
        )
        self.assertEqual(instant("2026-09-04T00:00:00+00:00"), boundary)

    def test_the_overlap_never_reaches_behind_activation(self):
        boundary = scrape_posts.scan_boundary(
            {"activated_at": "2026-09-09T00:00:00+00:00",
             "scanned_through": "2026-09-11T00:00:00+00:00"},
            instant("2026-09-11T12:00:00+00:00"),
        )
        self.assertEqual(instant("2026-09-09T00:00:00+00:00"), boundary)

    def test_an_interrupted_scan_keeps_its_items_and_retains_the_checkpoint(self):
        def explode(*args):
            yield FakePost("900", "2026-09-11T09:00:00+00:00")
            raise ConnectionException("page 2 timed out")

        checkpoint = {"activated_at": "2026-09-01T00:00:00+00:00",
                      "scanned_through": "2026-09-10T00:00:00+00:00"}
        with patch.object(scrape_posts, "_graphql_feed_posts", side_effect=explode):
            with self.assertRaises(ConnectionException):
                scrape_posts.scan_account(Mock(), {"handle": "acm.ucr", "instagram_user_id": 42}, checkpoint,
                                          instant("2026-09-11T12:00:00+00:00"))
        # The item collected before the failure survives on disk...
        self.assertTrue((self.root / "posts" / "acm.ucr" / "900.json").exists())
        # ...and the checkpoint did not advance, so the rest is retried.
        self.assertEqual("2026-09-10T00:00:00+00:00", checkpoint["scanned_through"])

    def test_a_busy_feed_reaches_the_boundary_beyond_sixty_posts(self):
        now = instant("2026-09-11T12:00:00+00:00")
        posts = [FakePost(str(900 - n), (now - timedelta(hours=n)).isoformat())
                 for n in range(80)]
        posts.append(FakePost("100", "2026-09-01T00:00:00+00:00"))
        checkpoint = {"activated_at": "2026-09-01T00:00:00+00:00",
                      "scanned_through": "2026-09-10T00:00:00+00:00"}
        # A second newest-first walk must not get stuck on the same 60 posts.
        for _ in range(2):
            result = self.scan(posts, checkpoint)
            self.assertTrue(result.complete)
            self.assertEqual([str(900 - n) for n in range(80)], result.media_ids)
        self.assertEqual(80, len(list(post_archive.iter_local_posts())))
        self.assertEqual(80, len(self.remote_writes.call_args.args[0]))

    def test_durable_write_failure_prevents_the_checkpoint_from_advancing(self):
        self.remote_writes.side_effect = RuntimeError("supabase unavailable")
        with self.assertRaises(RuntimeError):
            self.scan([FakePost("900", "2026-09-11T09:00:00+00:00")],
                      {"activated_at": "2026-09-01T00:00:00+00:00"})


class RestartRecoveryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        patcher = patch.object(scrape_posts, "POST_CHECKPOINTS_FILE",
                               self.root / "post_checkpoints.json")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_lost_local_cache_recovers_activation_instead_of_resetting_it(self):
        original = "2026-06-01T00:00:00+00:00"
        remote = {"acm.ucr": {"handle": "acm.ucr", "activated_at": original,
                              "scanned_through": "2026-09-10T00:00:00+00:00"}}
        claim = Mock(return_value={})
        with patch.object(scrape_posts, "_load_remote_checkpoints", return_value=remote), \
             patch.object(scrape_posts, "_claim_remote_activation", claim):
            resolved = scrape_posts.resolve_checkpoints(["acm.ucr"], instant("2026-09-11T12:00:00+00:00"))
        self.assertEqual(original, resolved["acm.ucr"]["activated_at"])
        # Nothing was re-activated, so no history can re-enter the feed.
        claim.assert_called_once_with([])

    def test_a_new_account_activates_once_and_keeps_the_stored_boundary(self):
        stored = {"acm.ucr": {"activated_at": "2026-09-01T00:00:00+00:00"}}
        with patch.object(scrape_posts, "_load_remote_checkpoints", return_value={}), \
             patch.object(scrape_posts, "_claim_remote_activation", return_value=stored):
            resolved = scrape_posts.resolve_checkpoints(["acm.ucr"], instant("2026-09-11T12:00:00+00:00"))
        # The durable row already held an earlier activation; the claim did not
        # move it, and the run adopts what the store actually has.
        self.assertEqual("2026-09-01T00:00:00+00:00", resolved["acm.ucr"]["activated_at"])

    def test_a_failed_claim_is_retried_with_the_original_local_activation(self):
        first = instant("2026-09-01T00:00:00+00:00")
        stored = {"acm.ucr": {"activated_at": first.isoformat()}}
        with patch.object(scrape_posts, "_load_remote_checkpoints", return_value={}), \
             patch.object(scrape_posts, "_claim_remote_activation",
                          side_effect=[{}, {}, stored]) as claim:
            for day in (0, 1, 2):
                resolved = scrape_posts.resolve_checkpoints(["acm.ucr"], first + timedelta(days=day))
                self.assertEqual(first.isoformat(), resolved["acm.ucr"]["activated_at"])
        self.assertEqual(
            [[{"handle": "acm.ucr", "activated_at": first.isoformat()}]] * 3,
            [call.args[0] for call in claim.call_args_list])
        # Once the retry is durable, losing the local file preserves the boundary.
        scrape_posts.POST_CHECKPOINTS_FILE.unlink()
        with patch.object(scrape_posts, "_load_remote_checkpoints", return_value=stored), \
             patch.object(scrape_posts, "_claim_remote_activation", return_value={}):
            restored = scrape_posts.resolve_checkpoints(["acm.ucr"], first + timedelta(days=3))
        self.assertEqual(first.isoformat(), restored["acm.ucr"]["activated_at"])

    def test_a_retry_adopts_the_durable_boundary_and_progress_after_a_read_failure(self):
        scrape_posts.write_local_checkpoints({"acm.ucr": {
            "activated_at": "2026-09-10T00:00:00+00:00"}})
        stored = {"acm.ucr": {"activated_at": "2026-06-01T00:00:00+00:00",
                              "scanned_through": "2026-09-09T00:00:00+00:00"}}
        with patch.object(scrape_posts, "_load_remote_checkpoints", return_value={}), \
             patch.object(scrape_posts, "_claim_remote_activation", return_value=stored):
            resolved = scrape_posts.resolve_checkpoints(["acm.ucr"], instant("2026-09-11T12:00:00+00:00"))
        self.assertEqual(stored, resolved)

    def test_progress_from_a_different_activation_cannot_skip_the_durable_interval(self):
        for through in (None, "2026-09-02T00:00:00+00:00"):
            with self.subTest(remote_through=through):
                scrape_posts.write_local_checkpoints({"acm.ucr": {
                    "activated_at": "2026-09-10T00:00:00+00:00",
                    "scanned_through": "2026-09-11T00:00:00+00:00"}})
                stored = {"acm.ucr": {"activated_at": "2026-06-01T00:00:00+00:00",
                                      "scanned_through": through}}
                with patch.object(scrape_posts, "_load_remote_checkpoints", return_value=stored), \
                     patch.object(scrape_posts, "_claim_remote_activation", return_value={}):
                    resolved = scrape_posts.resolve_checkpoints(
                        ["acm.ucr"], instant("2026-09-11T12:00:00+00:00"))
                self.assertEqual(through, resolved["acm.ucr"].get("scanned_through"))

    def test_a_pilot_run_keeps_the_checkpoints_of_accounts_it_did_not_touch(self):
        # `--handle acm.ucr` resolves one account. The file is a keyed store, so
        # the other clubs' activation boundaries have to survive the write —
        # losing one re-admits a back catalogue or silently skips an interval.
        seeded = {
            "acm.ucr": {"activated_at": "2026-06-01T00:00:00+00:00",
                        "scanned_through": "2026-09-10T00:00:00+00:00"},
            "ieee.ucr": {"activated_at": "2026-05-01T00:00:00+00:00",
                         "scanned_through": "2026-09-10T00:00:00+00:00"},
        }
        scrape_posts.write_local_checkpoints(seeded)
        with patch.object(scrape_posts, "_load_remote_checkpoints", return_value={}), \
             patch.object(scrape_posts, "_claim_remote_activation", return_value={}):
            resolved = scrape_posts.resolve_checkpoints(
                ["acm.ucr"], instant("2026-09-11T12:00:00+00:00"))
        # The run itself only carries the account it was asked for.
        self.assertEqual(["acm.ucr"], sorted(resolved))
        self.assertEqual(seeded, scrape_posts.load_local_checkpoints())
        resolved["acm.ucr"]["scanned_through"] = "2026-09-11T12:00:00+00:00"
        scrape_posts.write_local_checkpoints(resolved)
        self.assertEqual(seeded["ieee.ucr"], scrape_posts.load_local_checkpoints()["ieee.ucr"])

    def test_the_resume_point_is_the_older_of_local_and_remote_progress(self):
        scrape_posts.write_local_checkpoints({"acm.ucr": {
            "activated_at": "2026-06-01T00:00:00+00:00",
            "scanned_through": "2026-09-11T00:00:00+00:00"}})
        remote = {"acm.ucr": {"handle": "acm.ucr", "activated_at": "2026-06-01T00:00:00+00:00",
                              "scanned_through": "2026-09-05T00:00:00+00:00"}}
        with patch.object(scrape_posts, "_load_remote_checkpoints", return_value=remote), \
             patch.object(scrape_posts, "_claim_remote_activation", return_value={}):
            resolved = scrape_posts.resolve_checkpoints(["acm.ucr"], instant("2026-09-11T12:00:00+00:00"))
        self.assertEqual("2026-09-05T00:00:00+00:00", resolved["acm.ucr"]["scanned_through"])


class CheckpointWriteTests(unittest.TestCase):
    def test_progress_cannot_overwrite_an_unconfirmed_or_conflicting_activation(self):
        local = {"acm.ucr": {"activated_at": "2026-09-10T00:00:00+00:00",
                             "scanned_through": "2026-09-11T12:00:00+00:00"}}
        for claimed in ({}, {"acm.ucr": {"activated_at": "2026-06-01T00:00:00+00:00"}}):
            with self.subTest(claimed=claimed), \
                 patch.object(scrape_posts, "_claim_remote_activation", return_value=claimed), \
                 patch.dict(sys.modules, {"db": SimpleNamespace(upsert_batched=Mock())}):
                writer = sys.modules["db"].upsert_batched
                scrape_posts._write_remote_checkpoints(local)
                writer.assert_not_called()

    def test_progress_is_written_only_for_accounts_with_the_same_durable_boundary(self):
        local = {"acm.ucr": {"activated_at": "2026-09-01T00:00:00+00:00",
                             "scanned_through": "2026-09-11T12:00:00+00:00"},
                 "ieee.ucr": {"activated_at": "2026-09-02T00:00:00+00:00"}}
        claimed = {"acm.ucr": {"activated_at": "2026-09-01T00:00:00Z"}}
        writer = Mock()
        with patch.object(scrape_posts, "_claim_remote_activation", return_value=claimed) as claim, \
             patch.dict(sys.modules, {"db": SimpleNamespace(upsert_batched=writer)}):
            scrape_posts._write_remote_checkpoints(local)
        self.assertEqual(2, len(claim.call_args.args[0]))
        rows = writer.call_args.args[1]
        self.assertEqual(["acm.ucr"], [row["handle"] for row in rows])
        self.assertEqual(local["acm.ucr"]["scanned_through"], rows[0]["scanned_through"])


class FakeMirror:
    """The `instagram_posts` reads an archive restore actually makes."""

    def __init__(self, rows):
        self.rows = sorted(rows, key=lambda row: str(row["media_id"]))
        self.ranges: list[tuple[int, int]] = []
        self.id_requests: list[list[str]] = []
        self._selected: list[str] = []
        self._page: list[dict] = []

    def __call__(self):  # stands in for db.client()
        return self

    def table(self, name):
        assert name == "instagram_posts", name
        return self

    def select(self, columns):
        self._selected = [column.strip() for column in columns.split(",")]
        return self

    def order(self, field):
        return self

    def range(self, start, end):
        # PostgREST ranges are inclusive on both ends.
        self.ranges.append((start, end))
        self._page = self.rows[start:end + 1]
        return self

    def in_(self, field, values):
        self.id_requests.append(list(values))
        wanted = {str(value) for value in values}
        self._page = [row for row in self.rows if str(row[field]) in wanted]
        return self

    def execute(self):
        page, self._page = self._page, []
        return SimpleNamespace(data=[
            {column: row.get(column) for column in self._selected} for row in page])


class ArchiveRestoreTests(unittest.TestCase):
    """A lost `data/` directory comes back from the durable mirror."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        patcher = patch.object(post_archive, "POSTS_DIR", self.root / "posts")
        patcher.start()
        self.addCleanup(patcher.stop)

    def mirror_row(self, media_id="700", *, caption="Flyer", handle="acm.ucr",
                   first_seen="2026-09-01T00:00:00+00:00"):
        """One `instagram_posts` row, built by the collector's own serializer."""
        record = scrape_posts.serialize_post(
            FakePost(media_id, "2026-09-02T09:00:00+00:00", caption=caption, owner=handle),
            handle, seen_at=instant("2026-09-02T12:00:00+00:00"))
        return {"media_id": media_id, "handle": handle,
                "first_seen_at": first_seen, "record": record}

    def hydrate(self, client):
        with patch.dict(sys.modules, {"db": SimpleNamespace(client=client)}):
            return post_archive.hydrate_local_posts()

    def test_a_lost_archive_is_restored_from_the_mirror(self):
        mirror = FakeMirror([self.mirror_row("700"),
                             self.mirror_row("800", caption="Bake sale")])
        self.assertEqual(2, self.hydrate(mirror))
        saved = {record["media_id"]: record for record in post_archive.iter_local_posts()}
        self.assertEqual({"700", "800"}, set(saved))
        self.assertEqual("Bake sale", saved["800"]["caption"])
        # The durable first-seen survives: a restored post is not newly found.
        self.assertEqual("2026-09-01T00:00:00+00:00", saved["700"]["first_seen_at"])

    def test_a_restored_post_is_not_rediscovered_as_new(self):
        # The whole point of restoring: the next scan sees the post it already
        # collected, so it costs no OCR, no model call, and no "discovered".
        row = self.mirror_row("700")
        self.hydrate(FakeMirror([row]))
        rescanned = dict(row["record"], fetched_at="2026-09-11T12:00:00+00:00")
        self.assertEqual("unchanged", post_archive.write_post(rescanned))

    def test_a_post_already_on_disk_is_never_overwritten(self):
        # The local file was written before the mirror row it produced, so it is
        # at least as fresh — a stale mirror must not undo a caption correction.
        post_archive.write_post(
            self.mirror_row("700", caption="Study jam is cancelled")["record"])
        mirror = FakeMirror([self.mirror_row("700", caption="Study jam")])
        self.assertEqual(0, self.hydrate(mirror))
        # Nothing was even fetched, so an intact archive costs one request.
        self.assertEqual([], mirror.id_requests)
        saved = next(iter(post_archive.iter_local_posts()))
        self.assertEqual("Study jam is cancelled", saved["caption"])

    def test_a_corrupt_local_file_counts_as_absent_and_is_replaced(self):
        path = post_archive.post_path("acm.ucr", "700")
        path.parent.mkdir(parents=True)
        path.write_text("{ truncated")
        self.assertEqual(1, self.hydrate(FakeMirror([self.mirror_row("700")])))
        self.assertEqual("Flyer", post_archive.read_json(path)["caption"])

    def test_mirrored_identifiers_never_become_paths_outside_the_archive(self):
        for value in ("..", ".", "../../escaped", "a/b", "", None):
            with self.subTest(value=value):
                self.assertEqual("", post_archive._path_token(value))
        rows = [self.mirror_row("../../escaped"), self.mirror_row("700", handle="../..")]
        self.assertEqual(0, self.hydrate(FakeMirror(rows)))
        self.assertFalse((self.root / "posts").exists())

    def test_an_unreadable_mirror_costs_coverage_not_the_run(self):
        for failure in (RuntimeError("supabase unavailable"),
                        SystemExit("Supabase env missing")):
            with self.subTest(failure=type(failure).__name__):
                def explode(*args):
                    raise failure

                self.assertEqual(0, self.hydrate(explode))

    def test_a_mirror_larger_than_one_page_is_walked_completely(self):
        mirror = FakeMirror([self.mirror_row(str(media_id))
                             for media_id in (700, 800, 900)])
        with patch.object(post_archive, "RESTORE_PAGE", 2):
            self.assertEqual(3, self.hydrate(mirror))
        # An inclusive-range off-by-one here would silently skip a post.
        self.assertEqual([(0, 1), (2, 3)], mirror.ranges)
        self.assertEqual(3, len(list(post_archive.iter_local_posts())))

    def test_a_restored_post_outside_the_overlap_remains_available_for_live_event_refresh(self):
        self.hydrate(FakeMirror([self.mirror_row("700")]))
        now = instant("2026-09-20T12:00:00+00:00")
        rows = [{"source_key": "instagram:post:700", "event_ids": ["ig_future"]}]
        client = Mock()
        client.return_value.table.return_value.select.return_value.like.return_value.execute.return_value.data = rows
        with patch.dict(sys.modules, {"db": SimpleNamespace(
                client=client, get_event_rows_by_ids=lambda ids: [
                    {"id": "ig_future", "starts_at": "2026-09-25T22:00:00+00:00"}])}):
            eligible = scrape_posts.refresh_candidates(now)
        self.assertEqual(["700"], list(eligible))
        self.assertEqual("C700", eligible["700"]["shortcode"])


class CollectionRunTests(PostArchiveTests):
    """The collector entrypoint end to end, with Instagram mocked out."""

    def run_main(self, accounts, posts_by_handle, *, refresh=None, handles=None, direct_feed=False):
        def get_posts(loader, handle, user_id):
            return iter(posts_by_handle.get(handle, []))

        loader = Mock()
        with patch.object(scrape_posts.instaloader, "Instaloader", return_value=loader), \
             patch.object(scrape_posts, "_graphql_feed_posts", side_effect=get_posts), \
             patch.object(scrape_posts, "_login"), \
             patch.object(scrape_posts, "_attach_http_error_logger"), \
             patch.object(scrape_posts, "_persist_rotated_session"), \
             patch.object(scrape_posts, "_load_scrape_accounts", return_value=accounts), \
             patch.object(scrape_posts, "_load_remote_checkpoints", return_value={}), \
             patch.object(scrape_posts, "_claim_remote_activation", return_value={}), \
             patch.object(scrape_posts, "_write_remote_checkpoints"), \
             patch.object(scrape_posts, "refresh_candidates", return_value=refresh or {}), \
             patch.object(scrape_posts, "_sleep_between_accounts"), \
             patch.object(scrape_posts, "hydrate_local_posts") as hydrate, \
             patch.object(scrape_posts, "ensure_post_dirs"):
            scrape_posts.main(handles, direct_feed=direct_feed)
        self.hydrated = hydrate

    def test_a_first_run_activates_accounts_and_imports_nothing_older(self):
        accounts = [{"handle": "acm.ucr", "instagram_user_id": 42}, {"handle": "ieee.ucr", "instagram_user_id": 43}]
        posts = {
            "acm.ucr": [FakePost("900", "2026-09-11T09:00:00+00:00")],
            "ieee.ucr": [FakePost("800", "2020-01-01T09:00:00+00:00")],
        }
        self.run_main(accounts, posts)
        saved = sorted(path.stem for path in (self.root / "posts").glob("*/*.json"))
        # Activation happens at "now", so nothing published before this run
        # enters the archive — not even a club's whole back catalogue.
        self.assertEqual([], saved)
        checkpoints = scrape_posts.load_local_checkpoints()
        self.assertEqual({"acm.ucr", "ieee.ucr"}, set(checkpoints))
        self.assertTrue(all(entry["activated_at"] for entry in checkpoints.values()))

    def test_collection_restores_the_archive_before_judging_what_is_new(self):
        # Discovery, the refresh pass, and the extraction that follows all read
        # the archive, so the restore has to happen before any of them looks.
        self.run_main([{"handle": "acm.ucr", "instagram_user_id": 42}], {})
        self.hydrated.assert_called_once_with()

    def test_a_later_run_collects_what_was_published_after_activation(self):
        scrape_posts.write_local_checkpoints({"acm.ucr": {
            "activated_at": "2026-09-01T00:00:00+00:00",
            "scanned_through": "2026-09-10T00:00:00+00:00"}})
        self.run_main([{"handle": "acm.ucr", "instagram_user_id": 42}],
                      {"acm.ucr": [FakePost("900", "2026-09-11T09:00:00+00:00")]})
        self.assertTrue((self.root / "posts" / "acm.ucr" / "900.json").exists())
        self.assertEqual("complete",
                         scrape_posts.load_local_checkpoints()["acm.ucr"]["last_status"])

    def test_a_busy_account_catches_up_and_advances_only_after_durable_writes(self):
        now = instant("2026-09-11T12:00:00+00:00")
        feed = [FakePost(str(900 - n), (now - timedelta(hours=n)).isoformat())
                for n in range(80)]
        for durable in (False, True):
            with self.subTest(durable=durable):
                scrape_posts.write_local_checkpoints({"acm.ucr": {
                    "activated_at": "2026-09-01T00:00:00+00:00",
                    "scanned_through": "2026-09-10T00:00:00+00:00"}})
                self.remote_writes.side_effect = None if durable else RuntimeError("mirror unavailable")
                with patch.object(scrape_posts, "_utc_now", return_value=now):
                    if durable:
                        self.run_main([{"handle": "acm.ucr", "instagram_user_id": 42}], {"acm.ucr": feed})
                    else:
                        with self.assertRaises(RuntimeError):
                            self.run_main([{"handle": "acm.ucr", "instagram_user_id": 42}], {"acm.ucr": feed})
                saved = scrape_posts.load_local_checkpoints()["acm.ucr"]
                self.assertEqual(now.isoformat() if durable else "2026-09-10T00:00:00+00:00",
                                 saved["scanned_through"])
                self.assertEqual(80, len(self.remote_writes.call_args.args[0]))

    def test_a_rate_limit_stops_collection_and_keeps_every_checkpoint(self):
        scrape_posts.write_local_checkpoints({
            handle: {"activated_at": "2026-09-01T00:00:00+00:00",
                     "scanned_through": "2026-09-10T00:00:00+00:00"}
            for handle in ("acm.ucr", "ieee.ucr")})

        def rate_limited():
            raise TooManyRequestsException("429 Too Many Requests")

        accounts = [{"handle": "acm.ucr", "instagram_user_id": 42}, {"handle": "ieee.ucr", "instagram_user_id": 43}]
        with self.assertLogs("pipeline", level="ERROR"):
            with self.assertRaises(instagram_cooldown.CollectionStopped) as raised:
                self.run_main(accounts, {"acm.ucr": _Exploding(rate_limited)})
        self.assertIn("rate limited", str(raised.exception))
        self.assertIn("checkpoints were retained", str(raised.exception))
        saved = scrape_posts.load_local_checkpoints()
        # Neither account advanced, so the uncollected interval is retried.
        for handle in ("acm.ucr", "ieee.ucr"):
            self.assertEqual("2026-09-10T00:00:00+00:00", saved[handle]["scanned_through"])
        # Story collection is paused as well, not just the rest of this scan.
        with self.assertRaisesRegex(instagram_cooldown.CollectionPaused,
                                    "posts collection was throttled"):
            instagram_cooldown.ensure_collection_allowed("stories")

    def test_a_bare_400_on_one_account_stops_collection(self):
        # A post scan asks about one account, so there is no bad userid to isolate.
        def bad_request():
            raise QueryReturnedBadRequestException(
                '400 Bad Request - "fail" status, message "invalid request"')

        accounts = [{"handle": "acm.ucr", "instagram_user_id": 42}, {"handle": "ieee.ucr", "instagram_user_id": 43}]
        with self.assertLogs("pipeline", level="ERROR"):
            with self.assertRaisesRegex(instagram_cooldown.CollectionStopped,
                                        "posts collection was challenged"):
                self.run_main(accounts, {"acm.ucr": _Exploding(bad_request)})

    def test_refreshes_skip_posts_already_fetched_by_discovery(self):
        scrape_posts.write_local_checkpoints({"acm.ucr": {
            "activated_at": "2026-09-01T00:00:00+00:00",
            "scanned_through": "2026-09-10T00:00:00+00:00"}})
        known = {"900": {"media_id": "900", "handle": "acm.ucr", "shortcode": "C900"},
                 "700": {"media_id": "700", "handle": "acm.ucr", "shortcode": "C700"}}
        with patch.object(scrape_posts, "refresh_post") as refresh:
            self.run_main([{"handle": "acm.ucr", "instagram_user_id": 42}],
                          {"acm.ucr": [FakePost("900", "2026-09-11T09:00:00+00:00")]},
                          refresh=known)
        # 900 came back from discovery this run; only 700 costs a request.
        self.assertEqual(["700"], [call.args[1]["media_id"] for call in refresh.call_args_list])


    def test_direct_pilot_limits_accounts_skips_refresh_and_retains_incomplete_checkpoint(self):
        before = {"activated_at": "2026-09-01T00:00:00+00:00",
                  "scanned_through": "2026-09-10T00:00:00+00:00"}
        scrape_posts.write_local_checkpoints({"acm.ucr": before, "ieee.ucr": before})
        accounts = [{"handle": "acm.ucr", "instagram_user_id": 42},
                    {"handle": "ieee.ucr", "instagram_user_id": 43}]
        def limited(*args):
            yield FakePost("700", "2026-09-11T09:00:00+00:00")
            raise scrape_posts.DirectFeedLimitReached("budget exhausted")
        with patch.object(scrape_posts, "_direct_feed_posts", side_effect=limited) as feed, \
             patch.object(scrape_posts, "refresh_post") as refresh:
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                self.run_main(accounts, {}, handles=[" ACM.UCR "], direct_feed=True,
                              refresh={"800": {"handle": "ieee.ucr"}})
        self.assertEqual(1, feed.call_count)
        refresh.assert_not_called()
        saved = scrape_posts.load_local_checkpoints()
        self.assertEqual(before["scanned_through"], saved["acm.ucr"]["scanned_through"])
        self.assertEqual("incomplete", saved["acm.ucr"]["last_status"])
        self.assertEqual(before, saved["ieee.ucr"])
        self.assertEqual(1, len(self.remote_writes.call_args.args[0]))

    def test_direct_pushback_pauses_both_channels_without_default_fallback(self):
        accounts = [{"handle": "acm.ucr", "instagram_user_id": 42},
                    {"handle": "ieee.ucr", "instagram_user_id": 43}]
        with patch.object(scrape_posts, "_direct_feed_page", side_effect=TooManyRequestsException("429")) as page, \
             patch.object(scrape_posts, "refresh_post") as refresh:
            with self.assertRaises(instagram_cooldown.CollectionStopped):
                self.run_main(accounts, {}, handles=["acm.ucr", "ieee.ucr"], direct_feed=True)
        page.assert_called_once()
        refresh.assert_not_called()
        for checkpoint in scrape_posts.load_local_checkpoints().values():
            self.assertNotIn("scanned_through", checkpoint)
        with self.assertRaises(instagram_cooldown.CollectionPaused):
            instagram_cooldown.ensure_collection_allowed("stories")


class _Exploding:
    """A feed whose first page raises, to model a mid-pagination failure."""

    def __init__(self, raise_now):
        self._raise_now = raise_now

    def __iter__(self):
        self._raise_now()
        return iter(())


class RefreshDurabilityTests(PostArchiveTests):
    def test_a_refreshed_post_is_mirrored_durably_not_just_locally(self):
        # A corrected caption that only reached the local archive would be lost
        # on restore, and the stale copy would keep publishing a withdrawn event.
        known = {"media_id": "700", "handle": "acm.ucr", "shortcode": "C700"}
        refreshed = FakePost("700", "2026-09-11T09:00:00+00:00",
                             caption="Study jam is cancelled")
        with patch.object(scrape_posts.instaloader.Post, "from_shortcode", return_value=refreshed):
            scrape_posts.refresh_post(Mock(), known, instant("2026-09-12T12:00:00+00:00"))
        saved = post_archive.read_json(self.root / "posts" / "acm.ucr" / "700.json")
        self.assertEqual("Study jam is cancelled", saved["caption"])
        self.remote_writes.assert_called_once()
        self.assertEqual("Study jam is cancelled",
                         self.remote_writes.call_args.args[0][0]["caption"])


class RefreshEligibilityTests(unittest.TestCase):
    def test_only_posts_backing_an_unfinished_event_stay_eligible(self):
        now = instant("2026-09-11T12:00:00+00:00")
        rows = [{"source_key": "instagram:post:700", "event_ids": ["ig_a"]},
                {"source_key": "instagram:post:800", "event_ids": ["ig_b"]}]
        events = [{"id": "ig_a", "starts_at": "2026-09-20T22:00:00+00:00", "ends_at": None},
                  {"id": "ig_b", "starts_at": "2026-09-01T22:00:00+00:00",
                   "ends_at": "2026-09-02T00:00:00+00:00"}]
        archive = [{"media_id": "700", "handle": "acm.ucr", "shortcode": "C700"},
                   {"media_id": "800", "handle": "acm.ucr", "shortcode": "C800"}]
        client = Mock()
        client.return_value.table.return_value.select.return_value.like.return_value.execute.return_value.data = rows
        with patch.dict(sys.modules, {"db": SimpleNamespace(
                client=client, get_event_rows_by_ids=lambda ids: events)}), \
             patch.object(scrape_posts, "iter_local_posts", return_value=archive):
            eligible = scrape_posts.refresh_candidates(now)
        # The finished event's post is dropped: refreshing it cannot change a
        # listing that is already over.
        self.assertEqual(["700"], sorted(eligible))


class SerializationTests(PostArchiveTests):
    def test_carousel_slides_keep_their_order_and_identities(self):
        record = scrape_posts.serialize_post(
            FakePost("700", "2026-09-11T09:00:00+00:00", images=3), "acm.ucr",
            seen_at=instant("2026-09-11T12:00:00+00:00"),
        )
        self.assertEqual([0, 1, 2], [entry["index"] for entry in record["media"]])
        self.assertEqual(["700_0_n", "700_1_n", "700_2_n"],
                         [entry["media_key"] for entry in record["media"]])
        self.assertFalse(record["has_video"])
        self.assertEqual("https://www.instagram.com/p/C700/", record["permalink"])

    def test_a_refreshed_url_alone_is_not_recorded_as_a_change(self):
        post = FakePost("700", "2026-09-11T09:00:00+00:00")
        first = scrape_posts.serialize_post(post, "acm.ucr", seen_at=instant("2026-09-11T12:00:00+00:00"))
        self.assertEqual("new", post_archive.write_post(first))
        later = dict(first, fetched_at="2026-09-12T12:00:00+00:00")
        self.assertEqual("unchanged", post_archive.write_post(later))
        edited = dict(later, caption="Flyer (moved to Tuesday)")
        self.assertEqual("updated", post_archive.write_post(edited))

    def test_a_video_post_is_recorded_as_carrying_video(self):
        record = scrape_posts.serialize_post(
            FakePost("800", "2026-09-11T09:00:00+00:00", video=True), "acm.ucr",
            seen_at=instant("2026-09-11T12:00:00+00:00"),
        )
        self.assertTrue(record["has_video"])
        self.assertTrue(record["media"][0]["is_video"])
        self.assertTrue(record["media"][0]["image_url"])

    def test_a_sidecar_video_keeps_its_cover_frame_url(self):
        record = scrape_posts.serialize_post(
            FakePost("700", "2026-09-11T09:00:00+00:00", images=2, video=True), "acm.ucr",
            seen_at=instant("2026-09-11T12:00:00+00:00"),
        )
        self.assertFalse(record["media"][0]["is_video"])
        self.assertTrue(record["media"][1]["is_video"])
        self.assertTrue(record["media"][1]["image_url"])
        self.assertEqual("700_1_n", record["media"][1]["media_key"])


if __name__ == "__main__":
    unittest.main()
