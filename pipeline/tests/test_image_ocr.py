"""Verify the image transport used by post extraction without network calls."""
import base64
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import image_ocr
import instagram_cooldown


class ImageOcrTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(image_ocr, "GOOGLE_VISION_API_KEY_PRIMARY", "new-test-key"))
        self.enterContext(patch.object(image_ocr, "GOOGLE_VISION_API_KEY", "old-test-key"))
        self.enterContext(patch.object(image_ocr, "GOOGLE_VISION_API_KEY_SECONDARY", None))
        self.enterContext(patch.object(image_ocr, "GOOGLE_VISION_API_KEY_TERTIARY", None))
        self.db = self.enterContext(patch("db.client")).return_value
        self.db.rpc.return_value.execute.return_value.data = {
            "slot": "primary", "month": "2026-09-01", "used": 1,
        }
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.enterContext(patch.object(instagram_cooldown, "INSTAGRAM_COOLDOWN_FILE",
                                       Path(directory.name) / "cooldown.json"))
        self.enterContext(patch.object(instagram_cooldown, "_UNSAVED", None))

    def test_expired_url_does_not_pause_other_images(self):
        response = Mock(status_code=403)
        with patch("requests.get", return_value=response) as request:
            with self.assertRaises(image_ocr.ImageExpired):
                image_ocr._download_image("https://cdn.example/expired.jpg")
            response.status_code = 200
            response.content = b"flyer"
            self.assertEqual(b"flyer", image_ocr._download_image("https://cdn.example/next.jpg"))
        self.assertEqual(2, request.call_count)
        self.assertIsNone(instagram_cooldown.current())

    def test_unreachable_regional_cdn_retries_same_signed_image_on_general_cdn(self):
        import requests

        url = "https://instagram.ftpa1-1.fna.fbcdn.net/v/flyer.jpg?oh=signature&_nc_ht=instagram.ftpa1-1.fna.fbcdn.net"
        response = Mock(status_code=200, content=b"flyer")
        for error in (requests.ConnectionError("[Errno 101] Network is unreachable"),
                      requests.ConnectTimeout("IPv6 unreachable")):
            with self.subTest(error=error), patch("requests.get", side_effect=[error, response]) as request, \
                 patch.object(image_ocr.time, "sleep"):
                self.assertEqual(b"flyer", image_ocr._download_image(url))
                self.assertEqual(url, request.call_args_list[0].args[0])
                self.assertEqual(url.replace("instagram.ftpa1-1.fna.fbcdn.net", "scontent.cdninstagram.com", 1),
                                 request.call_args_list[1].args[0])

    def test_download_retries_are_bounded_and_do_not_reroute_other_hosts(self):
        import requests

        for url in ("https://cdn.example/flyer.jpg", "https://instagram.fna.fbcdn.net.example/flyer.jpg"):
            with self.subTest(url=url), patch("requests.get", side_effect=requests.ConnectionError("offline")) as request, \
                 patch.object(image_ocr.time, "sleep") as sleep:
                with self.assertRaises(requests.ConnectionError):
                    image_ocr._download_image(url)
                self.assertEqual(3, request.call_count)
                self.assertTrue(all(call.args[0] == url for call in request.call_args_list))
                self.assertEqual([1, 2], [call.args[0] for call in sleep.call_args_list])

    def test_expired_regional_url_is_not_retried_or_rerouted(self):
        for status in (401, 403, 404, 410):
            with self.subTest(status=status), patch("requests.get", return_value=Mock(status_code=status)) as request:
                with self.assertRaises(image_ocr.ImageExpired):
                    image_ocr._download_image("https://instagram.ftpa1-1.fna.fbcdn.net/expired.jpg")
                request.assert_called_once()

    def test_image_download_returns_bytes_and_reports_expired_urls(self):
        response = Mock(status_code=200, content=b"flyer")
        with patch("requests.get", return_value=response) as download:
            self.assertEqual(b"flyer", image_ocr._download_image("https://cdn.example/flyer.jpg"))
            download.assert_called_once_with("https://cdn.example/flyer.jpg", timeout=10)
            response.raise_for_status.assert_called_once()
            for status in (404, 410):
                response.status_code = status
                with self.assertRaises(image_ocr.ImageExpired):
                    image_ocr._download_image("https://cdn.example/expired.jpg")

    def test_vision_reads_the_uploaded_image_and_surfaces_api_errors(self):
        response = Mock()
        response.json.return_value = {"responses": [{"fullTextAnnotation": {"text": " Workshop "}}]}
        with patch.object(image_ocr, "GOOGLE_VISION_API_KEY", "test-key"), \
             patch("requests.post", return_value=response) as request:
            self.assertEqual("Workshop", image_ocr._vision_ocr(b"flyer"))
            request.assert_called_once_with(
                "https://vision.googleapis.com/v1/images:annotate",
                headers={"X-Goog-Api-Key": "new-test-key"},
                json={"requests": [{"image": {"content": base64.b64encode(b"flyer").decode("ascii")},
                                    "features": [{"type": "DOCUMENT_TEXT_DETECTION"}]}]},
                timeout=20,
            )
            response.json.return_value = {"responses": [{"error": {"message": "OCR unavailable"}}]}
            with self.assertRaisesRegex(RuntimeError, "OCR unavailable"):
                image_ocr._vision_ocr(b"flyer")

    def test_missing_image_or_credentials_never_make_a_request(self):
        with patch("requests.get") as download, patch("requests.post") as request, \
             patch.object(image_ocr, "GOOGLE_VISION_API_KEY", None):
            with self.assertRaises(ValueError):
                image_ocr._download_image(None)
            with self.assertRaisesRegex(RuntimeError, "GOOGLE_VISION_API_KEY"):
                image_ocr._vision_ocr(b"flyer")
            download.assert_not_called()
            request.assert_not_called()

    def test_primary_then_overflow_selection_uses_durable_reservations(self):
        self.db.rpc.return_value.execute.side_effect = [
            Mock(data={"slot": "primary", "used": 1000}),
            Mock(data={"slot": "overflow", "used": 1}),
            Mock(data={"slot": "overflow", "used": 1001}),
        ]
        response = Mock()
        response.json.return_value = {"responses": [{}]}
        with patch("requests.post", return_value=response) as request:
            for _ in range(3):
                image_ocr._vision_ocr(b"flyer")
        self.assertEqual(["new-test-key", "old-test-key", "old-test-key"], [
            call.kwargs["headers"]["X-Goog-Api-Key"] for call in request.call_args_list
        ])
        self.assertEqual(3, self.db.rpc.call_count)
        self.db.rpc.assert_called_with("reserve_vision_ocr_request", {})

    def test_accounting_failure_or_invalid_response_never_sends_ocr(self):
        with patch("requests.post") as request:
            self.db.rpc.return_value.execute.side_effect = RuntimeError("database unavailable")
            with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                image_ocr._vision_ocr(b"flyer")
            self.db.rpc.return_value.execute.side_effect = None
            for invalid in (None, [], {}, {"slot": "unknown"}):
                self.db.rpc.return_value.execute.return_value.data = invalid
                with self.assertRaisesRegex(RuntimeError, "Invalid Vision usage reservation"):
                    image_ocr._vision_ocr(b"flyer")
            request.assert_not_called()

    def test_additional_keys_follow_reserved_slots_without_exposing_secrets_to_db(self):
        response = Mock()
        response.json.return_value = {"responses": [{}]}
        self.db.rpc.return_value.execute.side_effect = [
            Mock(data={"slot": slot, "used": 1000})
            for slot in ("primary", "secondary", "tertiary", "overflow")
        ]
        with patch.object(image_ocr, "GOOGLE_VISION_API_KEY_SECONDARY", "second-key"), \
             patch.object(image_ocr, "GOOGLE_VISION_API_KEY_TERTIARY", "third-key"), \
             patch("requests.post", return_value=response) as request:
            for _ in range(4):
                image_ocr._vision_ocr(b"flyer")
        self.assertEqual(["new-test-key", "second-key", "third-key", "old-test-key"],
                         [call.kwargs["headers"]["X-Goog-Api-Key"] for call in request.call_args_list])
        self.db.rpc.assert_called_with("reserve_vision_ocr_request", {
            "p_secondary_enabled": True, "p_tertiary_enabled": True})

    def test_optional_keys_can_be_enabled_independently(self):
        for slot in ("secondary", "tertiary"):
            with self.subTest(slot=slot), \
                 patch.object(image_ocr, f"GOOGLE_VISION_API_KEY_{slot.upper()}", "extra-key"), \
                 patch("requests.post", return_value=Mock(json=lambda: {"responses": [{}]})) as request:
                self.db.rpc.return_value.execute.return_value.data = {"slot": slot}
                image_ocr._vision_ocr(b"flyer")
                self.db.rpc.assert_called_with("reserve_vision_ocr_request", {
                    "p_secondary_enabled": slot == "secondary", "p_tertiary_enabled": slot == "tertiary"})
                self.assertEqual("extra-key", request.call_args.kwargs["headers"]["X-Goog-Api-Key"])

    def test_unconfigured_reserved_slot_never_sends_ocr(self):
        self.db.rpc.return_value.execute.return_value.data = {"slot": "secondary"}
        with patch("requests.post") as request:
            with self.assertRaisesRegex(RuntimeError, "Invalid Vision usage reservation"):
                image_ocr._vision_ocr(b"flyer")
        request.assert_not_called()

    def test_duplicate_optional_keys_never_reserve_or_send_ocr(self):
        for second, third in (("old-test-key", None), (None, "new-test-key"), ("same", "same")):
            with self.subTest(second=second, third=third), \
                 patch.object(image_ocr, "GOOGLE_VISION_API_KEY_SECONDARY", second), \
                 patch.object(image_ocr, "GOOGLE_VISION_API_KEY_TERTIARY", third), patch("requests.post") as request:
                with self.assertRaisesRegex(RuntimeError, "must be different"):
                    image_ocr._vision_ocr(b"flyer")
                self.db.rpc.assert_not_called()
                request.assert_not_called()

    def test_timeout_keeps_reservation_and_does_not_retry_another_key(self):
        import requests

        def timeout(*args, **kwargs):
            self.db.rpc.return_value.execute.assert_called_once()
            raise requests.Timeout("uncertain delivery")

        with patch("requests.post", side_effect=timeout) as request:
            with self.assertRaises(requests.Timeout):
                image_ocr._vision_ocr(b"flyer")
            request.assert_called_once()
        self.db.rpc.assert_called_once_with("reserve_vision_ocr_request", {})

    def test_missing_primary_or_duplicate_keys_do_not_consume_usage(self):
        with patch("requests.post") as request:
            for primary in (None, "old-test-key"):
                with patch.object(image_ocr, "GOOGLE_VISION_API_KEY_PRIMARY", primary):
                    with self.assertRaises(RuntimeError):
                        image_ocr._vision_ocr(b"flyer")
            self.db.rpc.assert_not_called()
            request.assert_not_called()
