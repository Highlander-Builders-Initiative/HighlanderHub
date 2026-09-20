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
                "https://vision.googleapis.com/v1/images:annotate?key=test-key",
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
