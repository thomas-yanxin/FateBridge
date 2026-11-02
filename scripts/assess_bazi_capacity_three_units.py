"""Assess fixed candidate gates without treating unknowns or repetitions as gains."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def assess(result):
    active = "mediated_v1"
    rows = result["prospective_rows"]
    assert rows and len({r["source_case"]["id"] for r in rows}) == len(rows)
    known = [r for r in rows if r["source_case"]["expected_strength"] is not None]
    unknown = [r for r in rows if r["source_case"]["expected_strength"] is None]
    assert all(
        all(v is None for v in r["matches_all_variants"].values()) for r in unknown
    )
    gains = [
        r["source_case"]["id"]
        for r in known
        if r["source_case"]["new_nonoverlap_input"]
        and r["matches_all_variants"][active] is True
        and r["matches_all_variants"]["production_v7"] is False
    ]
    regressions = [
        r["source_case"]["id"]
        for r in known
        if r["matches_all_variants"]["production_v7"] is True
        and r["matches_all_variants"][active] is False
    ]
    conditions = {
        "no_old_known_regressions": not result["exposed_summary"]["known_regressions"][
            active
        ],
        "no_old_negative_constraint_regressions": not result["exposed_summary"][
            "new_negative_constraint_regressions"
        ][active],
        "no_new_known_regressions": not regressions,
        "at_least_one_fresh_explicit_source_gain": bool(gains),
    }
    return {
        "new_records": len(rows),
        "new_known": len(known),
        "new_unknown": len(unknown),
        "fresh_nonoverlap_gains": gains,
        "new_known_regressions": regressions,
        "conditions": conditions,
        "numerical_adoption_gate_passed": all(conditions.values()),
        "mechanism_sufficiency_established": False,
        "mechanism_review": "Three units do not establish all sufficient predicates; thermal receiving capacity remains a separate unresolved condition. Numeric gate already fails; no adoption.",
        "adopted": False,
        "new_independent_external_validation_credit": 0,
        "new_model_executions": 0,
        "full_goal_complete": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    digest = hashlib.sha256(args.input.read_bytes()).hexdigest()
    assert digest == args.input.with_suffix(".sha256").read_text().strip()
    result = assess(json.loads(gzip.decompress(args.input.read_bytes())))
    result.update(
        input_sha256=digest,
        assessor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    args.output.with_suffix(".sha256").write_text(
        hashlib.sha256(args.output.read_bytes()).hexdigest() + "\n"
    )
    print(json.dumps(result, ensure_ascii=False))
    return int(not result["numerical_adoption_gate_passed"])


if __name__ == "__main__":
    raise SystemExit(main())
