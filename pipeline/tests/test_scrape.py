"""Tests for the batched Instagram story scrape.

These drive real `Story` / `StoryItem` objects built from JSON fixtures shaped
like Instagram's actual reels_media responses, rather than `Mock`s. A `Mock`
fabricates any attribute you ask it for, so a test written against one can
assert a field instaloader does not define and still pass — which is how
`story_cta_url` stayed `None` for every archived story while its test was green.
"""
from __future__ import annotations

import importlib
import json
import pickle
import sys
import tempfile
import types
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import Mock, patch

import instaloader
from instaloader.exceptions import (
    ConnectionException,
    QueryReturnedBadRequestException,
)
from instaloader.structures import Story

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Handles that have a live story in the fixtures, and handles that don't.
POSTING = {"acm_ucr": 10839758322, "cyber_ucr": 449388329, "ucrvsa": 220034115}
SILENT = {"asucr": 449388330, "bcoe_ucr": 220034116, "ucrhighlanders": 10839758323}

# Content-Length the fake HEAD reports per video rendition. instaloader compares
# these to pick the best video URL, so the iphone rendition has to be the bigger
# one for the fixture to behave like a real response.
VIDEO_BYTES = {
    "https://scontent.cdninstagram.com/acm_ucr/clip_480.mp4": 912_000,
    "https://scontent.cdninstagram.com/acm_ucr/clip_1080.mp4": 4_240_000,
}


def _load_fixture(name: str) -> dict[str, Any]:
    with (FIXTURES / name).open(encoding="utf-8") as f:
        return json.load(f)


def account(handle: str, userid: int | None) -> dict[str, Any]:
    entry: dict[str, Any] = {"handle": handle, "label": handle.upper()}
    if userid is not None:
        entry["instagram_user_id"] = userid
    return entry


class FakeContext:
    """Stands in for InstaloaderContext, serving the iphone reels fixture.

    Real `Story` and `StoryItem` objects only need a context for the iphone
    struct lookup, so this is enough to exercise instaloader's own parsing
    without a network call.
    """

    def __init__(self, iphone_reels: dict[str, Any]) -> None:
        self.iphone_support = True
        self.is_logged_in = True
        self._iphone_reels = iphone_reels
        self.iphone_requests: list[str] = []
        self.errors: list[str] = []

    def get_iphone_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        owner_id = path.rsplit("reel_ids=", 1)[-1]
        self.iphone_requests.append(owner_id)
        # Instagram omits owners with nothing live, which is what makes
        # Story.get_items() raise KeyError.
        reel = self._iphone_reels.get(owner_id)
        return {"reels": {owner_id: reel} if reel is not None else {}}

    def head(self, url: str, allow_redirects: bool = False) -> Any:
        return types.SimpleNamespace(
            headers={"Content-Length": str(VIDEO_BYTES.get(url, 0))}
        )

    def error(self, msg: Any, repeat_at_end: bool = True) -> None:
        self.errors.append(str(msg))


class FakeLoader:
    """Stands in for Instaloader, answering get_stories from a reels fixture.

    `get_stories` is a generator here exactly as it is in instaloader, so a
    rejection surfaces while the caller iterates rather than when it calls —
    the shape the split-retry has to cope with.
    """

    def __init__(
        self,
        context: FakeContext,
        reels_by_userid: dict[int, dict[str, Any]],
        *,
        poison: tuple[int, ...] = (),
        max_accepted: int | None = None,
        reject_everything: bool = False,
    ) -> None:
        self.context = context
        self._reels = reels_by_userid
        self._poison = set(poison)
        self._max_accepted = max_accepted
        self._reject_everything = reject_everything
        self.requests: list[list[int]] = []

    def get_stories(self, userids: list[int] | None = None) -> Iterator[Story]:
        requested = list(userids or [])
        self.requests.append(requested)
        if self._reject_everything:
            raise QueryReturnedBadRequestException(
                '400 Bad Request - "fail" status, message "invalid request"'
            )
        if self._max_accepted is not None and len(requested) > self._max_accepted:
            raise QueryReturnedBadRequestException(
                f'400 Bad Request - too many reel_ids ({len(requested)})'
            )
        if self._poison.intersection(requested):
            raise QueryReturnedBadRequestException(
                '400 Bad Request - "fail" status, message "invalid request"'
            )
        for userid in requested:
            node = self._reels.get(userid)
            if node is not None:
                yield Story(self.context, node)

    @property
    def request_sizes(self) -> list[int]:
        return [len(request) for request in self.requests]


