"""Weighted keyword category inference for Instagram event text."""
from __future__ import annotations

import re

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


def infer_category_from_text(
    title: str,
    description: str,
) -> str:
    fields = (
        (title.lower(), _TITLE_WEIGHT),
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
