"""Weighted keyword inference of an Instagram event's activity.

The category is what a student would be doing there: hanging out, getting
involved with a group, building a career, learning, playing, watching a show
or volunteering. Who hosts is a separate filter (the feed's Hosted by group,
from the account directory), so words like "club" or "community" say nothing
here. Text that names no activity is "other" and appears only under All,
never in a topic it was guessed into.
"""
from __future__ import annotations

import re

_TITLE_WEIGHT = 3
_DESCRIPTION_WEIGHT = 1

# How much a concept counts in (title, description). Named in the title, a
# strong concept is the activity; in the caption it is a hint.
_STRONG = (_TITLE_WEIGHT, _DESCRIPTION_WEIGHT)
# A caption mentions these in passing ("follow our socials", "best practices"),
# so they count only in the title.
_TITLE_ONLY = (_TITLE_WEIGHT, 0)
# A format or an incidental mention, not the activity: "dance workshop" is
# arts and "watch the full interview" promotes a performance. These count at
# description weight wherever they appear, so the advertised activity wins.
_INCIDENTAL = (_DESCRIPTION_WEIGHT, _DESCRIPTION_WEIGHT)
# A weak title word that decides only when nothing stronger is named: a bare
# "meeting" is a club's, but "Social Meeting: Pumpkin Patch" is an outing.
_TITLE_HINT = (2, 0)
# Captions list what else is coming up ("see you at our general meeting") and
# name things in passing, so a single caption mention is not enough to file an
# event under a topic: it takes the title, or two signals that agree.
_MIN_SCORE = 2

