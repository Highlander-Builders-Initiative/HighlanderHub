from __future__ import annotations

import importlib
import sys
import types
import unittest
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

        fake_exceptions = types.ModuleType("instaloader.exceptions")
        fake_exceptions.ConnectionException = _ConnectionException
        fake_exceptions.LoginRequiredException = _LoginRequiredException
        fake_exceptions.ProfileNotExistsException = _ProfileNotExistsException
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
            with patch.object(self.scrape, "load_accounts", return_value=accounts):
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
            with patch.object(self.scrape, "load_accounts", return_value=accounts):
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

    def test_rest_story_item_serialization(self) -> None:
        item_dict = {
            "pk": 12345678,
            "media_type": 2,
            "taken_at": 1716192000,
            "expiring_at": 1716278400,
            "image_versions2": {
                "candidates": [{"url": "https://ig.com/flyer.jpg"}]
            },
            "video_versions": [{"url": "https://ig.com/flyer.mp4"}],
            "caption": {"text": "Come to our ACM meeting! @member1 @member2"},
            "story_link_stickers": [
                {"story_link": {"url": "https://linktr.ee/acm_ucr"}}
            ]
        }
        item = self.scrape.RestStoryItem(item_dict, 10839758322, "acm_ucr")

        self.assertEqual(12345678, item.mediaid)
        self.assertEqual(10839758322, item.owner_profile.userid)
        self.assertEqual("acm_ucr", item.owner_profile.username)
        self.assertEqual("StoryVideo", item.typename)
        self.assertTrue(item.is_video)
        self.assertEqual("2024-05-20T08:00:00", item.date_utc.isoformat())
        self.assertEqual("2024-05-21T08:00:00", item.expiring_utc.isoformat())
        self.assertEqual("https://ig.com/flyer.jpg", item.url)
        self.assertEqual("https://ig.com/flyer.mp4", item.video_url)
        self.assertEqual("Come to our ACM meeting! @member1 @member2", item.caption)
        self.assertEqual(["member1", "member2"], item.caption_mentions)
        self.assertEqual("https://linktr.ee/acm_ucr", item.story_cta_url)

    def test_get_stories_via_rest_success(self) -> None:
        loader = Mock()
        loader.context.get_iphone_json.return_value = {
            "reels": {
                "10839758322": {
                    "items": [
                        {
                            "pk": 987654,
                            "media_type": 1,
                            "taken_at": 1716192000,
                            "image_versions2": {
                                "candidates": [{"url": "https://ig.com/flyer.jpg"}]
                            }
                        }
                    ]
                }
            }
        }

        stories = self.scrape._get_stories_via_rest(loader, [10839758322], "acm_ucr")
        self.assertEqual(1, len(stories))
        items = list(stories[0].get_items())
        self.assertEqual(1, len(items))
        self.assertEqual(987654, items[0].mediaid)
        self.assertFalse(items[0].is_video)
        self.assertEqual("https://ig.com/flyer.jpg", items[0].url)


if __name__ == "__main__":
    unittest.main()
