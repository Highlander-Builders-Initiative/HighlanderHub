"""Run the reviewed semantic cases through the actual model, without publishing.

    python evaluate_content_assessment.py --report /tmp/assessment-eval.json

Unlike contract tests, this measures real classification responses. The report
records failures and source evidence; it contains no credentials. Existing
versioned assessments are reused unless --fresh is supplied.

To trial another model, override it and also re-assess a sample of saved real
decisions. These are fresh calls; nothing is cached or published:

    python evaluate_content_assessment.py --report /tmp/eval.json \\
        --model gemini-3.5-flash-lite --archive 30

A saved decision is the current model's answer, not ground truth: archive
disagreements need a human look and do not fail the run.
"""
import argparse
import itertools
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import content_assessment as semantic
from assessed_events import CACHE_DIR, cached_assessment

TOKEN_KEYS = ("prompt_token_count", "cached_content_token_count", "candidates_token_count", "thoughts_token_count")


def fresh_assessment(source: dict, usage: list) -> dict:
    try:
        return {"status": "complete", "result": semantic.assess(source, usage=usage)}
    except semantic.GroundingRejected as exc:
        return {"status": "error", "error": str(exc), "retryable": False, "validation_attempts": exc.attempts}


def decision(payload: dict) -> dict:
    """What publication acts on: kind, date role and dates, or a refusal."""
    if payload.get("status") != "complete":
        return {"status": "refused" if payload.get("retryable") is False else "error"}
    result, schedule = payload["result"], payload["result"].get("schedule")
    starts = (datetime.fromisoformat(item["starts_at"].replace("Z", "+00:00")) for item in result["occurrences"])
    return {"kind": result["kind"], "date_role": result["date_role"],
            "starts_at": sorted(start.astimezone(timezone.utc).isoformat() for start in starts),
            "schedule": schedule and [schedule["first_day"], schedule["last_day"], sorted(schedule["weekdays"])]}


def archive_sample(limit: int) -> list[dict]:
    """Saved model decisions, taken round-robin across kinds and refusals."""
    groups = defaultdict(list)
    for path in sorted(CACHE_DIR.glob("*.json")):
        saved = json.loads(path.read_text())
        # Reviewed decisions are regressions, not model answers; only Instagram
        # sources are still assessed.
        if not saved.get("model") or saved["source"].get("origin") != "instagram":
            continue
        if saved.get("status") == "complete":
            groups[saved["result"]["kind"]].append(saved)
        elif saved.get("retryable") is False:
            groups["refused"].append(saved)
    return [saved for row in itertools.zip_longest(*groups.values()) for saved in row if saved][:limit]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--synthetic", action="store_true", help="only authored test examples; exclude saved real source content")
    parser.add_argument("--model", help=f"trial this model instead of {semantic.MODEL} (implies --fresh)")
    parser.add_argument("--temperature", type=float, help=f"instead of {semantic.TEMPERATURE} (implies --fresh)")
    parser.add_argument("--flex", action="store_true", help="use Flex PayGo (implies --fresh)")
    parser.add_argument("--archive", type=int, default=0, metavar="N",
                        help="also re-assess N saved real decisions and report agreement (implies --fresh)")
    args = parser.parse_args()
    if args.synthetic and args.archive:
        parser.error("--archive re-assesses saved real sources; it cannot be combined with --synthetic")
    logging.basicConfig(level=logging.INFO)
    semantic.MODEL = args.model or semantic.MODEL
    semantic.TEMPERATURE = semantic.TEMPERATURE if args.temperature is None else args.temperature
    semantic.FLEX = args.flex or semantic.FLEX
    fresh = args.fresh or bool(args.model or args.temperature is not None or args.flex or args.archive)
    cases = json.loads((Path(__file__).parent / "tests/fixtures/content_assessment_cases.json").read_text())
    if args.synthetic:
        cases = [case for case in cases if case.get("synthetic", False)]
    usage, results, archive = [], [], []
    for case in cases:
        started = time.monotonic()
        try:
            payload = fresh_assessment(case["source"], usage) if fresh else cached_assessment(case["source"])
            kind = payload.get("result", {}).get("kind")
            # A reminder can name today's service session or its whole service
            # schedule. Either interpretation must produce individual sessions.
            expected = {case["expected_kind"]}
            if case["expected_kind"] == "service_schedule":
                expected.add("activity")
            passed = payload["status"] == "complete" and kind in expected
            if "expected_date_role" in case:
                passed &= payload.get("result", {}).get("date_role") == case["expected_date_role"]
            if "expected_starts_at" in case:
                passed &= sorted(item["starts_at"] for item in payload.get("result", {}).get("occurrences", [])) == sorted(case["expected_starts_at"])
        except Exception as exc:
            payload, passed = {"status":"error", "error":str(exc)}, False
        results.append({"name":case["name"], "expected_kind":case["expected_kind"], "passed":passed,
                        "expected_date_role":case.get("expected_date_role"),
                        "expected_starts_at":case.get("expected_starts_at"),
                        "seconds":round(time.monotonic() - started, 1), "assessment":payload})
        logging.info("%s %s", "PASS" if passed else "FAIL", case["name"])
    for saved in archive_sample(args.archive):
        started = time.monotonic()
        try:
            payload = fresh_assessment(saved["source"], usage)
        except Exception as exc:
            payload = {"status":"error", "error":str(exc)}
        before, after = decision(saved), decision(payload)
        archive.append({"source_key":saved["source"]["source_key"], "agrees":before == after, "saved":before,
                        "trial":after, "seconds":round(time.monotonic() - started, 1), "assessment":payload})
        logging.info("%s %s", "SAME" if before == after else "DIFF", saved["source"]["source_key"])
    tokens = {key: sum(call[key] for call in usage) for key in TOKEN_KEYS}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({"model":semantic.MODEL, "temperature":semantic.TEMPERATURE, "flex":semantic.FLEX,
                                       "model_calls":len(usage), "tokens":tokens, "cases":results, "archive":archive},
                                      indent=2, ensure_ascii=False))
    failed = sum(not item["passed"] for item in results)
    print(f"{semantic.MODEL} temperature={semantic.TEMPERATURE} flex={semantic.FLEX}: "
          f"{len(results)-failed}/{len(results)} semantic cases passed")
    if archive:
        refusals = [sum(item[side].get("status") == "refused" for item in archive) for side in ("saved", "trial")]
        errors = sum(item["trial"].get("status") == "error" for item in archive)
        print(f"{sum(item['agrees'] for item in archive)}/{len(archive)} saved decisions unchanged; "
              f"refusals {refusals[0]} -> {refusals[1]}; {errors} call errors")
    if usage:
        seconds = [item["seconds"] for item in results + archive]
        print(f"{len(usage)} model calls in {sum(seconds):.0f}s (slowest {max(seconds):.0f}s); "
              + ", ".join(f"{key.removesuffix('_token_count')} {value}" for key, value in tokens.items()))
    print(args.report)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
