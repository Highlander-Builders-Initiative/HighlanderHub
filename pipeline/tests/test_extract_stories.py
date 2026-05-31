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
                        with patch.object(self.extract_stories, "_upload_story_flyer") as upload:
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
            upload.assert_not_called()
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
                        with patch.object(self.extract_stories, "_upload_story_flyer") as upload:
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
            self.assertNotIn("image_url", cache)
            upload.assert_not_called()
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

    def test_gemini_prompt_warns_about_schedule_grids(self) -> None:
        prompt = self.extract_stories._build_gemini_prompt(
            {"handle": "ucrlibrary", "posted_at": "2026-05-31T16:00:00Z"},
            {"label": "UCR Library", "category": "academic"},
            "WEEK 10\nSun. May 31\nMon. June 1\nTues. June 2",
        )

        self.assertIn("weekly schedule grids", prompt)
        self.assertIn("never invent a time", prompt)

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
            "image_url": "https://cdn.example/durable.jpg",
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
                    with patch.object(
                        self.extract_stories,
                        "_download_image",
                        return_value=b"image",
                    ) as download:
                        with patch.object(
                            self.extract_stories,
                            "_upload_story_flyer",
                            return_value="https://cdn.example/durable.jpg",
                        ) as upload:
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
            self.assertEqual("https://cdn.example/durable.jpg", result["image_url"])
            self.assertEqual(gemini_result, result["result"])
            self.assertEqual(
                result,
                json.loads((extracted_dir / f"{raw['id']}.json").read_text()),
            )
            download.assert_called_once_with(raw["image_url"])
            upload.assert_called_once_with(raw, b"image")
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
                        with patch.object(self.extract_stories, "_upload_story_flyer") as upload:
                            with patch.object(self.extract_stories, "_vision_ocr", return_value="  \n "):
                                with patch.object(self.extract_stories, "_write_remote_cache"):
                                    result = self.extract_stories._process_story(
                                        raw,
                                        {"label": "UCR Cybersecurity Club", "category": "club"},
                                    )

            self.assertEqual("no_text", result["status"])
            download.assert_called_once()
            upload.assert_not_called()

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

    def test_upload_story_flyer_uses_existing_bytes_and_deterministic_path(self) -> None:
        calls: dict[str, object] = {}

        class FakeBucket:
            def upload(self, path, file, file_options):
                calls["upload"] = (path, file, file_options)

            def get_public_url(self, path):
                calls["public_url_path"] = path
                return f"https://cdn.example/storage/{path}"

        class FakeStorage:
            def from_(self, bucket):
                calls["bucket"] = bucket
                return FakeBucket()

        fake_db = types.SimpleNamespace(
            client=lambda: types.SimpleNamespace(storage=FakeStorage())
        )

        raw = {"id": "3894795737410658776", "handle": "acm_ucr"}
        with patch.dict(sys.modules, {"db": fake_db}):
            url = self.extract_stories._upload_story_flyer(raw, b"image")

        self.assertEqual(
            "https://cdn.example/storage/instagram/acm_ucr/3894795737410658776.jpg",
            url,
        )
        self.assertEqual(self.extract_stories.DURABLE_FLYER_BUCKET, calls["bucket"])
        self.assertEqual(
            (
                "instagram/acm_ucr/3894795737410658776.jpg",
                b"image",
                {
                    "content-type": "image/jpeg",
                    "cache-control": "31536000",
                    "upsert": "true",
                },
            ),
            calls["upload"],
        )
        self.assertEqual(
            "instagram/acm_ucr/3894795737410658776.jpg",
            calls["public_url_path"],
        )

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
            "image_url": "https://cdn.example/durable.jpg",
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
        self.assertEqual(cached["image_url"], row["image_url"])
        self.assertEqual(raw["story_cta_url"], row["rsvp_url"])
        self.assertTrue(row["rsvp_required"])
        self.assertFalse(row["has_free_food"])

    def test_cached_event_flags_free_food_without_touching_category(self) -> None:
        # A boba study session: the LLM picks a real category ("club"), and free
        # food is detected deterministically from the OCR text instead.
        raw = {
            "id": "3908252818582041234",
            "handle": "wincucr",
            "permalink": "https://www.instagram.com/stories/wincucr/3908252818582041234/",
        }
        cached = {
            "status": "ok",
            "ocr_text": "WINC STUDY SESSION SOCIAL\nSANDWICHES AND BOBA WILL BE PROVIDED",
            "result": {
                "is_event": True,
                "title": "WINC Study Session Social",
                "description": "Study session social.",
                "starts_at": "2026-06-02T13:00:00-07:00",
                "ends_at": "2026-06-02T14:00:00-07:00",
                "location": "WCH 205/206",
                "category": "club",
                "tags": ["study session", "social"],
                "is_free": True,
                "rsvp_required": False,
                "rsvp_url": None,
                "confidence": "high",
            },
        }

        row = self.extract_stories._to_event_row(
            raw,
            cached,
            {"label": "Women in Computing", "category": "club"},
            "2026-05-30T20:22:48+00:00",
        )

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual("club", row["category"])
        self.assertTrue(row["has_free_food"])

    def test_llm_cannot_choose_free_food_but_storage_still_accepts_it(self) -> None:
        # The model picks the real type; free food is detected separately. The
        # value stays valid for storage so legacy/cached rows still round-trip.
        enum = self.extract_stories.GEMINI_RESPONSE_SCHEMA["properties"]["category"][
            "enum"
        ]
        self.assertNotIn("free_food", enum)
        self.assertIn("free_food", self.extract_stories.EVENT_CATEGORIES)

    def test_cached_legacy_free_food_category_round_trips(self) -> None:
        # A cached extraction predating the split still maps to free_food rather
        # than being reclassified to a fallback.
        raw = {
            "id": "3894795737410658799",
            "handle": "cyber_ucr",
            "permalink": "https://www.instagram.com/stories/cyber_ucr/3894795737410658799/",
        }
        cached = {
            "status": "ok",
            "result": {
                "is_event": True,
                "title": "Pizza Social",
                "starts_at": "2026-05-15T19:00:00-07:00",
                "category": "free_food",
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
        self.assertEqual("free_food", row["category"])

    def test_cached_event_blanks_host_for_anonymized_handle(self) -> None:
        raw = {
            "id": "3894795737410658769",
            "handle": "highlander_opps",
            "permalink": "https://www.instagram.com/stories/highlander_opps/3894795737410658769/",
        }
        cached = {
            "status": "ok",
            "result": {
                "is_event": True,
                "title": "Opportunity Fair",
                "starts_at": "2026-05-15T19:00:00-07:00",
            },
        }

        row = self.extract_stories._to_event_row(
            raw,
            cached,
            {"label": "highlander_opps", "category": "club"},
            "2026-05-14T12:00:00+00:00",
        )

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual("", row["host"])
        self.assertIsNone(row["host_handle"])

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

    def test_event_row_skips_collapsed_multiday_schedule_grid(self) -> None:
        # A two-week finals-week schedule grid: the LLM collapsed every day
        # column into a single 13-day "event" anchored on the empty Sun May 31
        # column. The flyer lists many dates and the span is far longer than a
        # day, so the row is skipped instead of published with a wrong start.
        raw = {
            "id": "3909284982299534837",
            "handle": "ucrlibrary",
            "posted_at": "2026-05-31T16:00:00Z",
        }
        cached = {
            "status": "ok",
            "ocr_text": (
                "FINALS WEEK STRESS RELIEF\nWEEK 10\n"
                "Sun. May 31\nMon. June 1\nTues. June 2\nWed. June 3\n"
                "Thurs. June 4\nFri. June 5\nFINALS WEEK\n"
                "Sun. June 7\nMon. June 8\nTues. June 9\nWed. June 10\n"
                "Thurs. June 11\nFri. June 12"
            ),
            "result": {
                "is_event": True,
                "title": "FINALS WEEK STRESS RELIEF",
                "starts_at": "2026-05-31T13:00:00-07:00",
                "ends_at": "2026-06-12T17:00:00-07:00",
            },
        }

        row = self.extract_stories._to_event_row(
            raw,
            cached,
            {"label": "UCR Library", "category": "academic"},
            "2026-05-31T16:09:54+00:00",
        )

        self.assertIsNone(row)

    def test_event_row_keeps_single_day_event_that_lists_many_dates(self) -> None:
        # The OCR names several dates (a "save these dates" series promo), but the
        # event the model returns spans a single afternoon. Only multi-day spans
        # look like a collapsed grid, so this one is kept.
        raw = {"id": "3894795737410658780", "handle": "cyber_ucr"}
        cached = {
            "status": "ok",
            "ocr_text": (
                "WORKSHOP SERIES\nMay 31\nJune 7\nJune 14\n"
                "First session details below"
            ),
            "result": {
                "is_event": True,
                "title": "Workshop Series Kickoff",
                "starts_at": "2026-05-31T13:00:00-07:00",
                "ends_at": "2026-05-31T15:00:00-07:00",
            },
        }

        row = self.extract_stories._to_event_row(
            raw,
            cached,
            {"label": "UCR Cybersecurity Club", "category": "club"},
            "2026-05-30T12:00:00+00:00",
        )

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual("2026-05-31T20:00:00+00:00", row["starts_at"])

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

    def test_filter_deleted_events_suppresses_admin_deleted_ids(self) -> None:
        rows = [
            {"id": "ig_cyber_ucr_20260515T1900Z"},
            {"id": "ig_ucrwrc_20260531T1800Z"},
        ]
        fake_db = types.SimpleNamespace(
            get_deleted_event_ids=lambda: {"ig_cyber_ucr_20260515T1900Z"}
        )

        with patch.dict(sys.modules, {"db": fake_db}):
            filtered = self.extract_stories._filter_deleted_events(rows)

        self.assertEqual([row["id"] for row in filtered], ["ig_ucrwrc_20260531T1800Z"])

    def test_filter_deleted_events_suppresses_duplicate_event_group(self) -> None:
        rows = [
            {
                "id": "ig_highlander_opps_20260531T1800Z",
                "title": "Matcha Crawl",
                "starts_at": "2026-05-31T18:00:00+00:00",
            },
            {
                "id": "ig_ucrwrc_20260531T1800Z",
                "title": "Matcha Crawl",
                "starts_at": "2026-05-31T11:00:00-07:00",
            },
            {
                "id": "ig_ucrlibrary_20260601T0700Z",
                "title": "Finals Week Stress Relief",
                "starts_at": "2026-06-01T00:00:00-07:00",
            },
        ]
        fake_db = types.SimpleNamespace(
            get_deleted_event_ids=lambda: {"ig_highlander_opps_20260531T1800Z"}
        )

        with patch.dict(sys.modules, {"db": fake_db}):
            filtered = self.extract_stories._filter_deleted_events(rows)

        self.assertEqual(
            [row["id"] for row in filtered],
            ["ig_ucrlibrary_20260601T0700Z"],
        )

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
