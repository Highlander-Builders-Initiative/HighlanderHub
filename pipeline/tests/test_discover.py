from __future__ import annotations

import copy
import importlib
import json
import sys
import types
import unittest
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
ORG_FIXTURE = FIXTURES_DIR / "highlander_link_org.json"

if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))


class DiscoverPureFunctionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fake_dotenv = types.ModuleType("dotenv")
        fake_dotenv.load_dotenv = lambda *args, **kwargs: None  # type: ignore[misc]
        fake_config = types.SimpleNamespace(
            ACCOUNTS_FILE=PIPELINE_ROOT / "accounts.json",
            HIGHLANDER_LINK_COOKIE="test-cookie",
        )
        cls._saved_modules = {
            name: sys.modules.get(name) for name in ("config", "discover", "dotenv")
        }
        sys.modules["dotenv"] = fake_dotenv
        sys.modules["config"] = fake_config
        sys.modules.pop("discover", None)
        cls.discover = importlib.import_module("discover")

    @classmethod
    def tearDownClass(cls) -> None:
        for name, mod in cls._saved_modules.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod

    def test_normalize_handle_url_variants(self) -> None:
        cases = [
            ("https://www.instagram.com/Ucrvsa/", "ucrvsa"),
            ("Instagram.com/Ucrvsa/", "ucrvsa"),
            ("@ucrvsa", "ucrvsa"),
            ("ucrvsa", "ucrvsa"),
            ("https://instagram.com/cyber_ucr?igsh=abc", "cyber_ucr"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(self.discover._normalize_handle(raw), expected)

    def test_normalize_handle_rejects_invalid(self) -> None:
        for raw in ("", None, "not a handle!", "!!!"):
            with self.subTest(raw=raw):
                self.assertIsNone(self.discover._normalize_handle(raw))

    def test_extract_handle_from_structured_socials(self) -> None:
        detail = {
            "socialMedia": {"InstagramUrl": "https://www.instagram.com/acm_ucr/"},
            "description": "<p>No IG link here</p>",
        }
        self.assertEqual(self.discover._extract_handle(detail), "acm_ucr")

    def test_extract_handle_falls_back_to_description_text(self) -> None:
        detail = {
            "socialMedia": {},
            "description": "<p>Find us at https://www.instagram.com/hbi.ucr/</p>",
        }
        self.assertEqual(self.discover._extract_handle(detail), "hbi.ucr")

    def test_extract_handle_from_text_plain_url(self) -> None:
        text = "DM us @ucrvsa or visit https://instagram.com/ucrvsa/events"
        self.assertEqual(self.discover._extract_handle_from_text(text), "ucrvsa")

    def test_map_category_single_and_multiple(self) -> None:
        self.assertEqual(
            self.discover._map_category(["Academic/Professional"]),
            "academic-professional",
        )
        self.assertEqual(
            self.discover._map_category(["Cultural", "Service"]),
            "cultural",
        )

    def test_map_category_empty_defaults_to_club(self) -> None:
        for names in ([], None, [""], ["   "]):
            with self.subTest(names=names):
                self.assertEqual(self.discover._map_category(names), "club")

    def test_merge_accounts_existing_wins_and_sorts(self) -> None:
        existing = [
            {"handle": "ucrvsa", "label": "UCR VSA", "category": "club"},
            {"handle": "zebra_club", "label": "Zebra Club", "category": "club"},
        ]
        discovered = [
            {
                "handle": "ucrvsa",
                "label": "Vietnamese Student Association at UCR",
                "category": "cultural",
            },
            {"handle": "alpha_club", "label": "Alpha Club", "category": "service"},
        ]
        existing_copy = copy.deepcopy(existing)

        merged = self.discover._merge_accounts(existing, discovered)

        self.assertEqual(existing, existing_copy)
        self.assertEqual(
            [e["handle"] for e in merged],
            ["alpha_club", "ucrvsa", "zebra_club"],
        )
        by_handle = {e["handle"]: e for e in merged}
        self.assertEqual(by_handle["ucrvsa"]["label"], "UCR VSA")

    def test_fixture_end_to_end_account_shape(self) -> None:
        detail = json.loads(ORG_FIXTURE.read_text())
        handle = self.discover._extract_handle(detail)
        self.assertEqual(handle, "cyber_ucr")

        org = {
            "Name": "Cyber @ UCR",
            "CategoryNames": ["Academic/Professional"],
        }
        entry = {
            "handle": handle,
            "label": org.get("Name") or detail.get("name") or handle,
            "category": self.discover._map_category(org.get("CategoryNames")),
        }
        self.assertEqual(
            entry,
            {
                "handle": "cyber_ucr",
                "label": "Cyber @ UCR",
                "category": "academic-professional",
            },
        )


if __name__ == "__main__":
    unittest.main()
