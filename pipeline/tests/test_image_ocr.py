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
        self.enterContext(patch.object(image_ocr, "GOOGLE_VISION_API_KEY_PRIMARY", "old-test-key"))
        self.enterContext(patch.object(image_ocr, "GOOGLE_VISION_API_KEY", "new-test-key"))
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
        with patch("requests.post", return_value=response) as request:
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

    def test_transient_vision_response_errors_retry_with_fresh_reservations(self):
        for code in (4, 8, 13, 14):
            with self.subTest(code=code):
                self.db.reset_mock()
                self.db.rpc.return_value.execute.side_effect = [
                    Mock(data={"slot": "primary", "used": 1000}),
                    Mock(data={"slot": "overflow", "used": 1}),
                ]
                failed = Mock(status_code=200)
                failed.json.return_value = {"responses": [{"error": {
                    "code": code, "message": "The service is currently unavailable.",
                }}]}
                success = Mock(status_code=200)
                success.json.return_value = {"responses": [{"fullTextAnnotation": {"text": " Workshop "}}]}

                def respond(*args, **kwargs):
                    # Every outgoing request must already have its own reservation.
                    self.assertEqual(request.call_count, self.db.rpc.return_value.execute.call_count)
                    return [failed, success][request.call_count - 1]

                with patch("requests.post", side_effect=respond) as request, \
                     patch.object(image_ocr.time, "sleep") as sleep:
                    self.assertEqual("Workshop", image_ocr._vision_ocr(b"flyer"))
                    self.assertEqual(2, request.call_count)
                    self.assertEqual(["new-test-key", "old-test-key"], [
                        call.kwargs["headers"]["X-Goog-Api-Key"] for call in request.call_args_list
                    ])
                    self.assertEqual(request.call_args_list[0].kwargs["json"],
                                     request.call_args_list[1].kwargs["json"])
                    sleep.assert_called_once_with(1)

    def test_vision_response_retries_are_bounded_and_keep_error_codes(self):
        response = Mock(status_code=200)
        response.json.return_value = {"responses": [{"error": {
            "code": 14, "message": "The service is currently unavailable.",
        }}]}
        with patch("requests.post", return_value=response) as request, \
             patch.object(image_ocr.time, "sleep") as sleep:
            with self.assertRaisesRegex(RuntimeError, r"HTTP 200, code 14.*service is currently unavailable"):
                image_ocr._vision_ocr(b"flyer")
            self.assertEqual(3, request.call_count)
            self.assertEqual(3, self.db.rpc.return_value.execute.call_count)
            self.assertEqual([1, 2], [call.args[0] for call in sleep.call_args_list])

    def test_permanent_or_unknown_vision_response_errors_are_not_retried(self):
        for code in (3, 5, 7, 16, 999, None):
            with self.subTest(code=code):
                self.db.reset_mock()
                response = Mock(status_code=200)
                response.json.return_value = {"responses": [{"error": {
                    "code": code, "message": "Cannot process this image",
                }}]}
                with patch("requests.post", return_value=response) as request, \
                     patch.object(image_ocr.time, "sleep") as sleep:
                    with self.assertRaisesRegex(RuntimeError, "Cannot process this image"):
                        image_ocr._vision_ocr(b"flyer")
                    request.assert_called_once()
                    self.db.rpc.assert_called_once()
                    sleep.assert_not_called()

    def test_vision_retries_only_transient_http_errors(self):
        import requests

        for status in (408, 429, 500, 502, 503, 504, 400, 401, 403, 404, 501):
            with self.subTest(status=status):
                self.db.reset_mock()
                response = Mock(status_code=status)
                response.raise_for_status.side_effect = requests.HTTPError(f"HTTP {status}", response=response)
                with patch("requests.post", return_value=response) as request, \
                     patch.object(image_ocr.time, "sleep") as sleep:
                    with self.assertRaises(requests.HTTPError):
                        image_ocr._vision_ocr(b"flyer")
                    attempts = 3 if status in (408, 429, 500, 502, 503, 504) else 1
                    self.assertEqual(attempts, request.call_count)
                    self.assertEqual(attempts, self.db.rpc.return_value.execute.call_count)
                    self.assertEqual(attempts - 1, sleep.call_count)

    def test_accounting_failure_during_retry_stops_before_another_ocr_request(self):
        import requests

        response = Mock(status_code=503)
        failure = requests.HTTPError("accounting unavailable", response=response)
        self.db.rpc.return_value.execute.side_effect = [
            Mock(data={"slot": "primary", "used": 1}), failure,
        ]
        with patch("requests.post", side_effect=requests.Timeout("uncertain delivery")) as request, \
             patch.object(image_ocr.time, "sleep"):
            with self.assertRaisesRegex(requests.HTTPError, "accounting unavailable"):
                image_ocr._vision_ocr(b"flyer")
            request.assert_called_once()
            self.assertEqual(2, self.db.rpc.return_value.execute.call_count)

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

    def test_transport_retries_are_bounded_and_keep_every_reservation(self):
        import requests

        for error in (requests.Timeout, requests.ConnectionError):
            with self.subTest(error=error):
                self.db.reset_mock()

                def fail(*args, **kwargs):
                    self.assertEqual(request.call_count, self.db.rpc.return_value.execute.call_count)
                    raise error("uncertain delivery")

                with patch("requests.post", side_effect=fail) as request, \
                     patch.object(image_ocr.time, "sleep") as sleep:
                    with self.assertRaises(error):
                        image_ocr._vision_ocr(b"flyer")
                    self.assertEqual(3, request.call_count)
                    self.assertEqual(3, self.db.rpc.return_value.execute.call_count)
                    self.assertEqual([1, 2], [call.args[0] for call in sleep.call_args_list])

    def test_missing_overflow_or_duplicate_keys_do_not_consume_usage(self):
        with patch("requests.post") as request:
            for overflow in (None, "new-test-key"):
                with patch.object(image_ocr, "GOOGLE_VISION_API_KEY_PRIMARY", overflow):
                    with self.assertRaises(RuntimeError):
                        image_ocr._vision_ocr(b"flyer")
            self.db.rpc.assert_not_called()
            request.assert_not_called()
