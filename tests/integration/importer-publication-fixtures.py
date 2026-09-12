"""Run real importer entrypoints through RPC serialization, without network IO."""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pipeline"))
import assessed_events as publication
import extract_posts as posts
import extract_stories as stories
import normalize_events as structured

batches = []
client = MagicMock()

def rpc(name, arguments):
    assert name == "reconcile_source_assessments"
    batches.append(arguments["updates"])
    response = MagicMock()
    response.execute.return_value.data = {"written": 0, "deleted": 0}
    return response

client.rpc.side_effect = rpc
text = "Drop-in advising September 15, 2026 Tuesday 10 AM-12 PM and 1 PM-3 PM."
raw = {"id": "123", "handle": "club", "posted_at": "2026-09-10T17:00:00Z"}
cached = {"status": "ok", "ocr_text": text, "result": {
    "is_event": True, "title": "Advising", "starts_at": "2026-09-15T10:00:00-07:00",
    "ends_at": "2026-09-15T15:00:00-07:00"}}

with tempfile.TemporaryDirectory() as directory, \
     patch.object(publication, "CACHE_DIR", Path(directory)), \
     patch.object(publication, "load_registry", return_value={}), \
     patch("db.client", return_value=client), \
     patch("db.get_imported_events", return_value=[]):
    src = publication.story_source(raw, cached)
    evidence = [{"field": "ocr_text", "quote": text}]
    result = {"kind": "service_schedule", "date_role": "recurring_hours", "reason": "Printed advising hours",
              "activity_evidence": evidence, "date_evidence": evidence, "use_source_occurrences": False,
              "occurrences": [], "schedule": {"title": "Advising", "location": "HUB",
              "first_day": "2026-09-15", "last_day": "2026-09-15", "weekdays": [1],
              "windows": [{"start": "10:00", "end": "12:00"}, {"start": "13:00", "end": "15:00"}]}}
    publication.record_review(src, result, reviewer="integration fixture")
    with patch.object(stories, "ensure_dirs"), \
         patch.object(stories, "_load_account_meta", return_value={}), \
         patch.object(stories, "_iter_raw_stories", return_value=[raw]), \
         patch.object(stories, "_process_story", return_value=cached):
        stories.main(notify=False)
        result.update(kind="announcement", date_role="none", schedule=None, activity_evidence=[], date_evidence=[])
        publication.record_review(src, result, reviewer="integration fixture")
        stories.main(notify=False)

    calendar = {"id": 456, "title": "Workshop", "description_text": "Student workshop",
                "first_date": "2026-09-15T10:00:00-07:00",
                "filters": {"event_audience": [{"name": "Students"}]}}
    src = publication.structured_source(calendar, "localist")
    result.update(kind="activity", date_role="occurrence", use_source_occurrences=True,
                  activity_evidence=[{"field": "description", "quote": "Student workshop"}],
                  date_evidence=[{"field": "dates", "quote": src["texts"]["dates"]}])
    publication.record_review(src, result, reviewer="integration fixture")
    with patch.object(structured, "_collect_raw", side_effect=[[calendar], []]):
        structured.main(notify=False)
    with patch.object(structured, "_collect_raw", side_effect=[[], []]), \
         patch("db.get_imported_events", return_value=[{"id": "ucr_events_456"}]):
        structured.main(["ucr_events_"], notify=False)

    # A feed post is the source. A story resharing it is not published.
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
    reshare = {"id": "555", "handle": "ieee.ucr", "posted_at": "2026-09-10T18:00:00Z",
               "caption": None, "permalink": "https://www.instagram.com/stories/ieee.ucr/555/",
               "reshared_post": {"media_id": "700", "owner_username": None,
                                 "caption": "Join ACM for a study jam"}}
    reshare_cached = {"status": "ok", "ocr_text": flyer, "result": {}}
    occurrence = {"title": "Study Jam", "starts_at": "2026-09-15T15:00:00-07:00",
                  "ends_at": "2026-09-15T17:00:00-07:00", "all_day": False, "location": ""}
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
    publication.publish_instagram([(reshare, reshare_cached)], [(post, post_cached)],
                                  meta, "2026-09-11T19:00:00Z", notify=False)

    # The club corrects the caption to say the session is cancelled; with the
    # reshare skipped, the post is the only source and the listing withdraws.
    corrected = {**post, "caption": "Study jam is cancelled, see you next term"}
    corrected_src = publication.post_source(corrected, post_cached)
    review(corrected_src, "caption", kind="announcement")
    publication.publish_instagram([], [(corrected, post_cached)], meta,
                                  "2026-09-11T20:00:00Z", notify=False)

    # A second post from an unrelated club with the same title and time.
    other = {**post, "media_id": "800", "handle": "ieee.ucr", "owner_username": "ieee.ucr",
             "shortcode": "COther", "permalink": "https://www.instagram.com/p/COther/"}
    other_src = publication.post_source(other, post_cached)
    review(other_src, "slide_1_ocr")
    publication.publish_instagram([], [(other, post_cached)], meta,
                                  "2026-09-11T21:00:00Z", notify=False)

    # The post now has a blank slide and no caption. Run extraction through
    # publication so the SQL test consumes the actual no_text withdrawal.
    emptied = {**post, "caption": "", "media": [{
        "index": 0, "is_video": False, "media_key": "blank",
        "image_url": "https://cdn.example/blank.jpg"}]}
    prior = {post_src["source_key"]: {
        "event_ids": [item["id"] for item in batches[4][0]["rows"]]}}
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
