"""Closest representable solar roots and honest boundary-resolution witnesses."""

import math
import os
import subprocess
import sys
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core import human_design_time as times
from fatebridge.core.human_design import (
    activation_longitude_fraction,
    longitude_activation,
    solar_root_subdivisions,
)
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from tests.support.ephemeris_case_runtime import native_ephemeris_files_module

SPEC = next(s for s in CATALOG if s.key == "human_design")
ROOT = Path(__file__).resolve().parents[2]
INPUT = dict(
    birth_year=2000,
    birth_month=1,
    birth_day=1,
    birth_hour=12,
    birth_minute=0,
    birth_timezone="UTC",
)


@pytest.mark.parametrize("birth", [2451545.0, 2451545.123456789])
@pytest.mark.parametrize("num,den", [(1, 1), (49, 50), (51, 50), (19, 20), (21, 20)])
def test_exact_linear_oracle_requires_the_best_representable_TT(
    monkeypatch, birth, num, den
):
    rate = Fraction(num, den)
    p = Fraction(131328125, 1000000)

    def sun(tt, *args, **kwargs):
        return float((p + rate * (Fraction(tt) - Fraction(birth))) % 360)

    monkeypatch.setattr(times, "sun_at_tt", sun)
    solved = times.solve_design_epoch_tt(birth)
    true = Fraction(birth) - 88 / rate
    nearest = float(true)
    candidates = {
        nearest,
        math.nextafter(nearest, -math.inf),
        math.nextafter(nearest, math.inf),
    }

    def residual(tt):
        return (Fraction(sun(birth)) - Fraction(sun(tt))) % 360 - 88

    best = min(candidates, key=lambda t: (abs(residual(t)), t))
    assert solved["time"]["jd_tt"] == best
    assert solved["solver"]["residual_degrees"] == float(residual(best))


def test_submillisecond_bracket_does_not_certify_one_base(monkeypatch):
    birth = 2451545.0
    rate = Fraction(51, 50)
    p = Fraction(131328125, 1000000)
    monkeypatch.setattr(
        times,
        "sun_at_tt",
        lambda t, *a, **k: float((p + rate * (Fraction(t) - Fraction(birth))) % 360),
    )
    solved = times.solve_design_epoch_tt(birth)
    witness = solved["solver"]["numerical_precision"]
    lo, hi = witness["lower"], witness["upper"]
    assert math.nextafter(lo["jd_tt"], math.inf) == hi["jd_tt"]
    assert {longitude_activation(r["sun_longitude"])["base"] for r in [lo, hi]} == {
        1,
        5,
    }
    assert witness["physical_time_accuracy_certified"] is False


@pytest.fixture(scope="module")
def complete(native_ephemeris_files_module):
    return execute_tool(SPEC, SPEC.request_model(**INPUT))


def test_full_backend_witness_selects_verified_files_from_an_empty_ambient_path(
    tmp_path,
):
    empty = tmp_path / "empty-ephemeris"
    empty.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            str(Path(__file__).resolve())
            + "::test_current_full_backend_cannot_bypass_root_check_by_deleting_reference_witness",
        ],
        cwd=ROOT,
        env={**os.environ, "SE_EPHE_PATH": str(empty)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_current_full_reading_keeps_numeric_root_and_physical_precision_separate(
    complete,
):
    w = complete["design_solver"]["numerical_precision"]
    assert w["physical_time_accuracy_certified"] is False
    assert w["other_bodies_bracket_sensitivity_assessed"] is True
    assert w["solar_endpoint_subdivisions"]
    for row in w["solar_endpoint_subdivisions"]:
        assert (
            activation_longitude_fraction(row["Earth"])
            == (activation_longitude_fraction(row["Sun"]) + 180) % 360
        )
    assert complete["interpretation"]["design_time_precision_meaning"]
    check = verify_human_design_reading(complete)
    assert check["status"] == "verified_fixed_template_reading", check


@pytest.mark.parametrize("delete_selected_witness", [False, True])
def test_current_full_backend_cannot_bypass_root_check_by_deleting_reference_witness(
    complete,
    delete_selected_witness,
):
    from fatebridge.validation.human_design_backend import verify_full_backend_report

    value = deepcopy(complete)
    report = value["ephemeris_backend_comparison"]
    assert report["selected_physical_models"] == ["swieph"]
    assert report["status"] == "full_backend_compared"
    assert verify_full_backend_report(value)["checked_adjacent_solar_root_count"] == 1
    report["reference_chart"]["design_solver"].pop("numerical_precision")
    if delete_selected_witness:
        value["design_solver"].pop("numerical_precision")
    assert verify_full_backend_report(value)["errors"]


@pytest.mark.parametrize(
    "tamper",
    [
        "selected_TT",
        "birth_TT",
        "endpoint_TT",
        "endpoint_sun",
        "residual",
        "adjacency",
        "certificate",
        "solar_base",
        "shifted_entire_solar_function",
        "missing",
    ],
)
def test_forged_solver_context_cannot_pass_by_rehashing_and_regenerating_rule_trace(
    complete, tamper
):
    value = deepcopy(complete)
    s = value["design_solver"]
    w = s.get("numerical_precision")
    if tamper == "selected_TT":
        s["design_jd_tt"] += 0.01
    elif tamper == "birth_TT":
        s["birth_jd_tt"] += 0.01
    elif tamper == "missing":
        s.pop("numerical_precision", None)
    elif tamper == "shifted_entire_solar_function":
        w["birth_sun_longitude"] += 1
        for key in ("lower", "upper", "selected"):
            w[key]["sun_longitude"] += 1
        w.update(solar_root_subdivisions(s))
    else:
        assert w is not None
        if tamper == "endpoint_TT":
            w["lower"]["jd_tt"] -= 0.01
        elif tamper == "endpoint_sun":
            w["lower"]["sun_longitude"] += 0.01
        elif tamper == "residual":
            w["lower"]["exact_residual"]["numerator"] = "999"
        elif tamper == "adjacency":
            w["upper"]["jd_tt"] = math.nextafter(w["upper"]["jd_tt"], math.inf)
        elif tamper == "certificate":
            w["physical_time_accuracy_certified"] = True
        else:
            w["solar_endpoint_subdivisions"][0]["Sun"]["base"] = 99
    # An attacker may also update producer-shaped source traces; the verifier
    # still has to link the original root, endpoint arithmetic and chart TT.
    for trace in value["rule_trace"]:
        if trace["rule_id"] == "design_solar_arc":
            trace["result"] = {"design_utc": value["design_utc"], **s}
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )
    check = verify_human_design_reading(value)
    assert check["status"] == "rejected"
    assert any(
        e["code"] == "solar_root_numerical_witness_mismatch" for e in check["errors"]
    )
