"""Source-backed regressions from the October 1 runs and live publication audit."""
import copy
import itertools
import json
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import assessed_events as publication
import content_assessment as semantic
import reconcile_events as reconcile
from classify import classify_content_kind

FIXTURES = Path(__file__).parent / 'fixtures'
CASES = json.loads((FIXTURES / 'oct1-sources.json').read_text())
DUPLICATES = json.loads((FIXTURES / 'oct1-duplicates.json').read_text())
NOW = '2026-10-02T05:15:00Z'


def rows(name):
    case = CASES[name]
    return publication.post_rows(case['record'], case['cached'], case['assessment'], {}, NOW)[0]


class ClassificationTests(unittest.TestCase):
    def test_a_blood_drive_is_an_activity_with_food(self):
        published = rows('blood_drive')
        self.assertEqual(1, len(published))
        self.assertEqual('student_event', published[0]['content_kind'])
        self.assertTrue(published[0]['has_free_food'])

    def test_monetary_requests_still_make_a_fundraiser(self):
        for description in ('Blood drive: donate $5 to support our club.',
                            'Blood donations and a bake sale.', 'Donate to our fundraiser.'):
            self.assertEqual('fundraiser', classify_content_kind(
                'instagram', title='Blood Drive', description=description, assessed_kind='activity'))

    def test_a_sibling_fundraiser_does_not_hide_ama_networking(self):
        published = rows('ama_networking')
        self.assertEqual(['Getting to Know AMA + Speed Networking'], [r['title'] for r in published])
        self.assertFalse(published[0]['has_free_food'])
        self.assertTrue(published[0]['rsvp_required'])
        self.assertEqual(CASES['ama_networking']['record']['caption'], published[0]['description'])

    def test_a_sibling_fundraiser_paragraph_leaves_the_sessions_own_caption(self):
        case = copy.deepcopy(CASES['ama_networking'])
        caption = ('Our first GBM is here! Free pizza will be provided 🍕\n'
                   'October 5 | 6:30-8:30 PM | Pentland FG\n\n'
                   '🍦 Afterwards, support us at our Yogurtland fundraiser, October 5, 9-10:30 PM!')
        case['record']['caption'] = case['assessment']['source']['texts']['caption'] = caption
        # Only the meeting cites the caption; the fundraiser cites its flyer.
        networking, fundraiser = case['assessment']['result']['occurrences']
        networking['title'] = 'General Body Meeting'
        for key in ('activity_evidence', 'date_evidence', 'location_evidence'):
            fundraiser[key] = [c for c in fundraiser.get(key) or [] if c['field'] != 'caption']
            for citation in networking.get(key) or []:
                if citation['field'] == 'caption':
                    citation['quote'] = caption
        published = publication.post_rows(case['record'], case['cached'], case['assessment'], {}, NOW)[0]
        self.assertEqual(['General Body Meeting'], [r['title'] for r in published])
        self.assertTrue(published[0]['has_free_food'])

    def test_calendar_fundraiser_fine_print_does_not_hide_other_sessions(self):
        published = rows('bsib_calendar')
        self.assertIn('Professional Development w NSA', [r['title'] for r in published])
        self.assertIn('Guest Speaker Event', [r['title'] for r in published])

    def test_the_continuous_cecert_fair_keeps_its_own_hours(self):
        published = rows('cecert_offerings')
        self.assertEqual(3, len(published))
        fair = next(r for r in published if 'Resource Fair' in r['title'])
        self.assertEqual('2026-10-06T16:00:00+00:00', fair['starts_at'])
        self.assertEqual('2026-10-06T22:30:00+00:00', fair['ends_at'])
        semantic.validate(copy.deepcopy(CASES['cecert_offerings']['assessment']['result']),
                          CASES['cecert_offerings']['assessment']['source'])

    def test_explicit_application_cutoffs_cannot_be_hidden_as_windows(self):
        for name in ('lmsa_member', 'lmsa_mentor'):
            case = CASES[name]['assessment']
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'dated application cutoff'):
                semantic.validate(copy.deepcopy(case['result']), case['source'])

    def test_an_application_window_without_an_action_cutoff_stays_nonpublic(self):
        case = copy.deepcopy(CASES['lmsa_member']['assessment'])
        case['source']['texts'] = {'caption': 'General member applications are open September 30 - October 14.'}
        for key in ('activity_evidence', 'date_evidence'):
            case['result'][key] = [{'field': 'caption'}]
        result = semantic._attach_source_quotes(case['result'], case['source'])
        self.assertEqual('application', semantic.validate(result, case['source'])['kind'])
        # A dateless cutoff line does not borrow the next line's session date,
        # and a closed application has no upcoming cutoff to publish.
        for caption in ('Applications are due on a rolling basis\nInfo session Oct 7 at 6 PM',
                        'Applications closed Sept 28. Next cycle opens in winter.'):
            case['source']['texts'] = {'caption': caption}
            result = semantic._attach_source_quotes(copy.deepcopy(case['result']), case['source'])
            self.assertEqual('application', semantic.validate(result, case['source'])['kind'])


