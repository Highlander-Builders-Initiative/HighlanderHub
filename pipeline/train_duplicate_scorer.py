"""Fit the duplicate scorer's weights from labelled pairs of listings.

    python train_duplicate_scorer.py            # report only
    python train_duplicate_scorer.py --write    # also save duplicate_scorer_model.json

Labelled pairs live in tests/fixtures/duplicate-scorer-pairs.json; pass more
files of the same shape with --pairs (an export of admin decisions, say).
The fit is a plain L2 logistic regression, small enough to need no library.
Thresholds come from held-out scores: every pair is scored by a model that
never saw its day.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import duplicate_scorer as scorer
import reconcile_events as rules
from event_dates import PACIFIC_TZ

PAIRS_FILE = Path(__file__).parent / "tests/fixtures/duplicate-scorer-pairs.json"
FOLDS, EPOCHS, RATE, L2 = 5, 4000, 1.0, 0.001
# A false merge hides an event; a missed duplicate is clutter. The merge
# threshold must clear every held-out non-duplicate by this margin, measured
# in log-odds so that it still means something near 1.
MERGE_MARGIN, MERGE_FLOOR, DISMISS_BELOW = 0.5, 0.95, 0.10


def load(paths: list[Path]) -> list[dict]:
    examples = []
    for path in paths:
        data = json.loads(path.read_text())
        for pair in data["pairs"]:
            left, right = data["rows"][pair["a"]], data["rows"][pair["b"]]
            if pair["label"] == "unclear" or not scorer.comparable(left, right):
                continue
            day = rules._parse_instant(left["starts_at"]).astimezone(PACIFIC_TZ).date().isoformat()
            values = scorer.features(left, right, data["corpus"])
            examples.append({"x": [values[name] for name in scorer.FEATURES], "y": pair["label"] == "duplicate",
                             "day": day, "source": pair["source"], "pair": (left, right)})
    return examples


def fit(examples: list[dict]) -> tuple[float, list[float]]:
    """Batch gradient descent, weighting both labels equally."""
    positives = sum(e["y"] for e in examples)
    weight = {True: len(examples) / (2 * positives), False: len(examples) / (2 * (len(examples) - positives))}
    bias, weights = 0.0, [0.0] * len(scorer.FEATURES)
    for _ in range(EPOCHS):
        grad_bias, grad = 0.0, [0.0] * len(weights)
        for e in examples:
            total = bias + sum(w * x for w, x in zip(weights, e["x"]))
            error = (1 / (1 + math.exp(-max(-30.0, min(30.0, total)))) - e["y"]) * weight[e["y"]]
            grad_bias += error
            for i, x in enumerate(e["x"]):
                if x:
                    grad[i] += error * x
        bias -= RATE * grad_bias / len(examples)
        weights = [w - RATE * (g / len(examples) + L2 * w) for w, g in zip(weights, grad)]
    return bias, weights


def predict(bias: float, weights: list[float], x: list[float]) -> float:
    return 1 / (1 + math.exp(-max(-30.0, min(30.0, bias + sum(w * v for w, v in zip(weights, x))))))


def held_out(examples: list[dict]) -> list[float]:
    """Each pair's score from a model fit without any pair from its day."""
    days = sorted({e["day"] for e in examples})
    fold = {day: i % FOLDS for i, day in enumerate(days)}
    scores = [0.0] * len(examples)
    for k in range(FOLDS):
        bias, weights = fit([e for e in examples if fold[e["day"]] != k])
        for i, e in enumerate(examples):
            if fold[e["day"]] == k:
                scores[i] = predict(bias, weights, e["x"])
    return scores


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pairs", type=Path, action="append", default=[])
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    examples = load([PAIRS_FILE, *args.pairs])
    scores = held_out(examples)
    # Pairs the rules already merge teach the shape of a duplicate but are
    # never scored in production, so thresholds ignore them.
    hard = [(s, e) for s, e in zip(scores, examples) if e["source"] != "rules"]
    highest_different = max(s for s, e in hard if not e["y"])
    clear = 1 / (1 + math.exp(-(math.log(highest_different / (1 - highest_different)) + MERGE_MARGIN)))
    merge_at = math.ceil(max(MERGE_FLOOR, clear) * 1000) / 1000
    counts = Counter((e["y"], "merge" if s >= merge_at else "dismiss" if s < DISMISS_BELOW else "review")
                     for s, e in hard)
    print(f"{len(examples)} pairs ({sum(e['y'] for e in examples)} duplicates); "
          f"{len(hard)} the rules leave apart")
    print(f"held out: highest non-duplicate {highest_different:.3f}, lowest duplicate "
          f"{min(s for s, e in hard if e['y']):.3f}; merge_at {merge_at}; dismiss_below {DISMISS_BELOW}")
    for label, name in ((True, "duplicates"), (False, "non-duplicates")):
        print(f"  {name}: merge {counts[(label, 'merge')]}, review {counts[(label, 'review')]}, "
              f"dismiss {counts[(label, 'dismiss')]}")
    # The review queue is where a verdict would save an admin's time; random
    # same-day pairs are easy to dismiss and flatter the totals above.
    queue = [(s, e) for s, e in hard if e["source"] != "random"]
    by_verdict = Counter((e["y"], "merge" if s >= merge_at else "dismiss" if s < DISMISS_BELOW else "review")
                         for s, e in queue)
    ordered = sum((a > b) + 0.5 * (a == b) for a, x in queue if x["y"] for b, z in queue if not z["y"])
    print(f"  queue-like pairs only ({len(queue)}): duplicates merge {by_verdict[(True, 'merge')]}, "
          f"review {by_verdict[(True, 'review')]}, dismiss {by_verdict[(True, 'dismiss')]}; non-duplicates "
          f"merge {by_verdict[(False, 'merge')]}, review {by_verdict[(False, 'review')]}, "
          f"dismiss {by_verdict[(False, 'dismiss')]}")
    print(f"  a duplicate outranks a non-duplicate {ordered / max(1, sum(e['y'] for _, e in queue) * sum(not e['y'] for _, e in queue)):.0%} of the time")
    for cut in (0.5, 0.8, 0.9, 0.95, 0.98, 0.99, 0.995, 0.999):
        print(f"  at {cut}: {sum(s >= cut for s, e in hard if e['y'])} duplicates, "
              f"{sum(s >= cut for s, e in hard if not e['y'])} non-duplicates")
    for s, e in sorted(hard, key=lambda item: -item[0]):
        if (not e["y"] and s >= 0.5) or (e["y"] and s < DISMISS_BELOW):
            print(f"  {'duplicate' if e['y'] else 'different'} scored {s:.2f}: "
                  f"{e['pair'][0]['title']!r} / {e['pair'][1]['title']!r}")
    bias, weights = fit(examples)
    for name, w in sorted(zip(scorer.FEATURES, weights), key=lambda item: -item[1]):
        print(f"  {w:+.2f} {name}")
    if args.write:
        model = {"bias": round(bias, 4), "weights": {n: round(w, 4) for n, w in zip(scorer.FEATURES, weights)},
                 "merge_at": merge_at, "dismiss_below": DISMISS_BELOW,
                 "trained_on": {"pairs": len(examples), "duplicates": sum(e["y"] for e in examples),
                                "held_out_duplicates": {v: counts[(True, v)] for v in ("merge", "review", "dismiss")},
                                "held_out_non_duplicates": {v: counts[(False, v)] for v in ("merge", "review", "dismiss")}}}
        scorer.MODEL_FILE.write_text(json.dumps(model, indent=1) + "\n")
        print(f"wrote {scorer.MODEL_FILE.name}")


if __name__ == "__main__":
    main()
