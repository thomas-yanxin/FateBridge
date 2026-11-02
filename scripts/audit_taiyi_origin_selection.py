"""Separate a count epoch label from the current winter-selection boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/taiyi_origin_activation_v45"
SOURCE_SHA = "876bcf3e15d8365773a13d9f4de24836c08c6b8a2837c353dc5ad586d936a8ed"
REFERENCE_SHA = "c6322710410eee20f5bc439b89375fe4a6939ae9a51f02ebf1b36a36154132e6"
POLICY_ID = "latest_elapsed_winter_solstice_instant_modern_v1"


def references() -> list[dict[str, Any]]:
    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    assert sha(CORPUS / "freeze.json") == SOURCE_SHA
    source = json.loads((CORPUS / "freeze.json").read_text())
    assert all(sha(CORPUS / n) == h for n, h in source["files"].items())
    assert sha(CORPUS / "reference-freeze.json") == REFERENCE_SHA
    reference = json.loads((CORPUS / "reference-freeze.json").read_text())
    assert all(sha(CORPUS / n) == h for n, h in reference["files"].items())
    code = json.loads((CORPUS / "reference-code-freeze.json").read_text())
    assert all(sha(CORPUS / n) == h for n, h in code["files"].items())
    rows = json.loads((CORPUS / "civil-reference.json").read_text())["rows"]
    assert len(rows) == 96
    return list(rows)


@contextmanager
def native_inputs() -> Iterator[None]:
    names = [
        "FATEBRIDGE_SOLAR_TERM_MODEL",
        "SE_EPHE_PATH",
        "FATEBRIDGE_JPL_FILE",
        "FATEBRIDGE_SOLAR_SPK_FILE",
    ]
    saved = {n: os.environ.get(n) for n in names}
    data = json.loads((CORPUS / "physical-data.json").read_text())["files"]
    path = ROOT / "ephe"
    assert all(
        hashlib.sha256((path / n).read_bytes()).hexdigest() == h
        for n, h in data.items()
    )
    try:
        os.environ["FATEBRIDGE_SOLAR_TERM_MODEL"] = "native"
        os.environ["SE_EPHE_PATH"] = str(path)
        for n in names[2:]:
            os.environ.pop(n, None)
        yield
    finally:
        for n, value in saved.items():
            if value is None:
                os.environ.pop(n, None)
            else:
                os.environ[n] = value


def inputs(row: dict[str, Any], *, solar: bool = False) -> dict[str, Any]:
    wall = datetime.fromisoformat(row["target_wall"])
    options = dict(calculation_mode="day" if row["mode"] == "day" else "hour")
    if row["mode"] == "key_hour":
        options["hour_profile"] = "key_hour_winter_jiazi_v1"
    if row["tool"] == "taiyi":
        return dict(
            analysis_year=wall.year,
            analysis_month=wall.month,
            analysis_day=wall.day,
            analysis_hour=wall.hour,
            analysis_minute=wall.minute,
            analysis_second=wall.second,
            analysis_timezone=row["zone"],
            analysis_longitude=150.0,
            use_true_solar_time=solar,
            **options,
        )
    return dict(
        date=wall.date().isoformat(),
        time=wall.time().isoformat(),
        zone=row["zone"],
        gps_lon=150.0,
        use_true_solar_time=solar,
        taiyi_options=options,
    )


def calculate(row: dict[str, Any], *, solar: bool = False) -> dict[str, Any]:
    from fatebridge.services.divination import calculate_sanshiunited_analysis
    from fatebridge.services.metaphysics import calculate_taiyi_analysis

    fn = (
        calculate_taiyi_analysis
        if row["tool"] == "taiyi"
        else calculate_sanshiunited_analysis
    )
    return fn(**inputs(row, solar=solar))


def inspect(
    result: dict[str, Any], row: dict[str, Any], *, solar: bool = False
) -> dict[str, Any]:
    board = result["taiyi"]
    calendar = board["calendar_rules"]
    origin = calendar["day_origin" if row["mode"] == "day" else "hour_origin"]
    expected_clock = origin.get(
        "origin_clock", origin["origin_effective_date"] + "T00:00:00"
    )
    winter = board["solar_anchors"]["winter_origin"]
    numeric = (
        None
        if solar
        else (
            calendar["counter"] == row["expected_counter_under_current_declared_policy"]
            and origin["origin_effective_date"] == row["expected_count_origin_date"]
            and expected_clock == row["expected_count_origin_clock"]
            and abs(
                winter["solar_model_details"]["selected_crossing_jd_tt"]
                - row["selected_winter_reference_tt"]
            )
            * 86400
            <= 0.05
        )
    )
    selected = board.get("winter_origin_selection", {})
    fidelity = (
        selected.get("policy_id") == POLICY_ID
        and selected.get("selected_winter_utc") == winter["datetime_with_offset"]
        and selected.get("count_origin_date") == origin["origin_effective_date"]
        and selected.get("count_origin_clock") == expected_clock
        and selected.get("clock_basis") == calendar["clock_basis"]
        and selected.get("classical_activation_adjudicated") is False
        and selected.get("source") == origin["source"]
        and selected.get("selection_switch_basis") == "winter_solstice_instant"
        and bool(selected.get("scope"))
    )
    return dict(
        numeric_control_passed=numeric,
        fidelity_receipt_passed=fidelity,
        actual_counter=calendar["counter"],
        actual_origin_clock=expected_clock,
        selected_winter_utc=winter["datetime_with_offset"],
        counter_origin_is_not_selection_switch_instant=True,
        classical_activation_adjudicated=False,
    )


def audit() -> dict[str, Any]:
    rows = []
    with native_inputs():
        for row in references():
            result = calculate(row)
            rows.append(dict(id=row["id"], **inspect(result, row)))
    phase = json.loads((CORPUS / "phase-reference.json").read_text())
    assert phase["cases"] == 120 and phase["origin_step_distribution"] == {
        "360": 109,
        "420": 11,
    }
    return dict(
        source_freeze_sha256=SOURCE_SHA,
        reference_freeze_sha256=REFERENCE_SHA,
        civil_rows=96,
        numeric_controls_passed=sum(r["numeric_control_passed"] for r in rows),
        fidelity_receipts_passed=sum(r["fidelity_receipt_passed"] for r in rows),
        rows=rows,
        independent_integer_cases=120,
        origin_step_distribution=phase["origin_step_distribution"],
        numerical_policy_changed=False,
        activation_classically_adjudicated=False,
        new_independent_observations=0,
        new_complete_dated_classical_cases=0,
        new_model_calls=0,
        whole_calendar_acceptance_passed=False,
        whole_classic_acceptance_passed=False,
        whole_explanation_fidelity_acceptance_passed=False,
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
                    "civil_rows",
                    "numeric_controls_passed",
                    "fidelity_receipts_passed",
                    "activation_classically_adjudicated",
                ]
            }
        )
    )
    return int(
        result["numeric_controls_passed"] != 96
        or result["fidelity_receipts_passed"] != 96
    )


if __name__ == "__main__":
    raise SystemExit(main())
