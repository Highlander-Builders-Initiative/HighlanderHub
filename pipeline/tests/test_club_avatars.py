"""Club avatars: Engage org matching, the paid Instagram gap-fill, and image shaping."""
from __future__ import annotations

import io
import random
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import club_avatars


def engage(orgs: list[dict]):
    """Fake Engage: one search page, then each org's detail record."""
    details = {str(org["Id"]): org.pop("instagram", None) for org in orgs}

    def fetch(_session, url, **params):
        if url.endswith("/search/organizations"):
            rows = orgs if params["skip"] == 0 else []
            return SimpleNamespace(json=lambda: {"value": rows})
        org_id = url.rsplit("/", 1)[1]
        return SimpleNamespace(json=lambda: {"socialMedia": {"InstagramUrl": details[org_id]}})
    return fetch


def org(org_id: int, name: str, instagram: str | None, picture: str | None = "logo.png",
        description: str = "") -> dict:
    return {"Id": org_id, "Name": name, "ProfilePicture": picture,
            "Description": description, "instagram": instagram}


class MatchingTests(unittest.TestCase):
    def logos(self, orgs, wanted):
        with patch.object(club_avatars, "fetch", engage(orgs)), patch.object(club_avatars.time, "sleep"):
            return club_avatars.engage_logos(None, wanted)

    def test_orgs_match_by_their_own_instagram_link(self):
        found = self.logos([
            org(1, "Association for Computing Machinery (ACM) at UCR",
                "https://www.instagram.com/acm_ucr/", "acm.png"),
            org(2, "Chinese Student Association", "",
                description='<a href="https://instagram.com/ucrcsa">Follow us</a>', picture="csa.png"),
            org(3, "Unrostered Club", "https://www.instagram.com/someone_else"),
            org(4, "No Logo Club", "https://www.instagram.com/nologo_ucr", picture=None),
        ], {"acm_ucr": "ACM at UCR", "ucrcsa": "Chinese Student Association at UCR",
            "nologo_ucr": "No Logo Club at UCR"})
        self.assertEqual(found, {"acm_ucr": "acm.png", "ucrcsa": "csa.png"})

    def test_shared_office_feed_takes_only_its_namesakes_logo(self):
        orgs = [org(1, "Commuter Programs at UCR", "https://www.instagram.com/ucrstudentlife", "commuter.png"),
                org(2, "Student Life", "https://www.instagram.com/ucrstudentlife", "life.png")]
        self.assertEqual(self.logos(orgs, {"ucrstudentlife": "UCR Student Life"}),
                         {"ucrstudentlife": "life.png"})

    def test_ambiguous_feed_without_a_namesake_gets_no_logo(self):
        orgs = [org(1, "Commuter Programs at UCR", "https://www.instagram.com/ucrstudentlife", "commuter.png"),
                org(2, "Transfer Programs", "https://www.instagram.com/ucrstudentlife", "transfer.png")]
        self.assertEqual(self.logos(orgs, {"ucrstudentlife": "UCR Student Life"}), {})

    def test_logo_less_namesake_does_not_hand_its_feed_to_another_org(self):
        orgs = [org(1, "Commuter Programs at UCR", "https://www.instagram.com/ucrstudentlife", "commuter.png"),
                org(2, "Student Life", "https://www.instagram.com/ucrstudentlife", picture=None)]
        self.assertEqual(self.logos(orgs, {"ucrstudentlife": "UCR Student Life"}), {})

    def test_instagram_handle_ignores_post_links(self):
        self.assertIsNone(club_avatars.instagram_handle("https://www.instagram.com/p/C123/"))
        self.assertEqual(club_avatars.instagram_handle("see instagram.com/ACM_UCR."), "acm_ucr")

    def test_same_org_ignores_the_campus_suffix(self):
        self.assertTrue(club_avatars.same_org("Hong Kong Students Association @UCR",
                                              "Hong Kong Students Association at UCR"))
        self.assertTrue(club_avatars.same_org("Student Life", "UCR Student Life"))
        self.assertFalse(club_avatars.same_org("Commuter Programs at UCR", "UCR Student Life"))


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
        with patch("apify_posts.ApifyClient", return_value=client):
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

    def test_wide_wordmark_is_shrunk_inside_the_circle(self):
        wordmark = Image.new("RGB", (600, 200), "white")
        ImageDraw.Draw(wordmark).rectangle((0, 60, 599, 140), fill="black")
        result = self.avatar(wordmark)
        # Letterboxed, not center-cropped: both ends of the mark survive...
        self.assertLess(sum(result.getpixel((14, 64))), 200)
        self.assertLess(sum(result.getpixel((113, 64))), 200)
        # ...and nothing reaches the corners a circular crop removes.
        for corner in [(8, 8), (119, 8), (8, 119), (119, 119), (4, 64), (123, 64)]:
            self.assertGreater(sum(result.getpixel(corner)), 700, corner)

    def test_off_center_logo_is_recentered(self):
        logo = Image.new("RGB", (400, 400), "white")
        ImageDraw.Draw(logo).ellipse((0, 0, 159, 159), fill="navy")
        result = self.avatar(logo)
        self.assertLess(sum(result.getpixel((64, 64))), 300)

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
