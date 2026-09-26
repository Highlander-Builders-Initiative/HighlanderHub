"""Admin decisions from the duplicate review queue override the rules."""
import copy
import itertools
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import assessed_events as publication  # noqa: E402
import db  # noqa: E402
from reconcile_events import Reviews, plan, review_candidates, same_event  # noqa: E402

ROWS = {row['id']: row for row in json.loads(
    (Path(__file__).parent / 'fixtures/sep25-duplicates.json').read_text())}
# SSA reposted USM's conference; the venues read "SoCal" and "University of
# Southern California", so no rule merges them.
USM, SSA = 'ig_unitedsikhmovement_p3984337006174941028', 'ig_ssa_ucr_p3992176458381655610'
# A schedule line and the event's own post, which the rules merge.
SOCIAL, SCHEDULE = ('ig_designingdreamsucr_p3991578622329622598',
                    'ig_designingdreamsucr_p3991225804188653761-20260925T2300Z')


def rows(*ids):
    return [copy.deepcopy(ROWS[event_id]) for event_id in ids]


def pair(a, b):
    return tuple(sorted((a, b)))


class ReviewsTests(unittest.TestCase):
    def test_queue_rows_become_merges_and_distinct_pairs(self):
        reviews = Reviews.from_queue([
            {'event_id': 'ig_a', 'other_event_id': 'ig_b', 'status': 'duplicate', 'kept_event_id': 'ig_b'},
            {'event_id': 'ig_b', 'other_event_id': 'ig_c', 'status': 'duplicate', 'kept_event_id': 'ig_c'},
            {'event_id': 'ig_d', 'other_event_id': 'ig_e', 'status': 'different', 'kept_event_id': None},
            {'event_id': 'ig_f', 'other_event_id': 'ig_g', 'status': 'pending', 'kept_event_id': None},
        ])
        self.assertEqual({'ig_a': 'ig_b', 'ig_b': 'ig_c'}, reviews.merged)
        self.assertEqual(frozenset({frozenset({'ig_d', 'ig_e'})}), reviews.distinct)
        # A listing kept once and merged away later hands on what it absorbed.
        self.assertEqual('ig_c', reviews.kept('ig_a'))
        self.assertIsNone(reviews.kept('ig_c'))
        self.assertIsNone(reviews.kept('ig_f'))

    def test_a_loop_of_merges_names_no_listing_to_keep(self):
        reviews = Reviews({SSA: USM, USM: SSA})
        self.assertEqual(USM, reviews.kept(SSA))
        self.assertEqual(([], set(), {}), plan(rows(USM, SSA), reviews=reviews))


class ReviewCandidateTests(unittest.TestCase):
    def test_a_pair_judged_different_is_not_asked_about_again(self):
        self.assertEqual([pair(USM, SSA)], [pair(a['id'], b['id']) for a, b in review_candidates(rows(USM, SSA))])
        reviews = Reviews(distinct=frozenset({frozenset({USM, SSA})}))
        self.assertEqual([], review_candidates(rows(USM, SSA), reviews=reviews))


class PlanTests(unittest.TestCase):
    def test_a_recreated_listing_rejoins_the_one_an_admin_kept(self):
        self.assertFalse(same_event(*rows(USM, SSA)))
        reviews = Reviews({SSA: USM})
        expected = plan(rows(USM, SSA), reviews=reviews)
        updates, removed, replacements = expected
        self.assertEqual({SSA: USM}, replacements)
        self.assertEqual({SSA}, removed)
        for ordered in itertools.permutations(rows(USM, SSA)):
            self.assertEqual(expected, plan(list(ordered), reviews=reviews))
        survivors = {r['id']: r for r in rows(USM, SSA) if r['id'] not in removed}
        survivors.update({r['id']: r for r in updates})
        self.assertEqual(([], set(), {}), plan(list(survivors.values()), reviews=reviews))

    def test_the_admin_choice_beats_the_rules_choice_of_listing(self):
        self.assertEqual({SCHEDULE: SOCIAL}, plan(rows(SOCIAL, SCHEDULE))[2])
        self.assertEqual({SOCIAL: SCHEDULE}, plan(rows(SOCIAL, SCHEDULE), reviews=Reviews({SOCIAL: SCHEDULE}))[2])

    def test_a_merge_waits_while_the_kept_listing_is_gone(self):
        self.assertEqual(([], set(), {}), plan(rows(SSA), reviews=Reviews({SSA: USM})))

    def test_a_pair_judged_different_never_merges(self):
        reviews = Reviews(distinct=frozenset({frozenset({SOCIAL, SCHEDULE})}))
        self.assertEqual(([], set(), {}), plan(rows(SOCIAL, SCHEDULE), reviews=reviews))

    def test_a_third_listing_cannot_bridge_a_pair_judged_different(self):
        repost = {**ROWS[SCHEDULE], 'id': 'ig_designingdreamsucr_p1-20260925T2300Z'}
        reviews = Reviews(distinct=frozenset({frozenset({SCHEDULE, repost['id']})}))
        for ordered in itertools.permutations([*rows(SOCIAL, SCHEDULE), repost]):
            replacements = plan(copy.deepcopy(list(ordered)), reviews=reviews)[2]
            self.assertNotEqual(replacements.get(SCHEDULE, SCHEDULE), replacements.get(repost['id'], repost['id']))


