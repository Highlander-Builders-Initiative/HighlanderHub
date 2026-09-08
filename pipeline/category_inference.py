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
