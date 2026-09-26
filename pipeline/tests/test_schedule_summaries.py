"""Incomplete schedule entries can resolve to one detailed event announcement."""
import copy
import itertools
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import assessed_events as publication
from reconcile_events import plan, same_event

ROWS = json.loads((Path(__file__).parent / 'fixtures/schedule-summaries.json').read_text())


def pair():
    detailed, summary = copy.deepcopy(ROWS)
    return summary, detailed


def competitor(detailed, **changes):
    return detailed | dict(id='ig_otherclub_p999', host='Other Club', host_handle='otherclub',
                           hosts=[], source_url='https://www.instagram.com/p/Other/', **changes)


class ScheduleSummaryTests(unittest.TestCase):
    def test_block_party_summary_converges_to_the_detailed_announcement(self):
        summary, detailed = pair()
        for ordered in itertools.permutations([summary, detailed]):
            self.assertTrue(same_event(*ordered))
            updates, removed, replacements = plan(list(ordered))
            self.assertEqual({summary['id']: detailed['id']}, replacements)
            self.assertEqual({summary['id']}, removed)
            winner = updates[0] if updates else detailed
            for key in ('title', 'starts_at', 'ends_at', 'all_day', 'location', 'image_url', 'description'):
                self.assertEqual(detailed[key], winner[key], key)
            self.assertEqual(([], set(), {}), plan([winner]))
            self.assertEqual(replacements, plan([winner, summary])[2])

    def test_tba_location_and_known_time_can_resolve_across_accounts(self):
        summary, detailed = pair()
        for location in ('', 'TBA', 'Room TBD', 'UC Riverside'):
            timed = summary | dict(all_day=False, starts_at=detailed['starts_at'], ends_at=None,
                                   location=location)
            self.assertTrue(same_event(timed, detailed), location)
            self.assertEqual({summary['id']: detailed['id']}, plan([timed, detailed])[2])

    def test_the_missing_detail_must_come_from_a_multi_event_post(self):
        summary, detailed = pair()
        self.assertFalse(same_event(summary | {'id': summary['id'].split('-')[0]}, detailed))
        self.assertFalse(same_event(summary | {'all_day': None}, detailed))
        self.assertFalse(same_event(summary | {'all_day': False}, detailed))
        self.assertFalse(same_event(summary, detailed | {'location': 'TBA'}))

    def test_explicit_conflicts_and_different_activities_stay_separate(self):
        summary, detailed = pair()
        for changes in (
            dict(title='Block Party 2027'), dict(title='Block Party Session 2'),
            dict(title='Commuter Block Party Meet Up'), dict(location='The Barn'),
            dict(starts_at='2026-09-27T07:00:00+00:00', ends_at='2026-09-28T07:00:00+00:00'),
            dict(content_kind='student_deadline'),
        ):
            with self.subTest(changes=changes):
                self.assertFalse(same_event(summary | changes, detailed))
        timed = summary | dict(all_day=False, starts_at=detailed['starts_at'], ends_at=detailed['ends_at'])
        self.assertFalse(same_event(timed | {'starts_at': '2026-09-26T22:00:00+00:00'}, detailed))
        self.assertFalse(same_event(timed | {'ends_at': '2026-09-27T05:00:00+00:00'}, detailed))
        for title in ('General Meeting', 'Fall Social', 'Welcome Workshop'):
            self.assertFalse(same_event(summary | {'title': title}, detailed | {'title': title}))

    def test_two_siblings_are_not_duplicates_even_when_their_fields_match(self):
        summary, detailed = pair()
        sibling = detailed | {'id': summary['id'] + '-abcdef'}
        self.assertFalse(same_event(summary, sibling))

    def test_ambiguous_summaries_cannot_bridge_different_events(self):
        summary, detailed = pair()
        for changes in (
            dict(location='The Barn'),
            dict(starts_at='2026-09-27T01:00:00+00:00'),
            dict(ends_at='2026-09-27T05:00:00+00:00'),
        ):
            other = competitor(detailed, **changes)
            for ordered in itertools.permutations([summary, detailed, other]):
                self.assertEqual(([], set(), {}), plan(list(ordered)), changes)
        # A removed competing occurrence remains evidence of ambiguity.
        other = competitor(detailed, location='The Barn')
        self.assertEqual(([], set(), {}), plan([summary, detailed], [other]))

    def test_multiple_announcements_of_one_event_do_not_create_ambiguity(self):
        summary, detailed = pair()
        repost = competitor(detailed)
        for ordered in itertools.permutations([summary, detailed, repost]):
            _, removed, replacements = plan(list(ordered))
            self.assertIn(summary['id'], removed)
            self.assertEqual(2, len(removed))
            self.assertEqual(1, len(set(replacements.values())))

    def test_locks_and_deletions_still_apply(self):
        summary, detailed = pair()
        self.assertEqual(([], {detailed['id']}, {detailed['id']: summary['id']}),
                         plan([summary | {'is_locked': True}, detailed]))
        self.assertEqual(([], {detailed['id']}, {}), plan([detailed], [summary]))
        self.assertEqual(([], set(), {}), plan([detailed | {'is_locked': True}], [summary]))


