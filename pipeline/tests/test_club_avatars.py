"""Club avatars: the paid Instagram gap-fill and image shaping."""
from __future__ import annotations

import io
import random
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import club_avatars


class InstagramTests(unittest.TestCase):
    def test_buys_profiles_only_and_keeps_verified_real_pictures(self):
        blank = "https://cdn.example/t51.2885-19/44884218_345707102882519_2446069589734326272_n.jpg"
        client = Mock()
        client._run.return_value = {"id": "run", "status": "SUCCEEDED", "defaultDatasetId": "ds"}
        client.items.return_value = [
            {"kind": "profile", "data": {"username": "ACM_UCR", "id": "1",
                                         "profile_pic_url": "https://cdn.example/acm.jpg"}},
            {"kind": "profile", "data": {"username": "reused_ucr", "id": "999",
                                         "profile_pic_url": "https://cdn.example/stranger.jpg"}},
            {"kind": "profile", "data": {"username": "blank_ucr", "id": "3", "profile_pic_url": blank}},
            {"kind": "profile", "input": "gone_ucr", "error": "Account not found"},
        ]
        with patch.object(club_avatars, "ApifyClient", return_value=client):
            pictures = club_avatars.instagram_pictures(
                {"acm_ucr": "1", "reused_ucr": "2", "blank_ucr": "3", "gone_ucr": "4"})
        self.assertEqual(pictures, {"acm_ucr": "https://cdn.example/acm.jpg"})

        payload = client._run.call_args.args[0]
        self.assertEqual(payload["profiles"], ["acm_ucr", "blank_ucr", "gone_ucr", "reused_ucr"])
        self.assertTrue(payload["scrape_profile_data"])
        for paid_extra in ("scrape_posts", "scrape_reels", "scrape_detailed_data", "scrape_restricted_posts"):
            self.assertFalse(payload[paid_extra], paid_extra)
        self.assertEqual(client._run.call_args.kwargs["max_charge"], 0.02)


def encode(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


class ShapingTests(unittest.TestCase):
    def avatar(self, image: Image.Image) -> Image.Image:
        result = Image.open(io.BytesIO(club_avatars.to_avatar(encode(image))))
        self.assertEqual((result.format, result.size), ("WEBP", (128, 128)))
        return result.convert("RGB")

    def test_full_bleed_photo_is_cropped_like_a_profile_picture(self):
        rng = random.Random(1)
        photo = Image.new("RGB", (300, 200))
        photo.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256))
                       for _ in range(300 * 200)])
        result = self.avatar(photo)
        # A crop keeps noise out to the corners; padding would have left a flat border.
        corner = [result.getpixel((x, y)) for x in range(4) for y in range(4)]
        self.assertGreater(len(set(corner)), 4)

    def test_transparency_flattens_onto_white(self):
        logo = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        ImageDraw.Draw(logo).ellipse((64, 64, 191, 191), fill=(200, 0, 0, 255))
        result = self.avatar(logo)
        self.assertGreater(sum(result.getpixel((2, 2))), 740)


if __name__ == "__main__":
    unittest.main()
