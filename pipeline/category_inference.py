"""Canonical event category inference for Localist and HighlanderLink sources.

Each resolver follows a three-tier flow: structured source labels first, then
weighted keyword scoring over title/source/description text, then ``community``
as the default fallback.

Localist type labels use table order for precedence (first match wins). That
order is deliberately independent of keyword tie-break priority — e.g. ``Arts``
beats ``Athletics`` even though sports ranks above arts in text scoring ties.
Generic labels such as ``Workshops`` stay unmapped so they only influence
keyword fallback.

Keyword concepts list every accepted textual form explicitly. Title, source
label, and description weights are 3/2/1. Bare ``performance`` and ``service``
are intentionally omitted from keyword fallback. Exact HLink category-name
labels (e.g. ``performance``, ``community service``) map via source tables;
multi-word keyword phrases such as ``dance performance`` match only in text
scoring.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

# Localist event_types: first matching row wins (independent of keyword priority).
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

# Exact observed HLink categoryNames labels (case-insensitive); not substring matching.
_HLINK_CATEGORY_NAME_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("concert", "arts"),
    ("performance", "arts"),  # HLink label only; bare keyword fallback excluded.
    ("exhibit", "arts"),
    ("dance", "arts"),
    ("cultural", "arts"),
    ("competition", "sports"),
    ("recreational", "sports"),
    ("educational", "academic"),
    ("community service", "community"),  # phrase only; bare ``service`` excluded.
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
        ("interview", "interviews", "interviewing"),
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
        ("exhibit", "exhibits", "exhibition", "exhibitions"),
        ("gallery", "galleries"),
        ("theater", "theaters", "theatre", "theatres"),
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
        ("volunteer", "volunteers", "volunteering"),
        ("outreach",),
        ("donate", "donates"),
    ),
}

# Keyword tie-break when scores are equal (independent of source-table order).
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
_missing_priority = set(_CATEGORY_CONCEPTS) - set(_CATEGORY_PRIORITY)
if _missing_priority:
    raise ValueError(
        "_CATEGORY_CONCEPTS categories missing from _CATEGORY_PRIORITY: "
        + ", ".join(sorted(_missing_priority))
    )

_TITLE_WEIGHT = 3
_SOURCE_TERM_WEIGHT = 2
_DESCRIPTION_WEIGHT = 1


def _alias_pattern_fragment(alias: str) -> str:
    parts = alias.split()
    if len(parts) == 1:
        return re.escape(alias)
    return r"\s+".join(re.escape(part) for part in parts)


def _concept_pattern(aliases: tuple[str, ...]) -> re.Pattern[str]:
    alternatives = "|".join(
        _alias_pattern_fragment(alias)
        for alias in sorted(aliases, key=len, reverse=True)
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
        key=lambda category: (scores[category], -_CATEGORY_RANK[category]),
    )


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