_CATEGORY_CONCEPTS: dict[str, tuple[tuple[tuple[str, ...], tuple[int, int]], ...]] = {
    "get_involved": (
        (("general meeting", "general meetings", "general body meeting",
          "general body meetings", "gbm", "gbms"), _STRONG),
        (("info session", "info sessions", "information session", "information sessions",
          "informational session", "informational sessions", "info night", "info nights",
          "information night", "info meeting", "interest meeting", "interest meetings"), _STRONG),
        (("tabling",), _STRONG),
        (("org fair", "involvement fair", "club fair", "organization fair",
          "organizations fair", "sig fair"), _STRONG),
        (("tryout", "tryouts", "try-outs"), _STRONG),
        (("audition", "auditions"), _STRONG),
        (("rush",), _STRONG),
        (("recruitment",), _STRONG),
        (("open house", "open houses"), _STRONG),
        (("orientation", "orientations"), _STRONG),
        (("first meeting", "welcome meeting", "kickoff meeting", "kick-off meeting",
          "intro meeting"), _STRONG),
        (("meet the board", "meet the e-board", "meet the eboard", "meet the officers",
          "meet the team"), _STRONG),
        (("meet and greet", "meet & greet", "meet-n-greet", "meet-and-greet"), _STRONG),
        (("meeting", "meetings"), _TITLE_HINT),
        (("intro to",), _TITLE_HINT),
    ),
    "hangout": (
        (("social", "socials"), _TITLE_ONLY),
        (("mixer", "mixers"), _STRONG),
        (("party", "parties"), _STRONG),
        (("kickback", "kickbacks"), _STRONG),
        (("game night", "game nights", "games night", "board game", "board games"), _STRONG),
        (("movie night", "movie nights"), _STRONG),
        (("boba",), _STRONG),
        (("bowling",), _STRONG),
        (("bbq", "barbecue", "barbeque", "cookout"), _STRONG),
        (("picnic", "picnics"), _STRONG),
        (("potluck", "potlucks"), _STRONG),
        (("karaoke",), _STRONG),
        (("trivia",), _STRONG),
        (("bingo",), _STRONG),
        (("scavenger hunt", "scavenger hunts"), _STRONG),
        (("field day",), _STRONG),
        (("bonfire", "bonfires"), _STRONG),
        (("arcade",), _STRONG),
        (("hangout", "hangouts", "hang out"), _STRONG),
        (("carnival", "carnivals"), _STRONG),
        (("festival", "festivals"), _STRONG),
        (("study break", "study breaks"), _STRONG),
        (("craft night", "crafts night"), _STRONG),
        (("dance party", "dance parties", "dance night"), _STRONG),
        (("celebration", "celebrations"), _TITLE_ONLY),
        (("dinner", "dinners", "lunch", "brunch", "breakfast"), _TITLE_HINT),
    ),
    "career": (
        (("career", "careers"), _STRONG),
        (("internship", "internships"), _STRONG),
        (("networking",), _STRONG),
        (("resume", "resumes", "résumé", "résumés"), _STRONG),
        (("interviewing", "mock interview", "mock interviews", "interview prep",
          "interview preparation", "interview skills", "interview tips"), _STRONG),
        (("hiring",), _STRONG),
        (("recruit", "recruits"), _STRONG),
        (("job", "jobs"), _TITLE_ONLY),
        (("linkedin",), _STRONG),
        (("headshot", "headshots"), _STRONG),
        (("professional development",), _STRONG),
        (("employer", "employers"), _STRONG),
        (("pre-med", "premed", "pre-health", "pre-law", "prelaw", "pre-dental", "predental",
          "pre-pharmacy", "pre-vet", "pre-pa"), _STRONG),
        (("medical school", "med school", "law school", "grad school", "graduate school"), _STRONG),
        (("workshop", "workshops"), _INCIDENTAL),
        (("interview", "interviews"), _INCIDENTAL),
    ),
    "academic": (
        (("lecture", "lectures"), _STRONG),
        (("seminar", "seminars"), _STRONG),
        (("colloquium", "colloquiums", "colloquia"), _STRONG),
        (("symposium", "symposiums", "symposia"), _STRONG),
        (("research",), _STRONG),
        (("thesis", "theses"), _STRONG),
        (("defense", "defenses"), _STRONG),
        (("class", "classes"), _TITLE_ONLY),
        (("conference", "conferences"), _STRONG),
        (("webinar", "webinars"), _STRONG),
        (("panel", "panels"), _STRONG),
        (("speaker", "speakers", "keynote"), _STRONG),
        (("study session", "study sessions", "study hall", "study halls", "study jam",
          "study jams", "study night", "study group", "study groups", "review session",
          "review sessions"), _STRONG),
        (("tutoring", "tutor", "tutors"), _STRONG),
        (("book club",), _STRONG),
        (("talk", "talks"), _TITLE_ONLY),
    ),
    "sports": (
        (("athletic", "athletics"), _STRONG),
        (("basketball",), _STRONG),
        (("soccer",), _STRONG),
        (("baseball", "softball"), _STRONG),
        (("volleyball",), _STRONG),
        (("tennis", "pickleball", "badminton"), _STRONG),
        (("football",), _STRONG),
        (("intramural", "intramurals"), _STRONG),
        (("rugby", "lacrosse", "water polo", "hockey", "cricket", "ultimate frisbee",
          "kickball", "dodgeball", "flag football"), _STRONG),
        (("tournament", "tournaments"), _STRONG),
        (("yoga",), _STRONG),
        (("5k", "10k"), _TITLE_ONLY),
        (("fun run", "marathon", "triathlon"), _STRONG),
        (("swim", "swimming"), _STRONG),
        (("fitness", "workout", "workouts"), _STRONG),
        (("climbing", "bouldering"), _STRONG),
        (("hike", "hikes", "hiking", "backpacking", "camping"), _STRONG),
        (("snorkeling", "snorkelling", "surfing", "kayaking"), _STRONG),
        (("martial arts", "jiu jitsu", "karate", "taekwondo", "boxing", "wrestling",
          "fencing", "archery"), _STRONG),
        (("practice", "practices"), _TITLE_ONLY),
    ),
    "arts": (
        (("concert", "concerts"), _STRONG),
        (("recital", "recitals"), _STRONG),
        (("exhibit", "exhibits", "exhibition", "exhibitions"), _STRONG),
        (("gallery", "galleries"), _STRONG),
        (("theater", "theaters", "theatre", "theatres"), _STRONG),
        (("dance performance", "dance performances"), _STRONG),
        (("film", "films"), _STRONG),
        (("screening", "screenings"), _STRONG),
        (("dance", "dancing", "dancers", "dancer", "choreography", "dance workshop", "dance workshops",
          "dance class", "dance classes", "dance team", "dance troupe"), _STRONG),
        (("live performance", "live performances", "his performance", "her performance",
          "their performance", "performing arts"), _STRONG),
        (("showcase", "showcases", "talent show", "fashion show"), _STRONG),
        (("open mic", "open mics", "poetry", "spoken word"), _STRONG),
        (("choir", "orchestra", "a cappella"), _STRONG),
        (("photography", "zine", "zines"), _STRONG),
        # Named in the title, art and music describe the activity ("Riverside
        # Art & Music Festival"); in a caption they are usually one attraction
        # among several ("music, food and games"), so they count only there.
        # Hyphenated forms such as "state-of-the-art" never match (see
        # _concept_pattern).
        (("art", "arts", "artwork", "artworks", "artist", "artists"), _TITLE_ONLY),
        (("music", "musical", "musician", "musicians"), _TITLE_ONLY),
    ),
    "volunteering": (
        (("volunteer", "volunteers", "volunteering"), _STRONG),
        (("community service", "service project", "service projects", "day of service"), _STRONG),
        (("outreach",), _STRONG),
        (("donate", "donates", "donation", "donations"), _STRONG),
        (("food drive", "clothing drive", "toy drive", "blood drive", "book drive",
          "supply drive"), _STRONG),
        (("cleanup", "clean-up", "clean up", "beach cleanup"), _STRONG),
        (("philanthropy",), _STRONG),
        (("charity",), _STRONG),
    ),
}

