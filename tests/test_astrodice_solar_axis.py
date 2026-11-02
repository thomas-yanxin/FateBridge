"""Counterexample replay, fixed premises, and evidence-tampering rejections."""

import json
import shutil
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.astrodice_clock_interval import I
from scripts.astrodice_solar_axis import atan, premise
from scripts.verify_astrodice_solar_axis import verify

ROOT = Path(__file__).parents[1]
RUN = ROOT / "docs/validation/astrodice-solar-axis-run-2026-10-28"


def test_independent_closed_form_covers_all_original_development_probes():
    result = verify(RUN, RUN / "development-first.json")
    assert result["samples"] == 16
    assert 0.48435124 < result["jump_arcsec_approx"] < 0.48435125
    assert result["universal_error_upper_arcsec_approx"] < 3e-11
    assert result["new_production_accuracy_holdouts"] == 0
    assert result["full_goal_complete"] is False


@pytest.mark.parametrize(
    "mutation", ["drop", "duplicate", "sign", "bound", "line", "credit"]
)
def test_independent_replay_rejects_omission_narrowing_and_false_credit(
    mutation, tmp_path
):
    data = json.loads((RUN / "development-first.json").read_text())
    if mutation == "drop":
        data["samples"].pop()
    elif mutation == "duplicate":
        data["samples"][-1] = data["samples"][0]
    elif mutation == "sign":
        data["samples"][0]["signed_deflection_arcsec"] = ["-1", "-1/2"]
    elif mutation == "bound":
        data["uniform_approach_error_upper_arcsec"] = "0"
    elif mutation == "line":
        data["old_rate_reference_line_arcsec_per_day"] = "0.02"
    else:
        data["new_production_accuracy_holdouts"] = 16
    path = tmp_path / "mutant.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        verify(RUN, path)


@pytest.mark.parametrize(
    "path",
    [
        "plan-before-analysis.json",
        "authority/sweph.c",
        "authority/sweph.h",
        "authority/native-solar-mass-v1.json",
    ],
)
def test_both_readers_refuse_changed_frozen_premises(path, tmp_path):
    shutil.copytree(RUN / "authority", tmp_path / "authority")
    shutil.copyfile(
        RUN / "plan-before-analysis.json", tmp_path / "plan-before-analysis.json"
    )
    target = tmp_path / path
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(ValueError):
        premise(tmp_path)
    with pytest.raises(ValueError):
        verify(tmp_path, RUN / "development-first.json")


def test_small_angle_enclosure_refuses_unproved_domain():
    with pytest.raises(ValueError, match="Outside the frozen"):
        atan(I(Q(1, 999)))
