"""Post extraction caching and the single-event publication boundary."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import assessed_events as publication
import content_assessment as semantic
import extract_posts as posts


def record(caption="Study Jam on September 15, 2026, 3-5 PM", slides=2, media_id="700"):
    return {
        "media_id": media_id, "handle": "acm.ucr", "owner_username": "acm.ucr",
        "shortcode": "CStudy", "permalink": "https://www.instagram.com/p/CStudy/",
        "posted_at": "2026-09-10T17:00:00+00:00", "typename": "GraphSidecar",
        "caption": caption, "caption_mentions": [], "has_video": False,
        "media": [
            {"index": index, "is_video": False,
             "image_url": f"https://cdn.example/v/t51/{media_id}_{index}_n.jpg?oh=sig{index}&oe=1",
             "media_key": f"{media_id}_{index}_n"}
            for index in range(slides)
        ],
        "fetched_at": "2026-09-11T12:00:00+00:00",
    }


def evidence(field, quote):
    return [{"field": field, "quote": quote}]


def post_decision(source, *, occurrences=None, field="slide_1_ocr", kind="activity"):
    quote = source["texts"][field]
    cited = evidence(field, quote)
    if occurrences is None:
        occurrences = [{
            "title": "Study Jam", "starts_at": "2026-09-15T15:00:00-07:00",
            "ends_at": "2026-09-15T17:00:00-07:00", "all_day": False, "location": "",
            "activity_evidence": cited, "date_evidence": cited,
        }]
    return {"kind": kind, "date_role": "occurrence", "reason": "Post announces a study jam.",
            "activity_evidence": cited, "date_evidence": cited,
            "use_source_occurrences": False, "schedule": None, "occurrences": occurrences}


class PostExtractionTests(unittest.TestCase):
    """OCR is paid for once per image and never repeated without cause."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = patch.object(posts, "POST_EXTRACTED_DIR", Path(directory.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        for name, value in (("_load_remote_cache", None), ("_write_remote_cache", None),
                            ("_upload_flyer", "https://storage.example/flyer.jpg")):
            attr = patch.object(posts, name, Mock(return_value=value))
            setattr(self, name.strip("_"), attr.start())
            self.addCleanup(attr.stop)
        self.download = patch.object(posts, "_download_image", Mock(return_value=b"bytes"))
        self.download.start()
        self.addCleanup(self.download.stop)
        self.qr = patch.object(posts, "qr_rsvp_urls", Mock(return_value=[]))
        self.qr.start()
        self.addCleanup(self.qr.stop)

    def ocr(self, *texts):
        return patch.object(posts, "_vision_ocr", Mock(side_effect=list(texts) * 20))

    def test_an_unchanged_rerun_makes_no_ocr_calls_at_all(self):
        item = record()
        with self.ocr("", "Study Jam September 15") as vision:
            first = posts.process_post(item)
            self.assertEqual("ok", first["status"])
            self.assertEqual(2, vision.call_count)
            second = posts.process_post(item)
            self.assertEqual(2, vision.call_count)
        self.assertEqual(first, second)

    def test_a_refreshed_cdn_url_alone_reuses_every_cache(self):
        item = record()
        with self.ocr("", "Study Jam September 15") as vision:
            posts.process_post(item)
            resigned = copy.deepcopy(item)
            for slide in resigned["media"]:
                slide["image_url"] = slide["image_url"].replace("oh=sig", "oh=fresh")
            posts.process_post(resigned)
            self.assertEqual(2, vision.call_count)

    def test_a_caption_edit_reuses_image_ocr_and_only_reassesses(self):
        item = record()
        with self.ocr("", "Study Jam September 15") as vision:
            first = posts.process_post(item)
            edited = record(caption="Study Jam moved to Tuesday")
            second = posts.process_post(edited)
            # No image changed, so no image was read again...
            self.assertEqual(2, vision.call_count)
        # ...but the assessment inputs did change, so the decision expires.
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])
        self.assertEqual([entry["ocr_text"] for entry in posts.ordered_slides(first)],
                         [entry["ocr_text"] for entry in posts.ordered_slides(second)])

    def test_a_replaced_slide_reads_only_the_slide_that_changed(self):
        item = record()
        with self.ocr("", "Study Jam September 15") as vision:
            posts.process_post(item)
            swapped = copy.deepcopy(item)
            swapped["media"][1]["media_key"] = "700_1b_n"
            swapped["media"][1]["image_url"] = "https://cdn.example/v/t51/700_1b_n.jpg?oh=x"
            posts.process_post(swapped)
            self.assertEqual(3, vision.call_count)

    def test_a_partial_media_failure_is_retryable_and_keeps_paid_slides(self):
        item = record(slides=3)
        calls = {"n": 0}

        def flaky(url):
            calls["n"] += 1
            if calls["n"] == 3:
                raise RuntimeError("connection reset")
            return b"bytes"

        with patch.object(posts, "_download_image", side_effect=flaky), \
             self.ocr("Slide one", "Slide two") as vision:
            failed = posts.process_post(item)
        self.assertEqual("error", failed["status"])
        self.assertEqual("download", failed["result"]["stage"])
        self.assertEqual(2, vision.call_count)
        # The retry re-reads only the slide that actually failed.
        with self.ocr("Slide three") as vision:
            repaired = posts.process_post(item)
        self.assertEqual("ok", repaired["status"])
        self.assertEqual(1, vision.call_count)
        self.assertEqual(["Slide one", "Slide two", "Slide three"],
                         [entry["ocr_text"] for entry in posts.ordered_slides(repaired)])

    def test_an_ocr_failure_never_becomes_a_negative_decision(self):
        with patch.object(posts, "_vision_ocr", side_effect=RuntimeError("vision 503")):
            result = posts.process_post(record(slides=1))
        self.assertEqual("error", result["status"])
        self.assertNotIn(result["status"], posts.TERMINAL_STATUSES)

    def test_a_video_cover_frame_is_read_like_any_other_slide(self):
        item = record(slides=1)
        item["media"] = [{"index": 0, "is_video": True,
                          "image_url": "https://cdn.example/v/t51/700_0_n.jpg?oh=sig",
                          "media_key": "700_0_n"}]
        item["has_video"] = True
        with self.ocr("Study Jam September 15, 2026, 3-5 PM") as vision:
            result = posts.process_post(item)
        self.assertEqual("ok", result["status"])
        vision.assert_called_once()
        self.assertEqual("Study Jam September 15, 2026, 3-5 PM",
                         result["images"][0]["ocr_text"])

    def test_a_mixed_carousel_reads_image_slides_and_video_covers(self):
        item = record(slides=2)
        item["media"][1]["is_video"] = True
        item["has_video"] = True
        with self.ocr("", "Study Jam September 15") as vision:
            result = posts.process_post(item)
        self.assertEqual("ok", result["status"])
        self.assertEqual(2, vision.call_count)

    def test_a_cached_video_skip_is_reopened_once_covers_are_readable(self):
        item = record(slides=1)
        item["media"] = [{"index": 0, "is_video": True,
                          "image_url": "https://cdn.example/cover.jpg",
                          "media_key": "700_0_n"}]
        stale = {"status": "unsupported_media", "fingerprint": posts.fingerprint(item),
                 "result": {"reason": "This version does not read video posts"}}
        with patch.object(posts, "_load_remote_cache", return_value=None), \
             self.ocr("Study Jam September 15") as vision:
            path = posts._cache_path(item["media_id"])
            path.write_text(json.dumps(stale))
            result = posts.process_post(item)
        self.assertEqual("ok", result["status"])
        vision.assert_called_once()

    def test_an_over_long_carousel_is_skipped_rather_than_truncated(self):
        item = record(slides=posts.MAX_SLIDES + 1)
        with self.ocr("Slide text") as vision:
            result = posts.process_post(item)
        self.assertEqual("unsupported_media", result["status"])
        self.assertIn("more than", result["result"]["reason"])
        vision.assert_not_called()

    def test_a_slide_recorded_without_a_url_is_retryable_not_partial(self):
        item = record(slides=3)
        item["media"][1]["image_url"] = None
        with self.ocr("Slide one") as vision:
            result = posts.process_post(item)
        # One slide read, then a stop — never a decision made on two of three.
        self.assertEqual("error", result["status"])
        self.assertEqual(1, vision.call_count)

    def test_a_post_with_no_text_anywhere_is_terminal(self):
        with self.ocr("", ""):
            result = posts.process_post(record(caption=""))
        self.assertEqual("no_text", result["status"])

    def test_a_caption_only_post_with_blank_images_still_extracts(self):
        with self.ocr("", ""):
            result = posts.process_post(record(caption="Study Jam Sept 15, 3-5 PM"))
        self.assertEqual("ok", result["status"])

    def test_a_stale_local_cache_still_reuses_durable_slide_work(self):
        # This machine never read the post, but another run did. The caption
        # has since been edited, so no cached decision applies — the images
        # are unchanged, so none of them may be read again.
        item = record()
        durable = {"status": "ok", "media_id": "700", "handle": "acm.ucr",
                   "fingerprint": "an-older-caption", "extraction_version": posts.EXTRACTION_VERSION,
                   "images": [{"media_key": f"700_{index}_n", "index": index,
                               "ocr_text": text, "qr_urls": [],
                               "qr_scan_version": posts.QR_SCAN_VERSION}
                              for index, text in enumerate(["", "Study Jam September 15"])]}
        with patch.object(posts, "_load_remote_cache", return_value=durable), \
             self.ocr("should not run") as vision:
            result = posts.process_post(item)
        vision.assert_not_called()
        self.assertEqual("ok", result["status"])
        self.assertEqual(posts.fingerprint(item), result["fingerprint"])
        self.assertEqual(["", "Study Jam September 15"],
                         [entry["ocr_text"] for entry in posts.ordered_slides(result)])

    def test_a_remote_cache_survives_local_cache_loss(self):
        item = record()
        with self.ocr("", "Study Jam September 15"):
            original = posts.process_post(item)
        for path in Path(posts.POST_EXTRACTED_DIR).glob("*.json"):
            path.unlink()
        with patch.object(posts, "_load_remote_cache", return_value=original), \
             self.ocr("should not run") as vision:
            recovered = posts.process_post(item)
        vision.assert_not_called()
        self.assertEqual(original["fingerprint"], recovered["fingerprint"])

    def test_a_carousel_repeating_one_image_reads_it_once(self):
        item = record(slides=2)
        for slide in item["media"]:
            slide["media_key"] = "700_0_n"
            slide["image_url"] = "https://cdn.example/v/t51/700_0_n.jpg?oh=a"
        with self.ocr("Study Jam September 15") as vision:
            result = posts.process_post(item)
        self.assertEqual("ok", result["status"])
        self.assertEqual(1, vision.call_count)

    def test_only_flyer_candidates_are_stored_durably(self):
        # The lead image (a caption-only event's flyer) and any image whose
        # text could be cited — never a blank middle slide.
        with self.ocr("", "Study Jam September 15", "") as _:
            posts.process_post(record(slides=3))
        stored = [call.args[1] for call in self.upload_flyer.call_args_list]
        self.assertEqual(["700_0_n", "700_1_n"], stored)