class ScrapeTestCase(unittest.TestCase):
    """Shared fixture loading and a throwaway RAW_DIR."""

    def setUp(self) -> None:
        self.scrape = importlib.import_module("scrape")

        self.graphql = _load_fixture("reels_media_graphql.json")
        self.iphone = _load_fixture("reels_media_iphone.json")
        self.context = FakeContext(self.iphone["reels"])
        self.reels_by_userid = {
            int(node["id"]): node for node in self.graphql["reels_media"]
        }

        self._raw = tempfile.TemporaryDirectory()
        self.raw_dir = Path(self._raw.name)
        self.addCleanup(self._raw.cleanup)
        raw_patch = patch.object(self.scrape, "RAW_DIR", self.raw_dir)
        raw_patch.start()
        self.addCleanup(raw_patch.stop)

    def loader(self, **kwargs: Any) -> FakeLoader:
        return FakeLoader(self.context, self.reels_by_userid, **kwargs)

    def written_files(self) -> list[str]:
        return sorted(
            str(path.relative_to(self.raw_dir))
            for path in self.raw_dir.rglob("*.json")
        )

    def read_written(self, handle: str, item_id: str) -> dict[str, Any]:
        with (self.raw_dir / handle / f"{item_id}.json").open() as f:
            return json.load(f)


class IndexByUseridTests(ScrapeTestCase):
    def test_accounts_split_into_batchable_and_unresolved(self) -> None:
        accounts = [
            account("acm_ucr", 10839758322),
            account("noid_ucr", None),
            account("cyber_ucr", 449388329),
        ]

        batchable, by_userid, skipped = self.scrape._index_by_userid(accounts)

        self.assertEqual(["acm_ucr", "cyber_ucr"], [a["handle"] for a in batchable])
        self.assertEqual("acm_ucr", by_userid[10839758322]["handle"])
        self.assertEqual(["noid_ucr"], [a["handle"] for a in skipped])

    def test_duplicate_userid_keeps_the_first_handle_and_warns(self) -> None:
        accounts = [
            account("acm_ucr", 10839758322),
            account("acm.ucr", 10839758322),
        ]

        with self.assertLogs(self.scrape.log, level="WARNING") as captured:
            batchable, by_userid, _ = self.scrape._index_by_userid(accounts)

        self.assertEqual(["acm_ucr"], [a["handle"] for a in batchable])
        self.assertEqual("acm_ucr", by_userid[10839758322]["handle"])
        self.assertIn("both claim instagram_user_id", captured.output[0])
        self.assertIn("acm.ucr", captured.output[0])

    def test_unparseable_userid_is_treated_as_missing(self) -> None:
        _, by_userid, skipped = self.scrape._index_by_userid(
            [account("acm_ucr", "not-a-number")]  # type: ignore[arg-type]
        )

        self.assertEqual({}, by_userid)
        self.assertEqual(["acm_ucr"], [a["handle"] for a in skipped])


