"""Source-backed regressions from the October 2 pipeline audit."""
import copy
import itertools
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import assessed_events as publication
import content_assessment as semantic
import reconcile_events as reconcile
from classify import detect_free_food
from event_dates import evidence_dates

CASES = json.loads((Path(__file__).parent / 'fixtures/oct2-sources.json').read_text())
NOW = '2026-10-02T17:00:00Z'


def rows(name):
    case = CASES[name]
    return publication.post_rows(case['record'], case['cached'], case['assessment'], {}, NOW)[0]


class DateEvidenceTests(unittest.TestCase):
    def test_plural_events_schedule_supports_named_date_rows(self):
        case = CASES['qtpoc']['assessment']
        result = semantic.validate(semantic._attach_source_quotes(
            copy.deepcopy(case['validation_attempts'][-1]['response']), case['source']), case['source'])
        self.assertEqual(3, len(result['occurrences']))
        self.assertEqual({(10, 14), (10, 28), (11, 18)},
                         evidence_dates(case['source']['texts']['slide_1_ocr']))

    def test_schedule_does_not_promote_fractions_or_room_numbers(self):
        for text in ('Events schedule\nRoom 10/14\nRoom 10/28',
                     'Events schedule\n1/2 cup milk\n3/4 cup flour',
                     'Events schedule\n10/14'):
            self.assertEqual(set(), evidence_dates(text))

    def test_homecoming_tiles_may_share_a_line(self):
        case = CASES['homecoming']['assessment']
        source = case['source']
        text = source['texts']['slide_1_ocr']
        self.assertTrue(semantic._day_supported(date(2026, 11, 7), text, source))
        self.assertFalse(semantic._day_supported(date(2027, 11, 7), text, source))
        self.assertEqual(set(), evidence_dates('11 07\n26'))
        self.assertEqual(set(), evidence_dates('11 07\nRoom 26\nMONTH DAY YEAR'))
        self.assertEqual(set(), evidence_dates('11 07\n26\nUnrelated heading\nMONTH DAY YEAR'))


class RelocatedScheduleTests(unittest.TestCase):
    def test_all_three_rush_sessions_converge_on_the_corrected_room(self):
        groups = [rows(name) for name in ('rush_old', 'rush_correction', 'rush_repeat')]
        for ordered in itertools.permutations(groups):
            updates, removed, replacements = reconcile.plan([r for group in ordered for r in group])
            self.assertEqual(6, len(removed))
            surviving = {r['id']: r for group in ordered for r in group if r['id'] not in removed}
            surviving.update({r['id']: r for r in updates})
            self.assertEqual(3, len(surviving))
            self.assertTrue(all(r['location'] == 'FSIC HUB 101A' for r in surviving.values()))
            self.assertEqual(3, len(set(replacements.values())))

    def test_republication_keeps_the_corrected_location(self):
        old, new = rows('rush_old')[0], rows('rush_correction')[0]
        fixed = reconcile.prefer_repost_source(old, [old, new])
        self.assertEqual(old['id'], fixed['id'])
        self.assertEqual('FSIC HUB 101A', fixed['location'])
        self.assertEqual(fixed, reconcile.prefer_repost_source(fixed, [old, new]))

    def test_repost_without_a_venue_keeps_the_established_one(self):
        old, new = rows('rush_old')[0], rows('rush_correction')[0]
        center = "Women's Resource Center"
        for host, location in ((old.get('host'), 'FSIC HUB 229'), (center, center)):
            for missing in (None, '', 'TBA'):
                with self.subTest(location=location, missing=missing):
                    winner = old | {'host': host, 'location': location}
                    fixed = reconcile.prefer_repost_source(winner, [winner, new | {'host': host, 'location': missing}])
                    self.assertEqual(location, fixed['location'])

    def test_venue_disagreements_and_admin_decisions_remain_protected(self):
        old, new = rows('rush_old')[0], rows('rush_correction')[0]
        for changes in ({'description': 'Rush Week is here!'}, {'host_handle': 'other_club'},
                        {'title': 'Rush LSU Info Night #2'}, {'starts_at': '2026-10-13T02:00:00Z'}):
            self.assertFalse(reconcile.same_event(old, new | changes))
        reviews = reconcile.Reviews(distinct=frozenset({frozenset({old['id'], new['id']})}))
        self.assertEqual(([], set(), {}), reconcile.plan([old, new], reviews=reviews))
        self.assertEqual({new['id']: old['id']}, reconcile.plan([old | {'is_locked': True}, new])[2])
        self.assertEqual(([], {new['id']}, {}), reconcile.plan([new], [old]))


class VisualReviewTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        cache = patch.object(publication, 'CACHE_DIR', Path(directory.name))
        cache.start()
        self.addCleanup(cache.stop)

    def review(self):
        case = CASES['cib_deadline']
        source = copy.deepcopy(case['assessment']['source'])
        result = copy.deepcopy(case['assessment']['validation_attempts'][-1]['response'])
        corrections = {'slide_1_ocr': source['texts']['slide_1_ocr'].replace('10/211:59pm', '10/2 11:59pm')}
        result['occurrences'][0]['starts_at'] = '2026-10-02T23:59:00-07:00'
        reviewed_source = {**source, 'texts': {**source['texts'], **corrections}}
        payload = publication.record_review(source, semantic._attach_source_quotes(result, reviewed_source),
                                            reviewer='Visually verified saved flyer', ocr_corrections=corrections)
        return source, payload

    def test_ambiguous_joined_ocr_requires_review(self):
        source, payload = self.review()
        self.assertEqual('Closes: 10/211:59pm', source['texts']['slide_1_ocr'].splitlines()[-3])
        self.assertEqual(source, payload['source'])
        self.assertEqual(semantic.fingerprint(source), payload['source_hash'])
        for day in (2, 21):
            self.assertFalse(semantic._day_supported(date(2026, 10, day),
                             source['texts']['slide_1_ocr'], source))
        semantic.validate(copy.deepcopy(payload['result']), publication.assessment_source(payload))

    def test_review_survives_remote_cache_replay_without_model_calls(self):
        source, payload = self.review()
        publication._cache_path(source['source_key']).unlink()
        with patch.object(semantic, 'assess', side_effect=AssertionError('Unexpected model call')):
            reused = publication.cached_assessment(source, payload)
            self.assertFalse(reused.produced_live)
            case = CASES['cib_deadline']
            published, _ = publication.post_rows(case['record'], case['cached'], reused.payload, {}, NOW)
        self.assertEqual('2026-10-03T06:59:00+00:00', published[0]['starts_at'])
        self.assertEqual('student_deadline', published[0]['content_kind'])

    def test_source_changes_and_explicit_refresh_expire_visual_review(self):
        source, payload = self.review()
        changed = copy.deepcopy(source)
        changed['texts']['caption'] += ' Updated deadline.'
        with patch.object(semantic, 'assess', side_effect=RuntimeError('model stub')) as model:
            for src, refresh in ((changed, False), (source, True)):
                result = publication.cached_assessment(src, payload, refresh=refresh, persist=False)
                self.assertTrue(result.produced_live)
                self.assertNotIn('ocr_corrections', result.payload)
            self.assertEqual(2, model.call_count)

    def test_review_cannot_override_caption_or_add_an_unknown_slide(self):
        source, payload = self.review()
        for correction in ({'caption': 'A replacement caption'}, {'slide_99_ocr': 'October 2'},
                           {'slide_1_ocr': ''}):
            with self.assertRaises(ValueError):
                publication.record_review(source, payload['result'], reviewer='review', ocr_corrections=correction)

    def test_bake_sale_does_not_suppress_sibling_movie_or_its_pizza(self):
        case = CASES['bsib']
        source = case['assessment']['source']
        corrections = {'slide_4_ocr': source['texts']['slide_4_ocr'].replace('COCTOBER', 'OCTOBER')}
        effective = source | {'texts': source['texts'] | corrections}
        result = copy.deepcopy(case['assessment']['validation_attempts'][-1]['response'])
        payload = publication.record_review(source, semantic._attach_source_quotes(result, effective),
                                            reviewer='Visually verified October 2 flyer',
                                            ocr_corrections=corrections)
        published, _ = publication.post_rows(case['record'], case['cached'], payload, {}, NOW)
        self.assertEqual({'BSIB General Body Meeting', 'BSIB Movie Night'}, {r['title'] for r in published})
        self.assertEqual({'BSIB Movie Night'}, {r['title'] for r in published if r['has_free_food']})

    def test_included_food_retains_negation_and_price_checks(self):
        self.assertTrue(detect_free_food('PIZZA INCLUDED'))
        for text in ('Pizza included for $5', 'No pizza included', 'Pizza is not included',
                     'Pizza included with a purchase', 'Pizza included for sale',
                     'Lunch included with your $15 ticket', 'Tickets $20, food included',
                     'Admission: $5 (pizza included)', 'Dinner included in registration fee'):
            with self.subTest(text=text):
                self.assertFalse(detect_free_food(text))
        self.assertTrue(detect_free_food('Free admission, pizza included'))
        # A price elsewhere on the flyer does not reach the food line's clause.
        self.assertTrue(detect_free_food('Bake sale $3\nPIZZA INCLUDED'))


class MergedVenueReplayTests(unittest.TestCase):
    def setUp(self):
        case = copy.deepcopy(CASES['replay_venue'])
        self.canonical = case['canonical']
        self.rows = case['rows']
        self.updates = [{'source_key': f'instagram:post:{index}',
                         'assessment': {'status': 'complete', 'result': {}}, 'rows': [row]}
                        for index, row in enumerate(self.rows)]
        self.registry = {u['source_key']: {'assessment': copy.deepcopy(u['assessment']),
                            'event_ids': [self.canonical['id']],
                            'known_event_ids': [self.canonical['id'], u['rows'][0]['id']]}
                         for u in self.updates}

    def replay(self):
        kept = publication._withhold_reconciled(copy.deepcopy(self.updates), self.registry,
                                               {self.canonical['id']: self.canonical})
        return next(r for u in kept for r in u['rows'] if r['id'] == self.canonical['id'])

    def test_current_source_support_preserves_merged_venue_spelling(self):
        self.assertEqual('', self.rows[0]['location'])
        self.assertEqual(self.canonical['location'], self.replay()['location'])
        self.assertEqual('', self.rows[0]['location'])

    def test_unsupported_saved_venue_is_not_restored(self):
        self.canonical['location'] = 'An obsolete venue'
        self.assertNotEqual('An obsolete venue', self.replay()['location'])

    def test_changed_owner_decision_does_not_restore_saved_venue(self):
        self.updates[0]['assessment']['result'] = {'reason': 'Source changed'}
        self.assertEqual('', self.replay()['location'])


if __name__ == '__main__':
    unittest.main()
