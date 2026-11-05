"""Independent inertial directions, frame closure and retained full failures."""

import hashlib
import json
import re
from copy import deepcopy

import pytest

from scripts import check_human_design_icrf_horizons as check
from scripts import gen_human_design_icrf_horizons as gen
from tests.ephemeris_case_runtime import (
    native_ephemeris_files_module as native_ephemeris_files_module,
)

BASE = gen.ROOT / "tests/data/human_design/icrf_horizons"
E = BASE / "evidence"


@pytest.fixture(scope="module")
def production(native_ephemeris_files_module):  # noqa: F811 - pytest fixture dependency
    return check.capture()


def raw(body="Uranus"):
    return (E / f"nasa-attempt1/{body}.response.json").read_bytes()


def test_independent_request_has_all_original_tt_and_same_response_two_frames():
    fixed = gen.plan()
    assert len(fixed["epochs"]) == 17 and fixed["angular_tolerance_arcseconds"] == 2
    for body, target in fixed["bodies"].items():
        params = gen.parameters(body)
        assert params["QUANTITIES"] == "'31,45'"
        assert params["TIME_TYPE"] == "'TT'" and params["CENTER"] == "'500@399'"
        assert params["REF_SYSTEM"] == "'ICRF'" and params["APPARENT"] == "'AIRLESS'"
        assert params["COMMAND"] == f"'{target}'"
        record = gen.parse_response(raw(body), body)
        assert len(record["rows"]) == 17
        assert record["target_ephemeris"] == record["center_ephemeris"] == "DE441"
        assert record["quantity45_frame"] == "ICRF_airless_apparent"
        assert [r["jd_tt"] for r in record["rows"]] == [
            r["jd_tt"] for r in fixed["epochs"]
        ]
    assert len(check.references()) == 2


@pytest.mark.parametrize(
    "fault",
    [
        "target",
        "center",
        "model",
        "time_scale",
        "astrometric",
        "refracted",
        "wrong_plane",
        "missing_column",
        "duplicate_header",
        "duplicate_table",
        "missing_epoch",
        "duplicate_epoch",
        "shifted_tt",
        "nan_ra",
        "bad_dec",
        "extra_cell",
        "truncated",
        "api_error",
    ],
)
def test_nasa_parse_never_accepts_wrong_frame_or_lost_original_row(fault):
    payload = json.loads(raw())
    text = payload["result"]
    replacements = {
        "target": ("Uranus Barycenter (7)", "Neptune Barycenter (8)"),
        "center": ("Earth (399)", "Sun (10)"),
        "model": ("DE441", "unknown"),
        "time_scale": ("Date_________JDTT", "Date_________JDTDB"),
        "astrometric": ("ICRF-a-app", "ICRF"),
        "refracted": ("ICRF-a-app", "ICRF-r-app"),
        "wrong_plane": ("ObsEcLon", "hEcl-Lon"),
        "missing_column": ("DEC_(ICRF-a-app)", ""),
    }
    if fault in replacements:
        text = text.replace(*replacements[fault])
    elif fault == "duplicate_header":
        line = next(s for s in text.splitlines() if "Date_________JDTT" in s)
        text = text.replace(line, line + "\n" + line)
    elif fault == "duplicate_table":
        text += "$$SOE"
    elif fault == "api_error":
        payload["error"] = "no solution"
    else:
        before, rest = text.split("$$SOE")
        table, after = rest.split("$$EOE")
        lines = table.strip().splitlines()
        if fault == "missing_epoch":
            lines.pop()
        elif fault == "duplicate_epoch":
            lines[-1] = lines[0]
        else:
            cells = lines[0].split(",")
            if fault == "shifted_tt":
                cells[0] = str(float(cells[0]) + 1)
            if fault == "nan_ra":
                cells[5] = "nan"
            if fault == "bad_dec":
                cells[6] = "91"
            if fault == "extra_cell":
                cells.append("0")
            if fault == "truncated":
                cells = cells[:5]
            lines[0] = ",".join(cells)
        text = before + "$$SOE\n" + "\n".join(lines) + "\n$$EOE" + after
    payload["result"] = text
    with pytest.raises(ValueError):
        gen.parse_response(json.dumps(payload).encode(), "Uranus")


def test_physical_tt_join_ignores_raw_row_order():
    payload = json.loads(raw())
    before, rest = payload["result"].split("$$SOE")
    table, after = rest.split("$$EOE")
    payload["result"] = (
        before
        + "$$SOE\n"
        + "\n".join(reversed(table.strip().splitlines()))
        + "\n$$EOE"
        + after
    )
    assert (
        gen.parse_response(json.dumps(payload).encode(), "Uranus")["rows"]
        == gen.parse_response(raw(), "Uranus")["rows"]
    )


