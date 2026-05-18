from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PIPELINE_ROOT / "extract_stories.py"
sys.path.insert(0, str(PIPELINE_ROOT))


class ExtractStoriesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(MODULE_PATH.exists(), "pipeline/extract_stories.py should exist")
        sys.modules.pop("extract_stories", None)
        self.extract_stories = importlib.import_module("extract_stories")

    def test_expired_story_image_is_cached_without_ocr_or_gemini_calls(self) -> None:
        raw = {
            "id": "3894795737410658765",
            "handle": "cyber_ucr",
            "is_video": False,
            "image_url": "https://cdn.example/expired.jpg",
            "permalink": "https://www.instagram.com/stories/cyber_ucr/3894795737410658765/",
        }

        with tempfile.TemporaryDirectory() as tmp:
            extracted_dir = Path(tmp)
            with patch.object(self.extract_stories, "EXTRACTED_DIR", extracted_dir):
                with patch.object(
                    self.extract_stories,
                    "_download_image",
                    side_effect=self.extract_stories.ImageExpired("expired"),
                ) as download:
                    with patch.object(self.extract_stories, "_vision_ocr") as vision:
                        with patch.object(self.extract_stories, "_gemini_extract") as gemini:
                            result = self.extract_stories._process_story(
                                raw,
                                {"label": "UCR Cybersecurity Club", "category": "club"},
                            )

            self.assertEqual("image_expired", result["status"])
            self.assertTrue((extracted_dir / f"{raw['id']}.json").exists())
            download.assert_called_once()
            vision.assert_not_called()
            gemini.assert_not_called()

    def test_no_ocr_text_is_cached_without_calling_gemini(self) -> None:
        raw = {
            "id": "3894795737410658766",
            "handle": "cyber_ucr",
            "is_video": False,
            "image_url": "https://cdn.example/flyer.jpg",
            "caption": None,
            "story_cta_url": None,
            "posted_at": "2026-05-12T18:30:00+00:00Z",
            "permalink": "https://www.instagram.com/stories/cyber_ucr/3894795737410658766/",
        }

        with tempfile.TemporaryDirectory() as tmp:
            extracted_dir = Path(tmp)
            with patch.object(self.extract_stories, "EXTRACTED_DIR", extracted_dir):
                with patch.object(self.extract_stories, "_download_image", return_value=b"image"):
                    with patch.object(self.extract_stories, "_vision_ocr", return_value="  \n "):
                        with patch.object(self.extract_stories, "_gemini_extract") as gemini:
                            result = self.extract_stories._process_story(
                                raw,
                                {"label": "UCR Cybersecurity Club", "category": "club"},
                            )

            self.assertEqual("no_text", result["status"])
            cache = json.loads((extracted_dir / f"{raw['id']}.json").read_text())
            self.assertEqual("no_text", cache["status"])
            gemini.assert_not_called()

    def test_cached_event_maps_to_instagram_event_row(self) -> None:
        raw = {
            "id": "3894795737410658767",
            "handle": "cyber_ucr",
            "image_url": "https://cdn.example/flyer.jpg",
            "story_cta_url": "https://lu.ma/example",
            "permalink": "https://www.instagram.com/stories/cyber_ucr/3894795737410658767/",
        }
        cached = {
            "status": "ok",
            "result": {
                "is_event": True,
                "title": "Security Night Workshop",
                "description": "Hands-on security practice.",
                "starts_at": "2026-05-15T19:00:00-07:00",
                "ends_at": None,
                "location": "",
                "category": "career",
                "tags": ["security", 101, ""],
                "is_free": True,
                "rsvp_required": True,
                "rsvp_url": None,
                "confidence": "high",
            },
        }

        row = self.extract_stories._to_event_row(
            raw,
            cached,
            {"label": "UCR Cybersecurity Club", "category": "club"},
            "2026-05-14T12:00:00+00:00",
        )

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual("ig_cyber_ucr_20260516T0200Z", row["id"])
        self.assertEqual("Security Night Workshop", row["title"])
        self.assertEqual("UCR Cybersecurity Club", row["host"])
        self.assertEqual("cyber_ucr", row["host_handle"])
        self.assertEqual("UC Riverside", row["location"])
        self.assertEqual("career", row["category"])
        self.assertEqual(["security", "101"], row["tags"])
        self.assertEqual("instagram", row["source"])
        self.assertEqual(raw["permalink"], row["source_url"])
        self.assertEqual(raw["image_url"], row["image_url"])
        self.assertEqual(raw["story_cta_url"], row["rsvp_url"])
        self.assertTrue(row["rsvp_required"])

    def test_event_row_rejects_non_iso_starts_at(self) -> None:
        raw = {
            "id": "3894795737410658768",
            "handle": "cyber_ucr",
        }
        cached = {
            "status": "ok",
            "result": {
                "is_event": True,
                "title": "Security Night Workshop",
                "starts_at": "May 15 7pm",
            },
        }

        row = self.extract_stories._to_event_row(
            raw,
            cached,
            {"label": "UCR Cybersecurity Club", "category": "club"},
            "2026-05-14T12:00:00+00:00",
        )

        self.assertIsNone(row)

    def test_event_row_normalizes_valid_llm_timestamps_to_utc(self) -> None:
        raw = {
            "id": "3894795737410658769",
            "handle": "cyber_ucr",
        }
        cached = {
            "status": "ok",
            "result": {
                "is_event": True,
                "title": "Security Night Workshop",
                "starts_at": "2026-05-15T19:00:00-07:00",
                "ends_at": "2026-05-15T21:00:00-07:00",
            },
        }

        row = self.extract_stories._to_event_row(
            raw,
            cached,
            {"label": "UCR Cybersecurity Club", "category": "club"},
            "2026-05-14T12:00:00+00:00",
        )

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual("2026-05-16T02:00:00+00:00", row["starts_at"])
        self.assertEqual("2026-05-16T04:00:00+00:00", row["ends_at"])

    def test_event_row_drops_invalid_optional_ends_at(self) -> None:
        raw = {
            "id": "3894795737410658770",
            "handle": "cyber_ucr",
        }
        cached = {
            "status": "ok",
            "result": {
                "is_event": True,
                "title": "Security Night Workshop",
                "starts_at": "2026-05-15T19:00:00-07:00",
                "ends_at": "May 15 9pm",
            },
        }

        row = self.extract_stories._to_event_row(
            raw,
            cached,
            {"label": "UCR Cybersecurity Club", "category": "club"},
            "2026-05-14T12:00:00+00:00",
        )

        self.assertIsNotNone(row)
        assert row is not None
        self.assertIsNone(row["ends_at"])

    def test_bool_or_default_parses_common_llm_boolean_forms(self) -> None:
        parse = self.extract_stories._bool_or_default

        self.assertFalse(parse("false", True))
        self.assertTrue(parse("TRUE", False))
        self.assertFalse(parse("0", True))
        self.assertTrue(parse(1, False))
        self.assertFalse(parse(0, True))
        self.assertTrue(parse("not a boolean", True))
        self.assertFalse(parse("not a boolean", False))


if __name__ == "__main__":
    unittest.main()
