"""Score how likely two listings are one occasion, and report it in shadow.

reconcile_events merges only corroborated repeats and queues the rest for an
admin, who cannot keep up: most queued pairs expire undecided, and most of
those are duplicates. This scores every same-day pair the rules left apart
with a small logistic model over the evidence the rules already compute, so
that a confident pair could merge, an unlikely one could leave the queue, and
only the middle would need a person.

Shadow mode: nothing here writes. Each run logs what the scorer would do and
how that compares with every decision an admin has made, which is the
evidence for (or against) letting it act.
"""
from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import reconcile_events as rules
from event_dates import PACIFIC_TZ

log = logging.getLogger("pipeline.duplicate_scorer")
MODEL_FILE = Path(__file__).with_name("duplicate_scorer_model.json")

# Words that mark a listing as one part of a larger occasion.
_PART_WORDS = frozenset("volunteer volunteers volunteering shift shifts tabling booth table "
                        "ride rides carpool tailgate rehearsal".split())
_CAMPUS = frozenset("ucr uc riverside university california highlander highlanders".split())


def _title_words(row: dict) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", rules._title_text(str(row.get("title") or "")))
            if len(word) > 1} - rules._TITLE_NOISE


def word_accounts(rows: list[dict]) -> dict:
    """How many accounts use each title word.

    A word many accounts put in a title ("meeting", "guest", "night") names a
    format; a word few do ("Diwali", "Coro") names an occasion. Counted from
    the listings themselves, so no stoplist needs keeping.
    """
    by_account: dict[str, set[str]] = {}
    for row in rows:
        by_account.setdefault(rules._account(row) or str(row.get("id")), set()).update(_title_words(row))
    return {"accounts": len(by_account),
            "words": dict(Counter(word for words in by_account.values() for word in words))}


def _rarity(word: str, corpus: dict) -> float:
    return math.log((corpus["accounts"] + 1) / (corpus["words"].get(word, 0) + 1))


def _grams(text: str, size: int = 3) -> set[str]:
    text = re.sub(r"[^a-z0-9]", "", rules._title_text(text))
    return {text[i:i + size] for i in range(max(1, len(text) - size + 1))} if text else set()


