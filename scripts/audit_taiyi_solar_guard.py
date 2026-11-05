"""Replay pre-frozen endpoint contracts without changing their denominator."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/taiyi_solar_guard_v44"
FREEZE_SHA = "b0f03b4240351a941443b62cab4cf62c4826c29020c08d77ef0ec1a07423ba8c"
MODEL = "fatebridge_de440_solar_v1"
NAMES = {10: "芒种", 11: "夏至", 22: "大雪", 23: "冬至"}


def reference() -> tuple[dict[str, Any], dict[tuple[int, int], dict[str, Any]]]:
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    assert digest(CORPUS / "freeze.json") == FREEZE_SHA
    frozen = json.loads((CORPUS / "freeze.json").read_text())
    assert all(digest(CORPUS / n) == h for n, h in frozen["files"].items())
    protocol = json.loads((CORPUS / "protocol.json").read_text())
    rows = json.loads((CORPUS / "reference.json").read_text())["rows"]
    assert len(rows) == 144
    return protocol, {(r["year"], r["index"]): r for r in rows}


@contextmanager
def policy(mode: str) -> Iterator[None]:
    names = [
        "FATEBRIDGE_SOLAR_TERM_MODEL",
        "FATEBRIDGE_JPL_FILE",
        "FATEBRIDGE_SOLAR_SPK_FILE",
    ]
    saved = {n: os.environ.get(n) for n in names}
    try:
        os.environ["FATEBRIDGE_SOLAR_TERM_MODEL"] = mode
        for n in names[1:]:
            os.environ.pop(n, None)
        yield
    finally:
        for n, value in saved.items():
            if value is None:
                os.environ.pop(n, None)
            else:
                os.environ[n] = value


def inputs(
    tool: str, case: dict[str, Any], profile: dict[str, str], solar: bool
) -> dict[str, Any]:
    if tool == "taiyi":
        return dict(
            analysis_year=case["year"],
            analysis_month=case["month"],
            analysis_day=case["day"],
            analysis_hour=case["hour"],
            analysis_minute=case.get("minute", 0),
            analysis_second=case.get("second", 0),
            analysis_timezone=case["zone"],
            analysis_longitude=case.get("longitude", 150.0),
            use_true_solar_time=solar,
            **profile,
        )
    return dict(
        date=f"{case['year']:04}-{case['month']:02}-{case['day']:02}",
        time=f"{case['hour']:02}:{case.get('minute', 0):02}:{case.get('second', 0):02}",
        zone=case["zone"],
        gps_lon=case.get("longitude", 150.0),
        use_true_solar_time=solar,
        taiyi_options=profile,
    )


def calculate(tool: str, values: dict[str, Any]) -> dict[str, Any]:
    from fatebridge.services.divination import calculate_sanshiunited_analysis
    from fatebridge.services.metaphysics import calculate_taiyi_analysis

    fn = (
        calculate_taiyi_analysis if tool == "taiyi" else calculate_sanshiunited_analysis
    )
    return fn(**values)


def root_error(details: dict[str, Any], expected: float) -> float:
    parts = details.get("selected_crossing_tt_parts")
    if parts:
        return math.fsum([parts[0] - expected, parts[1]]) * 86400
    return float(details["selected_crossing_jd_tt"] - expected) * 86400


def inspect_board(
    board: dict[str, Any],
    case: dict[str, Any],
    profile: dict[str, str],
    refs: dict[tuple[int, int], dict[str, Any]],
) -> dict[str, Any]:
    mode = profile["calculation_mode"]
    expected = {
        "boundary": case["month_anchor" if mode == "month" else "solstice_anchor"]
    }
    if mode == "day" or profile.get("hour_profile") == "key_hour_winter_jiazi_v1":
        expected["winter_origin"] = case["winter_anchor"]
    observed = board.get("solar_anchors", {})
    checks = []
    for name, key in expected.items():
        actual = observed.get(name, {})
        error = None
        if actual.get("solar_model_details"):
            error = root_error(
                actual["solar_model_details"], refs[key["year"], key["index"]]["jd_tt"]
            )
        checks.append(
            dict(
                anchor=name,
                expected_year=key["year"],
                expected_index=key["index"],
                expected_name=NAMES[key["index"]],
                actual_name=actual.get("name"),
                actual_provider=actual.get("resolution_provider"),
                actual_model=actual.get("ephemeris_model"),
                error_seconds_tt=error,
                passed=actual.get("name") == NAMES[key["index"]]
                and actual.get("resolution_provider") == "jpl_de440"
                and actual.get("ephemeris_model") == MODEL
                and error is not None
                and abs(error) <= 1.0,
            )
        )
    return dict(
        anchors=checks,
        actual_counter=board.get("calendar_rules", {}).get("counter"),
        actual_ju=board.get("ju"),
        passed=set(observed) == set(expected) and all(c["passed"] for c in checks),
        full_classical_correctness_certified=False,
    )


def audit() -> dict[str, Any]:
    from fatebridge.core import almanac

    protocol, refs = reference()
    rows = []
    roots = []
    outside = []
    for mode in protocol["policies"]:
        with policy(mode):
            for context in [1800, 2200]:
                for year in range(context - 1, context + 2):
                    for i, term in enumerate(
                        almanac._solar_terms_for_context_year(year, "UTC", context)
                    ):
                        error = root_error(
                            term.solar_model_details or {}, refs[year, i]["jd_tt"]
                        )
                        roots.append(
                            dict(
                                policy=mode,
                                year=year,
                                index=i,
                                context=context,
                                error_seconds_tt=error,
                                passed=term.resolution_provider == "jpl_de440"
                                and term.ephemeris_model == MODEL
                                and abs(error) <= 1.0,
                            )
                        )
            for case in protocol["cases"]:
                for profile in protocol["profiles"]:
                    for solar in protocol["solar_flags"]:
                        for tool in protocol["tools"]:
                            row = dict(
                                policy=mode,
                                case=case["id"],
                                profile=profile,
                                solar=solar,
                                tool=tool,
                            )
                            try:
                                result = calculate(
                                    tool, inputs(tool, case, profile, solar)
                                )
                                row.update(
                                    inspect_board(result["taiyi"], case, profile, refs)
                                )
                            except (ValueError, KeyError) as error:
                                row.update(
                                    passed=False,
                                    error_type=type(error).__name__,
                                    error=str(error),
                                )
                            rows.append(row)
    with policy("de440"):
        for year in protocol["preserve_public_grid_outside_years"]:
            try:
                almanac.get_solar_terms_for_year(year, "UTC")
                rejected = False
            except ValueError as error:
                rejected = "1800..2200" in str(error)
            outside.append(dict(year=year, standalone_rejected=rejected))
    assert len(rows) == protocol["business_control_rows"] == 720
    assert len(roots) == 288
    return dict(
        protocol_freeze_sha256=FREEZE_SHA,
        business_rows=len(rows),
        business_passed=sum(r["passed"] for r in rows),
        rows=rows,
        reused_root_controls=len(roots),
        reused_root_controls_passed=sum(r["passed"] for r in roots),
        root_controls=roots,
        standalone_outside_controls=outside,
        new_independent_observations=0,
        new_dated_classical_cases=0,
        new_model_calls=0,
        numerical_counter_formulas_changed=False,
        whole_calendar_acceptance_passed=False,
        whole_classic_acceptance_passed=False,
        whole_explanation_fidelity_acceptance_passed=False,
        real_world_efficacy="not_tested",
        whole_goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "business_rows",
                    "business_passed",
                    "reused_root_controls_passed",
                    "whole_goal_complete",
                ]
            }
        )
    )
    return int(
        result["business_passed"] != result["business_rows"]
        or result["reused_root_controls_passed"] != result["reused_root_controls"]
        or not all(
            r["standalone_rejected"] for r in result["standalone_outside_controls"]
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