class ScrapeChunkTests(ScrapeTestCase):
    def chunk(self, handles: list[str]) -> list[dict[str, Any]]:
        userids = {**POSTING, **SILENT}
        return [account(handle, userids[handle]) for handle in handles]

    def test_one_request_covers_the_chunk_and_only_posters_are_written(self) -> None:
        chunk = self.chunk(
            ["acm_ucr", "asucr", "cyber_ucr", "bcoe_ucr", "ucrvsa"]
        )
        _, by_userid, _ = self.scrape._index_by_userid(chunk)
        loader = self.loader()

        result = self.scrape.scrape_chunk(loader, chunk, by_userid)

        self.assertEqual([5], loader.request_sizes)
        self.assertEqual((4, 4, 3), (result.seen, result.new, result.posting))
        self.assertEqual(
            [
                "acm_ucr/3140000000000000001.json",
                "acm_ucr/3140000000000000002.json",
                "cyber_ucr/3140000000000000003.json",
                "ucrvsa/3140000000000000004.json",
            ],
            self.written_files(),
        )

    def test_rerunning_a_chunk_sees_the_same_items_but_writes_nothing(self) -> None:
        chunk = self.chunk(["acm_ucr"])
        _, by_userid, _ = self.scrape._index_by_userid(chunk)

        first = self.scrape.scrape_chunk(self.loader(), chunk, by_userid)
        second = self.scrape.scrape_chunk(self.loader(), chunk, by_userid)

        self.assertEqual((2, 2), (first.seen, first.new))
        self.assertEqual((2, 0), (second.seen, second.new))

    def test_written_item_carries_the_story_link_and_iphone_media(self) -> None:
        chunk = self.chunk(["acm_ucr"])
        _, by_userid, _ = self.scrape._index_by_userid(chunk)

        self.scrape.scrape_chunk(self.loader(), chunk, by_userid)
        payload = self.read_written("acm_ucr", "3140000000000000001")

        self.assertEqual("https://lu.ma/hack-night-2026", payload["story_cta_url"])
        self.assertEqual(
            "https://scontent.cdninstagram.com/acm_ucr/flyer_hd.jpg",
            payload["image_url"],
        )
        self.assertEqual("acm_ucr", payload["handle"])
        self.assertEqual(10839758322, payload["owner_userid"])
        self.assertEqual("2026-05-11T18:30:00Z", payload["posted_at"])
        self.assertEqual("2026-05-12T18:30:00Z", payload["expires_at"])
        self.assertEqual(["cyber_ucr"], payload["caption_mentions"])
        self.assertEqual(
            "https://www.instagram.com/stories/acm_ucr/3140000000000000001/",
            payload["permalink"],
        )

    def test_video_item_keeps_the_high_quality_rendition(self) -> None:
        chunk = self.chunk(["acm_ucr"])
        _, by_userid, _ = self.scrape._index_by_userid(chunk)

        self.scrape.scrape_chunk(self.loader(), chunk, by_userid)
        payload = self.read_written("acm_ucr", "3140000000000000002")

        self.assertTrue(payload["is_video"])
        self.assertEqual(
            "https://scontent.cdninstagram.com/acm_ucr/clip_1080.mp4",
            payload["video_url"],
        )

    def test_handle_rename_warns_but_keeps_the_existing_archive_directory(self) -> None:
        # accounts.json still says acm.ucr; Instagram now reports acm_ucr.
        chunk = [account("acm.ucr", POSTING["acm_ucr"])]
        _, by_userid, _ = self.scrape._index_by_userid(chunk)

        with self.assertLogs(self.scrape.log, level="WARNING") as captured:
            self.scrape.scrape_chunk(self.loader(), chunk, by_userid)

        self.assertIn("now posts as @acm_ucr", captured.output[0])
        self.assertEqual(
            [
                "acm.ucr/3140000000000000001.json",
                "acm.ucr/3140000000000000002.json",
            ],
            self.written_files(),
        )
        self.assertEqual("acm.ucr", self.read_written("acm.ucr", "3140000000000000001")["handle"])

    def test_owner_the_chunk_never_asked_about_is_ignored(self) -> None:
        chunk = self.chunk(["cyber_ucr"])
        _, by_userid, _ = self.scrape._index_by_userid(chunk)
        loader = self.loader()
        # Instagram answering with a reel nobody asked for would otherwise write
        # into a directory this run cannot name.
        loader._reels = {POSTING["cyber_ucr"]: self.reels_by_userid[POSTING["acm_ucr"]]}

        with self.assertLogs(self.scrape.log, level="WARNING") as captured:
            result = self.scrape.scrape_chunk(loader, chunk, by_userid)

        self.assertEqual(0, result.seen)
        self.assertEqual([], self.written_files())
        self.assertIn("never asked about", captured.output[0])

    def test_missing_iphone_reel_is_not_treated_as_an_error(self) -> None:
        chunk = self.chunk(["ucrvsa"])
        _, by_userid, _ = self.scrape._index_by_userid(chunk)
        self.context._iphone_reels = {}

        result = self.scrape.scrape_chunk(self.loader(), chunk, by_userid)

        self.assertEqual((0, 0, 0), (result.seen, result.new, result.posting))
        self.assertEqual([], self.written_files())


