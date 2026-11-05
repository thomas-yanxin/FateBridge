"""Preserve all ten captioned cases, incompatible labels and numeric controls."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.taiyi_year import cyclic_core
from fatebridge.validation.taiyi_caption_cycles import caption_candidates

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_cycles_v42"
FREEZE = "b01f239e7db1d83ca34563788173e5e1c9b0136dc7191866294a5a07dba4771f"


def source_readings() -> dict[str, Any]:
    if hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest() != FREEZE:
        raise ValueError("Caption source freeze changed")
    frozen = json.loads((CORPUS / "freeze.json").read_text())
    for base, key in ((CORPUS, "files"), (ROOT, "prior_sources")):
        for name, expected in frozen[key].items():
            if hashlib.sha256((base / name).read_bytes()).hexdigest() != expected:
                raise ValueError(f"Frozen caption source changed: {name}")
    result: dict[str, Any] = json.loads((CORPUS / "cases.json").read_text())
    return result


def audit() -> dict[str, Any]:
    source = source_readings()
    inventory = json.loads((CORPUS / "inventory.json").read_text())
    actual_rows = [
        (p.name, i, line)
        for p in sorted(CORPUS.glob("vol*.txt"))
        for i, line in enumerate(p.read_text().splitlines(), 1)
        if "局" in line and ("紀" in line or "元" in line)
    ]
    required_rows = [(r["file"], r["line"], r["literal"]) for r in inventory["rows"]]
    if actual_rows != required_rows:
        raise ValueError("Ten-volume caption inventory incomplete")
    reports = []
    for case in source["cases"]:
        inputs = {
            "ji60": case["ji_60"],
            "yuan72": case["yuan_72"],
            "ju": case["ju"],
            "ganzhi": case["ganzhi"],
        }
        candidates = caption_candidates(**inputs)
        numeric_controls = []
        for yin in case["evaluated_dun_hypotheses"]:
            core = cyclic_core(case["ju"], yin=yin)
            rows = [
                {
                    "field": field,
                    "printed": value,
                    "actual": core[field],
                    "matches": value == core[field],
                }
                for field, value in case["board_expected"].items()
            ]
            numeric_controls.append(
                {
                    "yin": yin,
                    "yin_explicit_in_source": case["declared_yin"] is not None,
                    "input_is_printed_ju_phase_not_absolute_counter": True,
                    "required_fields": len(rows),
                    "matching_fields": sum(r["matches"] for r in rows),
                    "rows": rows,
                }
            )
        relaxed = []
        for omitted in inputs:
            if inputs[omitted] is None:
                continue
            remaining = {k: v for k, v in inputs.items() if k != omitted}
            relaxed.append(
                {
                    "omitted_constraint_for_diagnostic_only": omitted,
                    "candidates": caption_candidates(**remaining),
                    "not_adopted_as_whole_caption_pass": True,
                }
            )
        reports.append(
            {
                "id": case["id"],
                "source_file": case["file"],
                "source_line": case["line"],
                "literal": case["literal"],
                "constraints": inputs,
                "ganzhi_unit": case["ganzhi_unit"],
                "candidates_under_declared_coordinate_assumption": candidates,
                "expected_frozen_candidates": case[
                    "expected_full_constraint_candidates"
                ],
                "solver_matches_frozen_math": candidates
                == case["expected_full_constraint_candidates"],
                "caption_status": (
                    "unique_phase_under_assumption"
                    if len(candidates) == 1
                    else (
                        "incompatible_under_assumption"
                        if not candidates
                        else "multiple_phases_under_assumption"
                    )
                ),
                "single_constraint_omission_controls": relaxed,
                "phase_only_numeric_controls": numeric_controls,
                "absolute_counter_or_ce_date_adjudicated": False,
                "whole_classical_case_passed": False,
            }
        )
    return {
        "source_freeze_sha256": FREEZE,
        "scope": source["scope"],
        "coordinate_assumption": source["coordinate_assumption"],
        "source_volumes": 10,
        "inventory_contexts": len(actual_rows),
        "captioned_cases": len(reports),
        "all_inventory_contexts_retained": True,
        "cases": reports,
        "unique_phase_cases_under_assumption": sum(
            len(r["candidates_under_declared_coordinate_assumption"]) == 1
            for r in reports
        ),
        "incompatible_caption_cases_under_assumption": [
            r["id"]
            for r in reports
            if not r["candidates_under_declared_coordinate_assumption"]
        ],
        "source_declared_dun_unknown_cases": [
            r["id"] for r in source["cases"] if r["declared_yin"] is None
        ],
        "all_solver_controls_match_frozen_math": all(
            r["solver_matches_frozen_math"] for r in reports
        ),
        "new_independent_cases": 0,
        "new_complete_dated_classical_cases_passed": 0,
        "new_model_invocations": 0,
        "independent_human_experts": 0,
        "whole_calendar_acceptance_passed": False,
        "whole_classic_acceptance_passed": False,
        "whole_interpretation_fidelity_acceptance_passed": False,
        "real_world_efficacy": "not_tested",
        "whole_goal_complete": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    report = audit()
    options.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "cases": report["captioned_cases"],
                "incompatible": report["incompatible_caption_cases_under_assumption"],
                "whole_goal_complete": False,
            }
        )
    )
    raise SystemExit(1)
