from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_ROOT = REPO_ROOT / "pipeline"
SCHEMAS_DIR = REPO_ROOT / "schemas"

if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMAS_DIR / name).read_text())


def _schema_keys(schema: dict) -> set[str]:
    return set(schema["properties"])


class SchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fake_config = types.SimpleNamespace(
            ROOT=PIPELINE_ROOT,
            RAW_DIR=PIPELINE_ROOT / "data" / "raw",
            EXTRACTED_DIR=PIPELINE_ROOT / "data" / "extracted",
            GEMINI_API_KEY="test",
            GOOGLE_VISION_API_KEY="test",
            ensure_dirs=lambda: None,
            load_accounts=lambda: [],
        )
        cls._saved_modules = {
            name: sys.modules.get(name) for name in ("config", "db")
        }
        sys.modules["config"] = fake_config
        sys.modules["db"] = types.SimpleNamespace(upsert_batched=lambda *a, **k: 0)
        sys.modules.pop("extract_stories", None)
        sys.modules.pop("normalize_events", None)
        sys.modules.pop("normalize", None)
        import extract_stories  # noqa: E402
        import normalize  # noqa: E402
        import normalize_events  # noqa: E402

        cls.extract_stories = extract_stories
        cls.normalize = normalize
        cls.normalize_events = normalize_events
        cls.events_schema = _load_schema("events.upsert.schema.json")
        cls.stories_schema = _load_schema("stories.upsert.schema.json")
        cls.event_keys = _schema_keys(cls.events_schema)
        cls.story_keys = _schema_keys(cls.stories_schema)
        cls.event_required = set(cls.events_schema["required"])
        cls.story_required = set(cls.stories_schema["required"])

    def _assert_row_matches_schema(self, row: dict[str, object], schema_keys: set[str], required: set[str]) -> None:
        keys = set(row.keys())
        self.assertTrue(keys <= schema_keys, keys - schema_keys)
        self.assertTrue(required <= keys, required - keys)

    @classmethod
    def tearDownClass(cls) -> None:
        for name, mod in cls._saved_modules.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod

    def test_extract_stories_event_row_keys(self) -> None:
        row = self.extract_stories._to_event_row(
            {
                "id": "3894795737410658765",
                "handle": "cyber_ucr",
                "permalink": "https://www.instagram.com/stories/cyber_ucr/3894795737410658765/",
                "image_url": "https://cdn.example/flyer.jpg",
            },
            {
                "status": "ok",
                "result": {
                    "is_event": True,
                    "title": "Security Night Workshop",
                    "starts_at": "2026-05-15T19:00:00-07:00",
                    "category": "career",
                    "tags": ["security"],
                },
            },
            {"label": "UCR Cybersecurity Club"},
            "2026-05-14T12:00:00+00:00",
        )
        self.assertIsNotNone(row)
        assert row is not None
        self._assert_row_matches_schema(row, self.event_keys, self.event_required)

    def test_normalize_events_localist_row_keys(self) -> None:
        row = self.normalize_events._to_event_row(
            {
                "id": 123,
                "title": "Security Night Workshop",
                "first_date": "2026-05-15T19:00:00-07:00",
                "localist_url": "https://events.ucr.edu/foo",
            },
            "2026-05-14T12:00:00+00:00",
        )
        self.assertIsNotNone(row)
        assert row is not None
        self._assert_row_matches_schema(row, self.event_keys, self.event_required)

    def test_normalize_events_highlander_link_row_keys(self) -> None:
        row = self.normalize_events._to_event_row_hlink(
            {
                "id": 456,
                "name": "Club Meetup",
                "startsOn": "2026-05-15T19:00:00-07:00",
                "endsOn": "2026-05-15T21:00:00-07:00",
            },
            "2026-05-14T12:00:00+00:00",
        )
        self.assertIsNotNone(row)
        assert row is not None
        self._assert_row_matches_schema(row, self.event_keys, self.event_required)

    def test_normalize_story_row_keys(self) -> None:
        row = self.normalize._to_story_row(
            {
                "id": "3140000000000000000",
                "handle": "acm.ucr",
                "posted_at": "2026-05-11T18:30:00+00:00Z",
                "is_video": False,
                "caption_mentions": ["other.handle"],
            },
            {"label": "ACM at UCR", "category": "club"},
        )
        self._assert_row_matches_schema(row, self.story_keys, self.story_required)


if __name__ == "__main__":
    unittest.main()