class SplitRetryTests(ScrapeTestCase):
    def eight_accounts(self) -> list[dict[str, Any]]:
        """Eight accounts with the poison one at index 4.

        Splitting is deterministic, so the request tree is: 8 fails, the first
        4 succeed, the second 4 fail, 2 fail, the poison singleton fails, its
        neighbour succeeds, the last 2 succeed.
        """
        return [
            account("acm_ucr", POSTING["acm_ucr"]),
            account("filler_a", 900000001),
            account("filler_b", 900000002),
            account("filler_c", 900000003),
            account("deadclub", 900000004),
            account("filler_d", 900000005),
            account("cyber_ucr", POSTING["cyber_ucr"]),
            account("filler_e", 900000006),
        ]

    def test_split_retry_isolates_a_single_poison_userid(self) -> None:
        chunk = self.eight_accounts()
        _, by_userid, _ = self.scrape._index_by_userid(chunk)
        loader = self.loader(poison=(900000004,))

        with self.assertLogs(self.scrape.log, level="WARNING"):
            result = self.scrape.scrape_chunk(loader, chunk, by_userid)

        self.assertEqual([900000004], result.rejected_userids)
        self.assertEqual([8, 4, 4, 2, 1, 1, 2], loader.request_sizes)
        # The healthy accounts in the chunk still got scraped.
        self.assertEqual((3, 3, 2), (result.seen, result.new, result.posting))

    def test_chunk_size_cap_degrades_to_requests_instagram_accepts(self) -> None:
        chunk = self.eight_accounts()
        _, by_userid, _ = self.scrape._index_by_userid(chunk)
        loader = self.loader(max_accepted=3)

        with self.assertLogs(self.scrape.log, level="WARNING"):
            result = self.scrape.scrape_chunk(loader, chunk, by_userid)

        self.assertEqual([], result.rejected_userids)
        self.assertEqual([2, 2, 2, 2], result.accepted_sizes)
        # Every account still got asked about, just in smaller requests.
        self.assertEqual((3, 3, 2), (result.seen, result.new, result.posting))

    def test_every_singleton_failing_stops_the_run(self) -> None:
        chunk = self.eight_accounts()[:4]
        _, by_userid, _ = self.scrape._index_by_userid(chunk)
        loader = self.loader(reject_everything=True)

        with self.assertLogs(self.scrape.log, level="WARNING"):
            with self.assertRaisesRegex(
                self.scrape.InstagramStoriesBadRequest,
                "Stopping the Instagram scrape",
            ):
                self.scrape.scrape_chunk(loader, chunk, by_userid)

        self.assertEqual([4, 2, 1, 1, 2, 1, 1], loader.request_sizes)

    def test_a_lone_account_rejected_on_its_own_is_not_session_death(self) -> None:
        chunk = [account("deadclub", 900000004)]
        _, by_userid, _ = self.scrape._index_by_userid(chunk)
        loader = self.loader(poison=(900000004,))

        with self.assertLogs(self.scrape.log, level="WARNING"):
            result = self.scrape.scrape_chunk(loader, chunk, by_userid)

        self.assertEqual([900000004], result.rejected_userids)


class StoryCtaUrlTests(ScrapeTestCase):
    def items_for(self, userid: int) -> dict[str, Any]:
        story = Story(self.context, self.reels_by_userid[userid])
        return {str(item.mediaid): item for item in story.get_items()}

    def test_link_sticker_url_is_unwrapped(self) -> None:
        item = self.items_for(POSTING["acm_ucr"])["3140000000000000001"]

        self.assertEqual(
            "https://lu.ma/hack-night-2026", self.scrape._story_cta_url(item)
        )

    def test_legacy_swipe_up_url_is_unwrapped(self) -> None:
        item = self.items_for(POSTING["cyber_ucr"])["3140000000000000003"]

        self.assertEqual(
            "https://forms.gle/securityNight", self.scrape._story_cta_url(item)
        )

    def test_story_without_a_link_has_no_cta_url(self) -> None:
        item = self.items_for(POSTING["ucrvsa"])["3140000000000000004"]

        self.assertIsNone(self.scrape._story_cta_url(item))

    def test_unwrapped_link_sticker_is_kept_as_is(self) -> None:
        reels = deepcopy(self.iphone["reels"])
        sticker = reels["10839758322"]["items"][0]["story_link_stickers"][0]
        sticker["story_link"]["url"] = "https://lu.ma/hack-night-2026"
        self.context._iphone_reels = reels

        item = self.items_for(POSTING["acm_ucr"])["3140000000000000001"]

        self.assertEqual(
            "https://lu.ma/hack-night-2026", self.scrape._story_cta_url(item)
        )

    def test_missing_iphone_struct_yields_no_cta_url(self) -> None:
        self.context.iphone_support = False

        item = self.items_for(POSTING["acm_ucr"])["3140000000000000001"]

        self.assertIsNone(self.scrape._story_cta_url(item))


