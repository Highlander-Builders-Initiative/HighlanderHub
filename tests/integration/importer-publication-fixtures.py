"""Run real importer entrypoints through RPC serialization, without network IO."""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pipeline"))
import assessed_events as publication
import extract_posts as posts

batches = []
client = MagicMock()

def rpc(name, arguments):
    assert name == "reconcile_source_assessments"
    batches.append(arguments["updates"])
    response = MagicMock()
    response.execute.return_value.data = {"written": 0, "deleted": 0}
    return response

client.rpc.side_effect = rpc
with tempfile.TemporaryDirectory() as directory, \
     patch.object(publication, "CACHE_DIR", Path(directory)), \
     patch.object(publication, "load_registry", return_value={}), \
     patch("db.client", return_value=client), \
     patch("db.get_imported_events", return_value=[]):
    # A feed post publishes one listing.
    flyer = "Study Jam September 15, 2026 3 PM-5 PM"
    post = {"media_id": "700", "handle": "acm.ucr", "owner_username": "acm.ucr",
            "shortcode": "CStudy", "permalink": "https://www.instagram.com/p/CStudy/",
            "posted_at": "2026-09-10T17:00:00Z", "typename": "GraphImage",
            "caption": "Join ACM for a study jam", "has_video": False,
            "media": [{"index": 0, "is_video": False, "media_key": "700_0_n",
                       "image_url": "https://cdn.example/700_0_n.jpg?oh=sig"}]}
    post_cached = {"status": "ok", "images": [
        {"media_key": "700_0_n", "index": 0, "ocr_text": flyer, "qr_urls": [],
         "image_url": "https://storage.example/700_0_n.jpg"}]}
    occurrence = {"title": "Study Jam", "starts_at": "2026-09-15T15:00:00-07:00",
                  "ends_at": "2026-09-15T17:00:00-07:00", "all_day": False, "location": "", "location_evidence": []}
    meta = {"acm.ucr": {"label": "ACM at UCR"}, "ieee.ucr": {"label": "IEEE at UCR"}}

    def review(source, field, *, kind="activity", start=None):
        cited = [{"field": field, "quote": source["texts"][field]}]
        body = {"kind": kind, "date_role": "occurrence" if kind == "activity" else "none",
                "reason": "Flyer announces a study jam.",
                "activity_evidence": cited if kind == "activity" else [],
                "date_evidence": cited if kind == "activity" else [],
                "use_source_occurrences": False, "schedule": None,
                "occurrences": [{**occurrence, "activity_evidence": cited, "date_evidence": cited,
                                 **({"starts_at": start} if start else {})}] if kind == "activity" else []}
        publication.record_review(source, body, reviewer="integration fixture")

    post_src = publication.post_source(post, post_cached)
    review(post_src, "slide_1_ocr")
    publication.publish_posts([(post, post_cached)], "2026-09-11T19:00:00Z", meta=meta, notify=False)

    # A cancellation withdraws the post-supported listing.
    corrected = {**post, "caption": "Study jam is cancelled, see you next term"}
    corrected_src = publication.post_source(corrected, post_cached)
    review(corrected_src, "caption", kind="announcement")
    publication.publish_posts([(corrected, post_cached)],
                                  "2026-09-11T20:00:00Z", meta=meta, notify=False)

    # A second post from an unrelated club with the same title and time.
    other = {**post, "media_id": "800", "handle": "ieee.ucr", "owner_username": "ieee.ucr",
             "shortcode": "COther", "permalink": "https://www.instagram.com/p/COther/"}
    other_src = publication.post_source(other, post_cached)
    review(other_src, "slide_1_ocr")
    publication.publish_posts([(other, post_cached)],
                                  "2026-09-11T21:00:00Z", notify=False)

    # The post now has a blank slide and no caption. Run extraction through
    # publication so the SQL test consumes the actual no_text withdrawal.
    emptied = {**post, "caption": "", "media": [{
        "index": 0, "is_video": False, "media_key": "blank",
        "image_url": "https://cdn.example/blank.jpg"}]}
    prior = {post_src["source_key"]: {
        "event_ids": [item["id"] for item in batches[0][0]["rows"]]}}
    with patch.object(posts, "POST_EXTRACTED_DIR", Path(directory) / "post_extractions"), \
         patch.object(posts, "_load_remote_cache", return_value=None), \
         patch.object(posts, "_write_remote_cache"), \
         patch.object(posts, "_download_image", return_value=b"blank image"), \
         patch.object(posts, "_vision_ocr", return_value=""), \
         patch.object(posts, "qr_rsvp_urls", return_value=[]), \
         patch.object(posts, "_upload_flyer", return_value=None), \
         patch.object(publication, "load_registry", return_value=prior), \
         patch.object(publication.semantic, "assess", side_effect=AssertionError("No text to assess")):
        empty_cache = posts.process_post(emptied)
        assert empty_cache["status"] == "no_text"
        publication.publish_posts([(emptied, empty_cache)], "2026-09-11T22:00:00Z",
                                  notify=False, meta=meta)

print(json.dumps(batches))
