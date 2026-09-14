"""The stop decision both Instagram collection channels share."""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from instaloader.exceptions import (
    AbortDownloadException,
    ConnectionException,
    LoginRequiredException,
    QueryReturnedBadRequestException,
    QueryReturnedForbiddenException,
    TooManyRequestsException,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import instagram_cooldown
import scrape
import scrape_posts
from instagram_cooldown import (
    Block,
    CollectionPaused,
    CollectionStopped,
    EveryAccountRejected,
    Kind,
)

NOW = datetime(2026, 9, 13, 17, 0, tzinfo=timezone.utc)
BARE_400 = '400 Bad Request - "fail" status, message "invalid request"'
CHALLENGE_REPLY = (
    '400 Bad Request - "fail" status, message "challenge_required" '
    "when accessing https://www.instagram.com/graphql/query"
)
FEEDBACK_REPLY = (
    '400 Bad Request - "fail" status, message "feedback_required" '
    "when accessing https://www.instagram.com/api/v1/feed/user/10839758322/?count=12"
)


class CooldownFileCase(unittest.TestCase):
    """Every pause lands in a throwaway file, never in pipeline/data."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "instagram_cooldown.json"
        for target, value in (("INSTAGRAM_COOLDOWN_FILE", self.path), ("_UNSAVED", None)):
            patcher = patch.object(instagram_cooldown, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def pause(self, kind, channel="stories", **kwargs):
        with self.assertLogs("pipeline", level="ERROR"):
            return instagram_cooldown.pause(Block(kind, "test"), channel, "detail", **kwargs)


class ClassificationTests(unittest.TestCase):
    def test_feedback_restrictions_are_throttles_even_when_instaloader_aborts(self):
        for error_type in (AbortDownloadException, QueryReturnedBadRequestException,
                           ConnectionException):
            with self.subTest(error_type=error_type.__name__):
                block = instagram_cooldown.classify(error_type(FEEDBACK_REPLY))
                self.assertEqual(Kind.THROTTLED, block.kind)
                self.assertEqual("action restricted (feedback_required)", block.reason)

    def test_challenges_and_throttles_are_named(self):
        cases = [
            (TooManyRequestsException("429 Too Many Requests"), Kind.THROTTLED),
            (AbortDownloadException(CHALLENGE_REPLY), Kind.CHALLENGED),
            (AbortDownloadException(
                "Redirected to login page. You've been logged out, please wait some "
                "time, recreate the session and try again"), Kind.CHALLENGED),
            (LoginRequiredException("Login required."), Kind.CHALLENGED),
            (QueryReturnedForbiddenException("403 Forbidden"), Kind.CHALLENGED),
            (EveryAccountRejected("Instagram rejected all 50 accounts"), Kind.CHALLENGED),
            # Refusals Instagram sends as a plain 400 or a `fail` status.
            (QueryReturnedBadRequestException(
                '400 Bad Request - "fail" status, message "login_required"'), Kind.CHALLENGED),
            (ConnectionException(
                'JSON Query to api/v1/feed/reels_media/: 401 Unauthorized - "fail" '
                'status, message "Please wait a few minutes before you try again."'),
             Kind.THROTTLED),
        ]
        for exc, kind in cases:
            with self.subTest(exc=f"{type(exc).__name__}: {exc}"[:70]):
                self.assertEqual(kind, instagram_cooldown.classify(exc).kind)

    def test_a_throttle_is_found_behind_instaloaders_retry_wrapper(self):
        # After its last retry Instaloader re-raises a plain ConnectionException
        # chained to the 429 underneath.
        gave_up = ConnectionException("JSON Query to graphql/query: gave up")
        gave_up.__cause__ = TooManyRequestsException("429")
        self.assertEqual(Kind.THROTTLED, instagram_cooldown.classify(gave_up).kind)

    def test_a_bare_400_is_pushback_only_for_a_lone_request(self):
        # In a story batch it can be one bad userid, which the split-retry isolates.
        bare = QueryReturnedBadRequestException(BARE_400)
        self.assertIsNone(instagram_cooldown.classify(bare))
        self.assertEqual(Kind.CHALLENGED, instagram_cooldown.classify(bare, lone_400=True).kind)

    def test_ordinary_failures_are_not_pushback(self):
        for exc in (
            ConnectionException("401 Unauthorized"),
            ConnectionException("HTTPSConnectionPool: Read timed out."),
            ValueError("odd payload"),
            # Only Instaloader's errors are read, whatever our own ones say.
            RuntimeError("Instagram scrape hit 2 failure(s): too many requests"),
        ):
            with self.subTest(exc=str(exc)):
                self.assertIsNone(instagram_cooldown.classify(exc, lone_400=True))

    def test_a_stop_is_never_classified_again(self):
        # Raised `from` the 429 it records, a CollectionStopped must not pause twice.
        try:
            try:
                raise TooManyRequestsException("429 Too Many Requests")
            except TooManyRequestsException as err:
                raise CollectionStopped("stories collection was throttled") from err
        except CollectionStopped as stopped:
            self.assertIsNone(instagram_cooldown.classify(stopped, lone_400=True))


class PauseTests(CooldownFileCase):
    def test_session_refresh_preserves_existing_misclassified_feedback_pause(self):
        for unsaved in (False, True):
            with self.subTest(unsaved=unsaved), patch.object(instagram_cooldown, "utc_now", return_value=NOW):
                with self.assertLogs("pipeline", level="ERROR"):
                    old = instagram_cooldown.pause(
                        Block(Kind.CHALLENGED, "challenge or logged-out session"),
                        "posts", FEEDBACK_REPLY, now=NOW)
                original = self.path.read_bytes()
                if unsaved:
                    instagram_cooldown._UNSAVED = old
                active = instagram_cooldown.lift_challenge()
                self.assertIsNotNone(active)
                self.assertEqual(Kind.THROTTLED, active.kind)
                self.assertEqual(old.until, active.until)
                self.assertEqual(original, self.path.read_bytes())
                for channel in ("posts", "stories"):
                    with self.assertRaisesRegex(CollectionPaused, "action restricted"):
                        instagram_cooldown.ensure_collection_allowed(channel)
                self.assertIsNone(instagram_cooldown.current(now=old.until))

    def test_a_pause_from_one_channel_stops_both_until_it_expires(self):
        self.pause(Kind.THROTTLED, "stories", now=NOW)
        for channel in ("stories", "posts"):
            with self.subTest(channel=channel):
                with self.assertRaisesRegex(CollectionPaused, "stories collection was throttled"):
                    instagram_cooldown.ensure_collection_allowed(
                        channel, now=NOW + timedelta(hours=23, minutes=59))
        instagram_cooldown.ensure_collection_allowed("posts", now=NOW + timedelta(hours=24))

    def test_the_cooldown_length_is_configurable(self):
        with patch.object(instagram_cooldown, "INSTAGRAM_COOLDOWN_HOURS", 2):
            paused = self.pause(Kind.THROTTLED, now=NOW)
        self.assertEqual(NOW + timedelta(hours=2), paused.until)

    def test_an_unsaved_pause_still_stops_the_rest_of_the_run(self):
        with patch.object(instagram_cooldown, "write_json", side_effect=OSError("disk full")):
            with self.assertLogs("pipeline", level="ERROR") as logged:
                instagram_cooldown.pause(Block(Kind.CHALLENGED, "test"), "stories", "detail")
        self.assertIn("this run only", "\n".join(logged.output))
        self.assertFalse(self.path.exists())
        with self.assertRaises(CollectionPaused):
            instagram_cooldown.ensure_collection_allowed("posts")

    def test_an_unreadable_record_holds_until_someone_deletes_it(self):
        for contents in ("{not json", '{"kind": "throttled", "reason": "rate limited"}'):
            with self.subTest(contents=contents):
                self.path.write_text(contents, encoding="utf-8")
                with self.assertRaisesRegex(CollectionPaused, "could not be read.*delete it"):
                    instagram_cooldown.ensure_collection_allowed(
                        "stories", now=NOW + timedelta(days=365))
                # A fresh session is no evidence that it was a challenge.
                self.assertEqual(Kind.UNREADABLE, instagram_cooldown.lift_challenge().kind)
                self.assertTrue(self.path.exists())

    def test_a_fresh_session_lifts_a_challenge_but_not_a_throttle(self):
        self.pause(Kind.CHALLENGED)
        with self.assertLogs("pipeline", level="INFO"):
            self.assertIsNone(instagram_cooldown.lift_challenge())
        instagram_cooldown.ensure_collection_allowed("stories")

        self.pause(Kind.THROTTLED)
        self.assertEqual(Kind.THROTTLED, instagram_cooldown.lift_challenge().kind)
        with self.assertRaises(CollectionPaused):
            instagram_cooldown.ensure_collection_allowed("stories")


class ChannelSharingTests(CooldownFileCase):
    """Both collectors in one process, as run.py schedules them."""

    def test_a_challenged_story_fetch_keeps_post_collection_from_starting(self):
        with (
            patch.object(scrape, "ensure_dirs"),
            patch.object(scrape, "_login"),
            patch.object(scrape, "_attach_http_error_logger"),
            patch.object(scrape, "_persist_rotated_session"),
            patch.object(scrape, "_load_scrape_accounts",
                         return_value=[{"handle": "acm_ucr", "instagram_user_id": 10839758322}]),
            patch.object(scrape.instaloader, "Instaloader", return_value=Mock()),
            patch.object(scrape, "scrape_chunk",
                         side_effect=AbortDownloadException(CHALLENGE_REPLY)),
        ):
            with self.assertLogs("pipeline", level="ERROR"):
                with self.assertRaisesRegex(CollectionStopped, "stories collection was challenged"):
                    scrape.main()

        with (
            patch.object(scrape_posts.instaloader, "Instaloader") as build,
            patch.object(scrape_posts, "hydrate_local_posts") as hydrate,
        ):
            with self.assertRaisesRegex(CollectionPaused, "Not collecting Instagram posts"):
                scrape_posts.main()
        build.assert_not_called()
        hydrate.assert_not_called()

    def test_a_throttle_while_posts_load_accounts_pauses_stories(self):
        with (
            patch.object(scrape_posts, "ensure_post_dirs"),
            patch.object(scrape_posts, "hydrate_local_posts"),
            patch.object(scrape_posts, "_login"),
            patch.object(scrape_posts, "_attach_http_error_logger"),
            patch.object(scrape_posts, "_persist_rotated_session"),
            patch.object(scrape_posts.instaloader, "Instaloader", return_value=Mock()),
            patch.object(scrape_posts, "_load_scrape_accounts",
                         side_effect=TooManyRequestsException("429 Too Many Requests")),
        ):
            with self.assertLogs("pipeline", level="ERROR"):
                with self.assertRaisesRegex(CollectionStopped, "posts collection was throttled"):
                    scrape_posts.main()

        with patch.object(scrape.instaloader, "Instaloader") as build:
            with self.assertRaisesRegex(CollectionPaused, "Not collecting Instagram stories"):
                scrape.main()
        build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