class MainTests(ScrapeTestCase):
    def setUp(self) -> None:
        super().setUp()
        for target, value in (("SESSION_FILE", None), ("STORY_CHUNK_SIZE", 3)):
            p = patch.object(self.scrape, target, value)
            p.start()
            self.addCleanup(p.stop)
        for target in ("ensure_dirs", "_login", "_attach_http_error_logger"):
            p = patch.object(self.scrape, target)
            p.start()
            self.addCleanup(p.stop)
        sleep = patch.object(self.scrape.time, "sleep")
        self.sleep = sleep.start()
        self.addCleanup(sleep.stop)

    def run_main(self, accounts: list[dict[str, Any]], loader: Any) -> None:
        with patch.object(self.scrape, "_load_scrape_accounts", return_value=accounts):
            with patch.object(
                self.scrape.instaloader, "Instaloader", return_value=loader
            ):
                self.scrape.main()

    def test_run_batches_accounts_and_jitters_between_chunks(self) -> None:
        accounts = [account(f"club_{i}", 900000100 + i) for i in range(7)]
        loader = self.loader()

        self.run_main(accounts, loader)

        self.assertEqual([3, 3, 1], loader.request_sizes)
        # Jitter goes between chunks, not after the last one.
        self.assertEqual(2, self.sleep.call_count)

    def test_accounts_without_a_userid_are_skipped_and_named(self) -> None:
        accounts = [
            account("acm_ucr", POSTING["acm_ucr"]),
            account("noid_ucr", None),
        ]
        loader = self.loader()

        with self.assertLogs(self.scrape.log, level="WARNING") as captured:
            self.run_main(accounts, loader)

        skip_warning = next(line for line in captured.output if "noid_ucr" in line)
        self.assertIn("no instagram_user_id", skip_warning)
        self.assertIn("resolve_ids.py", skip_warning)
        self.assertEqual([[POSTING["acm_ucr"]]], loader.requests)

    def test_rejected_account_fails_the_run_and_names_the_handle(self) -> None:
        accounts = [
            account("acm_ucr", POSTING["acm_ucr"]),
            account("deadclub", 900000004),
        ]
        loader = self.loader(poison=(900000004,))

        with self.assertLogs(self.scrape.log, level="WARNING") as captured:
            with self.assertRaisesRegex(RuntimeError, "1 failure"):
                self.run_main(accounts, loader)

        diagnosis = next(line for line in captured.output if "deadclub" in line)
        self.assertIn("bad userid", diagnosis)
        # The healthy account in the same chunk was still archived.
        self.assertIn("acm_ucr/3140000000000000001.json", self.written_files())

    def test_chunk_size_cap_is_reported_as_a_size_limit(self) -> None:
        accounts = [account(f"club_{i}", 900000100 + i) for i in range(6)]
        loader = self.loader(max_accepted=1)

        with self.assertLogs(self.scrape.log, level="WARNING") as captured:
            self.run_main(accounts, loader)

        diagnosis = next(
            line for line in captured.output if "server-side cap" in line
        )
        self.assertIn("lower STORY_CHUNK_SIZE from 3 to 1", diagnosis)

    def test_session_death_stops_before_the_next_chunk(self) -> None:
        accounts = [account(f"club_{i}", 900000100 + i) for i in range(6)]
        loader = self.loader(reject_everything=True)

        with self.assertLogs(self.scrape.log, level="WARNING"):
            with self.assertRaisesRegex(RuntimeError, "Stopping the Instagram scrape"):
                self.run_main(accounts, loader)

        # Only the first chunk was attempted, and no jitter was burned after it.
        self.assertEqual([3, 1, 2, 1, 1], loader.request_sizes)
        self.sleep.assert_not_called()

    def test_connection_error_keeps_going_but_fails_the_run(self) -> None:
        accounts = [account(f"club_{i}", 900000100 + i) for i in range(6)]
        loader = self.loader()

        with patch.object(
            self.scrape,
            "scrape_chunk",
            side_effect=ConnectionException("401 Unauthorized"),
        ) as scrape_chunk:
            with self.assertLogs(self.scrape.log, level="WARNING"):
                with self.assertRaisesRegex(RuntimeError, "2 failure"):
                    self.run_main(accounts, loader)

        self.assertEqual(2, scrape_chunk.call_count)


