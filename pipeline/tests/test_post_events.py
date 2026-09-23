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
import post_archive


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
            self.assertEqual(1, vision.call_count)
            second = posts.process_post(item)
            self.assertEqual(1, vision.call_count)
        self.assertEqual(first, second)

    def test_fresh_flyer_uses_ocr_bytes_without_another_download(self):
        item = record()
        with patch.object(posts, "_download_image", return_value=b"same image") as download, self.ocr(""):
            extracted = posts.process_post(item)
        download.assert_called_once_with(item["media"][0]["image_url"])
        self.upload_flyer.assert_called_once_with(item, item["media"][0]["media_key"], b"same image")
        self.assertEqual("https://storage.example/flyer.jpg", extracted["images"][0]["image_url"])

    def test_failed_flyer_upload_recovers_without_repeating_ocr_or_qr(self):
        for cache in ("local", "remote", "edited_caption"):
            with self.subTest(cache=cache):
                posts._cache_path("700").unlink(missing_ok=True)
                item = record()
                self.upload_flyer.reset_mock(side_effect=True)
                self.upload_flyer.side_effect = [None, "https://storage.example/recovered.jpg"]
                with self.ocr("") as vision, \
                     patch.object(posts, "qr_rsvp_urls", return_value=[]) as qr:
                    first = posts.process_post(item)
                    self.assertEqual("ok", first["status"])
                    self.assertFalse(first["images"][0].get("image_url"))
                    if cache == "remote":
                        posts._cache_path("700").unlink()
                    if cache == "edited_caption":
                        item["caption"] += " Bring a friend!"
                    item["media"][0]["image_url"] = "https://cdn.example/refreshed.jpg"
                    with patch.object(posts, "_load_remote_cache", return_value=first), \
                         patch.object(posts, "_download_image", return_value=b"retry") as download:
                        recovered = posts.process_post(item)
                        again = posts.process_post(item)
                    download.assert_called_once_with("https://cdn.example/refreshed.jpg")
                    vision.assert_called_once()
                    qr.assert_called_once()
                self.assertEqual(2, self.upload_flyer.call_count)
                self.assertEqual("https://storage.example/recovered.jpg", recovered["images"][0]["image_url"])
                self.assertEqual(recovered, again)
                self.assertEqual(recovered, posts._read_json(posts._cache_path("700")))
                self.write_remote_cache.assert_called_with(recovered)
                source = publication.post_source(item, recovered)
                payload = {"status": "complete", "source": source,
                           "result": post_decision(source, field="caption")}
                rows, _ = publication.post_rows(item, recovered, payload, {}, "2026-09-11T12:00:00Z")
                self.assertEqual("https://storage.example/recovered.jpg", rows[0]["image_url"])

    def test_flyer_recovery_failures_preserve_ocr_and_remain_retryable(self):
        item = record()
        self.upload_flyer.side_effect = [None, None, "https://storage.example/recovered.jpg"]
        with self.ocr("Study Jam") as vision:
            original = posts.process_post(item)
            with patch.object(posts, "_download_image", side_effect=RuntimeError("timeout")):
                self.assertEqual(original, posts.process_post(item))
            self.assertEqual(original, posts.process_post(item))
            recovered = posts.process_post(item)
        vision.assert_called_once()
        self.assertEqual(3, self.upload_flyer.call_count)
        self.assertEqual("https://storage.example/recovered.jpg", recovered["images"][0]["image_url"])

    def test_an_expired_flyer_url_is_not_requested_again_until_it_is_refreshed(self):
        item = record()
        self.upload_flyer.side_effect = [None, "https://storage.example/recovered.jpg"]
        with self.ocr("Study Jam") as vision:
            original = posts.process_post(item)
            with patch.object(posts, "_download_image", side_effect=posts.ImageExpired("HTTP 403")) as expired:
                failed = posts.process_post(item)
                self.assertEqual(failed, posts.process_post(item))
            expired.assert_called_once()
            self.assertEqual(original["images"][0]["ocr_text"], failed["images"][0]["ocr_text"])
            self.assertFalse(failed["images"][0].get("image_url"))
            self.assertEqual(failed, posts._read_json(posts._cache_path("700")))
            item["media"][0]["image_url"] = "https://cdn.example/refreshed.jpg"
            recovered = posts.process_post(item)
        vision.assert_called_once()
        self.assertEqual("https://storage.example/recovered.jpg", recovered["images"][0]["image_url"])
        self.assertNotIn("flyer_expired_url", recovered["images"][0])

    def test_cached_only_does_not_attempt_missing_flyer_recovery(self):
        item = record()
        self.upload_flyer.return_value = None
        with self.ocr("Study Jam"):
            original = posts.process_post(item)
        self.upload_flyer.reset_mock()
        with patch.object(posts, "_download_image") as download, self.ocr("unused") as vision:
            self.assertEqual(original, posts.process_post(item, cached_only=True))
            item["caption"] += " Bring a friend!"
            self.assertEqual("ok", posts.process_post(item, cached_only=True)["status"])
        download.assert_not_called()
        vision.assert_not_called()
        self.upload_flyer.assert_not_called()

    def test_cached_only_extraction_leaves_unread_posts_pending_without_requests(self):
        with patch.object(posts, "_download_image") as download, self.ocr("unused") as vision:
            result = posts.process_post(record(), cached_only=True)
        self.assertEqual("pending", result["status"])
        download.assert_not_called()
        vision.assert_not_called()
        self.assertFalse(posts._cache_path("700").exists())

    def test_extraction_continues_past_an_isolated_failure(self):
        records = [record(media_id=str(n)) for n in range(3)]
        with patch.object(posts, "ensure_post_dirs"), patch.object(posts, "hydrate_local_posts"), \
             patch.object(posts, "iter_local_posts", return_value=iter(records)), \
             patch.object(posts, "process_post", side_effect=[
                 {"status": "ok"}, {"status": "error", "result": {"error": "URL expired"}},
                 {"status": "ok"}]):
            processed, stats = posts.extract_all({"acm.ucr"}, archive=posts.ArchiveIndex())
        self.assertEqual(["0", "1", "2"], [row[0]["media_id"] for row in processed])
        self.assertEqual(1, stats["errors"])
        self.assertEqual("1", stats["first_error"]["media_id"])
        self.assertNotIn("stopped_at", stats)

    def test_extraction_stops_when_failures_run_together_and_returns_the_completed_prefix(self):
        limit = posts.MAX_CONSECUTIVE_FAILURES
        records = [record(media_id=str(n)) for n in range(limit + 2)]
        failure = {"status": "error", "result": {"error": "OCR timeout"}}
        with patch.object(posts, "ensure_post_dirs"), patch.object(posts, "hydrate_local_posts"), \
             patch.object(posts, "iter_local_posts", return_value=iter(records)), \
             patch.object(posts, "process_post", side_effect=[{"status": "ok"}] + [failure] * limit
                          + [AssertionError("Must stop after the failures")]) as process:
            processed, stats = posts.extract_all({"acm.ucr"}, archive=posts.ArchiveIndex())
        self.assertEqual(limit + 1, process.call_count)
        self.assertEqual(str(limit), stats["stopped_at"]["media_id"])

    def test_expired_images_do_not_block_later_posts_on_repeated_runs(self):
        records = [record(media_id=str(n), slides=1) for n in range(4)]

        def download(url):
            if "/3_" in url:
                return b"image"
            raise posts.ImageExpired("image URL returned HTTP 403")

        with patch.object(posts, "ensure_post_dirs"), patch.object(posts, "hydrate_local_posts"), \
             patch.object(posts, "iter_local_posts", side_effect=lambda *_: iter(records)), \
             patch.object(posts, "_download_image", side_effect=download), self.ocr("Study Jam") as vision:
            for _ in range(2):
                processed, stats = posts.extract_all({"acm.ucr"}, archive=posts.ArchiveIndex())
                self.assertEqual(["0", "1", "2", "3"], [raw["media_id"] for raw, _ in processed])
                self.assertEqual(["error", "error", "error", "ok"], [cached["status"] for _, cached in processed])
                self.assertEqual(3, stats["errors"])
                self.assertNotIn("stopped_at", stats)
            self.assertEqual(1, vision.call_count)

    def test_expiry_subclasses_persist_the_same_streak_policy(self):
        class ExpiredSignedUrl(posts.ImageExpired):
            pass

        records = [record(media_id=str(n)) for n in range(4)]
        with patch.object(posts, "ensure_post_dirs"), patch.object(posts, "hydrate_local_posts"), \
             patch.object(posts, "iter_local_posts", return_value=iter(records)), \
             patch.object(posts, "_download_image", side_effect=ExpiredSignedUrl("HTTP 403")):
            processed, stats = posts.extract_all({"acm.ucr"}, archive=posts.ArchiveIndex())
        self.assertEqual(4, len(processed))
        self.assertNotIn("stopped_at", stats)
        for raw, cached in processed:
            self.assertIs(False, cached["result"]["counts_toward_streak"])
            self.assertEqual(cached, posts._read_json(posts._cache_path(raw["media_id"])))

    def test_expired_images_do_not_reset_service_failure_streak(self):
        records = [record(media_id=str(n), slides=1) for n in range(6)]
        with patch.object(posts, "ensure_post_dirs"), patch.object(posts, "hydrate_local_posts"), \
             patch.object(posts, "iter_local_posts", return_value=iter(records)), \
             patch.object(posts, "_download_image", side_effect=[
                 RuntimeError("network unavailable"), posts.ImageExpired("HTTP 403"),
                 RuntimeError("network unavailable"), posts.ImageExpired("HTTP 403"),
                 RuntimeError("network unavailable"), AssertionError("Must stop")]) as download:
            processed, stats = posts.extract_all({"acm.ucr"}, archive=posts.ArchiveIndex())
        self.assertEqual(5, download.call_count)
        self.assertEqual(5, stats["errors"])
        self.assertEqual("4", stats["stopped_at"]["media_id"])

    def test_a_refreshed_cdn_url_alone_reuses_every_cache(self):
        item = record()
        with self.ocr("", "Study Jam September 15") as vision:
            posts.process_post(item)
            resigned = copy.deepcopy(item)
            for slide in resigned["media"]:
                slide["image_url"] = slide["image_url"].replace("oh=sig", "oh=fresh")
            posts.process_post(resigned)
            self.assertEqual(1, vision.call_count)

    def test_a_caption_edit_reuses_image_ocr_and_only_reassesses(self):
        item = record()
        with self.ocr("", "Study Jam September 15") as vision:
            first = posts.process_post(item)
            edited = record(caption="Study Jam moved to Tuesday")
            second = posts.process_post(edited)
            # No image changed, so no image was read again...
            self.assertEqual(1, vision.call_count)
        # ...but the assessment inputs did change, so the decision expires.
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])
        self.assertEqual([entry["ocr_text"] for entry in posts.ordered_slides(first)],
                         [entry["ocr_text"] for entry in posts.ordered_slides(second)])

    def test_a_replaced_first_slide_is_read_again(self):
        item = record()
        with self.ocr("", "Study Jam September 15") as vision:
            posts.process_post(item)
            swapped = copy.deepcopy(item)
            swapped["media"][0]["media_key"] = "700_0b_n"
            swapped["media"][0]["image_url"] = "https://cdn.example/v/t51/700_0b_n.jpg?oh=x"
            posts.process_post(swapped)
            self.assertEqual(2, vision.call_count)

    def test_first_slide_download_failure_retries_without_reading_later_slides(self):
        item = record(slides=3)
        with patch.object(posts, "_download_image", side_effect=RuntimeError("connection reset")) as download, \
             self.ocr("should not run") as vision:
            failed = posts.process_post(item)
        self.assertEqual("error", failed["status"])
        self.assertEqual("download", failed["result"]["stage"])
        download.assert_called_once_with(item["media"][0]["image_url"])
        vision.assert_not_called()
        with self.ocr("Slide one") as vision:
            repaired = posts.process_post(item)
        self.assertEqual("ok", repaired["status"])
        vision.assert_called_once()
        self.assertEqual(["Slide one"],
                         [entry["ocr_text"] for entry in posts.ordered_slides(repaired)])

    def test_later_slide_changes_do_not_invalidate_extraction(self):
        item = record(slides=3)
        with self.ocr("First slide") as vision:
            original = posts.process_post(item)
            item["media"][1]["media_key"] = "replacement"
            item["media"].append({"index": 3, "media_key": "added"})
            self.assertEqual(original, posts.process_post(item))
        vision.assert_called_once()

    def test_only_first_slide_is_downloaded_read_and_scanned_for_qr_codes(self):
        item = record(slides=20)
        with self.ocr("First slide") as vision, \
             patch.object(posts, "_download_image", return_value=b"first") as download, \
             patch.object(posts, "qr_rsvp_urls", return_value=[]) as qr:
            result = posts.process_post(item)
        download.assert_called_once_with(item["media"][0]["image_url"])
        vision.assert_called_once_with(b"first")
        qr.assert_called_once_with(b"first")
        self.assertEqual([0], [image["index"] for image in result["images"]])

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

    def test_a_mixed_carousel_reads_only_the_first_image(self):
        item = record(slides=2)
        item["media"][1]["is_video"] = True
        item["has_video"] = True
        with self.ocr("", "Study Jam September 15") as vision:
            result = posts.process_post(item)
        self.assertEqual("ok", result["status"])
        self.assertEqual(1, vision.call_count)

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

    def test_a_legacy_long_carousel_skip_is_reopened(self):
        item = record(slides=20)
        posts._write_cache(item["media_id"], {
            "status": "unsupported_media", "fingerprint": "legacy-version-1",
            "extraction_version": 1, "images": []})
        with self.ocr("First slide") as vision:
            result = posts.process_post(item)
        self.assertEqual("ok", result["status"])
        vision.assert_called_once()

    def test_a_slide_recorded_without_a_url_is_retryable_not_partial(self):
        item = record(slides=3)
        item["media"][0]["image_url"] = None
        with self.ocr("Slide one") as vision:
            result = posts.process_post(item)
        # A missing first slide never falls back to another image.
        self.assertEqual("error", result["status"])
        vision.assert_not_called()

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
        self.assertEqual([""],
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

    def test_legacy_carousel_cache_reuses_first_slide_and_drops_later_evidence(self):
        item = record(caption="Join us")
        legacy = {"status": "ok", "fingerprint": "legacy-version-1", "extraction_version": 1,
                  "images": [{"index": n, "media_key": f"700_{n}_n", "ocr_text": text,
                              "image_url": f"https://storage.example/700_{n}_n.jpg",
                              "qr_urls": [], "qr_scan_version": posts.QR_SCAN_VERSION}
                             for n, text in enumerate(["Club announcement", "September 15 event"])]}
        for location in ("local", "remote"):
            with self.subTest(location=location):
                posts._cache_path("700").unlink(missing_ok=True)
                if location == "local":
                    posts._write_cache("700", legacy)
                with patch.object(posts, "_load_remote_cache", return_value=legacy if location == "remote" else None), \
                     patch.object(posts, "_download_image") as download, self.ocr("unused") as vision:
                    result = posts.process_post(item)
                download.assert_not_called()
                vision.assert_not_called()
                self.assertEqual(posts.EXTRACTION_VERSION, result["extraction_version"])
                self.assertEqual([0], [image["index"] for image in result["images"]])
                source = publication.post_source(item, result)
                self.assertEqual({"caption": "Join us", "slide_1_ocr": "Club announcement"}, source["texts"])

    def test_extraction_restores_missing_raw_posts_and_reuses_their_durable_ocr(self):
        item = {**record(), "posted_at": "2026-09-01T17:00:00+00:00"}
        with self.ocr("", "Study Jam September 15"):
            original = posts.process_post(item)
        posts._cache_path(item["media_id"]).unlink()
        mirrored = {"media_id": item["media_id"], "handle": item["handle"], "record": item}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(post_archive, "POSTS_DIR", Path(directory) / "posts"), \
             patch.object(post_archive, "_mirrored_media_ids", return_value={item["media_id"]}), \
             patch.object(post_archive, "_mirrored_rows", return_value=[mirrored]), \
             patch.object(posts, "ensure_post_dirs"), \
             patch.object(posts, "_load_remote_cache", return_value=original), \
             patch.object(posts, "_download_image") as download, \
             self.ocr("should not run") as vision:
            processed, stats = posts.extract_all({item["handle"]}, archive=posts.ArchiveIndex())
        self.assertEqual(1, stats["posts"])
        self.assertEqual(item["media_id"], processed[0][0]["media_id"])
        self.assertEqual(original, processed[0][1])
        download.assert_not_called()
        vision.assert_not_called()

    def test_a_carousel_repeating_one_image_reads_it_once(self):
        item = record(slides=2)
        for slide in item["media"]:
            slide["media_key"] = "700_0_n"
            slide["image_url"] = "https://cdn.example/v/t51/700_0_n.jpg?oh=a"
        with self.ocr("Study Jam September 15") as vision:
            result = posts.process_post(item)
        self.assertEqual("ok", result["status"])
        self.assertEqual(1, vision.call_count)

    def test_only_the_first_slide_is_stored_as_a_flyer(self):
        # Even a blank first slide is kept for caption-only events.
        with self.ocr("", "Study Jam September 15", "") as _:
            posts.process_post(record(slides=3))
        stored = [call.args[1] for call in self.upload_flyer.call_args_list]
        self.assertEqual(["700_0_n"], stored)


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
        self.assertEqual("ig_acm.ucr_p700", row["id"])
        self.assertEqual("Study Jam", row["title"])
        self.assertEqual("2026-09-15T22:00:00+00:00", row["starts_at"])
        self.assertEqual("https://www.instagram.com/p/CStudy/", row["source_url"])
        self.assertEqual("student_event", row["content_kind"])
        self.assertEqual("instagram", row["source"])
        self.assertEqual("ACM at UCR", row["host"])
        self.assertEqual({row["id"]}, known)

    def test_the_flyer_is_the_first_slide_that_actually_supplied_evidence(self):
        rows, _ = self.rows()
        self.assertEqual("https://storage.example/slide1.jpg", rows[0]["image_url"])

    def test_location_evidence_can_select_the_flyer(self):
        self.cached["images"][1]["ocr_text"] = "Meet us in HUB 302"
        self.record["caption"] = "Study Jam September 15, 2026, 3-5 PM"
        self.source = publication.post_source(self.record, self.cached)
        result = post_decision(self.source, field="caption")
        result["occurrences"][0].update(
            location="HUB 302", location_evidence=evidence("slide_2_ocr", "HUB 302"))
        semantic.validate(result, self.source)
        rows, _ = self.rows(result)
        self.assertEqual("https://storage.example/slide1.jpg", rows[0]["image_url"])

    def test_a_recap_is_skipped_but_claims_its_previous_identities(self):
        self.record["posted_at"] = "2026-09-17T17:00:00+00:00"
        rows, known = self.rows()
        self.assertEqual([], rows)
        self.assertEqual({"ig_acm.ucr_p700"}, known)

    def test_posted_during_the_event_or_missing_post_time_stays_publishable(self):
        for posted_at in ("2026-09-15T23:00:00Z", None):
            with self.subTest(posted_at=posted_at):
                self.record["posted_at"] = posted_at
                self.assertEqual(1, len(self.rows()[0]))

    def test_caption_only_midnight_range_is_repaired(self):
        self.record["caption"] = "Study Jam September 15, 2026, 9pm–12am"
        for slide in self.cached["images"]:
            slide["ocr_text"] = ""
        self.source = publication.post_source(self.record, self.cached)
        result = post_decision(self.source, field="caption")
        result["occurrences"][0].update(starts_at="2026-09-15T21:00:00-07:00",
                                        ends_at="2026-09-15T00:00:00-07:00")
        rows, _ = self.rows(result)
        self.assertEqual("2026-09-16T07:00:00+00:00", rows[0]["ends_at"])

    def test_flyer_supplies_category_and_free_food_separately(self):
        self.cached["images"][1]["ocr_text"] += " Resume workshop. FREE PIZZA!"
        rows, _ = self.rows()
        self.assertEqual("career", rows[0]["category"])
        self.assertTrue(rows[0]["has_free_food"])

    def test_make_update_dispatches_a_post_without_a_mapper_argument(self):
        payload = {"status": "complete", "source": self.source,
                   "result": post_decision(self.source, field="slide_2_ocr")}
        with patch.object(publication, "cached_assessment", return_value=publication.AssessmentResult(payload, False)):
            update = publication.make_update(self.source, self.record, self.cached, None,
                                             self.meta, "2026-09-11T12:00:00Z").update
        self.assertEqual("complete", update["assessment"]["status"])
        self.assertEqual(["ig_acm.ucr_p700"], [row["id"] for row in update["rows"]])
        self.assertEqual("https://storage.example/slide1.jpg", update["rows"][0]["image_url"])
        self.assertEqual(self.record["caption"], update["rows"][0]["description"])

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

    def test_publication_claims_the_author_event_identity(self):
        rows, known = self.rows()
        self.assertEqual({"ig_acm.ucr_p700"}, known)
        self.assertEqual(rows[0]["id"], "ig_acm.ucr_p700")

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

    def test_post_row_privacy_classification_and_registration_policy(self):
        self.record["caption"] = "Join us! Register at https://lu.ma/studyjam"
        self.cached["images"][1]["ocr_text"] += " Resume workshop. FREE PIZZA!"
        for handle in ("acm.ucr", "highlander_opps"):
            with self.subTest(handle=handle):
                self.record.update(handle=handle, owner_username=handle)
                self.source = publication.post_source(self.record, self.cached)
                post = self.rows()[0][0]
                self.assertEqual("career", post["category"])
                self.assertTrue(post["has_free_food"])
                self.assertTrue(post["rsvp_required"])
                self.assertEqual("https://lu.ma/studyjam", post["rsvp_url"])
                if handle == "highlander_opps":
                    self.assertEqual(("", None), (post["host"], post["host_handle"]))

    def test_assessed_fundraisers_remain_outside_public_feed(self):
        result = post_decision(self.source, field="slide_2_ocr")
        result["occurrences"][0]["title"] = "Bake sale fundraiser"
        self.assertEqual([], self.rows(result)[0])


class PostIdentityTests(unittest.TestCase):
    """Post identities respect authors and publication constraints."""

    def setUp(self):
        self.cached = {"status": "ok", "images": [
            {"media_key": "700_0_n", "index": 0,
             "ocr_text": "Study Jam September 15, 2026, 3-5 PM", "qr_urls": []}]}
        self.record = record(caption="Join ACM for a study jam", slides=1)
        self.meta = {"acm.ucr": {"label": "ACM at UCR"}, "ieee.ucr": {"label": "IEEE at UCR"}}

    def post_row(self, **occurrence_changes):
        source = publication.post_source(self.record, self.cached)
        payload = {"status": "complete", "result": post_decision(source, field="slide_1_ocr"),
                   "source": source}
        payload["result"]["occurrences"][0].update(occurrence_changes)
        rows, known = publication.post_rows(self.record, self.cached, payload, self.meta,
                                            "2026-09-11T12:00:00+00:00")
        return rows[0], known

    def test_independent_deadlines_survive_publication_and_reconciliation(self):
        from event_identity import dedupe_event_rows
        from reconcile_events import plan
        cases = [
            ("acm_ucr", "2026-09-25T00:00:00-07:00", [
                ("3980467437204327812", "ACM Spark Applications", "spark"),
                ("3981465870551773335", "ACM Create Applications", "create")]),
            ("ideasandsociety", "2026-09-28T00:00:00-07:00", [
                ("3987078712734376425", "CIS Academic Book Clubs Applications", "books"),
                ("3987591811061361059", "CIS Research Writing Groups Applications", "writing")]),
        ]
        for owner, start, announcements in cases:
            with self.subTest(owner=owner):
                rows = []
                for media_id, title, destination in announcements:
                    self.record.update(media_id=media_id, handle=owner, owner_username=owner,
                                       caption=title, permalink=f"https://www.instagram.com/p/{destination}/")
                    row, known = self.post_row(title=title, starts_at=start, ends_at=None,
                                              rsvp_url=f"https://forms.example/{destination}")
                    self.assertEqual({row["id"]}, known)
                    rows.append(row)
                self.assertNotEqual(rows[0]["id"], rows[1]["id"])
                self.assertEqual(rows, dedupe_event_rows(rows))
                self.assertEqual(([], set(), {}), plan(rows))

    def test_post_identity_survives_title_and_deadline_corrections(self):
        first, _ = self.post_row()
        corrected, _ = self.post_row(title="Updated Study Jam", starts_at="2026-09-16T16:00:00-07:00")
        self.assertEqual(first["id"], corrected["id"])

    def test_missing_media_identity_fails_mapping_instead_of_withdrawing_support(self):
        source = publication.post_source(self.record, self.cached)
        payload = {"status": "complete", "source": source,
                   "result": post_decision(source, field="slide_1_ocr")}
        for media_id in (None, "", "invalid"):
            with self.subTest(media_id=media_id), \
                 patch.object(publication, "cached_assessment", return_value=publication.AssessmentResult(payload, False)):
                raw = {**self.record, "media_id": media_id}
                update = publication.make_update(source, raw, self.cached, None, self.meta,
                                                 "2026-09-11T12:00:00Z").update
                self.assertEqual("error", update["assessment"]["status"])
                self.assertEqual([], update["rows"])

    def test_repeat_advertisements_keep_separate_source_ids_but_reconcile(self):
        from reconcile_events import plan, same_event
        first, _ = self.post_row()
        self.record["media_id"] = "701"
        repeated, _ = self.post_row()
        self.assertNotEqual(first["id"], repeated["id"])
        self.assertTrue(same_event(first, repeated))
        self.assertTrue(same_event({**first, "id": "ig_acm.ucr_20260915T2200Z"}, repeated))
        updates, removed, replacements = plan([first, repeated])
        self.assertEqual(1, len(removed))
        self.assertEqual(([], set(), {}), plan([r for r in [first, repeated] if r["id"] not in removed]))


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
        # admin locks and tombstones by event id.
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


class RosterFilterTests(unittest.TestCase):
    """An empty roster reads nothing; only an unreadable one reads everything."""

    def archive(self, roster):
        seen = []
        with patch.object(posts, "ensure_post_dirs"), \
             patch.object(posts, "hydrate_local_posts"), \
             patch.object(posts, "iter_local_posts",
                          side_effect=lambda handles=None: seen.append(handles) or []):
            posts.extract_all(roster, archive=posts.ArchiveIndex())
        return seen[0]

    def test_an_empty_handle_set_filters_to_nobody(self):
        self.assertEqual(set(), self.archive(set()))

    def test_named_handles_filter_to_those_accounts(self):
        self.assertEqual({"acm.ucr"}, self.archive({"acm.ucr"}))

    def test_no_handles_defers_to_the_roster(self):
        with patch.object(posts, "_known_handles", return_value={"acm.ucr"}):
            self.assertEqual({"acm.ucr"}, self.archive(None))

    def test_an_empty_roster_reads_nothing(self):
        with patch.object(posts, "_known_handles", return_value=set()):
            self.assertEqual(set(), self.archive(None))

    def test_an_unreadable_roster_falls_back_to_the_whole_archive(self):
        with patch.object(posts, "load_accounts", side_effect=OSError("no accounts.json")):
            self.assertIsNone(posts._known_handles())
            self.assertIsNone(self.archive(None))

    def test_an_empty_roster_does_not_process_posts_present_on_disk(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(post_archive, "POSTS_DIR", Path(directory)), \
             patch.object(posts, "ensure_post_dirs"), \
             patch.object(posts, "hydrate_local_posts"), \
             patch.object(posts, "process_post") as process:
            post_archive.write_post(record())
            processed, stats = posts.extract_all(set(), archive=posts.ArchiveIndex())
        self.assertEqual([], processed)
        self.assertEqual(0, stats["posts"])
        process.assert_not_called()


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
                 patch("config.load_account_meta", return_value={}), \
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
    def test_telemetry_changes_cannot_reset_a_service_failure_streak(self):
        processed = [(record(media_id=str(n)), {"status": "ok", "images": []}) for n in range(6)]
        stats = {}

        def update(source, *args, **kwargs):
            n = int(source["source_key"].rsplit(":", 1)[1])
            # Simulate unrelated future instrumentation on cache hits.
            stats["model_calls"] = stats.get("model_calls", 0) + 1
            return publication.UpdateResult(self.update(n, "error" if n % 2 == 0 else "complete"), False)

        with patch.object(publication, "make_update", side_effect=update) as make:
            updates = publication.post_updates(processed, {}, "2026-09-11T12:00:00Z",
                                               registry={}, stats=stats, stop_on_error=True)
        self.assertEqual(5, make.call_count)
        self.assertEqual(5, len(updates))

    def test_cached_successes_and_refusals_do_not_reset_model_failure_streak(self):
        for cached_status in ("complete", "error"):
            with self.subTest(cached_status=cached_status), tempfile.TemporaryDirectory() as directory, \
                 patch.object(publication, "CACHE_DIR", Path(directory)):
                processed, registry = [], {}
                for n in range(8):
                    raw, cached = record(media_id=str(n)), {"status": "ok", "images": []}
                    processed.append((raw, cached))
                    if n % 2:
                        source = publication.post_source(raw, cached)
                        payload = {"source": source, "source_hash": semantic.fingerprint(source),
                                   "status": cached_status, "retryable": False,
                                   "result": {"occurrences": [], "schedule": None}}
                        registry[source["source_key"]] = {"assessment": payload,
                                                          "event_ids": [], "known_event_ids": []}
                with patch.object(publication, "load_registry", return_value=registry), \
                     patch.object(semantic, "assess", side_effect=RuntimeError("quota exhausted")) as model, \
                     patch.object(publication, "publish", return_value={}) as publish:
                    with self.assertRaisesRegex(RuntimeError, "3 source assessment.*quota exhausted"):
                        publication.publish_posts(processed, "2026-09-11T12:00:00Z", meta={}, notify=False)
                self.assertEqual(3, model.call_count)
                self.assertEqual(3, len(publish.call_args.args[0]))

    def test_live_responses_reset_model_failure_streak_without_caller_stats(self):
        for response in ({"occurrences": [], "schedule": None}, semantic.GroundingRejected("refused")):
            with self.subTest(response=response), tempfile.TemporaryDirectory() as directory, \
                 patch.object(publication, "CACHE_DIR", Path(directory)):
                processed = [(record(media_id=str(n)), {"status": "ok", "images": []}) for n in range(6)]
                with patch.object(semantic, "assess", side_effect=[
                    RuntimeError("quota"), RuntimeError("quota"), response,
                    RuntimeError("quota"), RuntimeError("quota"), response]) as model:
                    updates = publication.post_updates(processed, {}, "2026-09-11T12:00:00Z",
                                                       registry={}, stop_on_error=True)
                self.assertEqual(6, model.call_count)
                self.assertEqual(6, len(updates))

    @staticmethod
    def update(n, status="complete"):
        assessment = ({"status": "error", "retryable": True, "error": "Gemini 503"}
                      if status == "error" else {"status": status})
        return {"source_key": f"instagram:post:{n}", "assessment": assessment, "rows": []}

    def test_an_isolated_model_failure_does_not_stop_assessment(self):
        processed = [(record(media_id=str(n)), {"status": "ok", "images": []}) for n in range(3)]
        updates = [self.update(0), self.update(1, "error"), self.update(2)]
        with patch.object(publication, "load_registry", return_value={}), \
             patch.object(publication, "make_update", side_effect=[publication.UpdateResult(u, True) for u in updates]) as assess, \
             patch.object(publication, "publish", return_value={}) as publish:
            with self.assertRaisesRegex(RuntimeError, "1 source assessment.*Gemini 503"):
                publication.publish_posts(processed, "2026-09-18T00:00:00Z", meta={}, notify=False)
        self.assertEqual(3, assess.call_count)
        publish.assert_called_once_with(updates)

    def test_transport_roadblock_publishes_completed_updates_without_assessing_more(self):
        limit = publication.MAX_CONSECUTIVE_FAILURES
        processed = [(record(media_id=str(n)), {"status": "ok", "images": []}) for n in range(limit + 2)]
        updates = [self.update(0)] + [self.update(n, "error") for n in range(1, limit + 1)]
        with patch.object(publication, "load_registry", return_value={}), \
             patch.object(publication, "make_update", side_effect=[publication.UpdateResult(u, True) for u in updates]) as assess, \
             patch.object(publication, "publish", return_value={}) as publish:
            with self.assertRaisesRegex(RuntimeError, "Gemini 503"):
                publication.publish_posts(processed, "2026-09-18T00:00:00Z", meta={}, notify=False)
        self.assertEqual(limit + 1, assess.call_count)
        publish.assert_called_once_with(updates)

    def test_only_usable_and_retryable_extractions_produce_updates(self):
        cached_ok = {"status": "ok", "images": [
            {"media_key": "a", "index": 0, "ocr_text": "Study Jam September 15, 2026, 3-5 PM"}]}
        processed = [
            (record(media_id="1"), cached_ok),
            (record(media_id="2"), {"status": "error", "images": []}),
            (record(media_id="3"), {"status": "unsupported_media", "images": []}),
            (record(media_id="4"), {"status": "no_text", "images": []}),
        ]
        # Nothing here has published before, so a text-free post has no listing
        # to withdraw and says nothing at all.
        with patch.object(publication, "make_update",
                          side_effect=lambda source, *a, **k: publication.UpdateResult({"source_key": source["source_key"]}, True)):
            updates = publication.post_updates(processed, {}, "2026-09-11T12:00:00+00:00", registry={})
        self.assertEqual(["instagram:post:1", "instagram:post:2"],
                         [item["source_key"] for item in updates])
        self.assertEqual("error", updates[1]["assessment"]["status"])

    def supporting_registry(self, *event_ids):
        """A registry as the publication RPC leaves it for a published post."""
        return {"instagram:post:700": {
            "source_key": "instagram:post:700", "origin": "instagram",
            "event_ids": list(event_ids), "known_event_ids": list(event_ids)}}

    def test_removing_a_posts_text_withdraws_the_listing_it_published(self):
        # Deleting a caption is the same editorial act as replacing it with
        # words that announce nothing, and must withdraw the same listing.
        # Nothing is left to assess, so no model call stands between the two.
        processed = [(record(caption=""), {"status": "no_text", "images": []})]
        with patch.object(publication, "make_update") as assessed:
            updates = publication.post_updates(
                processed, {}, "2026-09-11T12:00:00+00:00",
                registry=self.supporting_registry("ig_acm.ucr_20260915T2200Z"))
        assessed.assert_not_called()
        self.assertEqual(["instagram:post:700"], [item["source_key"] for item in updates])
        self.assertEqual("complete", updates[0]["assessment"]["status"])
        self.assertEqual([], updates[0]["rows"])
        # The identity the row was published under is what the RPC retires.
        self.assertEqual(["ig_acm.ucr_20260915T2200Z"], updates[0]["known_event_ids"])

    def test_text_removed_from_a_post_that_published_nothing_stays_silent(self):
        processed = [(record(caption=""), {"status": "no_text", "images": []})]
        for registry in (self.supporting_registry(), {}):
            with self.subTest(registry=registry):
                self.assertEqual([], publication.post_updates(
                    processed, {}, "2026-09-11T12:00:00+00:00", registry=registry))

    def test_a_post_this_version_cannot_read_keeps_the_listing_it_published(self):
        # An over-long carousel and a record without slides are limits of the
        # reader and of the archive, not the club withdrawing the announcement.
        for status in ("unsupported_media", "no_media"):
            with self.subTest(status=status):
                self.assertEqual([], publication.post_updates(
                    [(record(), {"status": status, "images": []})], {},
                    "2026-09-11T12:00:00+00:00",
                    registry=self.supporting_registry("ig_acm.ucr_20260915T2200Z")))


if __name__ == "__main__":
    unittest.main()
