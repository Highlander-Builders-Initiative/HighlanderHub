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
            ("Graduate theses showcase", "academic"),
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

    def test_sorority_recruitment_resolves_to_social(self) -> None:
        self.assertEqual(
            "social",
            infer_category_from_text("Sorority Recruitment Week", ""),
        )

    def test_community_volunteering_alias(self) -> None:
        self.assertEqual(
            "community",
            infer_category_from_text("Community volunteering day", ""),
        )

    def test_multi_word_aliases_match_line_break_whitespace(self) -> None:
        self.assertEqual(
            "club",
            infer_category_from_text("general\nmeeting tonight", ""),
        )

    def test_bare_performance_is_excluded_from_keyword_fallback(self) -> None:
        self.assertEqual(
            "community",
            infer_category_from_text("Addressing Employee Performance Issues", ""),
        )

    def test_bare_service_is_excluded_from_keyword_fallback(self) -> None:
        self.assertEqual(
            "community",
            infer_category_from_text("Thriving After Military Service", ""),
        )

    def test_hyphenated_and_substring_terms_do_not_match(self) -> None:
        self.assertEqual(
            "community",
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


if __name__ == "__main__":
    unittest.main()