class SessionTests(ScrapeTestCase):
    def test_session_file_login_loads_without_verification(self) -> None:
        loader = Mock()

        with patch.object(self.scrape, "SESSION_FILE", "/tmp/ig-session"):
            with patch.object(self.scrape, "IG_USERNAME", "scraper"):
                self.scrape._login(loader)

        loader.load_session_from_file.assert_called_once_with(
            "scraper", "/tmp/ig-session"
        )
        loader.test_login.assert_not_called()

    def _loader_with_sessionid(self, value: str | None) -> Mock:
        loader = Mock()
        jar = []
        if value is not None:
            jar.append(
                types.SimpleNamespace(
                    name="sessionid", domain=".instagram.com", value=value
                )
            )
        loader.context._session.cookies = jar
        return loader

    def _loader_from_session_file(self, cookies: dict[str, str]) -> Any:
        """A real Instaloader with a session loaded off disk, as a run starts.

        Worth going through instaloader rather than hand-building a jar: the
        empty cookie domain this guards against is produced by its own
        `load_session`, not by anything we control.
        """
        path = Path(tempfile.mkdtemp()) / "session-scraper"
        with path.open("wb") as f:
            pickle.dump(cookies, f)
        loader = instaloader.Instaloader(quiet=True)
        loader.load_session_from_file("scraper", str(path))
        return loader

    def test_sessionid_loaded_from_a_session_file_counts_as_live(self) -> None:
        # instaloader rebuilds the jar with requests.utils.cookiejar_from_dict,
        # which leaves every cookie's domain empty. A domain match would reject
        # a perfectly good session on every run that Instagram never rotated.
        loader = self._loader_from_session_file(
            {"sessionid": "live-from-file", "csrftoken": "abc"}
        )

        self.assertEqual("live-from-file", self.scrape._current_sessionid(loader))

    def test_rotated_sessionid_wins_over_the_one_loaded_from_file(self) -> None:
        loader = self._loader_from_session_file(
            {"sessionid": "stale-from-file", "csrftoken": "abc"}
        )
        loader.context._session.cookies.set(
            "sessionid", "rotated-mid-run", domain=".instagram.com", path="/"
        )

        self.assertEqual("rotated-mid-run", self.scrape._current_sessionid(loader))

    def test_session_file_without_a_sessionid_is_still_refused(self) -> None:
        loader = self._loader_from_session_file({"csrftoken": "abc"})

        self.assertIsNone(self.scrape._current_sessionid(loader))

    def test_refusal_names_the_cookies_it_did_find(self) -> None:
        loader = self._loader_from_session_file({"csrftoken": "abc", "mid": "xyz"})

        with patch.object(self.scrape, "SESSION_FILE", "/tmp/ig-session"):
            with self.assertLogs(self.scrape.log, level="WARNING") as captured:
                self.scrape._persist_rotated_session(loader)

        self.assertIn("csrftoken, mid", captured.output[0])

    def test_persist_rotated_session_saves_when_sessionid_present(self) -> None:
        loader = self._loader_with_sessionid("rotated-value")
        with patch.object(self.scrape, "SESSION_FILE", "/tmp/ig-session"):
            self.scrape._persist_rotated_session(loader)
        loader.save_session_to_file.assert_called_once_with("/tmp/ig-session")

    def test_persist_rotated_session_refuses_logged_out_jar(self) -> None:
        loader = self._loader_with_sessionid(None)
        with patch.object(self.scrape, "SESSION_FILE", "/tmp/ig-session"):
            self.scrape._persist_rotated_session(loader)
        loader.save_session_to_file.assert_not_called()

    def test_persist_rotated_session_noop_without_session_file(self) -> None:
        loader = self._loader_with_sessionid("rotated-value")
        with patch.object(self.scrape, "SESSION_FILE", None):
            self.scrape._persist_rotated_session(loader)
        loader.save_session_to_file.assert_not_called()

    def test_main_persists_session_even_when_run_raises(self) -> None:
        loader = self._loader_with_sessionid("rotated-value")
        loader.get_stories.side_effect = ConnectionException("401")

        with patch.object(self.scrape, "SESSION_FILE", "/tmp/ig-session"):
            with patch.object(self.scrape, "ensure_dirs"):
                with patch.object(self.scrape, "_login"):
                    with patch.object(
                        self.scrape,
                        "_load_scrape_accounts",
                        return_value=[account("acm_ucr", POSTING["acm_ucr"])],
                    ):
                        with patch.object(
                            self.scrape.instaloader, "Instaloader", return_value=loader
                        ):
                            with self.assertLogs(self.scrape.log, level="WARNING"):
                                with self.assertRaises(RuntimeError):
                                    self.scrape.main()

        loader.save_session_to_file.assert_called_once_with("/tmp/ig-session")