class PostSourceTests(unittest.TestCase):
    def test_caption_and_each_slide_stay_separately_attributable(self):
        cached = {"images": [
            {"media_key": "a", "index": 0, "ocr_text": "STUDY JAM"},
            {"media_key": "b", "index": 1, "ocr_text": "September 15, 3-5 PM"},
        ]}
        source = publication.post_source(record(caption="Join us!"), cached)
        self.assertEqual("instagram:post:700", source["source_key"])
        self.assertEqual("instagram", source["origin"])
        self.assertEqual({"caption": "Join us!", "slide_1_ocr": "STUDY JAM",
                          "slide_2_ocr": "September 15, 3-5 PM"}, source["texts"])

    def test_evidence_on_a_later_slide_validates_against_that_slide(self):
        cached = {"images": [
            {"media_key": "a", "index": 0, "ocr_text": "ACM PRESENTS"},
            {"media_key": "b", "index": 1, "ocr_text": "Study Jam September 15, 2026, 3-5 PM"},
        ]}
        source = publication.post_source(record(caption="see you there"), cached)
        result = post_decision(source, field="slide_2_ocr")
        self.assertEqual(result, semantic.validate(result, source))

    def test_a_date_quoted_from_a_slide_that_does_not_print_it_is_rejected(self):
        cached = {"images": [{"media_key": "a", "index": 0, "ocr_text": "Study Jam September 15, 2026, 3-5 PM"},
                             {"media_key": "b", "index": 1, "ocr_text": "Bring your laptop"}]}
        source = publication.post_source(record(caption=""), cached)
        result = post_decision(source, field="slide_1_ocr")
        result["occurrences"][0]["date_evidence"] = evidence("slide_2_ocr", "Bring your laptop")
        with self.assertRaises(ValueError):
            semantic.validate(result, source)