# The HighlanderLink directory type of the posting account. It counts like a
# caption mention: it settles a tie, or confirms a caption's single mention (a
# volleyball team's "Lumberjack Classic" tournament), and never outweighs an
# activity the title names.
_HOST_TYPE_ACTIVITY = {
    "service": "volunteering",
    "athletics": "sports",
    "arts-and-expression": "arts",
    "academic-professional": "career",
    "fraternity-sorority": "hangout",
}

# Keyword tie-break when scores are equal (independent of source-table order).
# The specific activities lead; joining something and hanging out are what
# most club posts are, so they give way to anything more particular.
_CATEGORY_PRIORITY: tuple[str, ...] = (
    "sports",
    "arts",
    "career",
    "volunteering",
    "academic",
    "get_involved",
    "hangout",
)
_CATEGORY_RANK = {
    category: rank for rank, category in enumerate(_CATEGORY_PRIORITY)
}
_missing_priority = (set(_CATEGORY_CONCEPTS) | set(_HOST_TYPE_ACTIVITY.values())) - set(_CATEGORY_PRIORITY)
if _missing_priority:
    raise ValueError(
        "categories missing from _CATEGORY_PRIORITY: "
        + ", ".join(sorted(_missing_priority))
    )

UNCATEGORIZED = "other"


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
    category: tuple((_concept_pattern(aliases), weights) for aliases, weights in concepts)
    for category, concepts in _CATEGORY_CONCEPTS.items()
}


def _score(concepts: tuple[tuple[re.Pattern[str], tuple[int, int]], ...],
           title: str, description: str) -> int:
    """Each concept counts once, at the heaviest field it appears in."""
    return sum(
        max(
            (
                weight
                for text, weight in zip((title, description), weights)
                if weight and text and pattern.search(text)
            ),
            default=0,
        )
        for pattern, weights in concepts
    )


def infer_category_from_text(
    title: str,
    description: str,
    host_type: str | None = None,
) -> str:
    title, description = title.lower(), description.lower()
    scores: dict[str, int] = {}
    for category, concepts in _CATEGORY_PATTERNS.items():
        score = _score(concepts, title, description)
        if score:
            scores[category] = score
    if host_activity := _HOST_TYPE_ACTIVITY.get(host_type or ""):
        scores[host_activity] = scores.get(host_activity, 0) + _DESCRIPTION_WEIGHT
    if not scores or max(scores.values()) < _MIN_SCORE:
        return UNCATEGORIZED
    return max(
        scores,
        key=lambda category: (scores[category], -_CATEGORY_RANK[category]),
    )
