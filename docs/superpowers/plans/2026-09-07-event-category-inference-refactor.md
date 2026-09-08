# Event Category Inference Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract event-category policy from normalization and replace generic plural matching with explicit aliases that score once per concept.

**Architecture:** `pipeline/category_inference.py` will own source-taxonomy precedence and pure weighted keyword scoring. `pipeline/normalize_events.py` will extract source values, delegate category selection, and continue constructing event rows.

**Tech Stack:** Python 3 standard library (`re`, `unittest`); no new dependencies.

## Global Constraints

- Preserve Localist source-type precedence and athletics override.
- Preserve HighlanderLink theme/category-name precedence.
- Preserve title/source/description weights of 3/2/1 and existing category priority.
- Preserve `community` as the unmatched fallback.
- Every accepted plural must be explicit; aliases for one concept may score only once.
- Do not change the database schema or event-row shape.
- Keep imports at module scope.

---

### Task 1: Pure category-inference module

**Files:**
- Create: `pipeline/category_inference.py`
- Create: `pipeline/tests/test_category_inference.py`

**Interfaces:**
- Produces: `infer_category_from_text(title: str, description: str, source_terms: Iterable[str] = ()) -> str`
- Produces: `infer_localist_category(event_types: Iterable[str], event_topics: Iterable[str], has_athletics: bool, title: str, description: str) -> str`
- Produces: `infer_hlink_category(theme: object, category_names: list[str], title: str, description: str) -> str`

- [ ] **Step 1: Write focused failing tests**

Create `pipeline/tests/test_category_inference.py`:

```python
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
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
cd pipeline
python -m unittest tests.test_category_inference -v
```

Expected: import failure because `category_inference` does not exist.

- [ ] **Step 3: Implement explicit concept aliases and source resolvers**

Create `pipeline/category_inference.py`. Move the existing Localist,
HighlanderLink, weight, and priority tables from `normalize_events.py` into this
module using these exact definitions:

```python
from __future__ import annotations

import re
from collections.abc import Iterable


_LOCALIST_TYPE_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("theatre & plays", "arts"),
    ("film & screenings", "arts"),
    ("exhibitions", "arts"),
    ("arts", "arts"),
    ("athletics", "sports"),
    ("recreation", "sports"),
    ("commencement", "community"),
    ("fundraisers", "community"),
    ("career", "career"),
    ("conferences", "career"),
    ("seminars", "academic"),
    ("lectures & presentations", "academic"),
    ("academic calendar", "academic"),
    ("academic", "academic"),
    ("social", "social"),
)

_HLINK_THEME_TO_CATEGORY = {
    "athletics": "sports",
    "cultural": "arts",
    "social": "social",
    "spirituality": "community",
    "communityservice": "community",
    "fundraising": "community",
    "thoughtfullearning": "academic",
}

_HLINK_CATEGORY_NAME_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("concert", "arts"),
    ("performance", "arts"),
    ("exhibit", "arts"),
    ("dance", "arts"),
    ("cultural", "arts"),
    ("competition", "sports"),
    ("recreational", "sports"),
    ("educational", "academic"),
    ("community service", "community"),
    ("late night", "social"),
    ("gaming", "social"),
    ("social", "social"),
)

_CATEGORY_CONCEPTS: dict[str, tuple[tuple[str, ...], ...]] = {
    "academic": (
        ("lecture", "lectures"),
        ("seminar", "seminars"),
        ("colloquium", "colloquiums", "colloquia"),
        ("symposium", "symposiums", "symposia"),
        ("research",),
        ("thesis", "theses"),
        ("defense", "defenses"),
        ("class", "classes"),
    ),
    "career": (
        ("career", "careers"),
        ("internship", "internships"),
        ("workshop", "workshops"),
        ("networking",),
        ("resume", "resumes"),
        ("interview", "interviews"),
        ("hiring",),
        ("recruit", "recruits"),
    ),
    "sports": (
        ("athletic", "athletics"),
        ("basketball",),
        ("soccer",),
        ("baseball",),
        ("volleyball",),
        ("tennis",),
        ("football",),
        ("intramural", "intramurals"),
    ),
    "arts": (
        ("concert", "concerts"),
        ("recital", "recitals"),
        ("exhibit", "exhibits"),
        ("exhibition", "exhibitions"),
        ("gallery", "galleries"),
        ("theater", "theaters"),
        ("theatre", "theatres"),
        ("dance performance", "dance performances"),
        ("film", "films"),
        ("screening", "screenings"),
    ),
    "social": (
        ("mixer", "mixers"),
        ("social", "socials"),
        ("party", "parties"),
        ("greek", "greeks"),
        ("fraternity", "fraternities"),
        ("sorority", "sororities"),
        ("kickback", "kickbacks"),
    ),
    "club": (
        ("club", "clubs"),
        ("organization", "organizations"),
        ("rso", "rsos"),
        ("general meeting", "general meetings"),
        ("gbm", "gbms"),
    ),
    "community": (
        ("community", "communities"),
        ("volunteer", "volunteers"),
        ("outreach",),
        ("donate", "donates"),
    ),
}

_CATEGORY_PRIORITY: tuple[str, ...] = (
    "sports",
    "arts",
    "career",
    "club",
    "academic",
    "social",
    "community",
)
_CATEGORY_RANK = {
    category: rank for rank, category in enumerate(_CATEGORY_PRIORITY)
}
_UNRANKED = len(_CATEGORY_PRIORITY)

_TITLE_WEIGHT = 3
_SOURCE_TERM_WEIGHT = 2
_DESCRIPTION_WEIGHT = 1


def _concept_pattern(aliases: tuple[str, ...]) -> re.Pattern[str]:
    alternatives = "|".join(
        re.escape(alias) for alias in sorted(aliases, key=len, reverse=True)
    )
    return re.compile(rf"(?<![\w-])(?:{alternatives})(?![\w-])")


_CATEGORY_PATTERNS = {
    category: tuple(_concept_pattern(aliases) for aliases in concepts)
    for category, concepts in _CATEGORY_CONCEPTS.items()
}


def _match_source_category(
    labels: Iterable[str],
    table: tuple[tuple[str, str], ...],
) -> str | None:
    present = {
        label.strip().lower()
        for label in labels
        if isinstance(label, str) and label.strip()
    }
    for label, category in table:
        if label in present:
            return category
    return None
```

Implement scoring once per concept:

```python
def infer_category_from_text(
    title: str,
    description: str,
    source_terms: Iterable[str] = (),
) -> str:
    fields = (
        (title.lower(), _TITLE_WEIGHT),
        (" ".join(source_terms).lower(), _SOURCE_TERM_WEIGHT),
        (description.lower(), _DESCRIPTION_WEIGHT),
    )
    scores: dict[str, int] = {}
    for category, patterns in _CATEGORY_PATTERNS.items():
        score = sum(
            max(
                (
                    weight
                    for text, weight in fields
                    if text and pattern.search(text)
                ),
                default=0,
            )
            for pattern in patterns
        )
        if score:
            scores[category] = score
    if not scores:
        return "community"
    return max(
        scores,
        key=lambda category: (
            scores[category],
            -_CATEGORY_RANK.get(category, _UNRANKED),
        ),
    )
```

Implement source resolvers over normalized arguments:

```python
def infer_localist_category(
    event_types: Iterable[str],
    event_topics: Iterable[str],
    has_athletics: bool,
    title: str,
    description: str,
) -> str:
    if has_athletics:
        return "sports"
    types = list(event_types)
    mapped = _match_source_category(types, _LOCALIST_TYPE_CATEGORIES)
    if mapped:
        return mapped
    return infer_category_from_text(
        title,
        description,
        [*types, *event_topics],
    )


def infer_hlink_category(
    theme: object,
    category_names: list[str],
    title: str,
    description: str,
) -> str:
    if isinstance(theme, str):
        mapped = _HLINK_THEME_TO_CATEGORY.get(theme.strip().lower())
        if mapped:
            return mapped
    mapped = _match_source_category(
        category_names,
        _HLINK_CATEGORY_NAME_CATEGORIES,
    )
    if mapped:
        return mapped
    return infer_category_from_text(title, description, category_names)
```

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run:

