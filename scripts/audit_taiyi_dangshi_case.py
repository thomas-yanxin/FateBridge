"""Replay printed symbolic conditions; retain every unselected lodging/variant."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.liureng import twelve_god_layout
from fatebridge.core.metaphysics.ren_diurnal import resolve_diurnal
from fatebridge.core.metaphysics.ren_gods import GuirenProfile
from fatebridge.core.metaphysics.sanshi_correspondences import liuren_at_taiyi_palace
from fatebridge.core.metaphysics.taiyi_year import cyclic_core

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/taiyi_dangshi_case_v41"
FREEZE = "2af3019b0654def7551606b36f682af1059599565991ca57e98bf7527580cf74"


def source_readings() -> dict[str, Any]:
    if hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest() != FREEZE:
        raise ValueError("Dangshi source freeze changed")
    frozen = json.loads((CORPUS / "freeze.json").read_text())
    for base, key in ((CORPUS, "files"), (ROOT, "prior_sources")):
        for name, expected in frozen[key].items():
            if hashlib.sha256((base / name).read_bytes()).hexdigest() != expected:
                raise ValueError(f"Frozen source changed: {name}")
    result: dict[str, Any] = json.loads((CORPUS / "readings.json").read_text())
    return result


def audit() -> dict[str, Any]:
    source = source_readings()
    args = source["conditional_inputs"]
    core = cyclic_core(args["cycle_index"], yin=args["yin"])
    core_rows = [
        {
            "field": key,
            "printed": value,
            "actual": core[key],
            "matches": core[key] == value,
        }
        for key, value in source["literal_core_expected"].items()
    ]
    controls = []
    profiles: tuple[GuirenProfile, ...] = ("liuren_common_v1", "tanyuan_xieji_v1")
    for profile in profiles:
        for is_day in source["predeclared_diurnal_controls"]:
            layout = twelve_god_layout(
                hour_branch=args["hour_branch"],
                month_general_branch=args["month_general_branch"],
                day_stem=args["day_stem"],
                is_diurnal=is_day,
                guiren_profile=profile,
            )
            board = {
                "twelve_board": [
                    {
                        "earth_branch": earth,
                        "sky_branch": sky,
                        "god": layout["god_by_sky"][sky],
                    }
                    for earth, sky in layout["sky_by_earth"].items()
                ]
            }
            editions = []
            for edition in source["editions"]:
                rows = []
                for marker, palace, literal in zip(
                    ("太乙", "主大将", "主参将", "客大将", "客参将"),
                    source["marker_palaces"],
                    edition["marker_gods"],
                ):
                    expected = source["god_normalization"][literal]
                    actual = liuren_at_taiyi_palace(palace, board)
                    candidates = (
                        [actual]
                        if actual["status"] == "direct_branch_match"
                        else actual.get("sector_candidates", [])
                    )
                    compatible = expected is not None and any(
                        r["god"] == expected for r in candidates
                    )
                    unique = actual["status"] == "direct_branch_match" and compatible
                    rows.append(
                        {
                            "marker": marker,
                            "taiyi_number": palace,
                            "source_literal": literal,
                            "normalized_source_god": expected,
                            "actual": actual,
                            "source_literal_recognized": expected is not None,
                            "compatible_with_sector_candidates": compatible,
                            "unique_direct_branch_match": unique,
                            "unselected_lodging": actual["status"] == "not_assessed",
                            "status": (
                                "unrecognized_source_literal"
                                if expected is None
                                else (
                                    "direct_match"
                                    if unique
                                    else (
                                        "compatible_unselected_sector"
                                        if compatible
                                        else "does_not_match_source"
                                    )
                                )
                            ),
                        }
                    )
                editions.append(
                    {
                        "edition": edition["id"],
                        "required_marker_rows": 5,
                        "compatible_rows": sum(
                            r["compatible_with_sector_candidates"] for r in rows
                        ),
                        "unique_direct_matching_rows": sum(
                            r["unique_direct_branch_match"] for r in rows
                        ),
                        "unselected_lodging_rows": sum(
                            r["unselected_lodging"] for r in rows
                        ),
                        "unrecognized_literal_rows": sum(
                            not r["source_literal_recognized"] for r in rows
                        ),
                        "rows": rows,
                        "whole_case_passed": False,
                    }
                )
            controls.append(
                {
                    "profile": profile,
                    "is_diurnal": is_day,
                    "matches_explicit_source_morning_condition": is_day is True,
                    "noble_start_branch": layout["noble_start_branch"],
                    "noble_earth_branch": layout["noble_earth_branch"],
                    "is_reverse": layout["is_reverse"],
                    "editions": editions,
                }
            )
    return {
        "source_freeze_sha256": FREEZE,
        "scope": "One previously known undated source case; four predeclared profile/diurnal diagnostic controls, two edition readings. Candidate membership never counts as a selected lodging or whole-case pass.",
        "core_rows": core_rows,
        "core_matching_rows": sum(r["matches"] for r in core_rows),
        "source_heshen_retained_not_recomputed_from_a_guessed_calendar": source[
            "source_heshen"
        ],
        "automatic_modern_diurnal_for_source_hour": resolve_diurnal(
            args["hour_branch"], None
        ),
        "controls": controls,
        "acceptance_limits": source["acceptance_limits"],
        "new_independent_source_cases": 0,
        "new_complete_dated_joint_cases_passed": 0,
        "new_model_invocations": 0,
        "independent_human_experts": 0,
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
    options = parser.parse_args()
    report = audit()
    options.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "core_matching_rows": report["core_matching_rows"],
                "whole_goal_complete": False,
            }
        )
    )
    raise SystemExit(1)
