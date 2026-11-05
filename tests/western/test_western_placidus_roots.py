"""A separate root algorithm, without changing the original Astrolog study."""

import copy
import json
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from scripts.western.audit_western_polar_geometry import audit
from scripts.western.gen_western_placidus_roots import solve_cusps
from tests.western.test_western_house_reference import REFERENCE, separation

ROOTS = json.loads(
    (Path(__file__).parents[1] / "fixtures/western-placidus-bisection.json").read_text()
)


def test_complete_root_grid_and_predeclared_tolerance_are_retained():
    assert len(ROOTS["cases"]) == 126
    assert ROOTS["protocol"]["cusp_tolerance_arcseconds"] == 1.0
    assert sum(c["status"] == "solved" for c in ROOTS["cases"]) == 90
    assert (
        sum(
            c["status"] == "outside_full_ecliptic_rise_set_domain"
            for c in ROOTS["cases"]
        )
        == 36
    )


def test_new_scoped_audit_rejects_wrong_axis_or_wrong_root():
    wrong = copy.deepcopy(REFERENCE)
    wrong["cases"][1]["erfa_vector_angles"]["midheaven"] += 10
    assert audit(wrong, ROOTS)["scoped_numerical_gate_passed"] is False
    bad_roots = copy.deepcopy(ROOTS)
    bad_roots["cases"][3]["cusps"][0] += 10
    assert audit(REFERENCE, bad_roots)["scoped_numerical_gate_passed"] is False


@pytest.mark.parametrize("bad", [[0.0] * 11, [float("nan")] * 12])
def test_incomplete_or_nonfinite_root_arrays_cannot_pass_the_audit(bad):
    damaged = copy.deepcopy(ROOTS)
    damaged["cases"][3]["cusps"] = bad
    with pytest.raises(ValueError, match="twelve finite"):
        audit(REFERENCE, damaged)


@pytest.mark.parametrize("case", ROOTS["cases"])
def test_native_placidus_against_independent_monotone_roots(case):
    p = case["input"]
    if case["status"] != "solved":
        with pytest.raises(runtime.swe.Error):
            runtime.ephemeris_call(
                "houses_ex", p["jd_ut1"], p["latitude"], p["longitude"], b"P"
            )
        return
    native, _ = runtime.ephemeris_call(
        "houses_ex", p["jd_ut1"], p["latitude"], p["longitude"], b"P"
    )
    assert (
        max(separation(a, b) for a, b in zip(native, case["cusps"]))
        <= ROOTS["protocol"]["cusp_tolerance_arcseconds"]
    )


@pytest.mark.parametrize("theta", [0.0, 17.3, 359.999])
def test_flat_ecliptic_has_analytic_thirty_degree_placidus_intervals(theta):
    result = solve_cusps(theta, 50.0, 0.0, 1e-11, 64)
    assert (
        max(
            separation(x, (theta + 90 + 30 * i) % 360)
            for i, x in enumerate(result["cusps"])
        )
        < 1e-6
    )
