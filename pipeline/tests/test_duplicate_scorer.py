"""The shadow duplicate scorer: its shipped model, and that it only reports."""
import copy
import json
import logging
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import db  # noqa: E402
import duplicate_scorer as scorer  # noqa: E402
import reconcile_events as reconcile  # noqa: E402

# Two co-hosts' posts for one meeting, and two clubs' unrelated speakers.
CARDS = (('Hands On Health Care X Project Sunshine: Cards For Kids', 'handsonhealthcare_ucr'),
         ('Cards for Kids: Project Sunshine x Hands on Healthcare Collab Meeting', 'psucriverside'))
SPEAKERS = (('TASC Guest Speaker: Joe Sabo', 'tasc_ucr'), ('UBA Guest Speaker: Logan Jones', 'ubaucr'))
DATA = json.loads((Path(__file__).parent / 'fixtures/duplicate-scorer-pairs.json').read_text())
ROWS, CORPUS = DATA['rows'], DATA['corpus']
MODEL = scorer.Scorer()
NOW = datetime(2026, 11, 13, 22, tzinfo=timezone.utc)


def pair(a, b):
    return copy.deepcopy(ROWS[a]), copy.deepcopy(ROWS[b])


def titled(title, handle):
    return next(copy.deepcopy(row) for row in ROWS.values()
                if row['title'] == title and row['host_handle'] == handle)


class ShippedModelTests(unittest.TestCase):
    def test_model_weighs_exactly_the_features_computed(self):
        self.assertEqual(set(scorer.FEATURES), set(MODEL.model['weights']))
        self.assertLess(MODEL.dismiss_below, 0.5)
        self.assertGreaterEqual(MODEL.merge_at, 0.95)

    def test_every_feature_is_a_fraction_and_scores_ignore_order(self):
        for labelled in DATA['pairs']:
            left, right = pair(labelled['a'], labelled['b'])
            values = scorer.features(left, right, CORPUS)
            self.assertEqual(set(scorer.FEATURES), set(values))
            for name, value in values.items():
                self.assertTrue(0.0 <= value <= 1.0, (name, value, labelled))
            self.assertAlmostEqual(MODEL.score(left, right, CORPUS), MODEL.score(right, left, CORPUS))

    def test_no_labelled_different_pair_would_merge(self):
        verdicts = {'duplicate': [], 'different': []}
        for labelled in DATA['pairs']:
            left, right = pair(labelled['a'], labelled['b'])
            if labelled['label'] in verdicts and labelled['source'] != 'rules':
                verdicts[labelled['label']].append(MODEL.verdict(MODEL.score(left, right, CORPUS)))
        self.assertNotIn('merge', verdicts['different'])
        # Most unrelated pairs leave the queue, and almost no duplicate does.
        self.assertGreater(verdicts['different'].count('dismiss'), 0.8 * len(verdicts['different']))
        self.assertLessEqual(verdicts['duplicate'].count('dismiss'), 2)
        # The merge threshold is deliberately timid until admin decisions back it.
        self.assertGreaterEqual(verdicts['duplicate'].count('merge'), 5)
        self.assertGreater(verdicts['duplicate'].count('review'), 0.8 * len(verdicts['duplicate']))

    def test_known_pairs_land_where_a_person_would_put_them(self):
        self.assertEqual('merge', MODEL.verdict(MODEL.score(titled(*CARDS[0]), titled(*CARDS[1]), CORPUS)))
        self.assertEqual('dismiss', MODEL.verdict(MODEL.score(titled(*SPEAKERS[0]), titled(*SPEAKERS[1]), CORPUS)))
        # A stall at the fair shares the fair's name, slot and lawn.
        fair, stall = titled('Once Upon a Faire', 'aspb_ucr'), titled('Depop at UCR Pop-up at Once Upon a Faire',
                                                                       'ucrstylesociety')
        self.assertNotEqual('merge', MODEL.verdict(MODEL.score(fair, stall, CORPUS)))

    def test_pairs_that_cannot_be_one_occasion_score_zero(self):
        left, right = titled(*CARDS[0]), titled(*CARDS[1])
        self.assertGreater(MODEL.score(left, right, CORPUS), 0.9)
        for changed in (right | {'starts_at': '2026-11-04T00:30:00+00:00'},
                        right | {'content_kind': 'student_deadline'},
                        right | {'title': right['title'] + ' 2027'},
                        right | {'id': left['id']}, right | {'starts_at': None}):
            self.assertFalse(scorer.comparable(left, changed), changed)
            self.assertEqual(0.0, MODEL.score(left, changed, CORPUS))
        # Two sessions of one post share its caption and flyer.
        first = left | {'id': 'ig_club_p1-20261103T0030Z'}
        self.assertEqual(0.0, MODEL.score(first, first | {'id': 'ig_club_p1-20261103T0230Z'}, CORPUS))

    def test_rare_words_come_from_how_many_accounts_use_them(self):
        corpus = scorer.word_accounts([
            {'id': '1', 'host_handle': 'a', 'title': 'General Meeting'},
            {'id': '2', 'host_handle': 'a', 'title': 'General Meeting: Diwali'},
            {'id': '3', 'host_handle': 'b', 'title': 'General Meeting'},
            {'id': '4', 'host_handle': 'c', 'title': 'The Meeting'}])
        self.assertEqual(3, corpus['accounts'])
        self.assertEqual({'general': 2, 'meeting': 3, 'diwali': 1}, corpus['words'])
        self.assertGreater(scorer._rarity('diwali', corpus), scorer._rarity('meeting', corpus))


