"""Source-model evidence cannot erase reference uncertainty or fixed lines."""

import json
import shutil
from decimal import Decimal
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.astrodice_clock_interval import A
from scripts.astrodice_source_slope_bounds import angular_rate_bounds, pi_bounds
from scripts.verify_astrodice_source_slope import verify as verify_slopes
from scripts.verify_astrodice_source_slope_epoch import verify as verify_lp

FIXTURE = (
    Path(__file__).parent
    / "data/astrodice/reference_sets/fixture-venus-source-shape-v1"
)


def test_machin_pi_bounds_and_nonunit_vector_angular_units():
    lower, upper = pi_bounds()
    known = Q(Decimal("3.14159265358979323846264338327950288419716939937510"))
    assert lower < known < upper
    assert upper - lower < Q(1, 10**40)
    # alpha'=1rad/day, delta'=1/2rad/day for (2,0,2), v=(0,2,2).
    bounds = angular_rate_bounds([A(2, 0), A(0, 2), A(2, 2)])
    assert bounds[0] >= Q(648000) / upper
    assert bounds[0] <= Q(648000) / lower + Q(1, 10**60)
    assert bounds[1] >= Q(324000) / upper
    assert bounds[1] <= Q(324000) / lower + Q(1, 10**60)


def test_pole_cannot_receive_a_finite_RA_slope_certificate():
    with pytest.raises(ValueError):
        angular_rate_bounds([A(0), A(0), A(1)])


def test_independent_source_boxes_and_unscaled_LP_certificates_replay():
    slope = verify_slopes(FIXTURE)
    assert slope["derived_scalar_caps"] == [1932, 1930, 1934]
    assert slope["angular_rate_boxes_checked"] == 3456
    assert slope["decimal_component_containments_checked"] == 20736
    lp = verify_lp(FIXTURE)
    assert lp["direct_unscaled_primal_inequalities_checked"] == 25968
    assert lp["exact_dual_optima_checked"] == 264
    assert lp["production_acceptance_exit_code"] == 2


@pytest.mark.parametrize(
    "mutation",
    [
        "rate_box",
        "time_support",
        "node_epoch",
        "drop_segment",
        "physical_promotion",
        "epoch_assumption",
    ],
)
def test_independent_source_replay_refuses_underbounds_and_premise_changes(
    tmp_path, mutation
):
    names = [
        "shape-first.json",
        "source-slope-first.json",
        "source-slope-plan-before-evaluation.json",
    ]
    for name in names:
        shutil.copy2(FIXTURE / name, tmp_path / name)
    name = (
        "shape-first.json"
        if mutation == "node_epoch"
        else (
            "source-slope-plan-before-evaluation.json"
            if mutation == "epoch_assumption"
            else "source-slope-first.json"
        )
    )
    path = tmp_path / name
    data = json.loads(path.read_text())
    if mutation == "rate_box":
        data["rows"][0]["segments"][0]["absolute_RA_DEC_bounds_arcsec_per_day"][0] = "0"
    elif mutation == "time_support":
        data["rows"][0]["segments"][0]["exact_lower_nominal_TDB"] = "0"
    elif mutation == "node_epoch":
        data["rows"][0]["nodes"][0]["exact_nominal_epoch"] = "0"
    elif mutation == "drop_segment":
        data["rows"][0]["segments"].pop()
    elif mutation == "physical_promotion":
        data["physical_ephemeris_slope_bound_certified"] = True
    else:
        data["epoch_error_hypothesis_days"] = "1/2000000000"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        verify_slopes(tmp_path)


@pytest.mark.parametrize(
    "mutation", ["primal_and_own_optimum", "missing_window", "tuned_cap"]
)
def test_unscaled_LP_replay_rejects_forged_proofs_or_narrowed_scope(tmp_path, mutation):
    names = [
        "source-slope-plan-before-evaluation.json",
        "source-cap-first-certificates.json",
        "source-slope-first.json",
        "old-A-JD-reference.json",
        "old-B-JD-reference.json",
    ]
    for name in names:
        shutil.copy2(FIXTURE / name, tmp_path / name)
    name = (
        "source-slope-first.json"
        if mutation == "tuned_cap"
        else "source-cap-first-certificates.json"
    )
    path = tmp_path / name
    data = json.loads(path.read_text())
    if mutation == "tuned_cap":
        data["rows"][0]["scalar_cap_arcsec_per_day"] -= 1
    elif mutation == "missing_window":
        data["rows"][0]["fits"][1] = data["rows"][0]["fits"][0]
    else:
        certificate = data["rows"][0]["fits"][0]["axes"][0]["certificates"][0]
        certificate["primal"][0] = str(Q(certificate["primal"][0]) + 1)
        certificate["optimum"] = certificate["primal"][0]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        verify_lp(tmp_path)