```bash
cd pipeline
python -m unittest tests.test_category_inference -v
```

Expected: 5 tests pass.

- [ ] **Step 5: Commit the pure module**

```bash
git add pipeline/category_inference.py pipeline/tests/test_category_inference.py
git commit -m "Extract event category inference policy"
```

---

### Task 2: Integrate category inference with event normalization

**Files:**
- Modify: `pipeline/normalize_events.py:13-264`
- Test: `pipeline/tests/test_normalize_events.py:301-399`

**Interfaces:**
- Consumes: the three public resolver functions from Task 1.
- Produces: unchanged normalized event rows.

- [ ] **Step 1: Verify mapper characterization tests are GREEN before refactoring**

Run:

```bash
cd pipeline
python -m unittest tests.test_normalize_events -v
```

Expected: all existing normalize-event tests pass.

- [ ] **Step 2: Replace local category policy with module imports**

At module scope in `pipeline/normalize_events.py`, import:

```python
from category_inference import infer_hlink_category, infer_localist_category
```

Remove the category-policy constants and functions from
`_LOCALIST_TYPE_CATEGORIES` through `_infer_hlink_category`. Keep
`_HTML_TAG`, `_WHITESPACE`, `_filter_names`, and all normalization helpers.

In `_to_event_row`, extract reusable source labels and delegate:

```python
event_types = _filter_names(raw, "event_types")
event_topics = _filter_names(raw, "event_topic")
category = infer_localist_category(
    event_types=event_types,
    event_topics=event_topics,
    has_athletics=bool(_filter_names(raw, "event_athletics")),
    title=title,
    description=description,
)

audiences = _filter_names(raw, "event_audience")
tags = sorted(set(event_types + event_topics + audiences))
```

In `_to_event_row_hlink`, delegate with the already filtered category names:

```python
category_names = [
    category_name
    for category_name in (raw.get("categoryNames") or [])
    if isinstance(category_name, str)
]
category = infer_hlink_category(
    theme=raw.get("theme"),
    category_names=category_names,
    title=title,
    description=description,
)
```

- [ ] **Step 3: Strengthen the existing negative integration fixture**

Extend `test_keyword_fallback_matches_whole_words_only` with a separate
assertion for the previously untested hyphenated case:

```python
self.assertEqual(
    "community",
    self._localist_category(
        title="Classical self-defense",
        description_text="",
    ),
)
```

Keep the existing arts assertion as well.

- [ ] **Step 4: Run focused integration and pure tests**

Run:

```bash
cd pipeline
python -m unittest \
  tests.test_category_inference \
  tests.test_normalize_events \
  -v
```

Expected: all category-inference and normalize-event tests pass.

- [ ] **Step 5: Run the complete pipeline test suite**

Run:

```bash
cd pipeline
python -m unittest discover -s tests -p "test_*.py"
```

Expected: all tests pass with no errors or failures.

- [ ] **Step 6: Commit integration**

```bash
git add pipeline/normalize_events.py pipeline/tests/test_normalize_events.py
git commit -m "Delegate event category inference"
```

---

### Task 3: Final verification

**Files:**
- Verify: `pipeline/category_inference.py`
- Verify: `pipeline/normalize_events.py`
- Verify: `pipeline/tests/test_category_inference.py`
- Verify: `pipeline/tests/test_normalize_events.py`

**Interfaces:**
- Consumes: completed Tasks 1 and 2.
- Produces: verified PR branch ready to push.

- [ ] **Step 1: Check edited-file diagnostics**

Read IDE diagnostics for the four edited Python files. Expected: no new
diagnostics.

- [ ] **Step 2: Inspect the final diff**

Run:

```bash
git diff origin/fix/category-source-precedence...HEAD -- \
  pipeline/category_inference.py \
  pipeline/normalize_events.py \
  pipeline/tests/test_category_inference.py \
  pipeline/tests/test_normalize_events.py
```

Expected: category policy is absent from `normalize_events.py`, explicit aliases
live in `category_inference.py`, and unrelated working-tree files are absent.

- [ ] **Step 3: Verify repository status**

Run:

```bash
git status --short --branch
```

Expected: only the user's pre-existing unrelated changes remain uncommitted.
