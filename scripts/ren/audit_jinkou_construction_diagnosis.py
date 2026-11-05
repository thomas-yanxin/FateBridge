"""Decompose all original64 reconstructions without choosing a best-fit policy.

The arithmetic reference precedes production imports. Inverse solutions are
constraints of these selected formulae, not historical emendations or answers.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/jinkou_construction_diagnosis_v1"
PIN = "12ce6f75aecf0eea62f598a4a2c8d324959e9299fdd7527058992f0bb6c82763"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def reference(folder: Path = CORPUS) -> dict[str, Any]:
    if sha(folder / "freeze.json") != PIN:
        raise ValueError("Frozen construction diagnostic identity changed")
    manifest = json.loads((folder / "freeze.json").read_text())
    if set(manifest) != {"reference.json", "protocol.json"} or {
        p.name for p in folder.iterdir()
    } != {*manifest, "freeze.json"}:
        raise ValueError("Frozen construction diagnostic inventory changed")
    if any(sha(folder / n) != h for n, h in manifest.items()):
        raise ValueError("Frozen construction diagnostic reference changed")
    value: dict[str, Any] = json.loads((folder / "reference.json").read_text())
    for n, h in value["source_pins"].items():
        if sha(ROOT / n) != h:
            raise ValueError("Original source manifest changed")
        base = ROOT / n
        files = json.loads(base.read_text())["files"]
        if any(sha(base.parent / name) != digest for name, digest in files.items()):
            raise ValueError("Original source bytes changed")
    value["day_branches"] = json.loads(
        (ROOT / "tests/fixtures/ren_diurnal_v1/reference.json").read_text()
    )["software_policy"]["day_branches"]
    return value


def god_map(ref: dict[str, Any], stem: str, day: bool) -> dict[str, str]:
    mode = "day" if day else "night"
    branches = ref["branches"]
    start = branches.index(ref[mode + "_starts"][stem])
    direction = ref[mode + "_directions"][stem]
    return {
        branches[(start + direction * ordinal) % 12]: god
        for ordinal, god in enumerate(ref["god_sequence"])
    }


def human(ref: dict[str, Any], stem: str, ground: str) -> str:
    stems, branches = ref["stems"], ref["branches"]
    return str(
        stems[(stems.index(ref["zi_stems"][stem]) + branches.index(ground)) % 10]
    )


def expected_positions(
    ref: dict[str, Any], case: dict[str, Any], *, day: bool
) -> list[str]:
    ground = case["positions"][3]
    branches = ref["branches"]
    general = ref["month_generals"][str(case["lunar_month"])]
    return [
        human(ref, case["day"][0], ground),
        god_map(ref, case["day"][0], day)[ground],
        branches[
            (
                branches.index(general)
                + branches.index(ground)
                - branches.index(case["hour"])
            )
            % 12
        ],
        ground,
    ]


def negative_controls(ref: dict[str, Any]) -> dict[str, int]:
    changes = {}
    for label in json.loads((CORPUS / "protocol.json").read_text())[
        "negative_controls"
    ]:
        alt = copy.deepcopy(ref)
        if label == "swap_day_and_night":
            for key in ["starts", "directions"]:
                alt["day_" + key], alt["night_" + key] = (
                    alt["night_" + key],
                    alt["day_" + key],
                )
        elif label == "reverse_directions":
            for mode in ["day", "night"]:
                alt[mode + "_directions"] = {
                    k: -v for k, v in alt[mode + "_directions"].items()
                }
        elif label == "omit_night_reversal":
            alt["night_directions"] = copy.deepcopy(alt["day_directions"])
        elif label == "wrong_sun_start_for_geng":
            alt["day_starts"]["庚"] = "未"
        else:
            raise ValueError("Unknown predeclared negative control")
        changes[label] = sum(
            god_map(alt, stem, day)[ground] != god_map(ref, stem, day)[ground]
            for stem in ref["stems"]
            for day in [True, False]
            for ground in ref["branches"]
        )
    return changes


def audit() -> dict[str, Any]:
    ref = reference()
    cases = json.loads(
        (ROOT / "tests/fixtures/jinkou_patterns_v1/cases.json").read_text()
    )["cases"]
    if len(cases) != 64 or [c["id"] for c in cases] != [
        f"P{i:02}" for i in range(1, 65)
    ]:
        raise ValueError("All original64 entries required")
    # Expected arithmetic is independent of the functions checked below.
    reference_grid = {
        (stem, day): god_map(ref, stem, day)
        for stem in ref["stems"]
        for day in [True, False]
    }
    from fatebridge.core.metaphysics.jinkou import (
        _build_guishen_mapping,
        build_jinkou_board,
    )
    from fatebridge.core.metaphysics.jinkou_stems import wuzidun_stem
    from scripts.ren.audit_ren_classical import make_seed

    failures = []
    for (stem, day), expected_map in reference_grid.items():
        start, actual_map = _build_guishen_mapping(stem, "午" if day else "子", day)
        mode = "day" if day else "night"
        if start != ref[mode + "_starts"][stem] or actual_map != expected_map:
            failures.append(
                dict(
                    kind="god_grid",
                    stem=stem,
                    day=day,
                    start=start,
                    actual=actual_map,
                    expected=expected_map,
                )
            )
    for stem in ref["stems"]:
        for ground in ref["branches"]:
            actual_stem = wuzidun_stem(stem, ground)
            expected_stem = human(ref, stem, ground)
            if actual_stem != expected_stem:
                failures.append(
                    dict(
                        kind="human_grid",
                        stem=stem,
                        ground=ground,
                        actual=actual_stem,
                        expected=expected_stem,
                    )
                )
    rows = []
    component_counts: Counter[str] = Counter()
    engine_comparisons = 0
    for case in cases:
        if case["day"] is None:
            rows.append(
                dict(
                    id=case["id"],
                    status="missing_source_day",
                    original_matched=None,
                    alternatives=None,
                    source_day_emended=False,
                )
            )
            continue
        day = case["hour"] in ref["day_branches"]
        literal = list(case["positions"])
        literal[1] = ref["aliases"].get(literal[1], literal[1])
        modes = {
            mode: expected_positions(ref, case, day=flag)
            for mode, flag in [("day", True), ("night", False)]
        }
        default = modes["day" if day else "night"]
        differing = [
            name
            for name, a, b in zip(
                ["human", "god", "general", "ground"], default, literal, strict=True
            )
            if a != b
        ]
        component_counts.update(differing)
        seed = make_seed(
            dict(
                day=case["day"],
                hour=case["hour"],
                month=ref["branches"][(case["lunar_month"] + 1) % 12],
            )
        )
        for mode, explicit in [("default", None), ("day", True), ("night", False)]:
            board = build_jinkou_board(
                seed,
                {
                    "month_general": {
                        "branch": ref["month_generals"][str(case["lunar_month"])]
                    }
                },
                di_fen=literal[3],
                is_diurnal_override=explicit,
            )
            observed = [
                board["rows"][0]["content"],
                board["overview"]["guishen"]["name"],
                board["rows"][2]["content"],
                board["rows"][3]["content"],
            ]
            expected_positions_for_mode = default if mode == "default" else modes[mode]
            engine_comparisons += 1
            if observed != expected_positions_for_mode:
                failures.append(
                    dict(
                        kind="source_input_arithmetic",
                        id=case["id"],
                        mode=mode,
                        actual=observed,
                        expected=expected_positions_for_mode,
                    )
                )
        branches = ref["branches"]
        implied_general = branches[
            (
                branches.index(literal[2])
                - branches.index(literal[3])
                + branches.index(case["hour"])
            )
            % 12
        ]
        rows.append(
            dict(
                id=case["id"],
                status="compared_symbolic_month_general",
                source_day=case["day"],
                source_hour=case["hour"],
                source_lunar_month=case["lunar_month"],
                literal_positions=list(case["positions"]),
                comparison_positions=literal,
                original_selected_mode="day" if day else "night",
                original_actual=default,
                original_matched=not differing,
                differing_components=differing,
                alternatives=modes,
                modes_matching_god=[m for m, p in modes.items() if p[1] == literal[1]],
                modes_matching_whole=[m for m, p in modes.items() if p == literal],
                human_day_stem_constraints=[
                    s for s in ref["stems"] if human(ref, s, literal[3]) == literal[0]
                ],
                general_required_by_diagram=implied_general,
                month_general_matches=implied_general
                == ref["month_generals"][str(case["lunar_month"])],
                source_day_emended=False,
                policy_regraded=False,
            )
        )
    compared = [r for r in rows if r["original_matched"] is not None]
    mismatches = [r for r in compared if not r["original_matched"]]
    controls = negative_controls(ref)
    counts = dict(
        original_denominator=64,
        available_days=len(compared),
        original_matched=sum(r["original_matched"] for r in compared),
        original_not_matched=len(mismatches),
        missing_days=64 - len(compared),
        mismatched_components=dict(component_counts),
        only_god_mismatch=sum(r["differing_components"] == ["god"] for r in mismatches),
        mixed_component_mismatch=sum(
            len(r["differing_components"]) > 1 for r in mismatches
        ),
        mismatches_with_no_whole_match_under_either_mode=sum(
            not r["modes_matching_whole"] for r in mismatches
        ),
        mismatches_with_an_alternative_whole_match=sum(
            bool(r["modes_matching_whole"]) for r in mismatches
        ),
        god_cells=240,
        human_cells=120,
        engine_mode_comparisons=engine_comparisons,
    )
    return dict(
        reference_pin=PIN,
        counts=counts,
        rows=rows,
        implementation_failures=failures,
        negative_control_changed_god_cells=controls,
        arithmetic_checks_passed=not failures and all(controls.values()),
        original_classical_acceptance_passed=False,
        original_score_unchanged=True,
        stellar_boundary_adjudicated=False,
        source_emendations=0,
        new_independent_classical_cases=0,
        new_model_processes=0,
        goal_complete=False,
        scope="All64 source entries retained; selected symbolic construction, no real calendar dates or best-fit source edits",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = audit()
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps({k: v for k, v in value.items() if k != "rows"}, ensure_ascii=False)
    )
    raise SystemExit(0 if value["arithmetic_checks_passed"] else 1)


if __name__ == "__main__":
    main()
