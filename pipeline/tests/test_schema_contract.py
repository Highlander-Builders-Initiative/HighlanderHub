from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_ROOT = REPO_ROOT / "pipeline"
SCHEMAS_DIR = REPO_ROOT / "schemas"

if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMAS_DIR / name).read_text())


def _schema_keys(schema: dict) -> set[str]:
    return set(schema["properties"])


class SchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fake_config = types.SimpleNamespace(
            ROOT=PIPELINE_ROOT,
            GOOGLE_CLOUD_PROJECT="test-project",
            GOOGLE_CLOUD_LOCATION="global",
            GOOGLE_VISION_API_KEY="test",
            GOOGLE_VISION_API_KEY_PRIMARY="test-primary",
            POSTS_DIR=PIPELINE_ROOT / "data" / "posts",
            POST_EXTRACTED_DIR=PIPELINE_ROOT / "data" / "post_extractions",
            POST_CHECKPOINTS_FILE=PIPELINE_ROOT / "data" / "post_checkpoints.json",
            POST_OVERLAP_DAYS=7,
            DATA_DIR=PIPELINE_ROOT / "data",
            ensure_post_dirs=lambda: None,
            load_accounts=lambda: [],
            load_account_meta=lambda: {},
        )
        cls._saved_modules = {
            name: sys.modules.get(name) for name in ("config", "db")
        }
        sys.modules["config"] = fake_config
        sys.modules["db"] = types.SimpleNamespace(
            upsert_batched=lambda *a, **k: 0,
            get_deleted_event_ids=lambda: set(),
        )
        cls.events_schema = _load_schema("events.upsert.schema.json")
        cls.event_keys = _schema_keys(cls.events_schema)
        cls.event_required = set(cls.events_schema["required"])

    def _assert_row_matches_schema(self, row: dict[str, object], schema_keys: set[str], required: set[str]) -> None:
        keys = set(row.keys())
        self.assertTrue(keys <= schema_keys, keys - schema_keys)
        self.assertTrue(required <= keys, required - keys)

    @classmethod
    def tearDownClass(cls) -> None:
        for name, mod in cls._saved_modules.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod


    def test_assessed_post_event_row_keys(self) -> None:
        import assessed_events as publication

        flyer = "Study Jam September 15, 2026 3 PM-5 PM"
        record = {
            "media_id": "700",
            "handle": "acm.ucr",
            "owner_username": "acm.ucr",
            "permalink": "https://www.instagram.com/p/CStudy/",
            "posted_at": "2026-09-10T17:00:00+00:00",
            "caption": "Join ACM for a study jam",
        }
        cached = {"status": "ok", "images": [
            {"media_key": "700_0_n", "index": 0, "ocr_text": flyer, "qr_urls": [],
             "image_url": "https://storage.example/700_0_n.jpg"}]}
        source = publication.post_source(record, cached)
        cited = [{"field": "slide_1_ocr", "quote": flyer}]
        payload = {"status": "complete", "source": source, "result": {
            "kind": "activity", "date_role": "occurrence", "reason": "Flyer announces a study jam.",
            "activity_evidence": cited, "date_evidence": cited,
            "use_source_occurrences": False, "schedule": None,
            "occurrences": [{"title": "Study Jam", "starts_at": "2026-09-15T15:00:00-07:00",
                             "ends_at": "2026-09-15T17:00:00-07:00", "all_day": False,
                             "location": "", "activity_evidence": cited, "date_evidence": cited}]}}
        rows, _known = publication.post_rows(record, cached, payload, {}, "2026-09-11T12:00:00+00:00")
        self.assertEqual(1, len(rows))
        self._assert_row_matches_schema(rows[0], self.event_keys, self.event_required)


if __name__ == "__main__":
    unittest.main()
