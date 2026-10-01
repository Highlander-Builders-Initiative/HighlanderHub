"""Source-backed regressions from Actions run #60, September 30, 2026."""
import copy
import json
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import assessed_events as publication
import content_assessment as semantic
from classify import detect_free_food, title_offers_boba
from event_dates import evidence_dates
from instagram_rows import build_instagram_row

CASES = json.loads((Path(__file__).parent / 'fixtures/sep30-sources.json').read_text())
NOW = '2026-09-30T20:56:25Z'


def rows(name, result=None):
    case = CASES[name]
    payload = copy.deepcopy(case['assessment'])
    if result is not None:
        payload.update(status='complete', result=semantic.validate(
            semantic._attach_source_quotes(result, payload['source']), payload['source']))
    return publication.post_rows(case['record'], case['cached'], payload, {}, NOW)[0]


class FoodOfferTests(unittest.TestCase):
    def test_new_posts_with_affirmative_food_offers_are_detected(self):
        for name in ('bsma_boba', 'nasp_food', 'csa_drinks'):
            with self.subTest(name=name):
                self.assertTrue(rows(name)[0]['has_free_food'])

    def test_negated_paid_and_bring_your_own_food_are_not_offers(self):
        for text in ('No free food provided.', 'No refreshments.', 'Refreshments for purchase.',
                     'Bring your own refreshments.', 'Free pizza $5 per slice',
                     'Food is not provided.', 'No free tacos.', 'Boba $6 per cup',
                     'Refreshments will not be provided.', 'Free food with purchase',
                     'Free merch at Boba Tea House'):
            with self.subTest(text=text):
                self.assertFalse(detect_free_food(text))
        for title in ('No free boba', 'Boba for purchase', 'Boba Social $5'):
            self.assertFalse(title_offers_boba(title))
        self.assertFalse(title_offers_boba('Games & Boba', 'Boba $6 per cup'))

    def test_negation_does_not_cancel_a_separate_offer(self):
        self.assertTrue(detect_free_food('No free pizza, but free tacos for attendees.'))
        self.assertTrue(detect_free_food('Tickets $5. Free pizza provided.'))
        self.assertTrue(detect_free_food('Free tacos for attendees.'))
        self.assertFalse(detect_free_food('Free admission', 'boba'))

    def test_restaurant_trips_coffee_chats_and_priced_food_are_not_offers(self):
        for text in ('Come join us for dinner at Olive Garden!', 'Enjoy dinner at Pho Ha, bring cash',
                     'Come for coffee chats with our officers', 'Drinks available for $2',
                     'Pizza will be provided for $3'):
            with self.subTest(text=text):
                self.assertFalse(detect_free_food(text))


class SessionPolicyTests(unittest.TestCase):
    def test_a_followup_fundraiser_does_not_hide_the_hospice_timeline(self):
        published = rows('hospice_timeline')
        self.assertEqual({'Involvement Fair', 'Night at the SRC', 'Tabling', 'First Member Meeting'},
                         {r['title'] for r in published})
        self.assertTrue(all(r['content_kind'] == 'student_event' for r in published))
        self.assertTrue(all(not r['has_free_food'] for r in published))

    def test_a_student_org_food_sale_is_excluded(self):
        self.assertEqual([], rows('food_sale'))

    def test_flyer_fine_print_does_not_make_a_fundraiser(self):
        row = build_instagram_row(
            {'media_id': '1', 'handle': 'club', 'caption': 'GBM tonight!', 'posted_at': '2026-09-30T18:00:00Z'},
            {'title': 'General Meeting', 'starts_at': '2026-10-05T18:00:00-07:00', 'description': 'GBM tonight!'},
            identity_handle='club', host_handle='club', account_meta={}, text='', image_url=None,
            qr_urls=[], scraped_at=NOW, assessed_kind='activity',
            policy_text='GBM tonight!\nGENERAL MEETING\nDonations welcome via Venmo')
        self.assertEqual('student_event', row['content_kind'])

    def test_a_post_announcing_its_own_fundraiser_after_class_stays_a_fundraiser(self):
        caption = 'Join our boba fundraiser after class! $6 a cup'
        for session in (None, '20261006T0100Z'):
            with self.subTest(session=session):
                row = build_instagram_row(
                    {'media_id': '1', 'handle': 'club', 'caption': caption, 'posted_at': '2026-09-30T18:00:00Z'},
                    {'title': 'Boba Sale', 'starts_at': '2026-10-05T18:00:00-07:00', 'description': caption},
                    identity_handle='club', host_handle='club', account_meta={}, text=caption, image_url=None,
                    qr_urls=[], scraped_at=NOW, assessed_kind='activity', session=session, policy_text=caption)
                self.assertEqual('fundraiser', row['content_kind'])

    def test_a_details_link_is_kept_without_claiming_registration(self):
        published = rows('taps_trip')
        self.assertEqual(2, len(published))
        for row in published:
            self.assertEqual('https://events.ucr.edu/event/ride-to-the-cheech', row['rsvp_url'])
            self.assertFalse(row['rsvp_required'])

    def test_a_printed_short_registration_link_is_recovered(self):
        row = rows('cmsp_link')[0]
        self.assertEqual('https://tinyurl.com/UCRCMSP26', row['rsvp_url'])
        self.assertTrue(row['rsvp_required'])

    def test_shared_food_and_registration_do_not_leak_to_other_sessions(self):
        case = copy.deepcopy(CASES['hospice_timeline'])
        result = case['assessment']['result']
        result['occurrences'] = result['occurrences'][:2]
        source = case['assessment']['source']
        source['texts']['slide_1_ocr'] = ('30th Sept - Involvement Fair\n9:30 AM - 2 PM\n'
            'Free tacos. RSVP https://forms.gle/fair\n6th Oct Night at the SRC\n4 PM - 6 PM\n')
        source['texts']['caption'] = 'Free tacos at the fair! RSVP to the fair.'
        case['record']['caption'] = source['texts']['caption']
        case['cached']['images'][0]['ocr_text'] = source['texts']['slide_1_ocr']
        case['cached']['images'][0]['qr_urls'] = []
        published = publication.post_rows(case['record'], case['cached'], case['assessment'], {}, NOW)[0]
        fair, night = published
        self.assertTrue(fair['has_free_food'])
        self.assertTrue(fair['rsvp_required'])
        self.assertFalse(night['has_free_food'])
        self.assertFalse(night['rsvp_required'])
        self.assertIsNone(night['rsvp_url'])
        self.assertEqual(source['texts']['caption'], night['description'])


