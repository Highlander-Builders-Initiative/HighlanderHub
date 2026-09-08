from __future__ import annotations

import sys
import unittest
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from category_inference import infer_category_from_text


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
