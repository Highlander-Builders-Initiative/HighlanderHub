"""Instagram session persistence, request pacing, and roster regressions."""
from __future__ import annotations

import importlib
import pickle
import sys
import tempfile
import types
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch
import instaloader
from instaloader.exceptions import QueryReturnedBadRequestException, TooManyRequestsException
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ClientTestCase(unittest.TestCase):
    def setUp(self):
        self.scrape = importlib.import_module("instagram_client")
        sleeper = patch("time.sleep")
        self.sleep = sleeper.start()
        self.addCleanup(sleeper.stop)


def account(handle: str, userid: int | None) -> dict[str, Any]:
    entry: dict[str, Any] = {"handle": handle, "label": handle.upper()}
    if userid is not None:
        entry["instagram_user_id"] = userid
    return entry


class SessionTests(ClientTestCase):
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


class FollowedAccountsTests(ClientTestCase):
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
        followed = [account("acm_ucr", 10839758322)]

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
        curated = [account("acm.ucr", 10839758322)]

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


class PacingTests(ClientTestCase):
    def test_http_error_hook_keeps_diagnostics_and_is_attached_once(self):
        loader = types.SimpleNamespace(context=types.SimpleNamespace(
            _session=types.SimpleNamespace(hooks={})))
        self.scrape._attach_http_error_logger(loader)
        self.scrape._attach_http_error_logger(loader)
        hooks = loader.context._session.hooks["response"]
        self.assertEqual([self.scrape._log_http_errors], hooks)
        response = types.SimpleNamespace(
            status_code=429, reason="Too Many Requests", url="https://www.instagram.com/graphql/query",
            headers={"Retry-After": "60", "Set-Cookie": "private"}, text="rate limited")
        with self.assertLogs(self.scrape.log, level="WARNING") as logged:
            self.assertIs(response, hooks[0](response))
        self.assertIn("Retry-After", logged.output[0])
        self.assertNotIn("private", logged.output[0])

    def test_every_instagram_request_waits_a_minimum_gap(self) -> None:
        controller = self.scrape.PacedRateController(Mock())

        with patch.object(self.scrape.random, "uniform", return_value=1.7) as uniform:
            controller.wait_before_query("iphone")

        uniform.assert_called_once_with(*self.scrape.REQUEST_GAP_RANGE)
        self.sleep.assert_called_once_with(1.7)


    def test_a_429_is_raised_rather_than_waited_out(self) -> None:
        controller = self.scrape.PacedRateController(Mock())

        with self.assertRaises(TooManyRequestsException):
            controller.handle_429("iphone")

        self.sleep.assert_not_called()