class RelativeDateTests(unittest.TestCase):
    def test_visually_confirmed_october_ocr_spelling_is_supported(self):
        source = {'posted_at': '2026-09-29T20:00:00Z'}
        self.assertTrue(semantic._day_supported(date(2026, 10, 6), 'tuesday, oet. 6 5:00 pm', source))
        self.assertFalse(semantic._day_supported(date(2026, 10, 7), 'tuesday, oet. 6 5:00 pm', source))

    def test_next_week_on_tuesday_is_an_explicit_calendar_week(self):
        case = CASES['dinner_next_week']['assessment']
        self.assertTrue(semantic._day_supported(date(2026, 10, 6),
                                               case['source']['texts']['caption'], case['source'], week_scoped=True))
        for wrong in (date(2026, 9, 29), date(2026, 10, 13)):
            self.assertFalse(semantic._day_supported(wrong, case['source']['texts']['caption'],
                                                    case['source'], week_scoped=True))

    def test_next_week_dates_only_the_weekdays_it_names(self):
        source = {'posted_at': '2026-10-01T23:00:00Z'}
        text = 'We meet every Monday at 7 PM. Next week on Tuesday and Thursday we have socials!'
        for day in (date(2026, 10, 6), date(2026, 10, 8)):
            self.assertTrue(semantic._day_supported(day, text, source, week_scoped=True))
        self.assertFalse(semantic._day_supported(date(2026, 10, 5), text, source, week_scoped=True))

    def test_bare_and_standing_weekdays_remain_unsupported(self):
        source = {'posted_at': '2026-10-01T23:00:00Z'}
        for text in ('Next Tuesday at 7 PM', 'Every Tuesday at 7 PM', 'See you Tuesday!',
                     'Weekly meetings; join next week!', 'Week 2, Tuesday at 7 PM'):
            self.assertFalse(semantic._day_supported(date(2026, 10, 6), text, source, week_scoped=True))

    def test_a_monthly_caption_cannot_hide_one_sessions_clock_conflict(self):
        source = {'posted_at': '2026-10-01T23:00:00Z', 'texts': {
            'caption': 'Fall Reception\nOctober 10 | 6-9pm\n\nFilm Screening\nOctober 20 | 7pm',
            'slide_1_ocr': 'FALL RECEPTION\nOctober 10, 2026\n6:00-8:00PM'}}
        occurrence = {'title': 'Fall Reception', 'starts_at': '2026-10-10T18:00:00-07:00',
                      'ends_at': '2026-10-10T21:00:00-07:00', 'all_day': False, 'location': '',
                      'location_evidence': [], 'activity_evidence': [{'field': 'caption', 'quote': source['texts']['caption']}],
                      'date_evidence': [{'field': 'caption', 'quote': source['texts']['caption']}]}
        with self.assertRaisesRegex(ValueError, 'Conflicting source clock'):
            semantic.validate_occurrence(occurrence, source)

    def test_a_caption_time_correction_requires_the_corrected_clocks(self):
        source = {'posted_at': '2026-10-01T23:00:00Z', 'texts': {
            'caption': 'TIME UPDATE: Fall Reception\nOctober 10 | 6-9pm',
            'slide_1_ocr': 'FALL RECEPTION\nOctober 10, 2026\n6:00-8:00PM'}}
        occurrence = {'title': 'Fall Reception', 'starts_at': '2026-10-10T18:00:00-07:00',
                      'ends_at': '2026-10-10T21:00:00-07:00', 'all_day': False, 'location': '',
                      'location_evidence': [], 'activity_evidence': [{'field': 'caption', 'quote': source['texts']['caption']}],
                      'date_evidence': [{'field': 'caption', 'quote': source['texts']['caption']},
                                        {'field': 'slide_1_ocr', 'quote': source['texts']['slide_1_ocr']}]}
        semantic.validate_occurrence(occurrence, source)
        occurrence['ends_at'] = '2026-10-10T20:00:00-07:00'
        with self.assertRaisesRegex(ValueError, 'Conflicting source clock'):
            semantic.validate_occurrence(occurrence, source)


