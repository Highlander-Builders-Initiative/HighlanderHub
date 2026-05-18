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

        fake_exceptions = types.ModuleType("instaloader.exceptions")
        fake_exceptions.ConnectionException = _ConnectionException
        fake_exceptions.LoginRequiredException = _LoginRequiredException
        fake_instaloader.ConnectionException = _ConnectionException
        fake_instaloader.LoginRequiredException = _LoginRequiredException
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


if __name__ == "__main__":
    unittest.main()