class ScheduleRepublicationTests(unittest.TestCase):
    def setUp(self):
        self.summary, self.detailed = pair()
        self.sibling = self.summary | dict(id=self.summary['id'].replace('20260926T0700Z', '20261107T0800Z'),
                                            title='Homecoming 2026', starts_at='2026-11-07T08:00:00+00:00',
                                            ends_at='2026-11-08T08:00:00+00:00')
        self.key = 'instagram:post:3986151799102313494'
        self.payload = {'status': 'complete', 'result': {'occurrences': [self.summary, self.sibling],
                                                        'schedule': None}}
        self.update = {'source_key': self.key, 'assessment': self.payload,
                       'rows': [self.summary, self.sibling], 'known_event_ids': []}
        self.registry = {
            self.key: {'assessment': self.payload,
                       'event_ids': [self.detailed['id'], self.sibling['id']],
                       'known_event_ids': [self.summary['id'], self.sibling['id'], self.detailed['id']]},
            'instagram:post:3987699302558500071': {'event_ids': [self.detailed['id']]},
        }

    def published(self, *, extra_rows=(), updates=None, live=None):
        context = live if live is not None else {r['id']: r for r in [self.detailed, *extra_rows]}
        kept = publication._withhold_reconciled(copy.deepcopy(updates or [self.update]),
                                               self.registry, context)
        return [row['id'] for update in kept for row in update['rows']]

    def test_merged_occurrence_stays_merged_while_siblings_keep_publishing(self):
        self.assertEqual([self.sibling['id']], self.published())
        self.registry[self.key]['event_ids'] = [self.sibling['id']]
        self.assertEqual([self.sibling['id']], self.published())

    def test_missing_or_changed_canonical_event_restores_the_summary(self):
        self.assertIn(self.summary['id'], self.published(live={}))
        moved = self.detailed | {'starts_at': '2026-09-28T23:00:00+00:00'}
        self.assertIn(self.summary['id'], self.published(live={moved['id']: moved}))

    def test_changed_assessment_is_republished_for_fresh_reconciliation(self):
        update = copy.deepcopy(self.update)
        update['assessment']['result']['reason'] = 'The schedule changed.'
        self.assertIn(self.summary['id'], self.published(updates=[update]))

    def test_new_competing_event_restores_an_ambiguous_summary(self):
        other = competitor(self.detailed, location='The Barn')
        self.assertIn(self.summary['id'], self.published(extra_rows=[other]))
        fresh = {'source_key': 'instagram:post:999', 'assessment': {}, 'rows': [other]}
        self.assertIn(self.summary['id'], self.published(updates=[self.update, fresh]))

    def test_publication_reads_competitors_even_if_they_were_not_previously_merged(self):
        other = competitor(self.detailed, location='The Barn')
        with patch('db.get_imported_events', return_value=[self.detailed, other]) as fetch, \
             patch('db.get_event_rows_by_ids', return_value=[self.detailed]):
            context = publication._canonical_listings([({'media_id': '3986151799102313494'}, {})],
                                                       self.registry)
        fetch.assert_called_once_with()
        self.assertEqual({self.detailed['id'], other['id']}, set(context))

    def test_a_recurring_schedule_with_a_tba_venue_also_reads_competitors(self):
        self.registry[self.key]['assessment'] = {
            'result': {'occurrences': [], 'schedule': {'location': 'TBA'}}}
        with patch('db.get_imported_events', return_value=[self.detailed]) as fetch:
            publication._canonical_listings([({'media_id': '3986151799102313494'}, {})], self.registry)
        fetch.assert_called_once_with()

    def test_detailed_schedules_only_read_their_saved_replacements(self):
        self.registry[self.key]['assessment'] = {
            'result': {'occurrences': [self.detailed, self.detailed], 'schedule': None}}
        with patch('db.get_imported_events') as full_scan, \
             patch('db.get_event_rows_by_ids', return_value=[self.detailed]) as fetch:
            publication._canonical_listings([({'media_id': '3986151799102313494'}, {})], self.registry)
        full_scan.assert_not_called()
        fetch.assert_called_once_with([self.detailed['id']])


if __name__ == '__main__':
    unittest.main()