def _shingles(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", str(text or "").casefold())
    return {" ".join(words[i:i + 3]) for i in range(len(words) - 2)}


def _local(row: dict) -> datetime | None:
    start = rules._parse_instant(row.get("starts_at"))
    return start.astimezone(PACIFIC_TZ) if start else None


FEATURES = (
    "same_account", "same_start", "near_start", "far_start", "one_untimed", "both_untimed",
    "ends_conflict", "place_same", "place_conflict", "shared_venue", "same_signup",
    "title_rare_shared", "title_rare_jaccard", "title_subset", "title_spelling",
    "caption_overlap", "title_in_caption", "credited", "names_other_host",
    "part_marker", "held_at", "one_session", "both_session", "deadline",
    "same_title", "title_rare_unshared", "title_rare_extra", "both_own_named", "at_shared_occasion",
    "slot_venue_word", "account_start_word", "cross_far_start", "untimed_word",
    "cross_slot", "cross_slot_venue",
)


def features(left: dict, right: dict, corpus: dict) -> dict[str, float]:
    """The evidence for and against one occasion, each between 0 and 1."""
    same_account = rules._same_account(left, right)
    starts = [rules._parse_instant(row.get("starts_at")) for row in (left, right)]
    untimed = [rules._untimed(row) or not rules._specific_slot(row) for row in (left, right)]
    timed = not any(untimed)
    gap = abs((starts[0] - starts[1]).total_seconds()) / 60 if all(starts) else 0.0
    same_start = starts[0] == starts[1]
    ends = {rules._parse_instant(row.get("ends_at")) for row in (left, right)} - {None}
    place = rules._same_place(left, right)
    # Two unrelated webinars are both "on Zoom"; that names no shared venue.
    if place == "same" and rules._place_words(left) | rules._place_words(right) <= {"virtual"}:
        place = "missing"

    own = rules._own_name_words(left) | rules._own_name_words(right)
    words = [_title_words(row) - own for row in (left, right)]
    shared, either = words[0] & words[1], words[0] | words[1]
    rare_shared = sum(_rarity(word, corpus) for word in shared)
    rare_either = sum(_rarity(word, corpus) for word in either)
    distinct = [{word for word in group if _rarity(word, corpus) >= 2.0} for group in words]
    subset = bool(distinct[0] and distinct[1] and (distinct[0] <= distinct[1] or distinct[1] <= distinct[0]))
    grams = [_grams(str(row.get("title") or "")) for row in (left, right)]
    spelling = len(grams[0] & grams[1]) / max(1, min(len(grams[0]), len(grams[1])))

    captions = [_shingles(row.get("description")) for row in (left, right)]
    overlap = (len(captions[0] & captions[1]) / min(len(captions[0]), len(captions[1]))
               if min(len(captions[0]), len(captions[1])) >= 15 else 0.0)
    signup = rules._rsvp_identity(left.get("rsvp_url"))
    names_other = any((rules._own_name_words(other) - _CAMPUS - rules._GENERIC_WORDS) & _title_words(row)
                      for row, other in ((left, right), (right, left))) and not same_account
    part = [bool(_title_words(row) & _PART_WORDS) for row in (left, right)]
    held_at = any(rules._held_at(row, rules._slot_title_words(other)) and bool(rules._slot_title_words(other))
                  for row, other in ((left, right), (right, left)))
    sessions = [rules._session_row(row) for row in (left, right)]
    rare = min(rare_shared / 12, 1.0)
    # Distinctive words each title has that the other lacks: "add a course"
    # and "withdraw from a course" share a deadline's wording, not its action.
    extra = [sum(_rarity(word, corpus) for word in group - shared) for group in words]
    # "GCAP Tabling" and "Turning Point USA Tabling": each club put its own
    # name on its own table.
    own_named = [bool((rules._own_name_words(row) - _CAMPUS - rules._GENERIC_WORDS) & _title_words(row))
                 for row in (left, right)]
    # "Flower Bouquets at SWANA Heritage Night": what the titles share is
    # where this listing happens, and it names something of its own first.
    at_shared = any(
        bool(shared & _title_words({"title": title[match.end():]}))
        and bool(_title_words({"title": title[:match.start()]}) - shared - own)
        for title in (rules._title_text(str(row.get("title") or "")) for row in (left, right))
        for match in re.finditer(r"\s(?:at|@)\s", title))
    cross_slot = not same_account and timed and same_start and len(ends) <= 1
    return {
        "same_account": float(same_account),
        "same_start": float(same_start),
        "near_start": float(timed and not same_start and gap <= 60),
        "far_start": float(timed and gap > 60),
        "one_untimed": float(untimed[0] != untimed[1]),
        "both_untimed": float(all(untimed)),
        "ends_conflict": float(timed and len(ends) > 1),
        "place_same": float(place == "same"),
        "place_conflict": float(place == "conflicting"),
        "shared_venue": float(rules._shared_venue(left, right)),
        "same_signup": float(bool(signup) and signup == rules._rsvp_identity(right.get("rsvp_url"))),
        "title_rare_shared": rare,
        "title_rare_jaccard": rare_shared / rare_either if rare_either else 0.0,
        "title_subset": float(subset),
        "title_spelling": spelling,
        "caption_overlap": overlap,
        "title_in_caption": float(rules._title_phrase_in_description(left, right)
                                  or rules._title_phrase_in_description(right, left)),
        "credited": float(rules._credits(left, right) or rules._credits(right, left)),
        "names_other_host": float(names_other),
        "part_marker": float(part[0] != part[1]),
        "held_at": float(held_at),
        "one_session": float(sessions[0] != sessions[1]),
        "both_session": float(all(sessions)),
        "deadline": float(left.get("content_kind") == "student_deadline"),
        "same_title": float(bool(words[0]) and words[0] == words[1]),
        "title_rare_unshared": min(min(extra) / 12, 1.0),
        "title_rare_extra": min(max(extra) / 12, 1.0),
        "both_own_named": float(not same_account and all(own_named)),
        "at_shared_occasion": float(at_shared),
        # Evidence that only counts together.
        "slot_venue_word": float(same_start and place == "same") * rare,
        "account_start_word": float(same_account and same_start) * rare,
        "cross_far_start": float(not same_account and timed and gap > 60),
        "untimed_word": float(untimed[0] != untimed[1]) * rare,
        "cross_slot": float(cross_slot),
        "cross_slot_venue": float(cross_slot and place == "same"),
    }


def comparable(left: dict, right: dict) -> bool:
    """Whether a pair could be one occasion at all: one kind, one local day,
    not two sessions of one post, and titles that name no other occurrence."""
    days = [_local(row) for row in (left, right)]
    return bool(all(days) and days[0].date() == days[1].date()
                and left.get("content_kind") == right.get("content_kind")
                and left.get("id") != right.get("id")
                and not rules._sibling_sessions(left, right)
                and not rules._contradicting_titles(left, right))


class Scorer:
    def __init__(self, model: dict | None = None):
        self.model = model or json.loads(MODEL_FILE.read_text())
        self.merge_at, self.dismiss_below = self.model["merge_at"], self.model["dismiss_below"]

    def score(self, left: dict, right: dict, corpus: dict) -> float:
        """The probability that two comparable listings are one occasion."""
        if not comparable(left, right):
            return 0.0
        values = features(left, right, corpus)
        total = self.model["bias"] + sum(self.model["weights"][name] * values[name] for name in FEATURES)
        return 1 / (1 + math.exp(-max(-30.0, min(30.0, total))))

    def verdict(self, score: float) -> str:
        return "merge" if score >= self.merge_at else "dismiss" if score < self.dismiss_below else "review"


_ACTIONS = {"merge": "merge", "dismiss": "dismiss from review", "review": "leave for review"}


def _label(row: dict) -> str:
    return f"{row.get('id')} {row.get('title')!r} (@{row.get('host_handle')})"


def shadow_report(rows: list[dict], reviews: list[dict], *, now: datetime,
                  scorer: Scorer | None = None) -> dict:
    """What the scorer would do with the live listings, and how it compares
    with the admin's decisions. Pure: returns the lines to log."""
    scorer = scorer or Scorer()
    # Word rarity needs the whole feed: among a handful of listings every
    # word looks equally rare.
    corpus = word_accounts(rows)
    decided = {frozenset((r["event_id"], r["other_event_id"])): r["status"]
               for r in reviews if r["status"] != "pending"}
    upcoming = [row for row in rows if (start := rules._parse_instant(row.get("starts_at")))
                and (rules._parse_instant(row.get("ends_at")) or start) >= now]
    by_day: dict[tuple, list[dict]] = {}
    for row in upcoming:
        by_day.setdefault((row.get("content_kind"), _local(row).date()), []).append(row)
    queued = {frozenset((a["id"], b["id"])) for a, b in rules.review_candidates(rows, now=now)} - decided.keys()
    pairs, scored = [], 0
    for group in by_day.values():
        group.sort(key=lambda row: row["id"])
        for i, left in enumerate(group):
            for right in group[i + 1:]:
                pair = frozenset((left["id"], right["id"]))
                if pair in decided or not comparable(left, right) or rules.same_event(left, right):
                    continue
                scored += 1
                score = scorer.score(left, right, corpus)
                verdict = scorer.verdict(score)
                # Every queued pair is reported with its score, so another
                # threshold can be judged from the logs; an unqueued pair
                # only when it would merge.
                if pair in queued or verdict == "merge":
                    pairs.append({"score": score, "verdict": verdict, "queued": pair in queued,
                                  "left": left, "right": right})
    # Every decision an admin made, scored on the listings as they saw them.
    agreement: dict[str, Counter] = {"duplicate": Counter(), "different": Counter()}
    disagreements = []
    for review in reviews:
        left, right = review.get("event_snapshot"), review.get("other_snapshot")
        if review["status"] not in agreement or not isinstance(left, dict) or not isinstance(right, dict):
            continue
        score = scorer.score(left, right, corpus)
        verdict = scorer.verdict(score)
        agreement[review["status"]][verdict] += 1
        if (review["status"], verdict) in {("duplicate", "dismiss"), ("different", "merge")}:
            disagreements.append((review["status"], score, left, right))
    return {"scored": scored, "pairs": sorted(pairs, key=lambda p: (-p["score"], p["left"]["id"])),
            "queued": len(queued),
            "agreement": {status: dict(counts) for status, counts in agreement.items()},
            "disagreements": disagreements}


def main() -> None:
    """Log the shadow report. Never raises: this stage decides nothing."""
    try:
        from db import get_decided_duplicate_reviews, get_duplicate_reviews
        pending = [r for r in get_duplicate_reviews() if r["status"] == "pending"]
        report = shadow_report(rules._reconciliation_rows(), [*pending, *get_decided_duplicate_reviews()],
                               now=datetime.now(timezone.utc))
    except Exception:  # noqa: BLE001 - a report must not fail the run.
        log.exception("Shadow duplicate scorer failed; nothing was changed")
        return
    for pair in report["pairs"]:
        log.info("Shadow scorer would %s (%.3f, %s): %s and %s", _ACTIONS[pair["verdict"]], pair["score"],
                 "queued" if pair["queued"] else "not queued", _label(pair["left"]), _label(pair["right"]))
    for status, score, left, right in report["disagreements"]:
        log.warning("Shadow scorer disagrees with admin decision %r (%.3f): %s and %s",
                    status, score, _label(left), _label(right))
    counts = Counter(pair["verdict"] for pair in report["pairs"])
    log.info("Shadow scorer: %d pairs scored, %d of them queued; would merge %d, dismiss %d, leave %d for review",
             report["scored"], report["queued"], counts["merge"], counts["dismiss"], counts["review"])
    for status, counts in report["agreement"].items():
        log.info("Shadow scorer on %d admin %r decisions: merge %d, review %d, dismiss %d",
                 sum(counts.values()), status, counts.get("merge", 0), counts.get("review", 0),
                 counts.get("dismiss", 0))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
