from __future__ import annotations

import sys
import unittest
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from category_inference import (
    infer_category_from_text,
)


class CategoryInferenceTests(unittest.TestCase):
    def test_explicit_regular_and_irregular_aliases(self) -> None:
        cases = (
            ("Classes for beginners", "academic"),
            ("Graduate theses night", "academic"),
            ("Open galleries night", "arts"),
        )
        for title, expected in cases:
            with self.subTest(title=title):
                self.assertEqual(expected, infer_category_from_text(title, ""))

    def test_aliases_for_one_concept_score_once(self) -> None:
        self.assertEqual(
            "arts",
            infer_category_from_text("Class classes concert", ""),
        )

    def test_exhibit_and_exhibition_forms_score_once(self) -> None:
        # Separate concepts would double-score arts and beat academic here.
        self.assertEqual(
            "academic",
            infer_category_from_text(
                "Exhibit exhibitions",
                "Lecture seminar colloquium symposium",
            ),
        )

    def test_theater_and_theatre_forms_score_once(self) -> None:
        # Separate concepts would double-score arts and beat academic here.
        self.assertEqual(
            "academic",
            infer_category_from_text(
                "Theater theatre night",
                "Lecture seminar colloquium symposium",
            ),
        )

    def test_career_option_one_aliases(self) -> None:
        self.assertEqual(
            "career",
            infer_category_from_text("Interviewing skills workshop", ""),
        )

    def test_sorority_recruitment_is_getting_involved(self) -> None:
        self.assertEqual(
            "get_involved",
            infer_category_from_text("Sorority Recruitment Week", ""),
        )

    def test_community_volunteering_alias(self) -> None:
        self.assertEqual(
            "volunteering",
            infer_category_from_text("Community volunteering day", ""),
        )

    def test_multi_word_aliases_match_line_break_whitespace(self) -> None:
        self.assertEqual(
            "get_involved",
            infer_category_from_text("general\nmeeting tonight", ""),
        )

    def test_bare_performance_is_excluded_from_keyword_fallback(self) -> None:
        self.assertEqual(
            "other",
            infer_category_from_text("Addressing Employee Performance Issues", ""),
        )

    def test_bare_service_is_excluded_from_keyword_fallback(self) -> None:
        self.assertEqual(
            "other",
            infer_category_from_text("Thriving After Military Service", ""),
        )

    def test_hyphenated_and_substring_terms_do_not_match(self) -> None:
        self.assertEqual(
            "other",
            infer_category_from_text("Classical self-defense", ""),
        )

    def test_field_weights_are_preserved(self) -> None:
        self.assertEqual(
            "academic",
            infer_category_from_text(
                "Lecture",
                "Soccer and basketball",
            ),
        )

    def test_ties_use_category_priority(self) -> None:
        self.assertEqual(
            "sports",
            infer_category_from_text("Lecture and soccer", ""),
        )

    def test_the_activity_decides_not_the_host_being_a_club(self) -> None:
        cases = (
            ("Trivia Night", "Hosted by the club for our community", "hangout"),
            ("Game Night", "", "hangout"),
            ("Welcome Picnic", "", "hangout"),
            ("Boba Social", "", "hangout"),
            ("UCR Club Swim First Practice", "", "sports"),
            ("Info Night", "Come meet the club!", "get_involved"),
            ("ASME Tabling at BCOE Student Org Fair", "", "get_involved"),
            ("Men's Club Volleyball Tryouts", "", "sports"),
            ("Tea Talk!: Black Identity", "", "academic"),
            ("Beach Cleanup", "", "volunteering"),
        )
        for title, description, expected in cases:
            with self.subTest(title=title):
                self.assertEqual(expected, infer_category_from_text(title, description))

    def test_club_and_community_are_not_activities(self) -> None:
        self.assertEqual(
            "other",
            infer_category_from_text("APEC Community Hour", "A club for our community"),
        )

    def test_caption_mentions_of_socials_and_practice_do_not_decide(self) -> None:
        self.assertEqual(
            "other",
            infer_category_from_text(
                "Mucho Gusto",
                "Follow our socials! Best practices for commuting to campus.",
            ),
        )

    def test_a_bare_meeting_gives_way_to_the_outing_it_names(self) -> None:
        self.assertEqual(
            "hangout",
            infer_category_from_text("Social Meeting: Pumpkin Patch", ""),
        )
        self.assertEqual(
            "get_involved",
            infer_category_from_text("Toastmasters Meeting", ""),
        )

    def test_host_type_confirms_a_single_caption_mention(self) -> None:
        cases = (
            ("athletics", "Cheer on the Highlanders at the tournament", "sports"),
            ("service", "We still need volunteers!", "volunteering"),
            ("arts-and-expression", "Dancers of all levels welcome", "arts"),
            ("academic-professional", "Bring your resume", "career"),
            ("fraternity-sorority", "Costume party at the house", "hangout"),
        )
        for host_type, description, expected in cases:
            with self.subTest(host_type=host_type):
                self.assertEqual(
                    expected,
                    infer_category_from_text("Lumberjack Classic", description, host_type=host_type),
                )
                self.assertEqual(
                    "other",
                    infer_category_from_text("Lumberjack Classic", description),
                )

    def test_host_type_alone_does_not_file_an_event(self) -> None:
        for host_type in ("athletics", "service", "cultural", None):
            with self.subTest(host_type=host_type):
                self.assertEqual(
                    "other",
                    infer_category_from_text("Lumberjack Classic", "", host_type=host_type),
                )

    def test_one_passing_caption_mention_is_not_a_topic(self) -> None:
        self.assertEqual(
            "other",
            infer_category_from_text(
                "Rides to Church",
                "Meet at the HUB. See you at Thursday's general meeting!",
            ),
        )
        self.assertEqual(
            "hangout",
            infer_category_from_text(
                "Day 3: Botanical Gardens and Matcha",
                "A picnic in the gardens, then the arcade.",
            ),
        )

    def test_host_type_never_outweighs_the_activity_the_title_names(self) -> None:
        self.assertEqual(
            "get_involved",
            infer_category_from_text("General Meeting", "", host_type="service"),
        )
        self.assertEqual(
            "hangout",
            infer_category_from_text("Boba Social", "", host_type="academic-professional"),
        )


if __name__ == "__main__":
    unittest.main()
