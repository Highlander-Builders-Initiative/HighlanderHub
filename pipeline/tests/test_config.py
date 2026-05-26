from __future__ import annotations

import importlib
import json
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