class PostPublicationTests(unittest.TestCase):
    def setUp(self):
        self.cached = {"status": "ok", "images": [
            {"media_key": "700_0_n", "index": 0, "ocr_text": "", "qr_urls": [],
             "image_url": "https://storage.example/slide0.jpg"},
            {"media_key": "700_1_n", "index": 1,
             "ocr_text": "Study Jam September 15, 2026, 3-5 PM", "qr_urls": [],
             "image_url": "https://storage.example/slide1.jpg"},
        ]}
        self.record = record(caption="Join ACM for a study jam")
        self.source = publication.post_source(self.record, self.cached)
        self.meta = {"acm.ucr": {"label": "ACM at UCR"}}

    def rows(self, result=None, **kwargs):
        result = post_decision(self.source, field="slide_2_ocr", **kwargs) if result is None else result
        payload = {"status": "complete", "result": result, "source": self.source}
        return publication.post_rows(self.record, self.cached, payload, self.meta,
                                     "2026-09-11T12:00:00+00:00")

    def test_a_supported_single_event_publishes_with_the_post_permalink(self):
        rows, known = self.rows()
        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertEqual("ig_acm.ucr_20260915T2200Z", row["id"])
        self.assertEqual("Study Jam", row["title"])
        self.assertEqual("2026-09-15T22:00:00+00:00", row["starts_at"])
        self.assertEqual("https://www.instagram.com/p/CStudy/", row["source_url"])
        self.assertEqual("student_event", row["content_kind"])
        self.assertEqual("instagram", row["source"])
        self.assertEqual("ACM at UCR", row["host"])
        self.assertIn("ig_post_700_20260915T2200Z", known)

    def test_the_flyer_is_the_first_slide_that_actually_supplied_evidence(self):
        rows, _ = self.rows()
        self.assertEqual("https://storage.example/slide1.jpg", rows[0]["image_url"])

    def test_a_caption_only_event_falls_back_to_the_lead_image(self):
        cached = {"status": "ok", "images": [
            {"media_key": "700_0_n", "index": 0, "ocr_text": "", "qr_urls": [],
             "image_url": "https://storage.example/slide0.jpg"}]}
        item = record(caption="Study Jam September 15, 2026, 3-5 PM", slides=1)
        source = publication.post_source(item, cached)
        payload = {"status": "complete", "result": post_decision(source, field="caption"),
                   "source": source}
        rows, _ = publication.post_rows(item, cached, payload, self.meta, "2026-09-11T12:00:00+00:00")
        self.assertEqual("https://storage.example/slide0.jpg", rows[0]["image_url"])

    def test_multiple_occurrences_are_skipped_with_a_reason(self):
        second = {"title": "Study Jam II", "starts_at": "2026-09-16T15:00:00-07:00",
                  "ends_at": None, "all_day": False, "location": "",
                  "activity_evidence": evidence("slide_2_ocr", self.source["texts"]["slide_2_ocr"]),
                  "date_evidence": evidence("slide_2_ocr", self.source["texts"]["slide_2_ocr"])}
        result = post_decision(self.source, field="slide_2_ocr")
        result["occurrences"].append(second)
        with self.assertLogs("pipeline.assessed_events", level="INFO") as logged:
            rows, known = self.rows(result)
        self.assertEqual([], rows)
        self.assertIn("a post publishes exactly one event", "\n".join(logged.output))

    def test_an_announcement_publishes_nothing_but_withdraws_its_support(self):
        result = post_decision(self.source, field="slide_2_ocr", kind="announcement")
        result["date_role"] = "observance"
        result["occurrences"] = []
        rows, known = self.rows(result)
        self.assertEqual([], rows)
        # Nothing is claimed, so the RPC's stored ownership is what retires it.
        self.assertEqual(set(), known)

    def test_a_failed_assessment_publishes_nothing_and_claims_nothing(self):
        rows, known = publication.post_rows(
            self.record, self.cached, {"status": "error", "error": "Vertex timeout"},
            self.meta, "2026-09-11T12:00:00+00:00")
        self.assertEqual(([], set()), (rows, known))

    def test_a_corrected_date_claims_both_the_old_and_new_identities(self):
        rows, known = self.rows()
        self.assertEqual({"ig_acm.ucr_20260915T2200Z", "ig_post_700_20260915T2200Z"}, known)
        self.assertEqual(rows[0]["id"], "ig_acm.ucr_20260915T2200Z")

    def test_a_qr_destination_is_recovered_as_the_rsvp_link(self):
        self.cached["images"][1]["qr_urls"] = ["https://lu.ma/studyjam"]
        rows, _ = self.rows()
        self.assertEqual("https://lu.ma/studyjam", rows[0]["rsvp_url"])
        self.assertTrue(rows[0]["rsvp_required"])

    def test_two_distinct_qr_destinations_stay_ambiguous(self):
        self.cached["images"][0]["qr_urls"] = ["https://lu.ma/one"]
        self.cached["images"][1]["qr_urls"] = ["https://lu.ma/two"]
        rows, _ = self.rows()
        self.assertIsNone(rows[0]["rsvp_url"])

    def test_a_caption_link_ending_a_sentence_drops_the_punctuation(self):
        self.record = record(caption="Study jam! Sign up at https://lu.ma/studyjam!")
        self.source = publication.post_source(self.record, self.cached)
        rows, _ = self.rows()
        self.assertEqual("https://lu.ma/studyjam", rows[0]["rsvp_url"])

    def test_an_instagram_destination_is_never_an_rsvp_link(self):
        self.cached["images"][1]["qr_urls"] = ["https://instagram.com/acm.ucr"]
        rows, _ = self.rows()
        self.assertIsNone(rows[0]["rsvp_url"])


