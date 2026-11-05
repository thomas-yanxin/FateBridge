"""Exact LP witnesses, all constraints and shared-frame chain rule guards."""

import copy
import json
import math
import subprocess
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest

from scripts.astrodice.astrodice_interval_reference import (
    quality,
    replay_interval,
    verify,
)
from scripts.astrodice.audit_astrodice_horizons_wide_reference import validate
from scripts.astrodice.audit_astrodice_local_motion import display_reference

FIXTURE = (
    Path(__file__).parents[1]
    / "data/astrodice/reference_sets/fixture-local-interval-development-v1"
)


def test_known_development_raw_and_every_exact_witness_replay_without_solver():
    raw = validate(
        FIXTURE / "protocol.json",
        FIXTURE / "reference.json",
        FIXTURE / "raw",
        FIXTURE / "reference-seal.json",
    )
    assert raw["position_probes"] == 289
    row = json.loads((FIXTURE / "reference.json").read_text())["rows"][0]
    record = json.loads((FIXTURE / "certificate-row.json").read_text())
    assert quality(row, record["fits"]) == record["quality"]
    assert record["quality"]["selected_window_seconds"] == 1080
    # This is the known failedcase's newdevelopment proof, not a fresh holdout.
    assert row["role"] == "known_control"


def certificate():
    return {
        "status": "exact_primal_dual_optimum",
        "objective_sign": 1,
        "active": [1],
        "primal": ["1"],
        "dual": ["-1"],
        "optimum": "1",
    }


def test_negative_free_variable_minimum_is_accepted():
    c = certificate()
    c.update(primal=["-2"], optimum="-2")
    assert verify([[F(1)], [F(-1)]], [F(3), F(2)], c) == -2


@pytest.mark.parametrize(
    "field,value",
    [
        ("objective_sign", 0),
        ("active", [0, 1]),
        ("primal", ["0"]),
        ("dual", ["1"]),
        ("optimum", "0"),
        ("status", "solver_success"),
    ],
)
def test_forged_primal_dual_witness_rejected(field, value):
    c = certificate()
    c[field] = value
    with pytest.raises(ValueError):
        verify([[F(1)], [F(-1)]], [F(3), F(-1)], c)


def test_all_nonactive_constraints_are_checked():
    c = certificate()
    c.update(objective_sign=-1, active=[0], primal=["3"], optimum="-3")
    with pytest.raises(ValueError, match="feasible"):
        verify([[F(1)], [F(-1)], [F(1)]], [F(3), F(-1), F(2)], c)


def test_certificate_verification_cannot_be_disabled_with_python_optimization():
    code = "from fractions import Fraction as F;from scripts.astrodice.astrodice_interval_reference import verify;verify([[F(1)],[F(-1)]],[F(3),F(-1)],{'status':'exact_primal_dual_optimum','objective_sign':1,'active':[1],'primal':['0'],'dual':['-1'],'optimum':'1'})"
    result = subprocess.run(
        [sys.executable, "-O", "-c", code], capture_output=True, text=True
    )
    assert result.returncode != 0 and "ValueError" in result.stderr


def test_tampering_exact_declared_interval_does_not_keep_a_valid_certificate():
    row = json.loads((FIXTURE / "reference.json").read_text())["rows"][0]
    fit = copy.deepcopy(
        json.loads((FIXTURE / "certificate-row.json").read_text())["fits"][0]
    )
    fit["axes"][0]["lower_arcsec_per_day"] = "0"
    with pytest.raises(ValueError, match="differs"):
        replay_interval(row, fit)


def test_display_chain_rule_includes_shared_frame_rotation_and_bound():
    row = json.loads((FIXTURE / "reference.json").read_text())["rows"][0]
    axes = [
        (F(1000) - F(1, 10000), F(1000) + F(1, 10000)),
        (F(100) - F(2, 10000), F(100) + F(2, 10000)),
    ]
    omega = 1e-6
    identity = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    rotating = [[0, -omega, 0], [omega, 0, 0], [0, 0, 0]]
    result = display_reference(row, axes, identity, [rotating, rotating])
    assert result["midpoint_arcsec_per_day"] == pytest.approx(
        1000 + math.degrees(omega) * 3600, abs=1e-10
    )
    assert result["rounding_and_frame_check_radius_arcsec_per_day"] > 1e-4
    assert result["frame_check_qualified"]


def test_missing_support_fit_does_not_silently_shrink_the_plan():
    row = json.loads((FIXTURE / "reference.json").read_text())["rows"][0]
    record = json.loads((FIXTURE / "certificate-row.json").read_text())
    with pytest.raises(ValueError, match="plan changed"):
        quality(row, record["fits"][:-1])
