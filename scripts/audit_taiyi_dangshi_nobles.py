"""Retain all noble-table edition agreements and disagreements, never a full pass."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fatebridge.core.metaphysics.ren_gods import noble_start
from fatebridge.core.metaphysics.taiyi_dangshi import noble_source_assessment

if TYPE_CHECKING or __package__:
    from scripts.build_taiyi_dangshi_nobles import CORPUS, FREEZE, OUTPUT, build
else:
    from build_taiyi_dangshi_nobles import CORPUS, FREEZE, OUTPUT, build


def audit() -> dict[str, Any]:
    if OUTPUT.read_bytes() != build():
        raise ValueError("Packaged noble tables differ from frozen source")
    source = json.loads((CORPUS / "readings.json").read_text())
    matrices = []
    for edition in source["editions"]:
        profiles = []
        for profile in source["predeclared"]["profiles_to_compare"]:
            rows = []
            for row in edition["rows"]:
                for is_day in (True, False):
                    start = noble_start(row["stem"], is_day, profile)
                    expected = row["morning_branch" if is_day else "evening_branch"]
                    mini_board = {
                        "meta": {"guiren_profile": profile, "is_diurnal": is_day},
                        "rule_trace": [
                            {
                                "rule_id": "liuren.guiren_start",
                                "result": {
                                    "profile": profile,
                                    "is_diurnal": is_day,
                                    "start_branch": start,
                                },
                            }
                        ],
                    }
                    assessment = noble_source_assessment(
                        row["stem"], mini_board, taiyi_mode="hour"
                    )
                    selected = next(
                        r
                        for r in assessment["comparisons"]
                        if r["source_id"] == edition["id"]
                    )
                    assert selected["source_branch"] == expected
                    assert selected["matches"] is (start == expected)
                    rows.append(
                        {
                            "stem": row["stem"],
                            "selected_diurnal": is_day,
                            "expected_source_branch": expected,
                            "actual_profile_branch": start,
                            "matches": selected["matches"],
                        }
                    )
            profiles.append(
                {
                    "profile": profile,
                    "required_entries": 20,
                    "matching_entries": sum(r["matches"] for r in rows),
                    "rows": rows,
                }
            )
        matrices.append({"source_id": edition["id"], "profiles": profiles})
    return {
        "source_freeze_sha256": FREEZE,
        "scope": "Two full20-entry source tables compared to both existing profiles. Synthetic stem/diurnal controls, not80 independent cases or dated joint charts. No edition selected by fit.",
        "source_table_matrices": matrices,
        "source_case_context_retained_not_reconstructed": source["case_context"],
        "same_table_does_not_validate_morning_evening_boundary": True,
        "new_complete_dated_taiyi_or_joint_cases_passed": 0,
        "new_model_invocations": 0,
        "whole_dangshi_method_acceptance_passed": False,
        "whole_calendar_acceptance_passed": False,
        "whole_classic_acceptance_passed": False,
        "whole_interpretation_fidelity_acceptance_passed": False,
        "real_world_efficacy": "not_tested",
        "whole_goal_complete": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                r["source_id"]: [p["matching_entries"] for p in r["profiles"]]
                for r in result["source_table_matrices"]
            }
        )
    )
    raise SystemExit(1)
