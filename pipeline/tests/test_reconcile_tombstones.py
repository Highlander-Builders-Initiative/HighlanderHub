"""Deleted assessed identities must constrain corroborated source replacements."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import assessed_events as publication
import content_assessment as semantic
import reconcile_events as reconcile

NOW = '2026-09-11T20:00:00Z'


class AssessedTombstoneTests(unittest.TestCase):
    def setUp(self):
        # Other pipeline tests reload importers; keep lazy imports and patches
        # pointed at the same module instances for this fixture.
        modules = patch.dict(sys.modules, {
            'assessed_events': publication, 'content_assessment': semantic,
        })
        modules.start()
        self.addCleanup(modules.stop)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.registry = {}
        for target, name, value in (
            (publication, 'load_registry', lambda: self.registry),
            (publication, 'load_account_meta', lambda: {}),
        ):
            mocked = patch.object(target, name, side_effect=value)
            mocked.start()
            self.addCleanup(mocked.stop)
        mocked = patch('post_archive.iter_local_posts', return_value=[])
        mocked.start()
        self.addCleanup(mocked.stop)
        mocked = patch.object(semantic, 'assess', side_effect=AssertionError('Reconciliation must not assess'))
        mocked.start()
        self.addCleanup(mocked.stop)


    def test_post_tombstones_reconstruct_last_complete_assessment(self):
        import extract_posts as posts
        from test_post_events import record, post_decision

        raw = record(caption="Study Jam September 15, 2026, 3-5 PM", slides=1)
        cached = {"status": "ok", "images": []}
        source = publication.post_source(raw, cached)
        payload = {"status": "complete", "source": source,
                   "result": post_decision(source, field="caption")}
        rows, _ = publication.post_rows(raw, cached, payload, {}, NOW)
        self.assertEqual(1, len(rows))
        self.registry[source['source_key']] = {
            'origin': 'instagram', 'assessment': {'status': 'error'},
            'last_complete_assessment': payload,
            'event_ids': ['ig_canonical'],
            'known_event_ids': [rows[0]['id']],
        }
        cache = self.root / 'post.json'
        cache.write_text(json.dumps(cached))
        with patch('post_archive.iter_local_posts', return_value=[raw]), \
             patch.object(posts, '_cache_path', return_value=cache):
            for deleted in ({rows[0]['id']}, {'ig_canonical'}):
                with self.subTest(deleted=deleted):
                    rebuilt = reconcile._tombstoned_candidates(deleted)
                    self.assertEqual([rows[0]['id']], [row['id'] for row in rebuilt])
            self.assertEqual([], reconcile._tombstoned_candidates({'unrelated'}))


if __name__ == '__main__':
    unittest.main()