class PostAndReshareIdentityTests(unittest.TestCase):
    """One event posted once and reshared by other clubs is one listing."""

    def setUp(self):
        self.cached = {"status": "ok", "images": [
            {"media_key": "700_0_n", "index": 0,
             "ocr_text": "Study Jam September 15, 2026, 3-5 PM", "qr_urls": []}]}
        self.record = record(caption="Join ACM for a study jam", slides=1)
        self.meta = {"acm.ucr": {"label": "ACM at UCR"}, "ieee.ucr": {"label": "IEEE at UCR"}}

    def post_row(self):
        source = publication.post_source(self.record, self.cached)
        payload = {"status": "complete", "result": post_decision(source, field="slide_1_ocr"),
                   "source": source}
        rows, known = publication.post_rows(self.record, self.cached, payload, self.meta,
                                            "2026-09-11T12:00:00+00:00")
        return rows[0], known

    def test_a_reshare_that_names_no_author_still_lands_on_the_post_row(self):
        # A story resharing this post without naming the author keys its event
        # on the media identity. The direct post claims that same identity, so
        # the two settle on one listing instead of two.
        row, known = self.post_row()
        import extract_stories as ig
        reshare_identity = ig._instagram_event_id("post_700", row["starts_at"])
        self.assertIn(reshare_identity, known)
        self.assertEqual(ig._instagram_event_id("acm.ucr", row["starts_at"]), row["id"])

    def test_a_reshare_story_is_not_published_as_its_own_source(self):
        story = {"id": "555", "handle": "ieee.ucr", "posted_at": "2026-09-10T18:00:00+00:00",
                 "caption": None, "permalink": "https://www.instagram.com/stories/ieee.ucr/555/",
                 "reshared_post": {"media_id": "700", "owner_username": None,
                                   "caption": "Join ACM for a study jam"}}
        original = {"id": "111", "handle": "ieee.ucr", "posted_at": "2026-09-10T18:00:00+00:00",
                    "caption": "our own flyer", "permalink": "https://www.instagram.com/stories/ieee.ucr/111/"}
        cached = {"status": "ok", "ocr_text": "Study Jam September 15, 2026, 3-5 PM"}
        with patch.object(publication, "make_update",
                          side_effect=lambda source, *a, **k: {"source_key": source["source_key"]}):
            updates = publication.story_updates(
                [(story, cached), (original, cached)], self.meta,
                "2026-09-11T12:00:00+00:00", registry={})
        self.assertEqual(["instagram:111"], [item["source_key"] for item in updates])

    def test_publishing_both_channels_teaches_reshares_the_real_author(self):
        story = {"id": "555", "handle": "ieee.ucr", "posted_at": "2026-09-10T18:00:00+00:00",
                 "caption": None, "permalink": "https://www.instagram.com/stories/ieee.ucr/555/",
                 "reshared_post": {"media_id": "700", "owner_username": None,
                                   "caption": "Join ACM for a study jam"}}
        seen: list = []
        with patch.object(publication, "load_registry", return_value={}), \
             patch.object(publication, "story_updates",
                          side_effect=lambda processed, meta, now, registry, owners: seen.append(owners) or []), \
             patch.object(publication, "post_updates", return_value=[]), \
             patch.object(publication, "_complete"):
            publication.publish_instagram([(story, {"ocr_text": ""})], [(self.record, self.cached)],
                                          self.meta, "2026-09-11T12:00:00+00:00", notify=False)
        # The direct post is the authority on who wrote it; the reshare inherits it.
        self.assertEqual({"post_700": {"acm.ucr"}}, seen[0])

    def test_unrelated_clubs_sharing_a_title_and_time_stay_separate(self):
        from event_identity import dedupe_event_rows
        common = {"title": "General Meeting", "starts_at": "2026-09-15T22:00:00+00:00",
                  "source": "instagram", "description": "", "host": ""}
        rows = dedupe_event_rows([
            {**common, "id": "ig_acm.ucr_20260915T2200Z"},
            {**common, "id": "ig_ieee.ucr_20260915T2200Z"},
        ])
        self.assertEqual(2, len(rows))

    def test_a_published_post_row_satisfies_the_publication_rpc_contract(self):
        # The shared RPC accepts only imported, publishable rows, and applies
        # admin locks and tombstones by event id. A post row must qualify the
        # same way a story row does, or it would be rejected outright.
        row, _ = self.post_row()
        self.assertTrue(row["id"].startswith("ig_"))
        self.assertIn(row["content_kind"], {"student_event", "student_deadline"})
        self.assertNotEqual("manual", row["source"])

    def test_a_post_row_produces_a_stable_notification_key(self):
        from discord_notify import free_food_notification_key
        row, _ = self.post_row()
        rekeyed = {**row, "id": row["id"] + "_moved"}
        self.assertEqual(free_food_notification_key(row), free_food_notification_key(rekeyed))