def test_all34_current_comparisons_keep_in_plane_pass_and_full_direction_failure(
    production,
):
    result = check.compare(production, check.references())
    assert result["position_count"] == 34
    assert result["counts"] == {
        "horizons_minus_swiss": {
            "positions": 34,
            "angular_failed": 1,
            "longitude_failed": 0,
        },
        "horizons_minus_skyfield": {
            "positions": 34,
            "angular_failed": 1,
            "longitude_failed": 1,
        },
        "swiss_minus_skyfield": {
            "positions": 34,
            "angular_failed": 1,
            "longitude_failed": 1,
        },
    }
    assert result["status"] == "disagreements_remain"
    assert result["old_calendar_failure_regraded"] is False
    assert result["source_rotation_closure_accepted"] is True
    center = next(
        r for r in result["rows"] if r["body"] == "Uranus" and r["offset_days"] == 0
    )
    assert (
        center["comparisons"]["horizons_minus_swiss"][
            "icrf_angular_separation_arcseconds"
        ]
        > gen.plan()["angular_tolerance_arcseconds"]
    )
    assert center["frame_diagnostics_arcseconds"][
        "horizons31_minus_horizons45_in_declared_swiss_frame"
    ] == pytest.approx(0.6178763748835081, abs=1e-10)
    assert all(
        not r["production_coordinate_replaced"] and not r["original_failure_regraded"]
        for r in result["rows"]
    )


@pytest.mark.parametrize(
    "fault",
    ["delete", "duplicate", "epoch", "flags", "icrf_flags", "producer_coordinate"],
)
def test_supplied_producer_cannot_rebind_the_comparison(fault, production):
    production = deepcopy(production)
    if fault == "delete":
        production["rows"].pop()
    if fault == "duplicate":
        production["rows"][-1] = deepcopy(production["rows"][0])
    if fault == "epoch":
        production["rows"][0]["jd_tt"] += 1
    if fault == "flags":
        production["rows"][0]["default_return_flags"] = 260
    if fault == "icrf_flags":
        production["rows"][0]["icrf_return_flags"] = 133410
    if fault == "producer_coordinate":
        production["rows"][0]["position"]["longitude"] += 1
    with pytest.raises(ValueError):
        check.compare(production, check.references())


def test_angular_metric_keeps_out_of_plane_error_and_handles_wrap():
    assert check.separation(
        {"right_ascension": 12, "declination": 0},
        {"right_ascension": 12, "declination": 3 / 3600},
    ) == pytest.approx(3, abs=1e-12)
    assert check.signed(0.0001, 359.9999) == pytest.approx(0.72, abs=1e-9)
    matrix = ((0, -1, 0), (1, 0, 0), (0, 0, 1))
    assert check.spherical(check.mv(matrix, check.vector(0, 0)))["longitude"] == 90


@pytest.mark.parametrize("fault", ["scale", "reflection", "nan", "short"])
def test_invalid_rotation_does_not_become_a_valid_frame(fault, production):
    production = deepcopy(production)
    matrix = production["rows"][0]["declared_icrf_to_default_ecliptic_matrix"]
    if fault == "scale":
        matrix[0] = [v * 2 for v in matrix[0]]
    if fault == "reflection":
        matrix[0] = [-v for v in matrix[0]]
    if fault == "nan":
        matrix[0][0] = float("nan")
    if fault == "short":
        matrix.pop()
    with pytest.raises(ValueError):
        check.compare(production, check.references())


def test_latitude_closure_error_cannot_hide_behind_longitude_closure(production):
    production = deepcopy(production)
    production["rows"][0]["default_native_coordinates"][1] += 1
    result = check.compare(production, check.references())
    assert result["source_rotation_closure_accepted"] is False
    assert result["rotation_closure_maximum_arcseconds"]["swiss"] > 3599


def test_declared_bias_matrix_is_the_inspected_source_formula_not_a_residual_fit():
    raw = (BASE / "sources/swephlib.c").read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "d41eb2f396163fedd574749de02a25e8547b4e1e4c66783d47ccc0c7e4885a05"
    )
    source = raw.decode()
    block = source.split("if (bias_model == SEMOD_BIAS_IAU2006) {", 1)[1].split(
        "/* #else", 1
    )[0]
    terms = re.findall(r"rb\[(\d)\]\[(\d)\]\s*=\s*([+-][0-9.]+);", block)
    assert len(terms) == 9
    rb = {(int(i), int(j)): float(v) for i, j, v in terms}
    assert check.BIAS == tuple(tuple(rb[j, i] for j in range(3)) for i in range(3))
