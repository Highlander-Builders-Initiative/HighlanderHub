from __future__ import annotations

import importlib
import json
import sys
import tempfile
import types
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
                with patch.object(self.extract_stories, "_load_remote_cache", return_value=None):
                    with patch.object(
                        self.extract_stories,
                        "_download_image",
                        side_effect=self.extract_stories.ImageExpired("expired"),
                    ) as download:
                        with patch.object(self.extract_stories, "_vision_ocr") as vision:
                            with patch.object(self.extract_stories, "_gemini_extract") as gemini:
                                with patch.object(self.extract_stories, "_write_remote_cache"):
                                    result = self.extract_stories._process_story(
                                        raw,
                                        {
                                            "label": "UCR Cybersecurity Club",
                                            "category": "club",
                                        },
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
                with patch.object(self.extract_stories, "_load_remote_cache", return_value=None):
                    with patch.object(self.extract_stories, "_download_image", return_value=b"image"):
                        with patch.object(self.extract_stories, "_vision_ocr", return_value="  \n "):
                            with patch.object(self.extract_stories, "_gemini_extract") as gemini:
                                with patch.object(self.extract_stories, "_write_remote_cache"):
                                    result = self.extract_stories._process_story(
                                        raw,
                                        {
                                            "label": "UCR Cybersecurity Club",
                                            "category": "club",
                                        },
                                    )

            self.assertEqual("no_text", result["status"])
            cache = json.loads((extracted_dir / f"{raw['id']}.json").read_text())
            self.assertEqual("no_text", cache["status"])
            gemini.assert_not_called()

    def test_gemini_extract_uses_vertex_ai_client(self) -> None:
        calls: dict[str, dict[str, object]] = {}

        class FakeModels:
            def generate_content(self, **kwargs):
                calls["generate_content"] = kwargs
                return types.SimpleNamespace(parsed={"is_event": False})

        class FakeClient:
            def __init__(self, **kwargs):
                calls["client"] = kwargs
                self.models = FakeModels()

        fake_google = types.ModuleType("google")
        fake_genai = types.ModuleType("google.genai")
        fake_genai.Client = FakeClient
        fake_google.genai = fake_genai

        saved_google = sys.modules.get("google")
        saved_genai = sys.modules.get("google.genai")
        sys.modules["google"] = fake_google
        sys.modules["google.genai"] = fake_genai
        try:
            with patch.object(self.extract_stories, "GOOGLE_CLOUD_PROJECT", "ucr-cloud"):
                with patch.object(self.extract_stories, "GOOGLE_CLOUD_LOCATION", "global"):
                    result = self.extract_stories._gemini_extract(
                        {
                            "handle": "cyber_ucr",
                            "posted_at": "2026-05-12T18:30:00+00:00Z",
                        },
                        {"label": "UCR Cybersecurity Club", "category": "club"},
                        "Security Night Workshop",
                    )
        finally:
            if saved_google is None:
                sys.modules.pop("google", None)
            else:
                sys.modules["google"] = saved_google
            if saved_genai is None:
                sys.modules.pop("google.genai", None)
            else:
                sys.modules["google.genai"] = saved_genai

        self.assertEqual({"is_event": False}, result)
        self.assertEqual(
            {"vertexai": True, "project": "ucr-cloud", "location": "global"},
            calls["client"],
        )
        self.assertEqual(
            self.extract_stories.GEMINI_MODEL,
            calls["generate_content"]["model"],
        )
        self.assertEqual(
            "application/json",
            calls["generate_content"]["config"]["response_mime_type"],
        )

    def test_gemini_prompt_requires_pacific_wall_time(self) -> None:
        prompt = self.extract_stories._build_gemini_prompt(
            {
                "handle": "ucrwrc",
                "posted_at": "2026-05-26T15:37:33Z",
            },
            {"label": "Women's Resource Center @ UCR", "category": "community"},
            "SUNDAY, MAY 31ST\n11:00 AM 2:00 PM",
        )

        self.assertIn("America/Los_Angeles", prompt)
        self.assertIn("Do not change an explicit OCR date", prompt)
        self.assertIn("11:00 AM as starts_at and 2:00 PM as ends_at", prompt)

    def test_supabase_cache_hit_writes_local_cache_without_ocr_or_gemini_calls(self) -> None:
        raw = {
            "id": "3894795737410658772",
            "handle": "cyber_ucr",
            "is_video": False,
            "image_url": "https://cdn.example/flyer.jpg",
        }
        remote_cache = {
            "status": "ok",
            "story_id": raw["id"],
            "handle": raw["handle"],
            "ocr_text": "Security Night Workshop",
            "result": {
                "is_event": True,
                "title": "Security Night Workshop",
                "starts_at": "2026-05-15T19:00:00-07:00",
            },
            "extracted_at": "2026-05-14T12:00:00+00:00",
        }

        with tempfile.TemporaryDirectory() as tmp:
            extracted_dir = Path(tmp)
            with patch.object(self.extract_stories, "EXTRACTED_DIR", extracted_dir):
                with patch.object(
                    self.extract_stories,
                    "_load_remote_cache",
                    return_value=remote_cache,
                ) as load_remote:
                    with patch.object(self.extract_stories, "_download_image") as download:
                        with patch.object(self.extract_stories, "_vision_ocr") as vision:
                            with patch.object(self.extract_stories, "_gemini_extract") as gemini:
                                result = self.extract_stories._process_story(
                                    raw,
                                    {"label": "UCR Cybersecurity Club", "category": "club"},
                                )

            self.assertEqual(remote_cache, result)
            self.assertEqual(
                remote_cache,
                json.loads((extracted_dir / f"{raw['id']}.json").read_text()),
            )
            load_remote.assert_called_once_with(raw["id"])
            download.assert_not_called()
            vision.assert_not_called()
            gemini.assert_not_called()

    def test_ok_extraction_is_cached_to_supabase_and_disk(self) -> None:
        raw = {
            "id": "3894795737410658773",
            "handle": "cyber_ucr",
            "is_video": False,
            "image_url": "https://cdn.example/flyer.jpg",
            "caption": None,
            "story_cta_url": None,
            "posted_at": "2026-05-12T18:30:00+00:00Z",
        }
        gemini_result = {
            "is_event": True,
            "title": "Security Night Workshop",
            "starts_at": "2026-05-15T19:00:00-07:00",
        }

        with tempfile.TemporaryDirectory() as tmp:
            extracted_dir = Path(tmp)
            with patch.object(self.extract_stories, "EXTRACTED_DIR", extracted_dir):
                with patch.object(self.extract_stories, "_load_remote_cache", return_value=None):
                    with patch.object(self.extract_stories, "_download_image", return_value=b"image"):
                        with patch.object(
                            self.extract_stories,
                            "_vision_ocr",
                            return_value="Security Night Workshop",
                        ):
                            with patch.object(
                                self.extract_stories,
                                "_gemini_extract",
                                return_value=gemini_result,
                            ):
                                with patch.object(
                                    self.extract_stories,
                                    "_write_remote_cache",
                                ) as write_remote:
                                    result = self.extract_stories._process_story(
                                        raw,
                                        {"label": "UCR Cybersecurity Club", "category": "club"},
                                    )

            self.assertEqual("ok", result["status"])
            self.assertEqual(raw["id"], result["story_id"])
            self.assertEqual(raw["handle"], result["handle"])
            self.assertEqual("Security Night Workshop", result["ocr_text"])
            self.assertEqual(gemini_result, result["result"])
            self.assertEqual(
                result,
                json.loads((extracted_dir / f"{raw['id']}.json").read_text()),
            )
            write_remote.assert_called_once_with(result)

    def test_remote_error_cache_is_ignored_so_story_can_retry(self) -> None:
        raw = {
            "id": "3894795737410658774",
            "handle": "cyber_ucr",
            "is_video": False,
            "image_url": "https://cdn.example/flyer.jpg",
        }

        with tempfile.TemporaryDirectory() as tmp:
            extracted_dir = Path(tmp)
            with patch.object(self.extract_stories, "EXTRACTED_DIR", extracted_dir):
                with patch.object(
                    self.extract_stories,
                    "_load_remote_cache",
                    return_value={
                        "status": "error",
                        "story_id": raw["id"],
                        "handle": raw["handle"],
                        "error": "Gemini outage",
                        "extracted_at": "2026-05-14T12:00:00+00:00",
                    },
                ):
                    with patch.object(self.extract_stories, "_download_image", return_value=b"image") as download:
                        with patch.object(self.extract_stories, "_vision_ocr", return_value="  \n "):
                            with patch.object(self.extract_stories, "_write_remote_cache"):
                                result = self.extract_stories._process_story(
                                    raw,
                                    {"label": "UCR Cybersecurity Club", "category": "club"},
                                )

            self.assertEqual("no_text", result["status"])
            download.assert_called_once()

    def test_missing_remote_cache_configuration_is_treated_as_cache_miss(self) -> None:
        saved_db = sys.modules.get("db")
        sys.modules["db"] = type(
            "FakeDb",
            (),
            {
                "client": staticmethod(
                    lambda: (_ for _ in ()).throw(SystemExit("Supabase env missing"))
                )
            },
        )
        try:
            with patch.object(self.extract_stories.log, "warning") as warning:
                self.assertIsNone(
                    self.extract_stories._load_remote_cache("3894795737410658775")
                )
            warning.assert_called_once()
        finally:
            if saved_db is None:
                sys.modules.pop("db", None)
            else:
                sys.modules["db"] = saved_db

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

    def test_event_row_uses_unambiguous_ocr_date_over_gemini_date(self) -> None:
        raw = {
            "id": "3905650594048735498",
            "handle": "ucrwrc",
            "posted_at": "2026-05-26T15:37:33Z",
        }
        cached = {
            "status": "ok",
            "ocr_text": (
                "THIS SUNDAY!\n"
                "MATCHA CRAWL\n"
                "SUNDAY, MAY 31ST\n"
                "11:00 AM 2:00 PM\n"
                "Bring your R'Card and a reusable cup"
            ),
            "result": {
                "is_event": True,
                "title": "UCR Matcha Crawl",
                "starts_at": "2026-06-01T11:00:00-07:00",
                "ends_at": "2026-06-01T14:00:00-07:00",
            },
        }

        row = self.extract_stories._to_event_row(
            raw,
            cached,
            {"label": "Women's Resource Center @ UCR", "category": "community"},
            "2026-05-26T21:04:04+00:00",
        )

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual("ig_ucrwrc_20260531T1800Z", row["id"])
        self.assertEqual("2026-05-31T18:00:00+00:00", row["starts_at"])
        self.assertEqual("2026-05-31T21:00:00+00:00", row["ends_at"])

    def test_event_row_uses_pacific_zone_over_gemini_offset(self) -> None:
        raw = {
            "id": "3904501726242275192",
            "handle": "ucrwrc",
            "posted_at": "2026-05-25T01:34:57Z",
        }
        cached = {
            "status": "ok",
            "ocr_text": (
                "NEXT SUNDAY!\n"
                "MATCHA CRAWL\n"
                "SUNDAY, MAY 31ST\n"
                "11:00 AM 2:00 PM\n"
                "QAMARIA YEMENI COFFEE CO."
            ),
            "result": {
                "is_event": True,
                "title": "MATCHA CRAWL",
                "starts_at": "2026-05-31T11:00:00-08:00",
                "ends_at": "2026-05-31T14:00:00-08:00",
            },
        }

        row = self.extract_stories._to_event_row(
            raw,
            cached,
            {"label": "Women's Resource Center @ UCR", "category": "community"},
            "2026-05-26T21:04:04+00:00",
        )

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual("ig_ucrwrc_20260531T1800Z", row["id"])
        self.assertEqual("2026-05-31T18:00:00+00:00", row["starts_at"])
        self.assertEqual("2026-05-31T21:00:00+00:00", row["ends_at"])

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

    def test_event_row_drops_unsafe_external_urls(self) -> None:
        raw = {
            "id": "3894795737410658771",
            "handle": "cyber_ucr",
            "image_url": "ftp://cdn.example/flyer.jpg",
            "story_cta_url": "mailto:club@example.com",
            "permalink": "javascript:alert(1)",
        }
        cached = {
            "status": "ok",
            "result": {
                "is_event": True,
                "title": "Security Night Workshop",
                "starts_at": "2026-05-15T19:00:00-07:00",
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
        self.assertIsNone(row["source_url"])
        self.assertIsNone(row["image_url"])
        self.assertIsNone(row["rsvp_url"])

    def test_bool_or_default_parses_common_llm_boolean_forms(self) -> None:
        parse = self.extract_stories._bool_or_default

        self.assertFalse(parse("false", True))
        self.assertTrue(parse("TRUE", False))
        self.assertFalse(parse("0", True))
        self.assertTrue(parse(1, False))
        self.assertFalse(parse(0, True))
        self.assertTrue(parse("not a boolean", True))
        self.assertFalse(parse("not a boolean", False))

    def test_normalize_url_only_allows_http_urls(self) -> None:
        normalize = self.extract_stories._normalize_url

        self.assertEqual("https://lu.ma/example", normalize("lu.ma/example"))
        self.assertEqual("https://events.ucr.edu/foo", normalize("//events.ucr.edu/foo"))
        self.assertEqual("http://example.com/a", normalize("http://example.com/a"))
        self.assertEqual("https://example.com/a", normalize("https://example.com/a"))
        self.assertIsNone(normalize("javascript:alert(1)"))
        self.assertIsNone(normalize("mailto:club@example.com"))
        self.assertIsNone(normalize("ftp://example.com/file"))
        self.assertIsNone(normalize("https://link in bio"))
        self.assertIsNone(normalize("link in bio"))


if __name__ == "__main__":
    unittest.main()
