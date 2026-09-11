"""Decode QR destinations locally; never follow links found inside a flyer."""
from __future__ import annotations

from io import BytesIO

from url_utils import normalize_rsvp_url

QR_SCAN_VERSION = 1


def qr_rsvp_urls(image_bytes: bytes) -> list[str]:
    from PIL import Image
    import zxingcpp

    with Image.open(BytesIO(image_bytes)) as image:
        codes = zxingcpp.read_barcodes(image.convert("RGB"), formats=zxingcpp.BarcodeFormat.QRCode)
    return sorted({
        url for code in codes
        if code.text.strip().lower().startswith(("https://", "http://"))
        if (url := normalize_rsvp_url(code.text))
    })
