from __future__ import annotations

import sys
import unittest
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from classify import classify_content_kind  # noqa: E402


class ClassifyContentKindTests(unittest.TestCase):
    def test_fundraiser_terms_win_for_any_origin(self) -> None:
        self.assertEqual(
            "fundraiser",
            classify_content_kind(
                "instagram",
                title="Boba Fundraiser Night",
                description="Proceeds support our trip.",
            ),
        )
        self.assertEqual(
            "fundraiser",
            classify_content_kind(
                "localist",
                title="Percentage Night",
                description="A donation drive for the food pantry.",
            ),
        )

    def test_fundraiser_beats_deadline_terms(self) -> None:
        self.assertEqual(
            "fundraiser",
            classify_content_kind(
                "instagram",
                title="Scholarship bake sale",
                description="Application deadline aside, donate today!",
            ),
        )

    def test_instagram_defaults_to_student_event(self) -> None:
        self.assertEqual(
            "student_event",
            classify_content_kind(
                "instagram",
                title="ACM General Meeting",
                description="Pizza and project demos.",
            ),
        )

    def test_instagram_deadline_is_student_deadline(self) -> None:
        self.assertEqual(
            "student_deadline",
            classify_content_kind(
                "instagram",
                title="Officer Applications Due Friday",
                description="Apply by 11:59pm.",
            ),
        )

    def test_highlander_link_defaults_to_student_event(self) -> None:
        self.assertEqual(
            "student_event",
            classify_content_kind(
                "highlander_link",
                title="Club Meetup",
                description="Come hang out.",
            ),
        )

    def test_localist_student_event_is_promoted(self) -> None:
        # Student-relevance signal in the body promotes a Localist item.
        self.assertEqual(
            "student_event",
            classify_content_kind(
                "localist",
                title="Resume Workshop",
                description="A career workshop for students.",
            ),
        )
        # Student audience filter also promotes it.
        self.assertEqual(
            "student_event",
            classify_content_kind(
                "localist",
                title="Campus Concert",
                description="An evening performance.",
                audiences=["Undergraduate Students"],
            ),
        )

    def test_localist_unrelated_official_item_is_other(self) -> None:
        self.assertEqual(
            "other",
            classify_content_kind(
                "localist",
                title="Board of Trustees Quarterly Meeting",
                description="Administrative governance session.",
                audiences=["Faculty", "Staff"],
            ),
        )

    def test_localist_student_deadline(self) -> None:
        self.assertEqual(
            "student_deadline",
            classify_content_kind(
                "localist",
                title="Undergraduate Scholarship Applications Due",
                description="Open to all students.",
                audiences=["Students"],
            ),
        )

    def test_localist_deadline_without_student_signal_is_other(self) -> None:
        self.assertEqual(
            "other",
            classify_content_kind(
                "localist",
                title="Vendor Registration Closes",
                description="Procurement deadline for suppliers.",
                audiences=["Faculty", "Staff"],
            ),
        )


if __name__ == "__main__":
    unittest.main()
