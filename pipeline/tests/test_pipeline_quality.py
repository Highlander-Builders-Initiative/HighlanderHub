"""Regression cases from the Sep 10 extraction-quality review."""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import extract_stories as extract
from classify import classify_content_kind
from flyer_qr import qr_rsvp_urls
from story_dates import evidence_dates, has_source_date, is_single_session_reminder, midnight_end
from url_utils import normalize_rsvp_url

NOW = "2026-09-10T18:25:25+00:00"


class PipelineQualityTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = json.loads(
            (Path(__file__).parent / "fixtures/sep10_quality_stories.json").read_text()
        )

    def row(self, sid):
        fixture = self.fixtures[sid]
        return extract._to_event_row(fixture["raw"], fixture["cached"], {}, NOW)

    def test_capacity_does_not_hide_scheduled_events(self):
        for text in (
            "Limited slots. Meet September 21 at 5 PM.",
            "Reserve your spot for September 21 at 5 PM.",
            "Choose a slot. Meet September 21 at 5 PM.",
        ):
            with self.subTest(text=text):
                self.assertEqual("student_event", classify_content_kind(
                    "instagram", title="Sunset Hike", description=text,
                ))

    def test_booking_phrases_match_without_other_matching_phrases(self):
        for text in (
            "Select a slot", "Select a\nslot", "Choose your slot",
            "Pick a time slot", "Reserve your appointment", "Book your appointment",
            "Sign up for a slot",
        ):
            with self.subTest(text=text):
                self.assertEqual("student_application", classify_content_kind(
                    "instagram", title="Board Member Coffee Chats", ocr_text=text,
                ))

    def test_greetings_do_not_corroborate_fractions(self):
        for text in ("Happy Friday! 1/2 price boba", "Happy Friday! Half off 1/2 price boba", "Friday, 1/2 price boba"):
            self.assertEqual(set(), evidence_dates(text))
        for text in ("Signups close Thursday (6/11)", "6/11 (Thursday)", "Thursday\n6/11"):
            self.assertEqual({(6, 11)}, evidence_dates(text))

    def test_apply_today_cannot_supply_an_event_date(self):
        fixture = self.fixtures["3982580348213896675"]
        self.assertFalse(has_source_date(fixture["raw"], fixture["cached"]))
        row, retired = self.row("3982580348213896675")
        self.assertIsNone(row)
        self.assertIn("ig_ucrposc_academicadvising101_20260909T1903Z", retired)

    def test_coffee_chat_retires_the_old_posting_time_id(self):
        row, retired = self.row("3982071674776379510")
        self.assertEqual("student_application", row["content_kind"])
        self.assertEqual("2026-09-21T16:00:00+00:00", row["starts_at"])
        old_id = "ig_ucrhcg_20260909T0212Z"
        self.assertIn(old_id, retired)
        self.assertIn(row["id"], extract._inherit_tombstones({old_id}, {row["id"]: retired}))

    def test_reshared_resource_fair_and_cruise_dedupe_by_post(self):
        for ids in (
            ("3982819621169405952", "3983218921065494579", "3983255612447719308"),
            ("3982808608584563280", "3982841794136036299"),
            ("3982733858780214639", "3982688104342687256", "3983255452865768231"),
        ):
            with self.subTest(ids=ids):
                pairs = [(self.fixtures[s]["raw"], self.fixtures[s]["cached"]) for s in ids]
                rows, retired, retired_by = extract._collect_event_rows(pairs, {}, NOW)
                deduped = extract.dedupe_event_rows(rows)
                self.assertEqual(1, len(deduped))
                self.assertTrue(deduped[0]["id"].startswith("ig_post_"))
                self.assertGreaterEqual(len(retired), len(ids))
                old_id = next(iter(retired))
                locked = extract._inherit_tombstones({old_id}, retired_by)
                self.assertEqual([], extract.suppress_tombstoned_event_groups(rows, locked))

    def test_observed_author_is_shared_without_mutating_raw_stories(self):
        first = self.fixtures["3982808608584563280"]
        second = self.fixtures["3982841794136036299"]
        first["raw"]["reshared_post"]["owner_username"] = "rcycle_coop"
        pairs = [(f["raw"], f["cached"]) for f in (first, second)]
        for ordered in (pairs, pairs[::-1]):
            rows, _, _ = extract._collect_event_rows(ordered, {}, NOW)
            self.assertEqual({"ig_rcycle_coop_20260929T0130Z"}, {r["id"] for r in rows})
        self.assertIsNone(second["raw"]["reshared_post"]["owner_username"])

    def test_galilee_ends_at_midnight_the_next_day(self):
        row, _ = self.row("3982866140879738392")
        self.assertEqual("2026-09-20T00:00:00+00:00", row["starts_at"])
        self.assertEqual("2026-09-20T07:00:00+00:00", row["ends_at"])

    def test_midnight_repair_requires_the_printed_end(self):
        start = "2026-09-19T17:00:00-07:00"
        invalid = "2026-09-19T00:00:00-07:00"
        for text in ("September 19 5PM-8PM", "September 20 5PM-12AM", "September 19", "September 19, 2027 5PM-12AM"):
            self.assertEqual(invalid, midnight_end(text, start, invalid))
        self.assertEqual("2026-09-20T07:00:00+00:00", midnight_end("September 19, 2026 5PM–12AM", start, invalid))

    def test_ambiguous_schedules_are_skipped_and_old_ids_retired(self):
        for sid in ("3982663805918402695", "3982538491137133079", "3983255797651872521"):
            row, retired = self.row(sid)
            self.assertIsNone(row)
            self.assertTrue(retired)

    def test_current_session_reminders_and_related_dates_remain_events(self):
        for sid in ("3981747545054348909", "3911695212514710907", "3981981784413819767"):
            with self.subTest(sid=sid):
                row, _ = self.row(sid)
                self.assertIsNotNone(row)
                self.assertEqual("student_event", row["content_kind"])

    def test_today_does_not_resolve_a_single_day_time_grid(self):
        self.assertFalse(is_single_session_reminder(
            {"posted_at": "2026-09-10T16:00:00Z"},
            {"ocr_text": "Today! Study room schedule\nSeptember 10\nRoom A 12-2 PM\nRoom B 2-5 PM\nRoom C 5-7 PM"},
            "2026-09-10T19:00:00+00:00", "2026-09-11T02:00:00+00:00",
        ))

    def test_ocr_spaces_are_repaired_only_with_source_support(self):
        row, _ = self.row("3982733858780214639")
        self.assertEqual("https://BIT.LY/GRADPANEL26", row["rsvp_url"])
        self.assertIsNone(normalize_rsvp_url("BIT.LY/GRAD PANEL26"))
        self.assertIsNone(normalize_rsvp_url("link in bio", "link in bio"))
        self.assertIsNone(normalize_rsvp_url("https://www.instagram.com/asucrlegislative"))
        self.assertIsNone(normalize_rsvp_url("Forms.gle"))

    def test_instagram_cta_does_not_shadow_a_registration_link(self):
        fixture = self.fixtures["3982688104342687256"]
        fixture["raw"]["story_cta_url"] = "https://instagram.com/poderatucr"
        row, _ = self.row("3982688104342687256")
        self.assertEqual("https://BIT.LY/GRADPANEL26", row["rsvp_url"])

    def test_multiple_distinct_qr_destinations_are_not_guessed(self):
        fixture = self.fixtures["3983220415203469029"]
        fixture["cached"]["result"]["_qr_urls"] = ["https://example.org/a", "https://example.org/b"]
        row, _ = self.row("3983220415203469029")
        self.assertIsNone(row["rsvp_url"])
        self.assertTrue(row["rsvp_required"])

    def qr_image(self, value):
        import zxingcpp
        from PIL import Image
        pixels = memoryview(zxingcpp.write_barcode(zxingcpp.BarcodeFormat.QRCode, value, width=240, height=240))
        image = Image.frombytes("L", (pixels.shape[1], pixels.shape[0]), pixels.tobytes())
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def test_actual_qr_decoding_rejects_non_registration_payloads(self):
        self.assertEqual(["https://example.org/register"], qr_rsvp_urls(self.qr_image("https://example.org/register")))
        for value in ("https://instagram.com/club", "javascript:alert(1)", "WELCOME"):
            self.assertEqual([], qr_rsvp_urls(self.qr_image(value)))

    def test_cached_qr_recovery_runs_once_without_ocr_or_gemini(self):
        fixture = self.fixtures["3983220415203469029"]
        raw, cached = fixture["raw"], fixture["cached"]
        cached["image_url"] = "https://example.org/flyer.png"
        image = self.qr_image("https://example.org/register")
        with patch.object(extract, "_utc_now", return_value=NOW), \
             patch.object(extract, "_known_handles", return_value=set()), \
             patch.object(extract, "_download_image", return_value=image) as download, \
             patch.object(extract, "_persist_terminal_cache", side_effect=lambda _, c: c) as persist, \
             patch.object(extract, "_vision_ocr") as ocr, \
             patch.object(extract, "_gemini_extract") as gemini:
            repaired = extract._repair_cached_rsvp(raw, cached)
            self.assertEqual(repaired, extract._repair_cached_rsvp(raw, repaired))
        download.assert_called_once_with(cached["image_url"])
        persist.assert_called_once()
        ocr.assert_not_called()
        gemini.assert_not_called()
        row, _ = extract._to_event_row(raw, repaired, {}, NOW)
        self.assertEqual("https://example.org/register", row["rsvp_url"])
        self.assertNotIn("_qr_urls", cached["result"])

    def test_failed_qr_download_leaves_cache_retryable(self):
        fixture = self.fixtures["3983220415203469029"]
        with patch.object(extract, "_utc_now", return_value=NOW), \
             patch.object(extract, "_known_handles", return_value=set()), \
             patch.object(extract, "_download_image", side_effect=OSError("unavailable")), \
             patch.object(extract, "_persist_terminal_cache") as persist:
            self.assertEqual(fixture["cached"], extract._repair_cached_rsvp(fixture["raw"], fixture["cached"]))
        persist.assert_not_called()

    def test_successful_scan_without_a_qr_code_is_cached(self):
        fixture = self.fixtures["3983220415203469029"]
        with patch.object(extract, "qr_rsvp_urls", return_value=[]) as decode:
            scanned = extract._add_qr_result(fixture["cached"], b"flyer")
            self.assertEqual(scanned, extract._add_qr_result(scanned, b"flyer"))
        decode.assert_called_once()
        self.assertEqual([], scanned["result"]["_qr_urls"])
        self.assertTrue(scanned["result"]["rsvp_required"])

    def test_qr_metadata_survives_the_remote_cache_round_trip(self):
        fixture = self.fixtures["3983220415203469029"]
        with patch.object(extract, "qr_rsvp_urls", return_value=["https://example.org/register"]):
            scanned = extract._add_qr_result(fixture["cached"], b"flyer")
        remote = extract._remote_cache_row_to_payload(scanned)
        self.assertEqual(scanned["result"], remote["result"])

    def test_text_only_backfill_preserves_ocr_classification_by_default(self):
        import backfill_content_kind as backfill

        rows = [{
            "id": "ig_example", "source": "instagram", "is_locked": False,
            "title": "Board Member Coffee Chats", "description": "Meet our board members.",
            "content_kind": "student_application",
        }]
        client = Mock()
        client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = rows
        with patch.object(backfill, "client", return_value=client):
            self.assertEqual([], backfill.plan())
            self.assertEqual("student_event", backfill.plan(include_flyer_origins=True)[0]["new_content_kind"])
        client.table.return_value.select.return_value.eq.assert_called_with("is_locked", False)


if __name__ == "__main__":
    unittest.main()
