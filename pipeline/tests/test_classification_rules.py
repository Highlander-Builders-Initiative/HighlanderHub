from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from classify import (  # noqa: E402
    ClassificationEngine,
    DEFAULT_RULES_PATH,
    RulesConfigError,
    _default_engine,
    classify_content_kind,
    detect_free_food,
    explain_classification,
    load_engine,
)


class ClassificationRulesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = json.loads(DEFAULT_RULES_PATH.read_text(encoding="utf-8"))

    def test_shipped_metadata_examples(self) -> None:
        self.assertGreater(load_engine().check_examples(), 0)

    def test_new_format_and_regression_example_need_only_config_changes(self) -> None:
        event = {
            "origin": "localist",
            "title": "RSVPs shut on September 10",
            "audiences": ["Students"],
        }
        self.assertEqual("student_event", load_engine().classify(**event).content_kind)
        self.config["content_kind"]["rules"].insert(1, {
            "id": "rsvp-cutoff-format",
            "description": "A newly observed title format denotes a student cutoff.",
            "when": {"all": [
                {"student_relevant": True},
                {"field": "origin", "match": "equals", "patterns": ["localist"]},
                {"field": "title", "match": "regex", "patterns": [r"\brsvps? shut on\b"]},
                {"not": {"field": "title", "match": "contains", "patterns": ["preview"]}},
            ]},
            "value": "student_deadline",
        })
        self.config["examples"].append({
            "name": "New RSVP cutoff",
            "event": event,
            "expected": {"content_kind": "student_deadline", "rule_id": "rsvp-cutoff-format"},
        })
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "rules.json"
            path.write_text(json.dumps(self.config), encoding="utf-8")
            engine = load_engine(path)
            self.assertEqual(len(self.config["examples"]), engine.check_examples())
            self.assertEqual("rsvp-cutoff-format", engine.classify(**event).rule_id)
            # Reuse the same existing pipeline entry point with a new config file.
            with patch.dict(os.environ, {"PIPELINE_CLASSIFICATION_RULES": str(path)}):
                _default_engine.cache_clear()
                try:
                    self.assertEqual("student_deadline", classify_content_kind(**event))
                    self.assertEqual("rsvp-cutoff-format", explain_classification(**event).rule_id)
                finally:
                    _default_engine.cache_clear()
        for changes, expected in (
            ({"audiences": ["Faculty & Staff"]}, "other"),
            ({"origin": "instagram"}, "student_event"),
            ({"title": "Preview: RSVPs shut on September 10"}, "student_event"),
            ({"title": "Fundraiser RSVPs shut on September 10"}, "fundraiser"),
            ({"title": "Campus Briefing", "description": "RSVPs shut on September 10"}, "student_event"),
        ):
            with self.subTest(changes=changes):
                self.assertEqual(expected, engine.classify(**(event | changes)).content_kind)

    def test_new_student_format_respects_restricted_audience(self) -> None:
        self.config["student_relevance"]["rules"].append({
            "id": "enrolled-highlanders",
            "when": {"any": [
                {"field": "description", "match": "regex",
                 "patterns": [r"\bavailable to enrolled Highlanders\b"]},
                {"field": "tags", "match": "equals", "patterns": ["Enrolled Highlanders"]},
            ]},
            "value": True,
        })
        engine = ClassificationEngine(self.config)
        result = engine.classify("localist", description="Available to enrolled Highlanders.")
        self.assertEqual("student_event", result.content_kind)
        self.assertEqual("enrolled-highlanders", result.student_rule_id)
        self.assertEqual("other", engine.classify(
            "localist", description="Available to enrolled Highlanders.", audiences=["Staff"],
        ).content_kind)
        self.assertEqual("student_event", engine.classify(
            "localist", tags=["Enrolled Highlanders"],
        ).content_kind)
        self.assertEqual("other", engine.classify(
            "localist", tags=["Enrolled", "Highlanders"],
        ).content_kind)

    def test_rule_order_is_configuration(self) -> None:
        fundraiser = self.config["content_kind"]["rules"].pop(0)
        self.config["content_kind"]["rules"].append(fundraiser)
        result = ClassificationEngine(self.config).classify("instagram", title="Fundraiser Deadline")
        self.assertEqual("student_deadline", result.content_kind)
        self.assertEqual("student-deadline", result.rule_id)

    def test_default_is_configurable_and_explains_no_match(self) -> None:
        engine = load_engine()
        result = engine.classify("new-feed", title="Unrecognized item")
        self.assertEqual("other", result.content_kind)
        self.assertIsNone(result.rule_id)
        self.assertIsNone(result.student_rule_id)
        self.config["content_kind"]["default"] = "student_event"
        self.assertEqual("student_event", ClassificationEngine(self.config).classify("new-feed").content_kind)

    def test_existing_free_food_behavior_and_configuration_extension(self) -> None:
        for text, expected in (
            ("FREE PIZZA tonight", True), ("Boba meetup", True),
            ("refreshments", True), ("Bobak speaks", False), ("Pizza for sale", False),
            (None, False), ("", False),
        ):
            with self.subTest(text=text):
                self.assertEqual(expected, detect_free_food(text))
        self.assertFalse(load_engine().detect_free_food("Complimentary tacos"))
        self.config["free_food"]["patterns"].append(r"\bcomplimentary tacos\b")
        self.assertTrue(ClassificationEngine(self.config).detect_free_food("Complimentary tacos"))
        self.assertTrue(load_engine().detect_free_food(None, "Free", "snacks provided"))

    def test_audience_iterables_are_not_consumed_before_restriction_check(self) -> None:
        result = load_engine().classify(
            "localist", description="A workshop for students.",
            audiences=iter(["Faculty & Staff"]),
        )
        self.assertEqual("other", result.content_kind)
        self.assertEqual("restricted-audience", result.student_rule_id)

    def test_invalid_rules_report_the_config_location(self) -> None:
        cases = [
            (("version",), 2, "config.version"),
            (("version",), True, "config.version"),
            (("unexpected",), 1, "unknown keys"),
            (("content_kind", "default"), "new-database-kind", "content_kind.default"),
            (("student_relevance", "default"), "false", "student_relevance.default"),
            (("content_kind", "rules"), {}, "content_kind.rules"),
            (("content_kind", "rules", 0, "id"), "", "rules[0].id"),
            (("content_kind", "rules", 0, "id"), "student-event", "unique"),
            (("content_kind", "rules", 0, "priority"), 100, "unknown keys"),
            (("content_kind", "rules", 0, "value"), "concert", "rules[0].value"),
            (("content_kind", "rules", 0, "when", "field"), "titel", ".field"),
            (("content_kind", "rules", 0, "when", "match"), "python", ".match"),
            (("content_kind", "rules", 0, "when", "patterns"), [], ".patterns"),
            (("content_kind", "rules", 0, "when", "patterns"), [" "], ".patterns"),
            (("content_kind", "rules", 0, "when", "patterns"), [42], ".patterns"),
            (("content_kind", "rules", 0, "when"), {"all": []}, ".all"),
            (("content_kind", "rules", 0, "when"), {"any": "student"}, ".any"),
            (("content_kind", "rules", 0, "when"), {"not": {}}, ".not"),
            (("content_kind", "rules", 0, "when"), {"student_relevant": "true"}, "student_relevant"),
            (("student_relevance", "rules", 0, "when"), {"student_relevant": True}, "student_relevant"),
            (("free_food", "field"), "title", "free_food.field"),
            (("free_food", "patterns"), ["["], "free_food.patterns[0]"),
            (("examples",), {}, "examples"),
            (("examples", 0, "event", "audiences"), "Staff", ".audiences"),
            (("examples", 0, "expected", "content_kind"), "unknown", ".content_kind"),
            (("examples", 0, "expected", "student_relevant"), 1, ".student_relevant"),
            (("examples", 0, "expected", "rule_id"), False, ".rule_id"),
        ]
        for keys, value, message in cases:
            with self.subTest(keys=keys, value=value):
                config = copy.deepcopy(self.config)
                target = config
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = value
                with self.assertRaises(RulesConfigError) as error:
                    ClassificationEngine(config)
                self.assertIn(message, str(error.exception))

    def test_regression_example_reports_wrong_outcome(self) -> None:
        self.config["examples"][0]["expected"]["content_kind"] = "student_event"
        with self.assertRaisesRegex(RulesConfigError, "Staff audience.*expected.*got"):
            ClassificationEngine(self.config).check_examples()

    def test_missing_and_malformed_config_fail_instead_of_using_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "missing.json"
            with self.assertRaises(RulesConfigError) as error:
                load_engine(path)
            self.assertIn(str(path), str(error.exception))
            for content in ("{broken", "[]", "null"):
                with self.subTest(content=content):
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaises(RulesConfigError):
                        load_engine(path)

    def test_cli_checks_metadata_and_explains_an_event_without_services(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "event.json"
            path.write_text(json.dumps({
                "origin": "localist", "title": "Campus Update", "audiences": ["Staff"],
            }), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(PIPELINE_ROOT / "classify.py"),
                 "--rules", str(DEFAULT_RULES_PATH), "--event", str(path)],
                capture_output=True, text=True, check=True,
            )
            explanation = json.loads(result.stdout)
            self.assertEqual("other", explanation["content_kind"])
            self.assertEqual("restricted-audience", explanation["student_rule_id"])
            path.write_text(json.dumps({"origin": "localist", "audiences": "Staff"}), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(PIPELINE_ROOT / "classify.py"),
                 "--rules", str(DEFAULT_RULES_PATH), "--event", str(path)],
                capture_output=True, text=True,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn(".audiences: invalid field value", result.stderr)
            result = subprocess.run(
                [sys.executable, str(PIPELINE_ROOT / "classify.py"),
                 "--rules", str(DEFAULT_RULES_PATH), "--check"],
                capture_output=True, text=True, check=True,
            )
            self.assertIn("examples passed", result.stdout)
            self.config["examples"][0]["expected"]["content_kind"] = "student_event"
            rules_path = Path(temp) / "bad-rules.json"
            rules_path.write_text(json.dumps(self.config), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(PIPELINE_ROOT / "classify.py"),
                 "--rules", str(rules_path), "--check"],
                capture_output=True, text=True,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("Staff audience", result.stderr)


if __name__ == "__main__":
    unittest.main()
