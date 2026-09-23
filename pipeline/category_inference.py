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
        ("networking",),
        ("resume", "resumes"),
        ("interviewing", "mock interview", "mock interviews", "interview prep",
         "interview preparation", "interview skills", "interview tips"),
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
        ("dancers", "dancer", "choreography", "dance workshop", "dance workshops",
         "dance class", "dance classes", "dance team", "dance troupe"),
        ("live performance", "live performances", "his performance", "her performance",
         "their performance", "performing arts"),
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

# A format or an incidental mention, not the activity: "dance workshop" is
# arts and "watch the full interview" promotes a performance. These count at
# description weight wherever they appear, so the advertised activity wins.
_INCIDENTAL_CONCEPTS: dict[str, tuple[tuple[str, ...], ...]] = {
    "career": (
        ("workshop", "workshops"),
        ("interview", "interviews"),
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
_INCIDENTAL_PATTERNS = {
    category: tuple(_concept_pattern(aliases) for aliases in concepts)
    for category, concepts in _INCIDENTAL_CONCEPTS.items()
}


def _score(patterns: tuple[re.Pattern[str], ...],
           fields: tuple[tuple[str, int], ...]) -> int:
    return sum(
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


def infer_category_from_text(
    title: str,
    description: str,
) -> str:
    fields = (
        (title.lower(), _TITLE_WEIGHT),
        (description.lower(), _DESCRIPTION_WEIGHT),
    )
    incidental = tuple((text, _DESCRIPTION_WEIGHT) for text, _ in fields)
    scores: dict[str, int] = {}
    for category, patterns in _CATEGORY_PATTERNS.items():
        score = (_score(patterns, fields)
                 + _score(_INCIDENTAL_PATTERNS.get(category, ()), incidental))
        if score:
            scores[category] = score
    if not scores:
        return "community"
    return max(
        scores,
        key=lambda category: (scores[category], -_CATEGORY_RANK[category]),
    )
