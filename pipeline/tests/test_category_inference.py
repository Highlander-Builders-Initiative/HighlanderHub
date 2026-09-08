from __future__ import annotations

import sys
import unittest
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from category_inference import (
    infer_category_from_text,
    infer_hlink_category,
    infer_localist_category,
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

    def test_source_term_weight_beats_description(self) -> None:
        self.assertEqual(
            "academic",
            infer_category_from_text("", "soccer", ["lecture"]),
        )


class LocalistCategoryTests(unittest.TestCase):
    def test_athletics_override_wins_over_types_and_title(self) -> None:
        self.assertEqual(
            "sports",
            infer_localist_category(
                ["Seminars"],
                [],
                has_athletics=True,
                title="Art gallery opening",
                description="",
            ),
        )

    def test_whole_label_type_precedence(self) -> None:
        cases = (
            (["Academic Calendar"], "academic"),
            (["Seminars"], "academic"),
            (["Recreation", "Social"], "sports"),
        )
        for types, expected in cases:
            with self.subTest(types=types):
                self.assertEqual(
                    expected,
                    infer_localist_category(types, [], False, "", ""),
                )

    def test_arts_before_athletics_type_precedence(self) -> None:
        self.assertEqual(
            "arts",
            infer_localist_category(["Arts", "Athletics"], [], False, "", ""),
        )


class HlinkCategoryTests(unittest.TestCase):
    def test_theme_precedence_over_category_names(self) -> None:
        self.assertEqual(
            "sports",
            infer_hlink_category(
                "Athletics",
                ["Concert", "Performance"],
                "Art show",
                "",
            ),
        )

    def test_category_name_table_before_text_fallback(self) -> None:
        cases = (
            (None, ["Concert", "Free Food"], "Lecture night", "arts"),
            (None, ["Free Food"], "Graduate thesis defense", "academic"),
            (None, ["Performance"], "Addressing Employee Performance Issues", "arts"),
        )
        for theme, category_names, title, expected in cases:
            with self.subTest(title=title):
                self.assertEqual(
                    expected,
                    infer_hlink_category(theme, category_names, title, ""),
                )


if __name__ == "__main__":
    unittest.main()
