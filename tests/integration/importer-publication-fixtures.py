"""Run real importer entrypoints through RPC serialization, without network IO."""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pipeline"))
import assessed_events as publication
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

print(json.dumps(batches))
