"""Run the reviewed semantic cases through the actual model, without publishing.

    python evaluate_content_assessment.py --report /tmp/assessment-eval.json

Unlike contract tests, this measures real classification responses. The report
records failures and source evidence; it contains no credentials. Existing
versioned assessments are reused unless --fresh is supplied.
"""
import argparse
import json
import logging
from pathlib import Path

import content_assessment as semantic
from assessed_events import cached_assessment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--synthetic", action="store_true", help="only authored test examples; exclude saved real source content")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    cases = json.loads((Path(__file__).parent / "tests/fixtures/content_assessment_cases.json").read_text())
    if args.synthetic:
        cases = [case for case in cases if "raw" not in case]
    results = []
    for case in cases:
        try:
            payload = ({"status":"complete", "result":semantic.assess(case["source"])} if args.fresh
                       else cached_assessment(case["source"]))
            kind = payload.get("result", {}).get("kind")
            # A reminder can name today's service session or its whole service
            # schedule. Either interpretation must produce individual sessions.
            expected = {case["expected_kind"]}
            if case["expected_kind"] == "service_schedule":
                expected.add("activity")
            passed = payload["status"] == "complete" and kind in expected
        except Exception as exc:
            payload, passed = {"status":"error", "error":str(exc)}, False
        results.append({"name":case["name"], "expected_kind":case["expected_kind"], "passed":passed, "assessment":payload})
        logging.info("%s %s", "PASS" if passed else "FAIL", case["name"])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    failed = sum(not item["passed"] for item in results)
    print(f"{len(results)-failed}/{len(results)} semantic cases passed; {args.report}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
