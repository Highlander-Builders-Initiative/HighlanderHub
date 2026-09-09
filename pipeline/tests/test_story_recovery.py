"""Regression coverage for extraction recovery and conservative event identity."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import extract_stories as extract
import scrape
from event_identity import dedupe_event_rows, suppress_tombstoned_event_groups


class StoryRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(extract, "EXTRACTED_DIR", self.directory))
        self.remote = self.stack.enter_context(patch.object(extract, "_load_remote_cache", return_value=None))
        self.write_remote = self.stack.enter_context(patch.object(extract, "_write_remote_cache"))
        self.download = self.stack.enter_context(patch.object(extract, "_download_image", return_value=b"flyer"))
        self.vision = self.stack.enter_context(patch.object(extract, "_vision_ocr", return_value="June 3 6PM-9PM"))
        self.gemini = self.stack.enter_context(patch.object(extract, "_gemini_extract", return_value={
            "is_event": True, "title": "GBM", "starts_at": "2026-06-03T18:00:00-07:00",
        }))
        self.upload = self.stack.enter_context(patch.object(extract, "_upload_story_flyer", return_value="https://example.com/durable.jpg"))
        self.raw = {"id": "123", "handle": "club_a", "image_url": "https://example.com/flyer.jpg"}

    def test_failed_upload_recovers_on_next_run_and_then_stops_downloading(self) -> None:
        self.upload.side_effect = [None, "https://example.com/durable.jpg"]
        first = extract._process_story(self.raw, {})
        self.assertEqual("ok", first["status"])
        self.assertNotIn("image_url", first)
        second = extract._process_story(self.raw, {})
        third = extract._process_story(self.raw, {})
        self.assertEqual("https://example.com/durable.jpg", second["image_url"])
        self.assertEqual(second, third)
        self.assertEqual(2, self.download.call_count)
        self.assertEqual(2, self.upload.call_count)
        self.vision.assert_called_once()
        self.gemini.assert_called_once()
        self.assertEqual(second, json.loads((self.directory / "123.json").read_text()))
        self.write_remote.assert_called_with(second)

    def test_remote_cache_without_image_recovers_without_model_calls(self) -> None:
        self.remote.return_value = {"status": "ok", "story_id": "123", "result": {"is_event": True}}
        result = extract._process_story(self.raw, {})
        self.assertEqual("https://example.com/durable.jpg", result["image_url"])
        self.vision.assert_not_called()
        self.gemini.assert_not_called()
        self.write_remote.assert_called_with(result)

    def test_recovery_download_failure_preserves_event_and_can_retry(self) -> None:
        cached = {"status": "ok", "story_id": "123", "result": {"is_event": True}}
        extract._write_cache("123", cached)
        self.download.side_effect = [extract.ImageExpired("gone"), b"flyer"]
        self.assertEqual(cached, extract._process_story(self.raw, {}))
        self.assertEqual(cached, json.loads((self.directory / "123.json").read_text()))
        self.assertIn("image_url", extract._process_story(self.raw, {}))
        self.vision.assert_not_called()
        self.gemini.assert_not_called()

    def test_corrupt_and_nonterminal_local_caches_recover_from_remote(self) -> None:
        remote = {"status": "not_event", "story_id": "123"}
        self.remote.return_value = remote
        for data in (b'{broken', b'\xff', b'[]', b'null', b'{"status": "error"}'):
            with self.subTest(data=data):
                (self.directory / "123.json").write_bytes(data)
                self.assertEqual(remote, extract._process_story(self.raw, {}))
                self.assertEqual(remote, json.loads((self.directory / "123.json").read_text()))
        self.download.assert_not_called()

    def test_corrupt_cache_without_remote_reextracts(self) -> None:
        (self.directory / "123.json").write_text('{broken')
        self.assertEqual("ok", extract._process_story(self.raw, {})["status"])
        self.vision.assert_called_once()
        self.gemini.assert_called_once()

    def test_download_error_does_not_create_terminal_cache(self) -> None:
        self.download.side_effect = [requests.HTTPError("403 Forbidden"), b"flyer"]
        self.assertEqual("error", extract._process_story(self.raw, {})["status"])
        self.assertFalse((self.directory / "123.json").exists())
        self.write_remote.assert_not_called()
        self.assertEqual("ok", extract._process_story(self.raw, {})["status"])


class ImageStatusTests(unittest.TestCase):
    def test_403_is_retryable_but_404_and_410_are_expired(self) -> None:
        for status in (403, 404, 410, 500):
            with self.subTest(status=status):
                response = Mock(status_code=status)
                response.raise_for_status.side_effect = requests.HTTPError(str(status))
                expected = extract.ImageExpired if status in {404, 410} else requests.HTTPError
                with patch("requests.get", return_value=response):
                    with self.assertRaises(expected):
                        extract._download_image("https://example.com/flyer.jpg")


class StoryIdentityTests(unittest.TestCase):
    def test_same_title_and_time_from_other_clubs_survive_dedupe_and_tombstones(self) -> None:
        rows = [
            {"id": "ig_club_a_20260604T0100Z", "title": "GBM", "starts_at": "2026-06-04T01:00:00Z", "location": "Room A"},
            {"id": "ig_club_b_20260604T0100Z", "title": "gbm", "starts_at": "2026-06-03T18:00:00-07:00", "location": "Room B"},
        ]
        self.assertEqual(rows, dedupe_event_rows(rows))
        self.assertEqual([rows[1]], suppress_tombstoned_event_groups(rows, {rows[0]["id"]}))

    def test_anonymized_clubs_do_not_share_identity(self) -> None:
        rows = [
            {"id": f"ig_{handle}_20260604T0100Z", "title": "GBM", "starts_at": "2026-06-04T01:00:00Z", "host": "", "host_handle": None}
            for handle in ("highlander_opps", "another_club")
        ]
        self.assertEqual(rows, dedupe_event_rows(rows))

    def test_repeated_stories_with_same_event_id_still_dedupe(self) -> None:
        row = {"id": "ig_club_a_20260604T0100Z", "title": "GBM", "starts_at": "2026-06-04T01:00:00Z"}
        richer = {**row, "description": "Event details"}
        self.assertEqual([richer], dedupe_event_rows([row, richer]))


class OcrBoundaryTests(unittest.TestCase):
    def test_unrelated_years_and_geographic_words_do_not_disable_ocr(self) -> None:
        raw = {"posted_at": "2026-06-01T12:00:00Z"}
        for text in (
            "Spring Quarter 2026\nJune 3 6PM-9PM",
            "June 3 6PM-9PM\nRoom 2027",
            "June 3 6PM-9PM\nMarkaz Middle Eastern Theme Hall",
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    ("2026-06-04T01:00:00+00:00", "2026-06-04T04:00:00+00:00"),
                    extract._ocr_local_event_range(raw, {"ocr_text": text}),
                )

    def test_explicit_year_or_timezone_does_not_get_overridden(self) -> None:
        raw = {"id": "123", "handle": "club_a", "posted_at": "2026-06-01T12:00:00Z"}
        for text, start, end in (
            ("June 3, 2027 6PM-9PM", "2027-06-04T01:00:00+00:00", "2027-06-04T04:00:00+00:00"),
            ("June 3 6PM-9PM Eastern", "2026-06-03T22:00:00+00:00", "2026-06-04T01:00:00+00:00"),
            ("June 3 6PM-9PM EDT", "2026-06-03T22:00:00+00:00", "2026-06-04T01:00:00+00:00"),
            ("June 3 6PM-9PM UTC+2", "2026-06-03T16:00:00+00:00", "2026-06-03T19:00:00+00:00"),
        ):
            with self.subTest(text=text):
                cached = {"status": "ok", "ocr_text": text, "result": {"is_event": True, "title": "GBM", "starts_at": start, "ends_at": end}}
                self.assertIsNone(extract._ocr_local_event_range(raw, cached))
                row, prior_id = extract._to_event_row(raw, cached, {}, "2026-06-01T12:00:00Z")
                self.assertEqual(start, row["starts_at"])
                self.assertEqual(end, row["ends_at"])
                self.assertIsNone(prior_id)


class StoryRefreshTests(unittest.TestCase):
    def test_reobserved_story_refreshes_links_without_counting_as_new(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.object(scrape, "RAW_DIR", Path(tmp)):
            original = {"id": "123", "handle": "club_a", "caption": "Original", "image_url": "https://example.com/old.jpg"}
            self.assertTrue(scrape._write_item(original, "club_a"))
            fresh = {**original, "caption": None, "story_cta_url": "https://example.com/rsvp", "image_url": "https://example.com/new.jpg", "video_url": "https://example.com/new.mp4"}
            self.assertFalse(scrape._write_item(fresh, "club_a"))
            path = Path(tmp) / "club_a" / "123.json"
            saved = json.loads(path.read_text())
            self.assertEqual("Original", saved["caption"])
            for field in ("story_cta_url", "image_url", "video_url"):
                self.assertEqual(fresh[field], saved[field])
            self.assertFalse(scrape._write_item({**original, "image_url": None}, "club_a"))
            self.assertEqual(saved, json.loads(path.read_text()))

    def test_reobservation_repairs_invalid_raw_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.object(scrape, "RAW_DIR", Path(tmp)):
            directory = Path(tmp) / "club_a"
            directory.mkdir()
            path = directory / "123.json"
            fresh = {"id": "123", "handle": "club_a", "image_url": "https://example.com/new.jpg"}
            for content in ('{broken', '[]', 'null'):
                with self.subTest(content=content):
                    path.write_text(content)
                    self.assertFalse(scrape._write_item(fresh, "club_a"))
                    self.assertEqual(fresh, json.loads(path.read_text()))


if __name__ == "__main__":
    unittest.main()
