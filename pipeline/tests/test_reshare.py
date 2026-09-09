"""Coverage for reshared-post detection and the event identity it drives."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import extract_stories as extract
import scrape
from reshare import reshared_origin_handle, strip_byline

# The Sept 26 premiere three UCR accounts reshared on the same evening. Each
# copy renders a different slice of the co-author list, so the LLM read a
# different "title" off each one.
UCR_DANCE_OCR = (
    "'DE\n"
    "bluejadeandjoel and ucr_dance\n"
    "bluejadeandjoel Joel Mejia Smith: it's been a while...\n"
    "Saturday, September 26th, 2026..."
)
UCR_ARTS_OCR = (
    "bluejadeandjoel, ucrarts, ucrperforms and\n"
    "ucr_dance\n"
    "bluejadeandjoel Joel Mejia Smith: it's been a while...\n"
    "Saturday, September 26th, 2026..."
)
# A real flyer whose logo text ("swe") is handle-shaped and whose body starts
# with the same letters in a different case.
SWE_FLYER_OCR = (
    "@nsbe_ucr\nSWE X NSBE\nSTUDY JAM\nswe\nSWE at UCR\n"
    "General Meeting\n#5\nWCH 205/206\n5/29/2026\n2-3 PM"
)


class OriginHandleTests(unittest.TestCase):
    def test_co_author_byline_names_the_original_author(self) -> None:
        self.assertEqual(
            "bluejadeandjoel",
            reshared_origin_handle(UCR_DANCE_OCR, "ucr_dance"),
        )

    def test_byline_wrapped_across_lines_is_rejoined(self) -> None:
        self.assertEqual(
            "bluejadeandjoel",
            reshared_origin_handle(UCR_ARTS_OCR, "ucrarts"),
        )

    def test_flyer_logo_text_is_not_a_byline(self) -> None:
        self.assertIsNone(reshared_origin_handle(SWE_FLYER_OCR, "swe.ucr"))

    def test_flyer_prose_that_reads_like_handles_is_rejected(self) -> None:
        for text in ("pizza and snacks.", "donations and cannot", "creation and preservation"):
            with self.subTest(text=text):
                self.assertIsNone(reshared_origin_handle(text, "asucr", {"asucr"}))

    def test_lone_handle_needs_a_caption_attributed_to_it(self) -> None:
        self.assertIsNone(reshared_origin_handle("thewellucr\nFinals Week", "ucrlibrary"))
        self.assertEqual(
            "thewellucr",
            reshared_origin_handle(
                "thewellucr\nFinals Week\nthewellucr Finals week getting a little ruff?",
                "ucrlibrary",
            ),
        )

    def test_roster_membership_anchors_a_byline_the_viewer_is_absent_from(self) -> None:
        ocr = "ucriversideofficial and ucrstudentaffairs\nucriversideofficial Same, Scotty."
        self.assertIsNone(reshared_origin_handle(ocr, "ucrchass"))
        self.assertEqual(
            "ucriversideofficial",
            reshared_origin_handle(ocr, "ucrchass", {"ucriversideofficial"}),
        )


class StripBylineTests(unittest.TestCase):
    def test_title_that_is_only_a_byline_becomes_empty(self) -> None:
        self.assertEqual(
            "", strip_byline("bluejadeandjoel and ucr_dance", UCR_DANCE_OCR, "ucr_dance")
        )
        self.assertEqual("", strip_byline("bluejadeandjoel", UCR_ARTS_OCR, "ucrarts"))

    def test_byline_prefix_is_trimmed_off_a_real_title(self) -> None:
        ocr = "bluejadeandjoel, ucrperforms and ucr_dance\nbluejadeandjoel hopefully not my last"
        self.assertEqual(
            "hopefully not my last (2026) - world premiere",
            strip_byline(
                "bluejadeandjoel hopefully not my last (2026) - world premiere",
                ocr,
                "ucrperforms",
            ),
        )

    def test_ordinary_titles_survive_untouched(self) -> None:
        self.assertEqual(
            "Drag District", strip_byline("Drag District", UCR_DANCE_OCR, "ucr_dance")
        )
        # The flyer's own logo text is not a byline, so nothing is stripped.
        self.assertEqual(
            "SWE X NSBE STUDY JAM",
            strip_byline("SWE X NSBE STUDY JAM", SWE_FLYER_OCR, "swe.ucr"),
        )


class ReshareIdentityTests(unittest.TestCase):
    """Two clubs resharing one post must land on one event."""

    def _row(self, handle: str, ocr: str, title: str, **raw_extra):
        raw = {
            "id": f"story_{handle}",
            "handle": handle,
            "posted_at": "2026-09-08T21:47:57Z",
            "permalink": f"https://www.instagram.com/stories/{handle}/1/",
            **raw_extra,
        }
        cached = {
            "status": "ok",
            "ocr_text": ocr,
            "result": {
                "is_event": True,
                "title": title,
                "description": "Joel Mejia Smith: it's been a while... Saturday, September 26th, 2026",
                "starts_at": "2026-09-26T00:00:00-07:00",
                "ends_at": None,
                "location": "UCR",
                "category": "arts",
                "tags": [],
                "is_free": False,
                "rsvp_required": False,
                "rsvp_url": None,
            },
        }
        return extract._to_event_row(
            raw, cached, {"label": handle}, "2026-09-09T00:00:00+00:00",
            {"ucr_dance", "ucrarts"},
        )

    def test_reshares_from_two_clubs_collapse_onto_the_author(self) -> None:
        dance, dance_retired = self._row(
            "ucr_dance", UCR_DANCE_OCR, "bluejadeandjoel and ucr_dance"
        )
        arts, arts_retired = self._row("ucrarts", UCR_ARTS_OCR, "bluejadeandjoel")

        self.assertEqual("ig_bluejadeandjoel_20260926T0700Z", dance["id"])
        self.assertEqual(dance["id"], arts["id"])
        # One event survives; which club's copy represents it is a scoring
        # detail, but both are the same event and only one may be published.
        deduped = extract.dedupe_event_rows([dance, arts])
        self.assertEqual(1, len(deduped))
        self.assertEqual("ig_bluejadeandjoel_20260926T0700Z", deduped[0]["id"])
        # The rows these replaced are retired so the old duplicates get deleted.
        self.assertIn("ig_ucr_dance_20260926T0700Z", dance_retired)
        self.assertIn("ig_ucrarts_20260926T0700Z", arts_retired)

    def test_byline_never_reaches_the_public_title(self) -> None:
        dance, _ = self._row("ucr_dance", UCR_DANCE_OCR, "bluejadeandjoel and ucr_dance")
        self.assertEqual("Joel Mejia Smith: it's been a while", dance["title"])

    def test_attached_post_owner_wins_over_the_ocr_byline(self) -> None:
        row, _ = self._row(
            "ucr_dance",
            UCR_DANCE_OCR,
            "bluejadeandjoel and ucr_dance",
            reshared_post={"owner_username": "Bluejadeandjoel", "media_id": "42"},
        )
        self.assertEqual("ig_bluejadeandjoel_20260926T0700Z", row["id"])

    def test_an_original_flyer_keeps_its_own_account_identity(self) -> None:
        row, _ = self._row("swe.ucr", SWE_FLYER_OCR, "SWE X NSBE STUDY JAM")
        self.assertEqual("ig_swe.ucr_20260926T0700Z", row["id"])

    def test_admin_delete_survives_the_re_key(self) -> None:
        retired = {"ig_bluejadeandjoel_20260926T0700Z": {"ig_ucrarts_20260926T0700Z"}}
        self.assertEqual(
            {"ig_ucrarts_20260926T0700Z", "ig_bluejadeandjoel_20260926T0700Z"},
            extract._inherit_tombstones({"ig_ucrarts_20260926T0700Z"}, retired),
        )


class ReshareCaptureTests(unittest.TestCase):
    """The scraper reads the attached post out of the private story payload."""

    class _Item:
        mediaid = 1
        def __init__(self, struct):
            self._iphone_struct = struct

    def test_attached_post_is_read_from_a_known_key(self) -> None:
        item = self._Item(
            {
                "story_feed_media": [
                    {
                        "media_id": "3981900000000000000",
                        "code": "DAbCdEf",
                        "user": {"username": "bluejadeandjoel"},
                        "caption": {"text": "it's been a while... Saturday, September 26th, 2026"},
                    }
                ]
            }
        )
        post = scrape._reshared_post(item)
        self.assertEqual("bluejadeandjoel", post["owner_username"])
        self.assertEqual("3981900000000000000", post["media_id"])
        self.assertEqual("DAbCdEf", post["shortcode"])
        self.assertIn("September 26th", post["caption"])

    def test_a_story_with_no_attachment_reports_none(self) -> None:
        self.assertIsNone(scrape._reshared_post(self._Item({"story_link_stickers": []})))
        self.assertIsNone(scrape._reshared_post(self._Item("not-a-dict")))


if __name__ == "__main__":
    unittest.main()
