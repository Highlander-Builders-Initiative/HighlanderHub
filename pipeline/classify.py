"""Content-kind classification with fixed precedence and explicit Python tables.

Only title/description text establishes fundraising or student eligibility.
Audience cohorts are evaluated separately; deadlines match the title only.
Program applications are recognized last, so a dated cutoff still wins. OCR
text is read only by that check and to find the price behind a "good cause".
"""
from __future__ import annotations

import re
from typing import Iterable, Literal


# Shared database/app contract.
CONTENT_KINDS = (
    "student_event",
    "student_deadline",
    "student_application",
    "fundraiser",
    "other",
)
AudienceStance = Literal["student", "restricted", "unspecified"]

_STUDENT_ORIGINS = frozenset({"instagram", "manual"})

_FUNDRAISER_TERMS = (
    "fundraiser", "fundraising", "donate", "donation", "proceeds",
    "percentage night", "bake sale", "food sale", "selling food", "merch sale", "benefit night", "gofundme",
)

# A board position named for fundraising ("Fundraising Chair", "VP of
# Fundraising") recruits an officer; it does not advertise a fundraiser.
_FUNDRAISING_ROLE_PATTERN = re.compile(
    r"""
    \b(?:
        (?:fundrais(?:ing|er)|donations?)\s+
        (?:co-?)?(?:chairs?|chairpersons?|coordinators?|directors?|officers?
          |leads?|managers?|committees?|positions?|roles?|interns?)
      | (?:vp|vice\s+president|director|head|chair|coordinator|officer)
        \s+(?:of|for)\s+fundrais(?:ing|er)
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


# "All while supporting a good cause" names a beneficiary without the word
# "fundraiser". Volunteering serves a cause too, so the phrase alone is not
# enough: it becomes a fundraiser once participation is also priced
# ("Water balloon $1.50"), a price the flyer may print instead of the caption.
_CAUSE_PATTERN = re.compile(
    r"\b(?:for|support(?:s|ing)?|benefit(?:s|ing)?)\s+(?:a\s+|the\s+)?(?:good\s+)?cause\b"
    r"|\bfor\s+charity\b",
    re.IGNORECASE,
)
_PRICE_PATTERN = re.compile(r"\$\s?\d")


def _mentions_fundraising(text: str, ocr_text: str = "") -> bool:
    text = _FUNDRAISING_ROLE_PATTERN.sub(" ", text.casefold())
    # Giving blood is participation in a drive, not a monetary fundraiser.
    # Keep unrelated requests for money in the same announcement detectable.
    text = re.sub(r"\b(?:donat(?:e|ing)\s+blood|blood\s+donations?)\b", " ", text)
    if re.search(r"\bblood\s+drive\b", text):
        text = re.sub(r"\bdonations\s+for\s+citations\b", " ", text)
    if any(term in text for term in _FUNDRAISER_TERMS):
        return True
    return bool(_CAUSE_PATTERN.search(text)
                and _PRICE_PATTERN.search(f"{text}\n{ocr_text or ''}"))


_DEADLINE_TITLE_TERMS = (
    "deadline", "apply by", "register by", "closing date", "last day to",
    "applications due", "application due", "registration closes",
    "documents due",
)

# A program you join, not an occasion you attend: multi-week academies,
# fellowships, and cohorts recruit over a long window and have no single start
# time, so they age badly in a chronological feed. Recognized two ways — the
# post says how to apply, or it advertises a program-length commitment — and
# vetoed by an occasion noun in the title, because a Lunch & Learn *about* a
# program is still an event.
_OCCASION_TITLE_PATTERN = re.compile(
    r"""
    \b(?:
        workshop | seminar | webinar | session | sessions
      | office\ hours | drop-?in | hours
      | meeting | fair | expo | panel | mixer | social | reception
      | lunch | luncheon | dinner | breakfast | brunch | bbq | barbecue
      | party | anniversary | celebration | gala | festival | showcase
      | orientation | open\ house | conference | summit | symposium
      | talk | lecture | colloquium | tour | retreat | tabling
      | game | match | concert | screening | performance | watch\ party
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Unambiguous "you apply to join this" language. Bare "application" is
# deliberately absent: "Preparing for Internship Application Season" is a tips
# talk, not an application.
_APPLICATION_CALL_PATTERN = re.compile(
    r"""
    (?:
        applications?\ (?:are\ )?(?:now\ )?open
      | (?:now\ )?accepting\ applications
      | apply\ (?:now|today|here|online|early|by)
      | how\ to\ apply
      | application\ (?:deadline|window|period|portal|form)
      | priority\ deadline
      | enrollment\ is\ limited
      | enroll\ (?:now|today)
      | eligibility\ requirements
      | admission\ requirements
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# The named thing you enroll in.
_PROGRAM_NOUN_PATTERN = re.compile(
    r"""
    \b(?:
        academy|academies
      | fellowship | internship | apprenticeship | residency | practicum
      | bootcamp | boot\ camp | cohort | immersion | intensive | program
    )s?\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# A sign-up window, not an occasion: individually booked appointments.
# Like a program intake it has no single start time, so a chronological feed
# would date it to whichever hour the model guessed. The occasion-noun veto
# still applies, which is what keeps "Office Hours" an event.
_BOOKING_WINDOW_PATTERN = re.compile(
    r"""
    (?:
        book\s+(?:your|a|an)\s+(?:appointment|slot|time|meeting|1:1)
      | (?:select|choose|pick|reserve|claim|grab)\s+(?:a|your)\s+
        (?:time\s+)?(?:slot|appointment)
      | sign\s+up\s+for\s+a\s+(?:slot|time)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_APPOINTMENT_CONTEXT_PATTERN = re.compile(
    r"\b(?:appointments?|1:1|one[- ]on[- ]one|coffee\s+chats?)\b",
    re.IGNORECASE,
)

# "7-week in-person summer program", "10 month fellowship" — a printed span
# next to the program noun. Years are excluded on purpose ("10 Year
# Anniversary" is an event); the span must sit close to the noun so an
# unrelated "6 weeks away" elsewhere in the blurb cannot pair with it.
_PROGRAM_COMMITMENT_PATTERN = re.compile(
    r"""
    \b\d+\s*-?\s*(?:week|month)s?\b
    [\w\s,&'\-]{0,40}?
    \b(?:academy|fellowship|internship|apprenticeship|residency|bootcamp
        |cohort|immersion|intensive|program)s?\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Eligibility grammar is separate from the student-organization vocabulary.
# Generic activity nouns (workshop, concert, wellness) do not qualify.
_STUDENT_ELIGIBILITY = re.compile(
    r"""
    \b(?:
        open\ to\ (?:the\ )?(?:all\ |any\ |current\ |ucr\ )*students
      | (?:all|any|current|ucr|undergraduate|graduate|incoming|new|prospective
        |transfer|international|first-year|first-generation)\ students
      | students?\ (?:are\ |is\ )?(?:welcome|invited|encouraged)
      | for\ (?:ucr\ |all\ |our\ )?students
      | undergraduates?
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

_STUDENT_ORG_TERMS = (
    "student organization", "student org", "student club", "student group",
    "student body", "student government", "student leader", "student leaders",
    "student life", "student success center",
    "rso", "asucr", "hackathon", "intramural",
    "general meeting", "general body meeting", "gbm",
    "club meeting", "club fair", "club sport", "club social",
    "greek life", "sorority", "fraternity",
)
_STUDENT_ORG_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(term) for term in _STUDENT_ORG_TERMS) + r")\b",
    re.IGNORECASE,
)

# Whole audience tokens, including explicit inflections instead of stems.
_STUDENT_AUDIENCE_TOKENS = frozenset({"student", "students"})
_RESTRICTED_AUDIENCE_TOKENS = frozenset({
    "faculty", "staff", "employee", "employees",
    "alumni", "alumna", "alumnae", "alumnus",
    "parent", "parents", "family", "families",
    "retiree", "retirees", "emeritus", "emerita", "emeriti", "emeritae",
    "donor", "donors", "employer", "employers",
})
_OPEN_AUDIENCE_PHRASES = (
    "general public", "everyone", "campus community", "all audiences",
)

# Provision is required; naming a food or visiting a restaurant is insufficient.
_FOOD_NOUN = (r"(?:food|pizza|snacks?|drinks?|beverages?|refreshments|breakfast|lunch|dinner|"
              r"boba|tacos?|burgers?|hot dogs?|coffee|matcha|teas?|treats?|desserts?|"
              r"popsicles?|poke(?: bowls?)?|kona ice|shaved ice|ice cream)")
_FREE_FOOD_PATTERN = re.compile(
    rf"\b(?:free\s+(?:(?!at\b|from\b|with\b|for\b|to\b|in\b|during\b)\S+\s+){{0,3}}?{_FOOD_NOUN}|refreshments|"
    rf"{_FOOD_NOUN}(?:\s+(?:&|and)\s+\w+)?\s+(?:(?:will\s+be|is|are)\s+)?"
    rf"(?:provided|served|included|available|while supplies last)|"
    rf"(?:catering|serving|giving out|handing out)\s+(?:\w+\s+){{0,2}}?{_FOOD_NOUN}|"
    # Not 'join us for dinner'/'enjoy dinner': that is how restaurant trips read.
    rf"(?:there will be|come grab|we['’]re having|we['’]ll have|we will have)\s+"
    rf"(?:(?:some|light)\s+|music,\s*)?{_FOOD_NOUN})\b",
    re.IGNORECASE,
)
_FOOD_NEGATED_BEFORE = re.compile(
    r"\b(?:no|not|without|bring (?:your|their|our) own|(?:do|does) not (?:offer|provide)|"
    r"(?:won['’]?t|will not) (?:have|provide|offer|be (?:providing|serving)))\s*$", re.I)
_FOOD_NEGATED_AFTER = re.compile(
    r"\s*(?:(?:is|are|will be)\s+)?(?:not (?:provided|available|free|included|guaranteed)|"
    r"(?:will not|won['’]?t) be (?:provided|served|available)|"
    r"(?:for|available for) (?:sale|purchase)|with (?:a |any )?purchase|costs?\b|(?:for\s+)?\$\s*\d|chats?\b)", re.I)
# "Included" bundles food with something: a $15 ticket, a registration fee.
# Only an unpriced clause makes it an offer ("PIZZA INCLUDED").
_FOOD_BUNDLE_PRICED = re.compile(
    r"\$\s*\d|\b(?:purchase|paid)\b|(?<!free )\b(?:tickets?|fees?|dues|admission|registration)\b", re.I)
# Boba is a club's usual treat, but "Boba Tea House" is a shop students pay
# at, and a boba fundraiser ("fundy") sells it. Only a session's own title
# says what that session offers; a sibling session's boba says nothing.
_BOBA_TITLE_PATTERN = re.compile(r"\bboba\b(?!\s+(?:tea\s+)?(?:house|shop|fundraiser|fundy)\b)", re.IGNORECASE)


def detect_free_food(*texts: str | None) -> bool:
    """An affirmative food offer, with local negation and sale/price vetoes.

    Evaluate offers separately so 'no pizza, but free tacos' still counts, and
    never join unrelated fields into a new phrase ('free admission' + 'boba').
    """
    for text in texts:
        for clause in re.split(r"[;!?\n]|(?<!oz)(?<!\d)\.(?!\d)|\bbut\b", text or "", flags=re.I):
            for match in _FREE_FOOD_PATTERN.finditer(clause):
                if (_FOOD_NEGATED_BEFORE.search(clause[:match.start()])
                        or _FOOD_NEGATED_AFTER.match(clause, match.end())
                        or (match.group().casefold().endswith("included")
                            and _FOOD_BUNDLE_PRICED.search(clause))):
                    continue
                return True
    return False


def title_offers_boba(title: str, text: str = "") -> bool:
    """A session titled for its boba ("Games & Boba"), not a shop trip or fundraiser."""
    contradicted = re.search(r"\bboba\s+(?:\$\s*\d|for (?:sale|purchase)|not (?:provided|free))|"
                            r"\b(?:no|without)\s+(?:free\s+)?boba\b", text, re.I)
    return bool(_BOBA_TITLE_PATTERN.search(title) and not _mentions_fundraising(title) and not contradicted
                and not re.search(r"\$\s*\d|\b(?:no|without)\s+(?:free\s+)?boba\b|"
                                  r"\bboba\s+(?:for (?:sale|purchase)|not (?:provided|free))", title, re.I))


def is_informational_notice(title: str, description: str = "", ocr_text: str = "") -> bool:
    """Recognize dated service notices and awareness/resource posts, not gatherings."""
    if _mentions_fundraising(f"{title} {description}"):
        return False
    if re.search(r"\b(?:closures?|closed|modified hours)\b", title, re.IGNORECASE):
        return not _OCCASION_TITLE_PATTERN.search(title.replace("Hours", "").replace("hours", ""))
    if not re.search(r"\b(?:awareness|prevention)\b.*\b(?:day|week|month)\b", title, re.IGNORECASE):
        return False
    if _OCCASION_TITLE_PATTERN.search(title):
        return False
    text = f"{description}\n{ocr_text}"
    # Campaigns may advertise real timed activities; retain those.
    if (_OCCASION_TITLE_PATTERN.search(text)
            and re.search(r"\b\d{1,2}(?::\d{2})?\s*[ap]\.?m\b", text, re.IGNORECASE)):
        return False
    return True


def _audience_stance(audiences: Iterable) -> AudienceStance:
    """Student cohorts win; public cohorts remove restrictions without promoting."""
    restricted = False
    open_to_all = False
    for audience in audiences or ():
        # Normalize punctuation/spacing so "Parents/Family" and
        # "General Public/Off-Campus Community" match complete words/phrases.
        words = re.findall(r"\w+", str(audience).casefold().replace("_", " "))
        tokens = set(words)
        if tokens & _STUDENT_AUDIENCE_TOKENS:
            return "student"
        name = f" {' '.join(words)} "
        if any(f" {phrase} " in name for phrase in _OPEN_AUDIENCE_PHRASES):
            open_to_all = True
        if tokens & _RESTRICTED_AUDIENCE_TOKENS:
            restricted = True
    return "restricted" if restricted and not open_to_all else "unspecified"


def _is_program_application(title: str, text: str) -> bool:
    """True when the text recruits for a program rather than announcing an event."""
    # An occasion noun in the title settles it: this is something you attend.
    if _OCCASION_TITLE_PATTERN.search(title):
        return False
    if (_BOOKING_WINDOW_PATTERN.search(text)
            and _APPOINTMENT_CONTEXT_PATTERN.search(text)):
        return True
    if _APPLICATION_CALL_PATTERN.search(text):
        return bool(_PROGRAM_NOUN_PATTERN.search(text))
    return bool(_PROGRAM_COMMITMENT_PATTERN.search(text))


def classify_content_kind(
    origin: str,
    *,
    title: str = "",
    description: str = "",
    tags: Iterable = (),
    audiences: Iterable = (),
    ocr_text: str = "",
    assessed_kind: str | None = None,
) -> str:
    """Classify with fundraiser precedence, then eligibility, then title cutoff.

    Tags remain accepted for existing callers but never feed text matching.
    `ocr_text` is read by the program-application check: a flyer prints the
    sign-up mechanics ("select a slot", "limited slots") that the caption
    leaves out. Reading it for fundraising terms or eligibility would promote
    every donation line and audience note in a flyer's fine print, so it only
    supplies the price for a cause the title or description already names.
    """
    title = (title or "").casefold()
    text = f"{title} {description or ''}".casefold()
    if assessed_kind in {"announcement", "uncertain"}:
        return "other"
    if assessed_kind is None and is_informational_notice(title, description, ocr_text):
        return "other"
    if _mentions_fundraising(text, ocr_text):
        return "fundraiser"

    # Student/club origins bypass audience and text eligibility checks.
    if origin not in _STUDENT_ORIGINS:
        stance = _audience_stance(audiences)
        if stance == "restricted":
            return "other"
        if (stance == "unspecified"
                and not _STUDENT_ELIGIBILITY.search(text)
                and not _STUDENT_ORG_PATTERN.search(text)):
            return "other"

    # A source-grounded assessment establishes content type independently of
    # audience and fundraising. The legacy heuristics below only serve old
    # callers; production imports assess the source before publishing.
    # The kind is assessed per post, so an activity post that also prints a
    # cutoff ("Applications due 10 PM") titles that session as the deadline.
    if assessed_kind == "activity" and any(term in title for term in _DEADLINE_TITLE_TERMS):
        return "student_deadline"
    if assessed_kind is not None:
        return {
            "activity": "student_event", "service_schedule": "student_event",
            "deadline": "student_deadline", "application": "student_application",
        }.get(assessed_kind, "other")

    # Body text may mention a related cutoff without making this a deadline.
    if any(term in title for term in _DEADLINE_TITLE_TERMS):
        return "student_deadline"

    # Checked after the cutoff so a dated "Applications Due Friday" stays a
    # deadline; this catches the open-ended program pitch behind it.
    if _is_program_application(title, f"{text} {(ocr_text or '').casefold()}"):
        return "student_application"
    return "student_event"
