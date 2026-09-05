"""Configurable content-kind and free-food recognition for pipeline events.

Policy lives in classification_rules.json. Existing pipeline callers use the
functions below; load_engine() and explain_classification() support testing
new formats without changing the engine or writing to the database.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterable


# These values are a shared database/app contract, not configurable labels.
CONTENT_KINDS = ("student_event", "student_deadline", "fundraiser", "other")
DEFAULT_RULES_PATH = Path(__file__).with_name("classification_rules.json")
_FIELDS = frozenset({"origin", "title", "description", "tags", "audiences", "text"})
_EVENT_FIELDS = _FIELDS - {"text"}
Predicate = Callable[[dict[str, Any]], bool]


class RulesConfigError(ValueError):
    """A rules file cannot be interpreted."""


def _keys(value: Any, required: set[str], optional: set[str], path: str) -> None:
    if not isinstance(value, dict):
        raise RulesConfigError(f"{path}: expected an object")
    missing = required - value.keys()
    unknown = value.keys() - required - optional
    if missing or unknown:
        raise RulesConfigError(
            f"{path}: missing keys {sorted(missing)}, unknown keys {sorted(unknown)}"
        )


def _validate_event(event: Any, path: str) -> None:
    _keys(event, {"origin"}, _EVENT_FIELDS - {"origin"}, path)
    for field, value in event.items():
        valid = (isinstance(value, list) and all(isinstance(v, str) for v in value)
                 if field in {"tags", "audiences"} else isinstance(value, str))
        if not valid:
            raise RulesConfigError(f"{path}.{field}: invalid field value")


def _condition(
    spec: Any, path: str, *, allow_student: bool = False,
    fields: frozenset[str] = _FIELDS,
) -> Predicate:
    """Validate and compile declarative conditions; never execute config as code."""
    if not isinstance(spec, dict) or not spec:
        raise RulesConfigError(f"{path}: expected a non-empty condition object")
    if len(spec) == 1:
        operator, value = next(iter(spec.items()))
        if operator in {"all", "any"}:
            if not isinstance(value, list) or not value:
                raise RulesConfigError(f"{path}.{operator}: expected non-empty list")
            children = tuple(
                _condition(child, f"{path}.{operator}[{i}]",
                           allow_student=allow_student, fields=fields)
                for i, child in enumerate(value)
            )
            combine = all if operator == "all" else any
            return lambda event: combine(child(event) for child in children)
        if operator == "not":
            child = _condition(value, f"{path}.not", allow_student=allow_student, fields=fields)
            return lambda event: not child(event)
        if operator == "student_relevant":
            if not allow_student or type(value) is not bool:
                raise RulesConfigError(
                    f"{path}: student_relevant must be a boolean in content_kind rules"
                )
            return lambda event: event["student_relevant"] is value

    _keys(spec, {"field", "match", "patterns"}, set(), path)
    field, mode, patterns = spec["field"], spec["match"], spec["patterns"]
    if not isinstance(field, str) or field not in fields:
        raise RulesConfigError(f"{path}.field: expected one of {sorted(fields)}")
    if mode not in ("contains", "equals", "regex"):
        raise RulesConfigError(f"{path}.match: expected contains, equals, or regex")
    if (not isinstance(patterns, list) or not patterns
            or any(not isinstance(p, str) or not p.strip() for p in patterns)):
        raise RulesConfigError(f"{path}.patterns: expected non-empty strings")

    if mode == "regex":
        compiled = []
        for i, pattern in enumerate(patterns):
            try:
                compiled.append(re.compile(pattern, re.IGNORECASE))
            except re.error as exc:
                raise RulesConfigError(f"{path}.patterns[{i}]: invalid regex: {exc}") from exc
        matches = lambda text: any(pattern.search(text) for pattern in compiled)
    elif mode == "contains":
        folded = tuple(pattern.casefold() for pattern in patterns)
        matches = lambda text: any(pattern in text.casefold() for pattern in folded)
    else:
        choices = frozenset(patterns)
        matches = lambda text: text in choices

    # Collection fields match each value independently; text combines title,
    # description, tags, and audiences as in the original classifier.
    return lambda event: any(matches(value) for value in event[field])


@dataclass(frozen=True)
class _Rule:
    id: str
    value: str | bool
    matches: Predicate


@dataclass(frozen=True)
class _RuleSet:
    rules: tuple[_Rule, ...]
    default: str | bool

    def evaluate(self, event: dict[str, Any]) -> tuple[str | bool, str | None]:
        for rule in self.rules:
            if rule.matches(event):
                return rule.value, rule.id
        return self.default, None


def _rule_set(spec: Any, path: str, *, boolean: bool) -> _RuleSet:
    _keys(spec, {"rules", "default"}, set(), path)

    def check_value(value: Any, location: str) -> None:
        valid = type(value) is bool if boolean else value in CONTENT_KINDS
        if not valid:
            expected = "a boolean" if boolean else str(CONTENT_KINDS)
            raise RulesConfigError(f"{location}: expected {expected}")

    check_value(spec["default"], f"{path}.default")
    if not isinstance(spec["rules"], list):
        raise RulesConfigError(f"{path}.rules: expected a list")
    rules = []
    ids = set()
    for i, rule in enumerate(spec["rules"]):
        location = f"{path}.rules[{i}]"
        _keys(rule, {"id", "when", "value"}, {"description"}, location)
        rule_id = rule["id"]
        if not isinstance(rule_id, str) or not rule_id.strip() or rule_id in ids:
            raise RulesConfigError(f"{location}.id: expected a unique, non-empty string")
        if "description" in rule and not isinstance(rule["description"], str):
            raise RulesConfigError(f"{location}.description: expected a string")
        ids.add(rule_id)
        check_value(rule["value"], f"{location}.value")
        rules.append(_Rule(rule_id, rule["value"], _condition(
            rule["when"], f"{location}.when", allow_student=not boolean,
        )))
    return _RuleSet(tuple(rules), spec["default"])


@dataclass(frozen=True)
class ClassificationResult:
    content_kind: str
    rule_id: str | None
    student_relevant: bool
    student_rule_id: str | None


class ClassificationEngine:
    def __init__(self, config: dict[str, Any]) -> None:
        _keys(config, {"version", "student_relevance", "content_kind", "free_food"},
              {"examples"}, "config")
        if type(config["version"]) is not int or config["version"] != 1:
            raise RulesConfigError("config.version: only version 1 is supported")
        self._students = _rule_set(config["student_relevance"], "student_relevance", boolean=True)
        self._kinds = _rule_set(config["content_kind"], "content_kind", boolean=False)
        self._food = _condition(config["free_food"], "free_food", fields=frozenset({"text"}))
        self._examples = config.get("examples", [])
        self._validate_examples()

    def classify(
        self,
        origin: str,
        *,
        title: str = "",
        description: str = "",
        tags: Iterable = (),
        audiences: Iterable = (),
    ) -> ClassificationResult:
        # Materialize iterables once so audience checks also work on generators.
        event = {
            "origin": [origin], "title": [title or ""],
            "description": [description or ""],
            "tags": [str(tag) for tag in (tags or ())],
            "audiences": [str(audience) for audience in (audiences or ())],
        }
        event["text"] = [" ".join(
            value for field in ("title", "description", "tags", "audiences")
            for value in event[field]
        ).casefold()]
        student, student_rule_id = self._students.evaluate(event)
        event["student_relevant"] = student
        kind, rule_id = self._kinds.evaluate(event)
        return ClassificationResult(kind, rule_id, student, student_rule_id)

    def detect_free_food(self, *texts: str | None) -> bool:
        return self._food({"text": [" ".join(text for text in texts if text)]})

    def _validate_examples(self) -> None:
        if not isinstance(self._examples, list):
            raise RulesConfigError("examples: expected a list")
        for i, example in enumerate(self._examples):
            path = f"examples[{i}]"
            _keys(example, {"name", "event", "expected"}, set(), path)
            if not isinstance(example["name"], str) or not example["name"].strip():
                raise RulesConfigError(f"{path}.name: expected a non-empty string")
            _validate_event(example["event"], f"{path}.event")
            expected = example["expected"]
            _keys(expected, {"content_kind"}, {"rule_id", "student_relevant", "student_rule_id"},
                  f"{path}.expected")
            if expected["content_kind"] not in CONTENT_KINDS:
                raise RulesConfigError(f"{path}.expected.content_kind: unsupported content kind")
            for field in ("rule_id", "student_rule_id"):
                if field in expected and expected[field] is not None and not isinstance(expected[field], str):
                    raise RulesConfigError(f"{path}.expected.{field}: expected a string or null")
            if "student_relevant" in expected and type(expected["student_relevant"]) is not bool:
                raise RulesConfigError(f"{path}.expected.student_relevant: expected a boolean")

    def check_examples(self) -> int:
        """Verify config-owned regression examples without external services."""
        for example in self._examples:
            actual = asdict(self.classify(**example["event"]))
            for field, expected in example["expected"].items():
                if actual[field] != expected:
                    raise RulesConfigError(
                        f"Example {example['name']!r}: {field} expected {expected!r}, "
                        f"got {actual[field]!r}"
                    )
        return len(self._examples)


def load_engine(path: str | Path = DEFAULT_RULES_PATH) -> ClassificationEngine:
    """Load a fresh engine; invalid config fails instead of silently changing policy."""
    try:
        config = json.loads(Path(path).read_text(encoding="utf-8"))
        return ClassificationEngine(config)
    except (OSError, ValueError) as exc:
        raise RulesConfigError(f"{path}: {exc}") from exc


@lru_cache(maxsize=1)
def _default_engine() -> ClassificationEngine:
    # Read/compile once per process. Restart the pipeline after editing config.
    return load_engine(os.environ.get("PIPELINE_CLASSIFICATION_RULES") or DEFAULT_RULES_PATH)


def explain_classification(origin: str, **event: Any) -> ClassificationResult:
    """Return the winning classification and student-relevance rule IDs."""
    return _default_engine().classify(origin, **event)


def classify_content_kind(
    origin: str,
    *,
    title: str = "",
    description: str = "",
    tags: Iterable = (),
    audiences: Iterable = (),
) -> str:
    return explain_classification(
        origin, title=title, description=description, tags=tags, audiences=audiences,
    ).content_kind


def detect_free_food(*texts: str | None) -> bool:
    """True when the configured food pattern matches any of the text blobs."""
    return _default_engine().detect_free_food(*texts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules", type=Path,
                        default=os.environ.get("PIPELINE_CLASSIFICATION_RULES") or DEFAULT_RULES_PATH)
    parser.add_argument("--check", action="store_true", help="Validate rules and run their examples")
    parser.add_argument("--event", type=Path, help="Explain a normalized event from a JSON file")
    args = parser.parse_args()
    if not args.check and args.event is None:
        parser.error("provide --check or --event")
    try:
        engine = load_engine(args.rules)
        if args.check:
            print(f"Rules valid; {engine.check_examples()} examples passed.")
        if args.event is not None:
            event = json.loads(args.event.read_text(encoding="utf-8"))
            _validate_event(event, str(args.event))
            print(json.dumps(asdict(engine.classify(**event)), indent=2))
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
