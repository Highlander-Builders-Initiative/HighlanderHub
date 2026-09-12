"""Deleted assessed identities must constrain corroborated source replacements."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import assessed_events as publication
import content_assessment as semantic
import extract_stories as ig
import normalize_events as structured
import reconcile_events as reconcile

NOW = '2026-09-11T20:00:00Z'


class AssessedTombstoneTests(unittest.TestCase):
    def setUp(self):
        # Other pipeline tests reload importers; keep lazy imports and patches
        # pointed at the same module instances for this fixture.
        modules = patch.dict(sys.modules, {
            'extract_stories': ig, 'normalize_events': structured,
            'assessed_events': publication, 'content_assessment': semantic,
        })
        modules.start()
        self.addCleanup(modules.stop)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.registry = {}
        self.raws = {'localist': [], 'highlander_link': []}
        for target, name, value in (
            (publication, 'load_registry', lambda: self.registry),
            (ig, '_load_account_meta', lambda: {}),
            (ig, '_cache_path', lambda key: self.root / f'{key}.cache'),
            (structured, '_collect_raw', lambda path: self.raws['localist' if path == structured.UCR_EVENTS_RAW else 'highlander_link']),
        ):
            mocked = patch.object(target, name, side_effect=value)
            mocked.start()
            self.addCleanup(mocked.stop)
        mocked = patch.object(ig, 'RAW_DIR', self.root)
        mocked.start()
        self.addCleanup(mocked.stop)
        mocked = patch.object(semantic, 'assess', side_effect=AssertionError('Reconciliation must not assess'))
        mocked.start()
        self.addCleanup(mocked.stop)

    def prepare(self, origin, *, schedule=False):
        text = 'Student Robotics Building Workshop and Student Astronomy Telescope Night, September 15-16, 2026, Tuesday-Wednesday, 3-5 PM'
        raw = {'id': '123', 'handle': 'campusclub', 'posted_at': NOW,
               'title': 'Student Robotics Building Workshop', 'name': 'Student Robotics Building Workshop', 'description_text': text,
               'description': text, 'first_date': '2026-09-15T15:00:00-07:00',
               'startsOn': '2026-09-15T15:00:00-07:00',
               'filters': {'event_audience': [{'name': 'Students'}]}}
        cached = {'status': 'not_event', 'ocr_text': text, 'result': {}}
        source = (publication.story_source(raw, cached) if origin == 'instagram'
                  else publication.structured_source(raw, origin))
        field = 'ocr_text' if origin == 'instagram' else 'description'
        evidence = [{'field': field, 'quote': text}]
        result = {'kind': 'activity', 'date_role': 'occurrence', 'reason': 'Two campus activities',
                  'activity_evidence': evidence, 'date_evidence': evidence, 'use_source_occurrences': False,
                  'schedule': None, 'occurrences': [
                      {'title': title, 'starts_at': '2026-09-15T15:00:00-07:00',
                       'ends_at': '2026-09-15T17:00:00-07:00', 'location': 'HUB 302', 'all_day': False,
                       'activity_evidence': evidence, 'date_evidence': evidence}
                      for title in ('Student Robotics Building Workshop', 'Student Astronomy Telescope Night')]}
        if schedule:
            result.update(occurrences=[], schedule={
                'first_day': '2026-09-15', 'last_day': '2026-09-16', 'weekdays': [1, 2],
                'windows': [{'start': '15:00', 'end': '17:00'}],
                'title': 'Student Robotics Building Workshop', 'location': 'HUB 302'})
        payload = {'status': 'complete', 'source': source, 'result': semantic.validate(result, source)}
        if origin == 'instagram':
            folder = self.root / raw['handle']
            folder.mkdir(exist_ok=True)
            (folder / '123.json').write_text(json.dumps(raw))
            (self.root / '123.cache').write_text(json.dumps(cached))
            rows, _ = publication.story_rows(raw, cached, payload, {}, NOW)
        else:
            self.raws[origin] = [raw]
            rows, _ = publication.structured_rows(raw, origin, payload, NOW)
        self.assertEqual(2, len(rows))
        self.registry[source['source_key']] = {
            'origin': origin, 'assessment': payload, 'last_complete_assessment': payload,
            'event_ids': [], 'known_event_ids': [row['id'] for row in rows]}
        return rows, self.registry[source['source_key']]

    def test_assessed_hashes_and_schedule_fanout_block_cross_source_copies(self):
        for origin in ('instagram', 'localist', 'highlander_link'):
            for schedule in (False, True):
                with self.subTest(origin=origin, schedule=schedule):
                    self.registry.clear()
                    self.raws = {'localist': [], 'highlander_link': []}
                    rows, _ = self.prepare(origin, schedule=schedule)
                    tombstones = reconcile._tombstoned_candidates({rows[0]['id']})
                    self.assertEqual({row['id'] for row in rows}, {row['id'] for row in tombstones})
                    copies = [{**row, 'id': f'other_{i}'} for i, row in enumerate(rows)]
                    unrelated = {**copies[0], 'id': 'unrelated', 'starts_at': '2027-01-01T22:00:00Z'}
                    locked = {**copies[0], 'id': 'locked', 'is_locked': True}
                    self.assertEqual(([], {'other_0', 'other_1'}),
                                     reconcile.plan([*copies, unrelated, locked], tombstones))

    def test_error_uses_last_complete_assessment_and_remapped_identity(self):
        rows, record = self.prepare('instagram')
        record['assessment'] = {'status': 'error', 'error': 'Model unavailable'}
        record['event_ids'] = ['ucr_events_canonical']
        self.assertEqual({r['id'] for r in rows},
                         {r['id'] for r in reconcile._tombstoned_candidates({'ucr_events_canonical'})})

    def test_known_legacy_identity_constrains_assessed_replacements(self):
        rows, record = self.prepare('localist', schedule=True)
        record['known_event_ids'].append('ucr_events_old')
        self.assertEqual({r['id'] for r in rows},
                         {r['id'] for r in reconcile._tombstoned_candidates({'ucr_events_old'})})
        self.assertEqual([], reconcile._tombstoned_candidates({'ucr_events_unrelated'}))

    def test_negative_assessment_never_falls_back_to_legacy_projection(self):
        _, record = self.prepare('localist')
        payload = copy.deepcopy(record['assessment'])
        payload['result'].update(kind='announcement', date_role='notice_period', occurrences=[])
        record.update(assessment=payload, last_complete_assessment=payload)
        self.assertEqual([], reconcile._tombstoned_candidates({'ucr_events_123'}))

    def test_unregistered_legacy_deletions_still_block_copies(self):
        self.prepare('localist')
        self.registry.clear()
        tombstones = reconcile._tombstoned_candidates({'ucr_events_123'})
        self.assertEqual(['ucr_events_123'], [r['id'] for r in tombstones])
        self.assertEqual(([], {'ig_copy'}), reconcile.plan([{**tombstones[0], 'id': 'ig_copy'}], tombstones))


if __name__ == '__main__':
    unittest.main()