class ShadowReportTests(unittest.TestCase):
    def setUp(self):
        self.merge = [titled(*CARDS[0]), titled(*CARDS[1])]
        self.apart = [titled(*SPEAKERS[0]), titled(*SPEAKERS[1])]
        self.rows = [*self.merge, *self.apart]
        self.before = min(reconcile._parse_instant(row['starts_at']) for row in self.rows)

    def report(self, reviews=(), rows=None, now=None):
        # Word rarity as the whole feed gives it, not these four listings.
        with patch.object(scorer, 'word_accounts', return_value=CORPUS):
            return scorer.shadow_report(rows or self.rows, list(reviews), now=now or self.before, scorer=MODEL)

    def test_reports_merges_and_queue_dismissals_for_upcoming_pairs(self):
        report = self.report()
        self.assertEqual([('merge', {row['id'] for row in self.merge}), ('dismiss', {row['id'] for row in self.apart})],
                         [(p['verdict'], {p['left']['id'], p['right']['id']}) for p in report['pairs']])
        self.assertEqual([True, True], [p['queued'] for p in report['pairs']])
        self.assertEqual((2, 2), (report['scored'], report['queued']))
        # A pair the queue never saw is reported only when it would merge.
        with patch.object(reconcile, 'review_candidates', return_value=[]):
            self.assertEqual([('merge', False)], [(p['verdict'], p['queued']) for p in self.report()['pairs']])
        # Ended listings need no decision.
        ended = self.report(now=NOW)
        self.assertEqual((0, []), (ended['scored'], ended['pairs']))

    def test_pairs_the_rules_merge_or_an_admin_decided_are_not_scored(self):
        decided = [{'event_id': a['id'], 'other_event_id': b['id'], 'status': 'different',
                    'event_snapshot': a, 'other_snapshot': b}
                   for a, b in [sorted(self.merge, key=lambda row: row['id'])]]
        report = self.report(decided)
        self.assertEqual(['dismiss'], [p['verdict'] for p in report['pairs']])
        self.assertEqual(1, report['scored'])
        with patch.object(reconcile, 'same_event', return_value=True):
            self.assertEqual(0, self.report()['scored'])

    def test_admin_decisions_are_scored_on_their_snapshots(self):
        def decision(status, rows):
            a, b = sorted(rows, key=lambda row: row['id'])
            return {'event_id': a['id'], 'other_event_id': b['id'], 'status': status,
                    'event_snapshot': a, 'other_snapshot': b}
        reviews = [decision('duplicate', self.merge), decision('different', self.apart),
                   {'event_id': 'ig_a', 'other_event_id': 'ig_b', 'status': 'pending',
                    'event_snapshot': None, 'other_snapshot': None},
                   {'event_id': 'ig_c', 'other_event_id': 'ig_d', 'status': 'duplicate',
                    'event_snapshot': None, 'other_snapshot': None}]
        report = self.report(reviews, rows=[self.rows[0]])
        self.assertEqual({'duplicate': {'merge': 1}, 'different': {'dismiss': 1}}, report['agreement'])
        self.assertEqual([], report['disagreements'])
        # The admin's opposite calls are the disagreements worth reading.
        flipped = self.report([decision('different', self.merge), decision('duplicate', self.apart)],
                              rows=[self.rows[0]])
        self.assertEqual({'duplicate': {'dismiss': 1}, 'different': {'merge': 1}}, flipped['agreement'])
        self.assertEqual(['different', 'duplicate'], sorted(d[0] for d in flipped['disagreements']))


class ShadowStageTests(unittest.TestCase):
    def test_stage_logs_and_writes_nothing(self):
        rows = [titled(*CARDS[0]), titled(*CARDS[1])]
        database = Mock()
        with patch.object(reconcile, '_reconciliation_rows', return_value=rows), \
             patch.object(db, 'get_duplicate_reviews', return_value=[]), \
             patch.object(db, 'get_decided_duplicate_reviews', return_value=[]), \
             patch.object(db, 'client', return_value=database), \
             patch.object(scorer, 'word_accounts', return_value=CORPUS), \
             patch.object(scorer, 'datetime') as clock, \
             self.assertLogs('pipeline.duplicate_scorer', level='INFO') as logs:
            clock.now.return_value = min(reconcile._parse_instant(row['starts_at']) for row in rows)
            scorer.main()
        database.assert_not_called()
        self.assertEqual([], database.mock_calls)
        text = '\n'.join(logs.output)
        self.assertIn('Shadow scorer would merge (', text)
        self.assertIn('1 pairs scored, 1 of them queued; would merge 1, dismiss 0, leave 0 for review', text)

    def test_stage_never_fails_the_run(self):
        with patch.object(db, 'get_duplicate_reviews', side_effect=RuntimeError('database down')), \
             self.assertLogs('pipeline.duplicate_scorer', level='ERROR') as logs:
            scorer.main()
        self.assertIn('nothing was changed', logs.output[0])

    def test_decided_reviews_page_through_admin_decisions_only(self):
        query = Mock()
        query.table.return_value = query.select.return_value = query.neq.return_value = query
        query.order.return_value = query.range.return_value = query
        query.execute.return_value.data = [{'event_id': 'ig_a', 'other_event_id': 'ig_b', 'status': 'different'}]
        with patch.object(db, 'client', return_value=query):
            self.assertEqual(query.execute.return_value.data, db.get_decided_duplicate_reviews())
        query.table.assert_called_once_with('event_duplicate_reviews')
        query.neq.assert_called_once_with('status', 'pending')
        self.assertIn('event_snapshot', query.select.call_args.args[0])


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    unittest.main()
