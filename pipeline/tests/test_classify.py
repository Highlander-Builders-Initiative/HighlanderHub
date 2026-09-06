from __future__ import annotations

import sys
import unittest
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from classify import classify_content_kind, detect_free_food  # noqa: E402


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

    def test_deadline_terms_in_description_do_not_reclassify_events(self) -> None:
        cases = (
            (
                "Fall Registration Second Pass Begins",
                "First-pass registration closes at 9am, then second pass opens.",
            ),
            (
                "Fulbright Writing Drop-In Hours",
                "Get help before the Fulbright campus deadline.",
            ),
            (
                "School of Public Policy End-of-Year Celebration",
                "We will honor scholarship recipients.",
            ),
        )
        for title, description in cases:
            with self.subTest(title=title):
                self.assertEqual(
                    "student_event",
                    classify_content_kind(
                        "localist",
                        title=title,
                        description=description,
                        audiences=["Students"],
                    ),
                )

    def test_opening_and_subject_titles_are_not_deadlines(self) -> None:
        for title in (
            "Scholarship Applications Open",
            "Grant Writing Workshop",
            "Immigrant Student Resource Fair",
            "Office Hours Due to Midterms",
            "Close-Knit Club Social",
        ):
            with self.subTest(title=title):
                self.assertEqual(
                    "student_event",
                    classify_content_kind("instagram", title=title),
                )

    def test_cutoff_phrase_in_title_is_student_deadline(self) -> None:
        self.assertEqual(
            "student_deadline",
            classify_content_kind(
                "instagram",
                title="Last Day to Add Classes",
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

    def test_staff_audience_beats_incidental_student_mention(self) -> None:
        # Real cache row: a Provost office-hours slot for staff whose blurb
        # happens to name students as people the Provost hears from.
        self.assertEqual(
            "other",
            classify_content_kind(
                "localist",
                title="Provost's Office Hours - Staff",
                description=(
                    "Provost Watkins holds regular office hours to get to know "
                    "and hear from faculty, staff, and students at UCR."
                ),
                tags=["Faculty & Staff"],
                audiences=["Faculty & Staff"],
            ),
        )

    def test_staff_training_about_students_is_not_student_content(self) -> None:
        self.assertEqual(
            "other",
            classify_content_kind(
                "localist",
                title="Supporting International Student Success",
                description="A workshop on advising international students.",
                audiences=["Faculty & Staff"],
            ),
        )

    def test_generic_activity_words_do_not_establish_eligibility(self) -> None:
        # "workshop", "seminar", "performance" and friends describe what
        # happens, not who may attend.
        cases = (
            ("Faculty Workshop", "A grant-writing workshop.", ["Staff"]),
            ("Addressing Employee Performance Issues", "Manager training.", ["Faculty & Staff"]),
            ("Research Seminar: Guest Speaker", "A departmental seminar.", ["Faculty & Staff"]),
            ("Leadership Workshop", "A professional development workshop.", []),
            ("Campus Concert", "An evening performance.", ["General Public/Off-Campus Community"]),
        )
        for title, description, audiences in cases:
            with self.subTest(title=title):
                self.assertEqual(
                    "other",
                    classify_content_kind(
                        "localist",
                        title=title,
                        description=description,
                        audiences=audiences,
                    ),
                )

    def test_restricted_audience_blocks_deadline_promotion(self) -> None:
        self.assertEqual(
            "other",
            classify_content_kind(
                "localist",
                title="Applications Due for the Staff Award",
                description="Nominate a colleague who mentors students.",
                audiences=["Faculty & Staff"],
            ),
        )

    def test_all_student_audience_variants_are_recognized(self) -> None:
        for audience in (
            "Undergraduate Students",
            "Graduate Students",
            "International Students",
            "Transfer Students",
            "Prospective Students",
            "Student Organizations",
        ):
            with self.subTest(audience=audience):
                self.assertEqual(
                    "student_event",
                    classify_content_kind(
                        "localist",
                        title="Campus Concert",
                        description="An evening performance.",
                        audiences=[audience],
                    ),
                )

    def test_student_audience_wins_over_staff_audience(self) -> None:
        self.assertEqual(
            "student_event",
            classify_content_kind(
                "localist",
                title="Career Fair",
                description="Employers on campus.",
                audiences=["Faculty & Staff", "Undergraduate Students"],
            ),
        )

    def test_open_audience_is_not_a_restriction(self) -> None:
        # "General Public" does not exclude students, so explicit eligibility
        # language in the body can still promote the item.
        self.assertEqual(
            "student_event",
            classify_content_kind(
                "localist",
                title="Open Lecture",
                description="Open to all students.",
                audiences=["Faculty & Staff", "General Public/Off-Campus Community"],
            ),
        )

    def test_explicit_eligibility_language_promotes_without_audience_data(self) -> None:
        for description in (
            "Open to all students.",
            "Students are welcome to attend.",
            "A career workshop for students.",
        ):
            with self.subTest(description=description):
                self.assertEqual(
                    "student_event",
                    classify_content_kind(
                        "localist",
                        title="Campus Event",
                        description=description,
                    ),
                )

    def test_org_vocabulary_matches_phrases_in_title_or_description(self) -> None:
        for text in (
            "Meet every RSO on campus.", "Weekly general body meeting.",
            "Talk to your student leaders.", "Visit the club fair.",
            "Explore Greek life.", "Join our hackathon.",
        ):
            for field in ("title", "description"):
                with self.subTest(text=text, field=field):
                    self.assertEqual("student_event", classify_content_kind(
                        "localist", **{field: text},
                    ))

    def test_text_signals_do_not_match_parts_of_words(self) -> None:
        for text in ("Personality seminar", "Hackathoners meetup", "Club sportswear sale",
                     "For studentship administrators", "Undergraduateship overview"):
            with self.subTest(text=text):
                self.assertEqual("other", classify_content_kind("localist", title=text))

    def test_tags_do_not_establish_student_eligibility(self) -> None:
        for tag in ("RSO", "general body meeting", "open to all students", "undergraduate"):
            with self.subTest(tag=tag):
                self.assertEqual("other", classify_content_kind(
                    "localist", title="Campus Briefing", tags=[tag],
                ))

    def test_audience_metadata_does_not_feed_org_text_matching(self) -> None:
        for audience in ("RSO", "general body meeting", "sorority"):
            with self.subTest(audience=audience):
                self.assertEqual("other", classify_content_kind(
                    "localist", title="Campus Briefing", audiences=[audience],
                ))

    def test_metadata_does_not_reclassify_events_as_fundraisers_or_deadlines(self) -> None:
        for field in ("tags", "audiences"):
            for term in ("fundraiser", "donation", "bake sale", "applications due"):
                with self.subTest(field=field, term=term):
                    self.assertEqual("student_event", classify_content_kind(
                        "instagram", title="Club Meetup", **{field: [term]},
                    ))

    def test_student_audiences_match_tokens_instead_of_substrings(self) -> None:
        for audience in ("Nonstudent visitors", "Studentship administrators"):
            with self.subTest(audience=audience):
                self.assertEqual("other", classify_content_kind(
                    "localist", title="Campus Briefing", audiences=[audience],
                ))

    def test_restricted_audiences_use_explicit_singular_and_plural_tokens(self) -> None:
        for audience in (
            "Faculty & Staff", "Employee", "Employees", "Alumni", "Alumna",
            "Alumnae", "Alumnus", "Parent", "Parents/Family", "Families",
            "Retiree", "Retirees", "Emeritus", "Emerita", "Emeriti", "Emeritae",
            "Donor", "Donors", "Employer", "Employers",
        ):
            with self.subTest(audience=audience):
                self.assertEqual("other", classify_content_kind(
                    "localist", title="Campus Briefing", description="Open to all students.",
                    audiences=[audience],
                ))

    def test_restricted_audience_stems_do_not_match_unrelated_words(self) -> None:
        for audience in ("Familiar faces", "Emeritone members", "Transparent visitors",
                         "Stafford residents"):
            with self.subTest(audience=audience):
                self.assertEqual("student_event", classify_content_kind(
                    "localist", title="Campus Briefing", description="Open to all students.",
                    audiences=[audience],
                ))

    def test_bare_public_and_substrings_do_not_override_staff_restrictions(self) -> None:
        for audience in ("Publication editors", "Public policy professionals", "Public"):
            with self.subTest(audience=audience):
                self.assertEqual("other", classify_content_kind(
                    "localist", title="Campus Briefing", description="Open to all students.",
                    audiences=["Staff", audience],
                ))

    def test_open_audience_phrases_handle_punctuation_and_spacing(self) -> None:
        for audience in ("GENERAL PUBLIC/Off-Campus Community", "General-public",
                         "Campus   Community", "All Audiences", "Everyone"):
            with self.subTest(audience=audience):
                for description, expected in (("", "other"), ("Open to all students.", "student_event")):
                    self.assertEqual(expected, classify_content_kind(
                        "localist", title="Campus Briefing", description=description,
                        audiences=["Staff", audience],
                    ))

    def test_student_sources_bypass_audience_restrictions_but_not_fundraisers(self) -> None:
        for origin in ("instagram", "highlander_link", "manual", "submission"):
            for title, expected in (("Club Meetup", "student_event"),
                                    ("Applications Due", "student_deadline"),
                                    ("Fundraiser Deadline", "fundraiser")):
                with self.subTest(origin=origin, title=title):
                    self.assertEqual(expected, classify_content_kind(
                        origin, title=title, audiences=["Faculty & Staff"],
                    ))

    def test_mixed_audience_order_does_not_change_the_result(self) -> None:
        for audiences in (["Students", "Staff"], ["Staff", "Students"]):
            with self.subTest(audiences=audiences):
                self.assertEqual("student_event", classify_content_kind(
                    "localist", title="Campus Briefing", audiences=iter(audiences),
                ))
        self.assertEqual("other", classify_content_kind(
            "localist", description="Open to all students.", audiences=iter(["Staff"]),
        ))

    def test_free_food_detection_preserves_word_boundaries_and_optional_texts(self) -> None:
        for text, expected in (("FREE PIZZA tonight", True), ("Boba meetup", True),
                               ("refreshments", True), ("Bobak speaks", False),
                               ("Pizza for sale", False), (None, False), ("", False)):
            with self.subTest(text=text):
                self.assertEqual(expected, detect_free_food(text))
        self.assertTrue(detect_free_food(None, "Meet tonight.", "Snacks provided."))


if __name__ == "__main__":
    unittest.main()
