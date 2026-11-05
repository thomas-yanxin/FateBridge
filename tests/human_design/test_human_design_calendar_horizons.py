"""Frozen independent observations, rejected query drift and retained failures."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.human_design import check_human_design_calendar_horizons as check
from scripts.human_design.gen_human_design_calendar_horizons import (
    parameters,
    parse_response,
    plan,
)
from tests.support.ephemeris_case_runtime import (
    native_ephemeris_files_module as native_ephemeris_files_module,
)

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "tests/data/human_design/calendar_horizons"
E = BASE / "evidence"


@pytest.fixture(scope="module")
def production(native_ephemeris_files_module):  # noqa: F811 - pytest fixture dependency
    return check.capture()


def raw_response(body="Uranus"):
    return (E / f"horizons-attempt1/{body}.response.json").read_bytes()


def test_complete_predeclared_physical_tt_and_observer_request():
    fixed = plan()
    assert fixed["comparison_tolerance_arcseconds"] == 2
    assert len(fixed["epochs"]) == 17
    for body, target in fixed["bodies"].items():
        params = parameters(body)
        assert params["TIME_TYPE"] == "'TT'" and params["CENTER"] == "'500@399'"
        assert params["QUANTITIES"] == "'31'" and params["COMMAND"] == f"'{target}'"
        assert [float(s.strip("'")) for s in params["TLIST"].split()] == [
            r["jd_tt"] for r in fixed["epochs"]
        ]
        parsed = parse_response(raw_response(body), body)
        assert parsed["target_id"] == target and parsed["center_id"] == 399
        assert parsed["target_ephemeris"] == parsed["center_ephemeris"] == "DE441"
        assert [(r["id"], r["jd_tt"]) for r in parsed["rows"]] == [
            (r["id"], r["jd_tt"]) for r in fixed["epochs"]
        ]


@pytest.mark.parametrize(
    "fault",
    [
        "target",
        "center",
        "model",
        "scale",
        "quantity",
        "duplicate_marker",
        "api_error",
        "missing",
        "duplicate_epoch",
        "shift_epoch",
        "nonfinite",
        "longitude",
        "latitude",
        "truncated",
    ],
)
def test_invalid_source_or_epoch_never_becomes_a_passing_coordinate(fault):
    payload = json.loads(raw_response())
    text = payload["result"]
    if fault == "target":
        text = text.replace("Uranus Barycenter (7)", "Neptune Barycenter (8)")
    elif fault == "center":
        text = text.replace("Earth (399)", "Sun (10)")
    elif fault == "model":
        text = text.replace("DE441", "unknown")
    elif fault == "scale":
        text = text.replace("Date_________JDTT", "Date_________JDUT")
    elif fault == "quantity":
        text = text.replace("ObsEcLon", "hEcl-Lon")
    elif fault == "duplicate_marker":
        text += "$$SOE"
    elif fault == "api_error":
        payload["error"] = "incomplete ephemeris"
    else:
        prefix, rest = text.split("$$SOE")
        table, suffix = rest.split("$$EOE")
        lines = table.strip().splitlines()
        if fault == "missing":
            lines.pop()
        elif fault == "duplicate_epoch":
            lines[-1] = lines[0]
        else:
            cells = lines[0].split(",")
            if fault == "shift_epoch":
                cells[0] = str(float(cells[0]) + 1)
            elif fault == "nonfinite":
                cells[3] = "nan"
            elif fault == "longitude":
                cells[3] = "360"
            elif fault == "latitude":
                cells[4] = "91"
            else:
                cells = cells[:2]
            lines[0] = ",".join(cells)
        text = prefix + "$$SOE\n" + "\n".join(lines) + "\n$$EOE" + suffix
    payload["result"] = text
    with pytest.raises(ValueError):
        parse_response(json.dumps(payload).encode(), "Uranus")


def test_raw_order_is_matched_by_physical_epoch_not_position():
    payload = json.loads(raw_response())
    prefix, rest = payload["result"].split("$$SOE")
    table, suffix = rest.split("$$EOE")
    payload["result"] = (
        prefix
        + "$$SOE\n"
        + "\n".join(reversed(table.strip().splitlines()))
        + "\n$$EOE"
        + suffix
    )
    assert (
        parse_response(json.dumps(payload).encode(), "Uranus")["rows"]
        == parse_response(raw_response(), "Uranus")["rows"]
    )


def test_current_three_way_diagnostics_preserve_absolute_failure(production):
    result = check.compare(production, check.references())
    assert result["position_count"] == 34
    assert result["status"] == "disagreements_remain"
    assert result["original_failed_row_passed"] is False
    assert result["original_tolerances_changed"] is False
    assert result["complete_calendar_acceptance"] is False
    assert result["comparison_counts"] == {
        "swiss_minus_original_de440": {
            "positions": 34,
            "within_original_threshold": 33,
            "failed": 1,
        },
        "horizons_minus_original_de440": {
            "positions": 34,
            "within_original_threshold": 32,
            "failed": 2,
        },
        "horizons_minus_swiss": {
            "positions": 34,
            "within_original_threshold": 33,
            "failed": 1,
        },
    }
    center = next(
        r for r in result["rows"] if r["body"] == "Uranus" and r["offset_days"] == 0
    )
    effects = center["signed_differences_arcseconds"]
    assert (
        effects["swiss_minus_original_de440"]
        > plan()["comparison_tolerance_arcseconds"]
    )
    assert effects["horizons_minus_original_de440"] == 5.451327237449277
    assert (
        abs(
            effects["swiss_minus_original_de440"]
            - (
                effects["no_deflection_swiss_minus_de440"]
                + effects["swiss_deflection_effect"]
                - effects["skyfield_deflection_effect"]
            )
        )
        < 1e-8
    )
    assert all(r["production_longitude_replaced"] is False for r in result["rows"])


@pytest.mark.parametrize(
    "fault", ["delete", "duplicate", "epoch", "backend", "flags", "coordinates"]
)
def test_captured_producer_cannot_lose_a_case_or_change_its_coordinate_binding(
    fault, production
):
    value = deepcopy(production)
    if fault == "delete":
        value["rows"].pop()
    elif fault == "duplicate":
        value["rows"][-1] = deepcopy(value["rows"][0])
    elif fault == "epoch":
        value["rows"][0]["jd_tt"] += 1
    elif fault == "backend":
        value["rows"][0]["position"]["ephemeris_model"] = "moshier"
    elif fault == "flags":
        value["rows"][0]["controls"]["no_gravitational_deflection"][
            "return_flags"
        ] = 258
    else:
        value["rows"][0]["position"]["longitude"] += 0.01
    with pytest.raises(ValueError):
        check.compare(value, check.references())


def test_original_full_calendar_oracles_thresholds_and_generator_stay_frozen():
    from scripts.human_design.check_human_design_calendar_span import reference

    fixed, original = reference(ROOT)
    assert len(original["pairs"]) == len(fixed["birth_epochs"]) == 1200
    assert fixed["comparison_tolerance_arcseconds"] == 2.0
    assert fixed["design_root_time_tolerance_seconds"] == 5.0