class NumericDateTests(unittest.TestCase):
    def test_the_ama_refusal_was_a_false_rejection(self):
        result = CASES['ama_recruitment']['assessment']['validation_attempts'][-1]['response']
        self.assertEqual('2026-10-05T07:00:00+00:00', rows('ama_recruitment', result)[0]['starts_at'])

    def test_pfv_date_column_is_supported_without_inventing_later_clock_times(self):
        case = CASES['pfv_schedule']
        result = copy.deepcopy(case['assessment']['validation_attempts'][-1]['response'])
        # The saved model response got the Nov 2 midnight's DST offset wrong.
        result['occurrences'][2]['starts_at'] = '2026-11-02T00:00:00-08:00'
        published = rows('pfv_schedule', result)
        self.assertEqual(4, len(published))
        self.assertFalse(published[0]['all_day'])
        self.assertTrue(all(row['all_day'] for row in published[1:]))

    def test_fractions_prices_and_rooms_still_supply_no_date(self):
        for text in ('Recruitment costs 1/2 price boba', 'Room 10/5', 'Use 1/2 cup milk',
                     'Meeting 1/2 hour early', 'Workshop 2/3 full!',
                     'General meeting schedule\n1/2 cup milk\n3/4 cup flour'):
            with self.subTest(text=text):
                self.assertEqual(set(), evidence_dates(text))

    def test_unknown_dates_are_not_promoted_from_publication_time(self):
        case = CASES['safe_ride']['assessment']
        self.assertFalse(semantic._day_supported(date(2026, 10, 1), 'Monday - Friday', case['source']))


class SourceConflictTests(unittest.TestCase):
    def test_distinct_same_day_info_sessions_are_not_a_source_conflict(self):
        source = {'posted_at': '2026-09-30T20:00:00Z', 'texts': {
            'biology': 'Biology Info Night October 5 6-7 PM',
            'chemistry': 'Chemistry Info Night October 5 8-9 PM'}}
        for field, hour in [('biology', 18), ('chemistry', 20)]:
            evidence = [{'field': field, 'quote': source['texts'][field]}]
            semantic.validate_occurrence({
                'title': field.title() + ' Info Night', 'all_day': False, 'location': '',
                'starts_at': f'2026-10-05T{hour}:00:00-07:00',
                'ends_at': f'2026-10-05T{hour+1}:00:00-07:00',
                'date_evidence': evidence, 'activity_evidence': evidence, 'location_evidence': []}, source)

    def test_crf_caption_and_flyer_conflict_even_when_only_the_flyer_is_cited(self):
        case = CASES['crf_conflict']['assessment']
        result = copy.deepcopy(case['result'])
        result['occurrences'][0]['date_evidence'] = [
            {'field': 'slide_1_ocr', 'quote': case['source']['texts']['slide_1_ocr']}]
        with self.assertRaisesRegex(ValueError, 'Conflicting source clock'):
            semantic.validate(result, case['source'])
        # Picking the caption instead, or dropping the time, cannot bypass it.
        result['occurrences'][0].update(starts_at='2026-10-05T10:00:00-07:00',
                                        ends_at='2026-10-05T11:00:00-07:00')
        result['occurrences'][0]['date_evidence'] = [{'field': 'caption'}]
        with self.assertRaisesRegex(ValueError, 'Conflicting source clock'):
            semantic.validate(semantic._attach_source_quotes(result, case['source']), case['source'])
        result['occurrences'][0].update(all_day=True, starts_at='2026-10-05T00:00:00-07:00', ends_at=None)
        with self.assertRaisesRegex(ValueError, 'Conflicting source clock'):
            semantic.validate(semantic._attach_source_quotes(result, case['source']), case['source'])

    def test_drag_workshop_keeps_the_printed_noon_start_with_its_schedule_citation(self):
        case = CASES['drag_workshop']['assessment']
        result = copy.deepcopy(case['validation_attempts'][0]['response'])
        result['occurrences'][0]['ends_at'] = None
        self.assertEqual('2026-10-10T19:00:00+00:00', rows('drag_workshop', result)[0]['starts_at'])

    def test_shared_registration_deadline_still_applies_to_both_office_hours(self):
        case = copy.deepcopy(CASES['hospice_timeline'])
        case['record']['caption'] = 'Register by Monday, October 5!'
        for occurrence in case['assessment']['result']['occurrences']:
            occurrence['date_evidence'].append({'field': 'caption'})
        published = publication.post_rows(case['record'], case['cached'], case['assessment'], {}, NOW)[0]
        self.assertTrue(all(r['rsvp_required'] for r in published))


if __name__ == '__main__':
    unittest.main()