class FollowedAccountsTests(ScrapeTestCase):
    def test_followed_accounts_merge_curated_metadata(self) -> None:
        loader = Mock()
        loader.context = Mock(username="scraper_from_context")
        viewer = Mock()
        viewer.get_followees.return_value = [
            types.SimpleNamespace(
                username="acm_ucr", full_name="ACM at UCR", userid=10839758322
            ),
            types.SimpleNamespace(
                username="newclub_ucr", full_name="New Club at UCR", userid=999
            ),
        ]

        with patch.object(self.scrape.instaloader, "Profile") as profile_cls:
            profile_cls.from_username.return_value = viewer
            with patch.object(self.scrape, "IG_USERNAME", "scraper_from_context"):
                accounts, matched = self.scrape._load_followed_accounts(
                    loader,
                    [
                        {
                            "handle": "acm_ucr",
                            "label": "ACM @ UCR",
                            "category": "club",
                            "instagram_user_id": 10839758322,
                        }
                    ],
                )

        by_handle = {acct["handle"]: acct for acct in accounts}
        self.assertEqual(1, matched)
        self.assertEqual("ACM @ UCR", by_handle["acm_ucr"]["label"])
        self.assertEqual("club", by_handle["acm_ucr"]["category"])
        self.assertEqual("New Club at UCR", by_handle["newclub_ucr"]["label"])
        self.assertEqual(
            "instagram_followed", by_handle["newclub_ucr"]["account_source"]
        )
        profile_cls.from_username.assert_called_once_with(
            loader.context, "scraper_from_context"
        )

    def test_followed_account_source_writes_runtime_cache(self) -> None:
        loader = Mock()
        followed = [account("acm_ucr", POSTING["acm_ucr"])]

        with patch.object(self.scrape, "ACCOUNT_SOURCE", "followed"):
            with patch.object(self.scrape, "load_curated_accounts", return_value=[]):
                with patch.object(
                    self.scrape, "_load_followed_accounts", return_value=(followed, 0)
                ):
                    with patch.object(
                        self.scrape, "write_followed_accounts_cache"
                    ) as write:
                        accounts = self.scrape._load_scrape_accounts(loader)

        self.assertEqual(followed, accounts)
        write.assert_called_once_with(followed)

    def test_empty_followed_account_source_does_not_replace_cache(self) -> None:
        loader = Mock()

        with patch.object(self.scrape, "ACCOUNT_SOURCE", "followed"):
            with patch.object(self.scrape, "load_curated_accounts", return_value=[]):
                with patch.object(
                    self.scrape, "_load_followed_accounts", return_value=([], 0)
                ):
                    with patch.object(
                        self.scrape, "write_followed_accounts_cache"
                    ) as write:
                        with self.assertRaisesRegex(
                            RuntimeError, "zero followed accounts"
                        ):
                            self.scrape._load_scrape_accounts(loader)

        write.assert_not_called()

    def test_follow_list_graphql_failure_falls_back_to_accounts_json(self) -> None:
        loader = Mock()
        curated = [account("acm.ucr", POSTING["acm_ucr"])]

        with patch.object(self.scrape, "ACCOUNT_SOURCE", "followed"):
            with patch.object(
                self.scrape, "load_curated_accounts", return_value=curated
            ):
                with patch.object(
                    self.scrape,
                    "_load_followed_accounts",
                    side_effect=QueryReturnedBadRequestException(
                        '400 Bad Request - "invalid request"'
                    ),
                ):
                    with patch.object(
                        self.scrape, "load_followed_accounts_cache", return_value=[]
                    ):
                        with patch.object(
                            self.scrape, "write_followed_accounts_cache"
                        ) as write:
                            with self.assertLogs(self.scrape.log, level="WARNING"):
                                accounts = self.scrape._load_scrape_accounts(loader)

        self.assertEqual(curated, accounts)
        write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