class DuplicateTests(unittest.TestCase):
    def group(self, handle):
        return copy.deepcopy([r for r in DUPLICATES if r['host_handle'] == handle])

    def test_an_open_house_fair_and_tour_remain_distinct(self):
        fair, morning, afternoon = rows('cecert_offerings')
        self.assertEqual(([], set(), {}), reconcile.plan([fair, morning, afternoon]))
        # A historical single-row ID must not bypass the offering distinction
        # merely because it names the same source media.
        fair['id'] = fair['id'].split('-2026')[0]
        self.assertFalse(reconcile.same_event(fair, morning))

    def test_a_deadlines_program_year_can_follow_its_cutoff_year(self):
        first, second = self.group('ucrpbl.fbla')
        for row in (first, second):
            row.update(title='UC Fall 2027 Application Deadline', content_kind='student_deadline',
                       starts_at='2026-11-30T08:00:00Z', ends_at='2026-12-01T08:00:00Z',
                       all_day=True, location='')
        self.assertTrue(reconcile.same_event(first, second))
        second['title'] = 'UC Fall 2028 Application Deadline'
        self.assertFalse(reconcile.same_event(first, second))

    def test_updated_pfv_room_and_numbered_reminder_converge(self):
        group = self.group('precisionforvision')
        for ordered in itertools.permutations(group):
            updates, removed, replacements = reconcile.plan(list(ordered))
            self.assertEqual(2, len(removed))
            self.assertEqual({'ig_precisionforvision_p3997955879408138419'}, set(replacements.values()))
            survivor = next(r for r in [*updates, *ordered] if r['id'] not in removed)
            self.assertEqual('Pierce 2301', survivor['location'])

    def test_explicit_revised_pse_schedule_replaces_both_old_rooms(self):
        group = self.group('ucrpse')
        for ordered in itertools.permutations(group):
            _, removed, replacements = reconcile.plan(list(ordered))
            self.assertEqual(2, len(removed))
            self.assertTrue(all('p3997892115576749484-' in i for i in replacements.values()))

    def test_an_unlabelled_venue_conflict_remains_for_review(self):
        old, new = self.group('ucrpse')[:2]
        new['description'] = 'Join us for recruitment!'
        self.assertFalse(reconcile.same_event(old, new))
        new['description'] = 'NEW OFFICIAL SCHEDULE'
        new['host_handle'] = 'another_club'
        self.assertFalse(reconcile.same_event(old, new))

    def test_numbered_schedule_entry_matches_its_detailed_announcement(self):
        group = self.group('ucrpbl.fbla')
        self.assertTrue(reconcile.same_event(*group))
        self.assertEqual({group[0]['id']: group[1]['id']}, reconcile.plan(group)[2])

    def test_numbering_cannot_merge_two_explicitly_different_sessions(self):
        old, new = self.group('precisionforvision')[1:]
        old['title'] = 'PFV General Meeting #2'
        self.assertFalse(reconcile.same_event(old, new))
        old['title'] = 'PFV General Meeting'
        old['host_handle'] = 'another_club'
        self.assertFalse(reconcile.same_event(old, new))

    def test_accented_conference_teasers_resolve_to_the_timed_announcement(self):
        group = self.group('ucr_trc')
        for ordered in itertools.permutations(group):
            _, removed, replacements = reconcile.plan(list(ordered))
            self.assertEqual(2, len(removed))
            self.assertEqual({'ig_ucr_trc_p3986978176962716648'}, set(replacements.values()))

    def test_admin_locks_and_distinct_decisions_constrain_new_matches(self):
        old, new = self.group('ucrpbl.fbla')
        distinct = reconcile.Reviews(distinct=frozenset({frozenset({old['id'], new['id']})}))
        self.assertEqual(([], set(), {}), reconcile.plan([old, new], reviews=distinct))
        self.assertEqual({new['id']: old['id']}, reconcile.plan([old | {'is_locked': True}, new])[2])
        self.assertEqual(([], {new['id']}, {}), reconcile.plan([new], [old]))


if __name__ == '__main__':
    unittest.main()
