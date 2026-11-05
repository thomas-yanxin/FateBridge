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

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_dangshi_case_v41"
FREEZE = "aa2c0929a54a50f68b162cd7210e758b8b92a3f4036b858da3bad4ca8fe0b13f"


def source_readings(corpus: Path = CORPUS) -> dict[str, Any]:
    raw = (corpus / "freeze-original.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != FREEZE:
        raise ValueError("Dangshi source freeze changed")
    original = json.loads(raw)
    frozen = json.loads((corpus / "freeze.json").read_text())
    noble_path = "tests/fixtures/taiyi_dangshi_noble_v40/freeze.json"
    noble_corpus = (ROOT / noble_path).parent
    noble_original_raw = (noble_corpus / "freeze-original.json").read_bytes()
    if (
        hashlib.sha256(noble_original_raw).hexdigest()
        != original["prior_sources"][noble_path]
    ):
        raise ValueError("Dangshi original noble source commitment changed")
    noble_original = json.loads(noble_original_raw)
    noble_raw = (ROOT / noble_path).read_bytes()
    noble = json.loads(noble_raw)
    # Process reports were archived; retain both original commitments and
    # require their source-only descendants to preserve every source binding.
    if noble != {
        **noble_original,
        "prior_sources": {
            name: digest
            for name, digest in noble_original["prior_sources"].items()
            if name.startswith("tests/fixtures/")
        },
    }:
        raise ValueError("Dangshi noble source projection changed")
    prior_sources = {
        name: digest
        for name, digest in original["prior_sources"].items()
        if name.startswith("tests/fixtures/")
    }
    prior_sources[noble_path] = hashlib.sha256(noble_raw).hexdigest()
    if frozen != {**original, "prior_sources": prior_sources}:
        raise ValueError("Dangshi case source projection changed")
    for folder, manifest in ((noble_corpus, noble), (corpus, frozen)):
        for base, key in ((folder, "files"), (ROOT, "prior_sources")):
            for name, expected in manifest[key].items():
                if hashlib.sha256((base / name).read_bytes()).hexdigest() != expected:
                    raise ValueError(f"Frozen source changed: {name}")
    result: dict[str, Any] = json.loads((corpus / "readings.json").read_text())
    return result


def audit() -> dict[str, Any]:
    source = source_readings()
    collation = json.loads((CORPUS / "collation.json").read_text())
    original = json.loads((CORPUS / "freeze-original.json").read_text())
    if collation["source_case_freeze_sha256"] != FREEZE or any(
        original["prior_sources"].get(witness["file"]) != witness["sha256"]
        for witness in collation["witnesses"]
    ):
        raise ValueError("Dangshi collation source binding changed")
    if collation["literal_variant"]["readings"] != {
        edition["id"]: edition["marker_gods"][-1] for edition in source["editions"]
    }:
        raise ValueError("Dangshi collation replaced an edition reading")
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
                            # Reverse constraints use the known printed answer;
                            # they never select or validate a general lodging rule.
                            "source_constrained_earth_branches": [
                                r["earth_branch"]
                                for r in candidates
                                if expected is not None and r["god"] == expected
                            ],
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
                    "control_role": (
                        "explicit_source_morning_condition"
                        if is_day
                        else "predeclared_modern_night_negative_control"
                    ),
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
        "source_collation": collation,
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
