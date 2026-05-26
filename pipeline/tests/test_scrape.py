from __future__ import annotations

import importlib
import sys
import unittest
import types
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))


class ScrapeMainTests(unittest.TestCase):
    def setUp(self) -> None:
        fake_instaloader = types.ModuleType("instaloader")

        class _ConnectionException(Exception):
            pass

        class _LoginRequiredException(Exception):
            pass

        class _ProfileNotExistsException(Exception):
            pass

        class _QueryReturnedBadRequestException(Exception):
            pass

        fake_exceptions = types.ModuleType("instaloader.exceptions")
        fake_exceptions.ConnectionException = _ConnectionException
        fake_exceptions.LoginRequiredException = _LoginRequiredException
        fake_exceptions.ProfileNotExistsException = _ProfileNotExistsException
        fake_exceptions.QueryReturnedBadRequestException = _QueryReturnedBadRequestException
        fake_instaloader.ConnectionException = _ConnectionException
        fake_instaloader.LoginRequiredException = _LoginRequiredException
        fake_instaloader.ProfileNotExistsException = _ProfileNotExistsException
        fake_instaloader.Instaloader = Mock()
        fake_instaloader.Profile = Mock()
        fake_instaloader.exceptions = fake_exceptions
        self._instaloader_patch = patch.dict(
            sys.modules,
            {
                "instaloader": fake_instaloader,
                "instaloader.exceptions": fake_exceptions,
            },
        )
        self._instaloader_patch.start()
        sys.modules.pop("scrape", None)
        self.scrape = importlib.import_module("scrape")

    def tearDown(self) -> None:
        self._instaloader_patch.stop()

    def test_connection_errors_fail_the_instagram_source(self) -> None:
        accounts = [{"handle": "acm.ucr"}, {"handle": "cyber_ucr"}]

        with patch.object(self.scrape, "ensure_dirs"):
            with patch.object(self.scrape, "_load_scrape_accounts", return_value=accounts):
                with patch.object(self.scrape.instaloader, "Instaloader", return_value=Mock()):
                    with patch.object(self.scrape, "_login"):
                        with patch.object(
                            self.scrape,
                            "scrape_account",
                            side_effect=self.scrape.ConnectionException("401 Unauthorized"),
                        ):
                            with patch.object(self.scrape.time, "sleep"):
                                with self.assertRaisesRegex(
                                    RuntimeError,
                                    "Instagram scrape failed for 2 account",
                                ):
                                    self.scrape.main()

    def test_session_file_login_loads_without_verification(self) -> None:
        loader = Mock()

        with patch.object(self.scrape, "SESSION_FILE", "/tmp/ig-session"):
            with patch.object(self.scrape, "IG_USERNAME", "scraper"):
                self.scrape._login(loader)

        loader.load_session_from_file.assert_called_once_with(
            "scraper", "/tmp/ig-session"
        )
        loader.test_login.assert_not_called()

    def test_all_profiles_missing_after_session_load_reports_session_failure(self) -> None:
        accounts = [{"handle": "ucrvsa"}, {"handle": "cyber_ucr"}]

        with patch.object(self.scrape, "ensure_dirs"):
            with patch.object(self.scrape, "_load_scrape_accounts", return_value=accounts):
                with patch.object(self.scrape.instaloader, "Instaloader", return_value=Mock()):
                    with patch.object(self.scrape, "_login"):
                        with patch.object(
                            self.scrape,
                            "scrape_account",
                            side_effect=self.scrape.ProfileNotExistsException(
                                "Profile does not exist"
                            ),
                        ):
                            with patch.object(self.scrape.time, "sleep"):
                                with self.assertRaisesRegex(
                                    RuntimeError,
                                    "Instagram session appears invalid",
                                ):
                                    self.scrape.main()

    def test_scrape_account_uses_instaloader_stories_api(self) -> None:
        loader = Mock()
        profile = Mock(userid=10839758322)
        owner = Mock(userid=10839758322, username="acm_ucr")
        item = Mock(
            mediaid=987654,
            owner_profile=owner,
            typename="StoryImage",
            is_video=False,
            date_utc=datetime(2024, 5, 20, 8, 0, 0),
            expiring_utc=datetime(2024, 5, 21, 8, 0, 0),
            url="https://ig.com/flyer.jpg",
            caption="Come to our ACM meeting! @member1 @member2",
            caption_mentions=["member1", "member2"],
            story_cta_url="https://linktr.ee/acm_ucr",
        )
        story = Mock()
        story.get_items.return_value = [item]
        loader.get_stories.return_value = [story]

        with patch.object(self.scrape, "_resolve_profile", return_value=profile):
            with patch.object(self.scrape, "_write_item", return_value=True) as write_item:
                seen, new = self.scrape.scrape_account(
                    loader,
                    {"handle": "acm_ucr", "instagram_user_id": 10839758322},
                )

        loader.get_stories.assert_called_once_with(userids=[10839758322])
        self.assertEqual((1, 1), (seen, new))
        write_item.assert_called_once()
        payload, handle = write_item.call_args.args
        self.assertEqual("acm_ucr", handle)
        self.assertEqual("987654", payload["id"])
        self.assertEqual("https://ig.com/flyer.jpg", payload["image_url"])
        self.assertEqual("https://linktr.ee/acm_ucr", payload["story_cta_url"])

    def test_scrape_account_treats_missing_reels_entry_as_no_stories(self) -> None:
        loader = Mock()
        profile = Mock(userid=449388329)
        story = Mock()

        def missing_reels_items():
            raise KeyError("449388329")
            yield

        story.get_items.return_value = missing_reels_items()
        loader.get_stories.return_value = [story]

        with patch.object(self.scrape, "_resolve_profile", return_value=profile):
            seen, new = self.scrape.scrape_account(
                loader,
                {"handle": "asucr", "instagram_user_id": 449388329},
            )

        self.assertEqual((0, 0), (seen, new))

    def test_followed_accounts_merge_curated_metadata(self) -> None:
        loader = Mock()
        loader.context = Mock(username="scraper_from_context")
        viewer = Mock()
        viewer.get_followees.return_value = [
            types.SimpleNamespace(
                username="acm_ucr",
                full_name="ACM at UCR",
                userid=10839758322,
            ),
            types.SimpleNamespace(
                username="newclub_ucr",
                full_name="New Club at UCR",
                userid=999,
            ),
        ]
        self.scrape.instaloader.Profile.from_username.return_value = viewer

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

        by_handle = {account["handle"]: account for account in accounts}
        self.assertEqual(1, matched)
        self.assertEqual("ACM @ UCR", by_handle["acm_ucr"]["label"])
        self.assertEqual("club", by_handle["acm_ucr"]["category"])
        self.assertEqual("New Club at UCR", by_handle["newclub_ucr"]["label"])
        self.assertEqual("instagram_followed", by_handle["newclub_ucr"]["account_source"])
        self.scrape.instaloader.Profile.from_username.assert_called_once_with(
            loader.context,
            "scraper_from_context",
        )

    def test_followed_account_source_writes_runtime_cache(self) -> None:
        loader = Mock()
        followed = [{"handle": "acm_ucr"}]

        with patch.object(self.scrape, "ACCOUNT_SOURCE", "followed"):
            with patch.object(self.scrape, "load_curated_accounts", return_value=[]):
                with patch.object(
                    self.scrape,
                    "_load_followed_accounts",
                    return_value=(followed, 0),
                ):
                    with patch.object(self.scrape, "write_followed_accounts_cache") as write:
                        accounts = self.scrape._load_scrape_accounts(loader)

        self.assertEqual(followed, accounts)
        write.assert_called_once_with(followed)

    def test_empty_followed_account_source_does_not_replace_cache(self) -> None:
        loader = Mock()

        with patch.object(self.scrape, "ACCOUNT_SOURCE", "followed"):
            with patch.object(self.scrape, "load_curated_accounts", return_value=[]):
                with patch.object(
                    self.scrape,
                    "_load_followed_accounts",
                    return_value=([], 0),
                ):
                    with patch.object(self.scrape, "write_followed_accounts_cache") as write:
                        with self.assertRaisesRegex(RuntimeError, "zero followed accounts"):
                            self.scrape._load_scrape_accounts(loader)

        write.assert_not_called()

    def test_follow_list_graphql_failure_falls_back_to_accounts_json(self) -> None:
        loader = Mock()
        curated = [{"handle": "acm.ucr", "label": "ACM"}]

        with patch.object(self.scrape, "ACCOUNT_SOURCE", "followed"):
            with patch.object(self.scrape, "load_curated_accounts", return_value=curated):
                with patch.object(
                    self.scrape,
                    "_load_followed_accounts",
                    side_effect=self.scrape.QueryReturnedBadRequestException(
                        '400 Bad Request - "invalid request"'
                    ),
                ):
                    with patch.object(
                        self.scrape, "load_followed_accounts_cache", return_value=[]
                    ):
                        with patch.object(
                            self.scrape, "write_followed_accounts_cache"
                        ) as write:
                            accounts = self.scrape._load_scrape_accounts(loader)

        self.assertEqual(curated, accounts)
        write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