class PostAssessmentCostTests(unittest.TestCase):
    """The daily run's cost is what it reads and asks, not what it walks."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = patch.object(publication, "CACHE_DIR", Path(directory.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        flyer = "Study Jam September 15, 2026 3 PM-5 PM"
        self.cached = {"status": "ok", "images": [
            {"media_key": "700_0_n", "index": 0, "ocr_text": flyer, "qr_urls": []}]}
        self.record = record(caption="Join ACM for a study jam", slides=1)

    def test_an_unchanged_rerun_asks_the_model_nothing(self):
        source = publication.post_source(self.record, self.cached)
        decided = post_decision(source, field="slide_1_ocr")
        with patch.object(semantic, "assess", return_value=decided) as model:
            stats: dict = {}
            publication.post_updates([(self.record, self.cached)], {},
                                     "2026-09-11T12:00:00+00:00", registry={}, stats=stats)
            self.assertEqual({"model_calls": 1}, stats)
            rerun: dict = {}
            publication.post_updates([(self.record, self.cached)], {},
                                     "2026-09-11T13:00:00+00:00", registry={}, stats=rerun)
            self.assertEqual({"assessment_cache_hits": 1}, rerun)
            self.assertEqual(1, model.call_count)

    def test_a_caption_edit_expires_the_decision(self):
        source = publication.post_source(self.record, self.cached)
        with patch.object(semantic, "assess", return_value=post_decision(source, field="slide_1_ocr")) as model:
            publication.post_updates([(self.record, self.cached)], {},
                                     "2026-09-11T12:00:00+00:00", registry={})
            edited = record(caption="Study jam is cancelled", slides=1)
            publication.post_updates([(edited, self.cached)], {},
                                     "2026-09-11T13:00:00+00:00", registry={})
        self.assertEqual(2, model.call_count)


class PilotDryRunTests(unittest.TestCase):
    def test_a_dry_run_assesses_and_maps_without_publishing_or_notifying(self):
        flyer = "Study Jam September 15, 2026 3 PM-5 PM"
        item = record(caption="Join ACM for a study jam", slides=1)
        cached = {"status": "ok", "images": [
            {"media_key": "700_0_n", "index": 0, "ocr_text": flyer, "qr_urls": []}]}
        source = publication.post_source(item, cached)
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "pilot.json"
            with patch.object(posts, "extract_all", return_value=([(item, cached)], posts.Stats())), \
                 patch.object(publication, "load_registry", return_value={}), \
                 patch.object(publication, "CACHE_DIR", Path(directory) / "assessments"), \
                 patch.object(semantic, "assess",
                              return_value=post_decision(source, field="slide_1_ocr")), \
                 patch("extract_stories._load_account_meta", return_value={}), \
                 patch.object(publication, "publish_posts") as publish, \
                 patch.object(publication, "publish") as rpc:
                posts.main(publish=False, report=report)
            written = json.loads(report.read_text())
        publish.assert_not_called()
        rpc.assert_not_called()
        self.assertEqual(["instagram:post:700"], [item["source_key"] for item in written])
        # The report carries the evidence next to the row it produced.
        self.assertEqual("Study Jam", written[0]["rows"][0]["title"])
        self.assertEqual(flyer, written[0]["assessment"]["result"]["date_evidence"][0]["quote"])


class PostUpdateBatchTests(unittest.TestCase):
    def test_only_usable_and_retryable_extractions_produce_updates(self):
        cached_ok = {"status": "ok", "images": [
            {"media_key": "a", "index": 0, "ocr_text": "Study Jam September 15, 2026, 3-5 PM"}]}
        processed = [
            (record(media_id="1"), cached_ok),
            (record(media_id="2"), {"status": "error", "images": []}),
            (record(media_id="3"), {"status": "unsupported_media", "images": []}),
            (record(media_id="4"), {"status": "no_text", "images": []}),
        ]
        with patch.object(publication, "make_update",
                          side_effect=lambda source, *a, **k: {"source_key": source["source_key"]}):
            updates = publication.post_updates(processed, {}, "2026-09-11T12:00:00+00:00", registry={})
        self.assertEqual(["instagram:post:1", "instagram:post:2"],
                         [item["source_key"] for item in updates])
        self.assertEqual("error", updates[1]["assessment"]["status"])

    def test_posts_are_published_after_stories_so_the_post_link_wins(self):
        with patch.object(publication, "load_registry", return_value={}), \
             patch.object(publication, "story_updates", return_value=[{"source_key": "instagram:1"}]), \
             patch.object(publication, "post_updates", return_value=[{"source_key": "instagram:post:700"}]), \
             patch.object(publication, "_complete") as complete:
            publication.publish_instagram([], [], {}, "2026-09-11T12:00:00+00:00", notify=False)
        ordered = [item["source_key"] for item in complete.call_args.args[0]]
        self.assertEqual(["instagram:1", "instagram:post:700"], ordered)
        self.assertFalse(complete.call_args.kwargs["notify"])


if __name__ == "__main__":
    unittest.main()
