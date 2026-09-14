"""Regression cases from the Sep 10 extraction-quality review."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from classify import classify_content_kind
from flyer_qr import qr_rsvp_urls
from event_dates import evidence_dates, midnight_end

NOW = "2026-09-10T18:25:25+00:00"


class PipelineQualityTests(unittest.TestCase):


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


    def test_midnight_repair_requires_the_printed_end(self):
        start = "2026-09-19T17:00:00-07:00"
        invalid = "2026-09-19T00:00:00-07:00"
        for text in ("September 19 5PM-8PM", "September 20 5PM-12AM", "September 19", "September 19, 2027 5PM-12AM"):
            self.assertEqual(invalid, midnight_end(text, start, invalid))
        self.assertEqual("2026-09-20T07:00:00+00:00", midnight_end("September 19, 2026 5PM–12AM", start, invalid))


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