class RepublicationTests(unittest.TestCase):
    """The post an admin merged away is not recreated on the next run."""

    def update(self, row):
        return {'source_key': f"instagram:post:{row['id'].rsplit('_p', 1)[1]}", 'origin': 'instagram',
                'assessment': {'status': 'complete', 'result': 'decision'}, 'rows': [copy.deepcopy(row)],
                'known_event_ids': []}

    def withheld(self, reviews):
        usm, ssa = rows(USM, SSA)
        updates = [self.update(usm), self.update(ssa)]
        registry = {
            updates[0]['source_key']: {'assessment': updates[0]['assessment'],
                                       'event_ids': [USM], 'known_event_ids': [USM]},
            # merge_duplicate_events moved SSA's support onto USM's listing.
            updates[1]['source_key']: {'assessment': updates[1]['assessment'],
                                       'event_ids': [USM], 'known_event_ids': [SSA, USM]},
        }
        kept = publication._withhold_reconciled(updates, registry, {USM: usm}, {}, reviews)
        return [row['id'] for update in kept for row in update['rows']]

    def test_an_admin_merge_withholds_the_repost_the_rules_would_publish(self):
        self.assertEqual([USM, SSA], self.withheld(None))
        self.assertEqual([USM], self.withheld(Reviews({SSA: USM})))

    def test_publication_reads_decisions_only_when_a_source_was_remapped(self):
        with patch.object(publication, 'load_registry', return_value={}), \
             patch.object(publication, 'post_updates', return_value=[]) as updates, \
             patch.object(publication, 'publish', return_value={}), \
             patch('reconcile_events.load_reviews') as load:
            publication.publish_posts([], '2026-09-25T00:00:00Z', meta={}, notify=False)
        load.assert_not_called()
        self.assertIsNone(updates.call_args.kwargs['reviews'])


class QueueTests(unittest.TestCase):
    def test_the_pending_queue_follows_the_latest_run_and_decisions_stay(self):
        client = Mock()
        queue = [
            {'event_id': 'ig_a', 'other_event_id': 'ig_b', 'status': 'pending', 'kept_event_id': None},
            {'event_id': 'ig_c', 'other_event_id': 'ig_d', 'status': 'pending', 'kept_event_id': None},
            {'event_id': 'ig_e', 'other_event_id': 'ig_f', 'status': 'different', 'kept_event_id': None},
        ]
        with patch.object(db, 'client', return_value=client):
            db.queue_duplicate_reviews([('ig_b', 'ig_a'), ('ig_h', 'ig_g'), ('ig_e', 'ig_f')], queue)
        table = client.table.return_value
        table.upsert.assert_called_once_with([{'event_id': 'ig_g', 'other_event_id': 'ig_h'}],
                                             on_conflict='event_id,other_event_id', ignore_duplicates=True)
        table.delete.return_value.eq.assert_called_once_with('event_id', 'ig_c')
        table.delete.return_value.eq.return_value.eq.assert_called_once_with('other_event_id', 'ig_d')
        table.delete.return_value.eq.return_value.eq.return_value.eq.assert_called_once_with('status', 'pending')

    def test_the_queue_is_read_in_stable_pages(self):
        page = [{'event_id': f'ig_{n:04d}', 'other_event_id': 'ig_z', 'status': 'pending',
                 'kept_event_id': None} for n in range(1000)]
        query = Mock()
        for method in ('table', 'select', 'order', 'range'):
            getattr(query, method).return_value = query
        query.execute.side_effect = [types.SimpleNamespace(data=page), types.SimpleNamespace(data=page[:3])]
        with patch.object(db, 'client', return_value=query):
            self.assertEqual(1003, len(db.get_duplicate_reviews()))
        self.assertEqual([(0, 999), (1000, 1999)], [c.args for c in query.range.call_args_list])


if __name__ == '__main__':
    unittest.main()
