"""Frozen high-order evidence retains old contradictions and unknown premises."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from decimal import Decimal
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.verify_astrodice_taylor_scalar import verify as scalar_verify
from scripts.verify_astrodice_taylor_scalar import weights
from scripts.verify_astrodice_taylor_witnesses import verify

FIXTURE = Path(__file__).parent / "fixtures/astrodice-venus-taylor-v1"


def load(name):
    return json.loads((FIXTURE / name).read_text())


def copy_inputs(target):
    for name in [
        "plan-before-high-order-evaluation.json",
        "Taylor-first-enclosures.json",
    ]:
        shutil.copy2(FIXTURE / name, target / name)
    shutil.copytree(FIXTURE / "old-proofs", target / "old-proofs")


def test_frozen_inputs_and_original_qualification_are_preserved():
    manifest = FIXTURE / "manifest.json"
    assert (
        hashlib.sha256(manifest.read_bytes()).hexdigest()
        == "ffec8d477d01bf8f9dc0bb5c53fdb0e97944d86e31979e8975260cb1311c7111"
    )
    files = load("manifest.json")["files"]
    assert len(files) == 60
    for name, sha in files.items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == sha
    result = load("Taylor-first-enclosures.json")
    assert result["source_enclosure_exit_code"] == 0
    assert result["production_acceptance_exit_code"] == 2
    assert result["independent_decimal_components_checked"] == 20736
    assert result["new_conditions"] == result["candidate_calls"] == 0
    assert (
        result["source_Horizons_high_derivative_bound_equivalence_certified"] is False
    )


def test_all_five_old_witnesses_survive_the_derived_Taylor_allowance():
    observed = verify(FIXTURE, FIXTURE / "Taylor-first-enclosures.json")
    assert observed == load("independent-witnesses-first.json")
    assert observed["old_exact_proofs_verified"] == 5
    assert all(
        Q(r["original_scaled_contradiction"]) < Q(r["relaxed_scaled_combination"]) < 0
        for r in observed["rows"]
    )
    assert [r["source_coefficient_order"] for r in observed["rows"]] == [5, 5, 7, 5, 7]
    assert not observed["epoch_perturbation_allowance_included"]
    assert observed["production_acceptance_exit_code"] == 2


def test_independent_scalar_replay_in_a_fresh_process(tmp_path):
    root = (FIXTURE / "frozen-source").resolve()
    output = tmp_path / "scalar.json"
    cmd = [
        sys.executable,
        "-m",
        "scripts.verify_astrodice_taylor_scalar",
        "--run",
        str(FIXTURE.resolve()),
        "--enclosures",
        str((FIXTURE / "Taylor-first-enclosures.json").resolve()),
        "--output",
        str(output),
    ]
    p = subprocess.run(
        cmd,
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root)},
        capture_output=True,
        text=True,
    )
    assert p.returncode == 0, p.stderr
    assert json.loads(output.read_text()) == load("independent-scalar-first.json")


def test_scalar_weights_extract_normalized_coefficients_not_factorial_derivatives():
    for order, expected in [(5, 2), (7, 3)]:
        w = weights(order)
        assert (
            sum(
                (v * (2 * x**5 + 3 * x**7 + 5 * x**9) for x, v in zip(range(-7, 8), w)),
                Q(),
            )
            == expected
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_segment",
        "duplicate_support",
        "understated_maximum",
        "wrong_factorial",
        "physical_promotion",
        "old_weight",
        "old_observation",
    ],
)
def test_witness_replay_refuses_incomplete_or_redefined_material(tmp_path, mutation):
    copy_inputs(tmp_path)
    if mutation == "wrong_factorial":
        p = tmp_path / "plan-before-high-order-evaluation.json"
        d = json.loads(p.read_text())
        d["jet_coefficient_convention"] = "raw derivatives"
    elif mutation in ["old_weight", "old_observation"]:
        p = (
            tmp_path
            / "old-proofs"
            / (
                "exact-incompatibility-diagnostic.json"
                if mutation == "old_weight"
                else "development-reference.json"
            )
        )
        d = json.loads(p.read_text())
        if mutation == "old_weight":
            d["records"][0]["witness"]["weights"][0] = "1"
        else:
            row = d["rows"][0]
            row["samples"]["5"]["printed_angles"][0] = str(
                Decimal(row["samples"]["5"]["printed_angles"][0]) + Decimal("0.001")
            )
    else:
        p = tmp_path / "Taylor-first-enclosures.json"
        d = json.loads(p.read_text())
        if mutation == "missing_segment":
            d["rows"][0]["segments"].pop()
        elif mutation == "duplicate_support":
            d["rows"][0]["segments"][1] = d["rows"][0]["segments"][0]
        elif mutation == "understated_maximum":
            d["rows"][0]["global_normalized_coefficient_bounds_arcsec"]["5"][0] = "0"
        else:
            d["source_Horizons_high_derivative_bound_equivalence_certified"] = True
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError):
        verify(tmp_path, tmp_path / "Taylor-first-enclosures.json")


def test_a_nonnegative_relaxed_witness_does_not_become_a_feasibility_or_accuracy_claim(
    tmp_path,
):
    copy_inputs(tmp_path)
    p = tmp_path / "Taylor-first-enclosures.json"
    d = json.loads(p.read_text())
    for segment in d["rows"][0]["segments"]:
        segment["angular_coefficients_arcsec"][0][4] = {
            "lower_numerator": str(-(10**6) * 2**256),
            "upper_numerator": str(10**6 * 2**256),
            "denominator_power_two": 256,
        }
    d["rows"][0]["global_normalized_coefficient_bounds_arcsec"]["5"][0] = str(10**6)
    p.write_text(json.dumps(d))
    observed = verify(tmp_path, p)
    assert any(
        not r["relaxed_combination_still_strictly_negative"] for r in observed["rows"]
    )
    assert all(
        "feasibility is not certified" in r["meaning"]
        for r in observed["rows"]
        if not r["relaxed_combination_still_strictly_negative"]
    )
    assert (
        observed["production_acceptance_exit_code"] == 2
        and not observed["full_goal_complete"]
    )


def test_forged_center_coefficient_fails_independent_scalar_control(tmp_path):
    d = load("Taylor-first-enclosures.json")
    d["rows"][0]["center_angular_coefficients_arcsec"][0][4] = {
        "lower_numerator": "0",
        "upper_numerator": "0",
        "denominator_power_two": 256,
    }
    p = tmp_path / "altered.json"
    p.write_text(json.dumps(d))
    result = scalar_verify(FIXTURE, p)
    assert result["exit_code"] == 2 and result["production_acceptance_exit_code"] == 2
