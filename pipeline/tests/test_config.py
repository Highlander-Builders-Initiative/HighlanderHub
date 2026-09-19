from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))


class ConfigAccountSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        sys.modules.pop("config", None)
        self.config = importlib.import_module("config")

    def test_backfill_forces_curated_roster_for_collection_and_publication(self) -> None:
        with patch.dict(os.environ, {"PIPELINE_POST_BACKFILL_SINCE": "2025-08-01",
                                     "PIPELINE_ACCOUNT_SOURCE": "followed",
                                     "PIPELINE_POST_DISCOVERY": "following"}):
            importlib.reload(self.config)
        self.addCleanup(importlib.reload, self.config)
        self.assertEqual("profiles", self.config.POST_DISCOVERY_MODE)
        self.assertEqual("accounts_json", self.config.ACCOUNT_SOURCE)
        with patch.object(self.config, "load_curated_accounts", return_value=[{"handle": "curated"}]), \
             patch.object(self.config, "load_followed_accounts_cache") as followed:
            self.assertEqual({"curated": {"handle": "curated"}}, self.config.load_account_meta())
            followed.assert_not_called()

    def test_blank_backfill_restores_original_settings(self) -> None:
        with patch.dict(os.environ, {"PIPELINE_POST_BACKFILL_SINCE": "",
                                     "PIPELINE_ACCOUNT_SOURCE": "followed",
                                     "PIPELINE_POST_DISCOVERY": "following"}):
            importlib.reload(self.config)
        self.addCleanup(importlib.reload, self.config)
        self.assertEqual("following", self.config.POST_DISCOVERY_MODE)
        self.assertEqual("followed", self.config.ACCOUNT_SOURCE)

    def test_followed_cache_wins_when_followed_source_is_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            accounts_path = root / "accounts.json"
            followed_path = root / "data" / "followed_accounts.json"
            followed_path.parent.mkdir()
            accounts_path.write_text(
                json.dumps({"accounts": [{"handle": "from_accounts_json"}]}),
                encoding="utf-8",
            )
            followed_path.write_text(
                json.dumps({"accounts": [{"handle": "from_followed_cache"}]}),
                encoding="utf-8",
            )

            with patch.object(self.config, "ACCOUNT_SOURCE", "followed"):
                with patch.object(self.config, "ACCOUNTS_FILE", accounts_path):
                    with patch.object(self.config, "FOLLOWED_ACCOUNTS_FILE", followed_path):
                        accounts = self.config.load_accounts()

        self.assertEqual([{"handle": "from_followed_cache"}], accounts)

    def test_missing_followed_cache_falls_back_to_accounts_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            accounts_path = root / "accounts.json"
            followed_path = root / "data" / "followed_accounts.json"
            accounts_path.write_text(
                json.dumps({"accounts": [{"handle": "from_accounts_json"}]}),
                encoding="utf-8",
            )

            with patch.object(self.config, "ACCOUNT_SOURCE", "followed"):
                with patch.object(self.config, "ACCOUNTS_FILE", accounts_path):
                    with patch.object(self.config, "FOLLOWED_ACCOUNTS_FILE", followed_path):
                        accounts = self.config.load_accounts()

        self.assertEqual([{"handle": "from_accounts_json"}], accounts)


if __name__ == "__main__":
    unittest.main()
