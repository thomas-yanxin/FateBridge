"""Test the bound, its exact replay, and refusal to promote clock hypotheses."""

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
from decimal import Decimal, localcontext
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.astrodice_epoch_envelope import envelope_system, quality, replay_fit
from scripts.astrodice_interval_reference import dot, system

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/astrodice-epoch-envelope-v1"


def read(name):
    return json.loads((FIXTURE / name).read_text())


def test_reference_artifacts_and_uncertified_premises_stay_frozen():
    assert hashlib.sha256((FIXTURE / "manifest.json").read_bytes()).hexdigest() == (
        "1f69b8ea98e720b49ddacaf500f5424d98222654e37d9e3738878f1036d21262"
    )
    for name, digest in read("manifest.json")["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    for name in [
        "scripts/astrodice_epoch_envelope.py",
        "scripts/audit_astrodice_epoch_envelope.py",
    ]:
        assert (ROOT / name).read_bytes() == (
            FIXTURE / "frozen-reference-code" / name
        ).read_bytes()
    result = read("outer-first-result.json")
    assert result["candidate_accuracy_passes"] == result["new_holdout_conditions"] == 0
    assert result["production_acceptance_exit_code"] == 2
    assert not result["actual_epoch_envelope_certified"]
    assert not result["old_Farkas_proofs_or_scores_regraded"]


@pytest.mark.parametrize("epoch", [Q(), Q(1, 10**9)])
@pytest.mark.parametrize("order", [3, 5])
@pytest.mark.parametrize("rates", [(3600, -3600), (1200, -1800)])
def test_mean_value_envelope_contains_known_linear_truth_with_manufactured_jitter(
    epoch, order, rates
):
    samples = {}
    with localcontext() as context:
        context.prec = 60
        for t in range(-1440, 1441, 5):
            jitter = ((t // 5) % 3 - 1) * epoch
            values = [
                Q(base) + Q(rate, 3600) * (Q(t, 86400) + jitter)
                for base, rate in zip([100, 15], rates)
            ]
            samples[str(t)] = {
                "printed_angles": [
                    format(Decimal(v.numerator) / Decimal(v.denominator), ".9f")
                    for v in values
                ]
            }
    row = {"samples": samples}
    for axis, rate in enumerate(rates):
        a, b, baseline, scale, metadata = envelope_system(
            row, 1440, order, axis, epoch, 3600
        )
        true_primal = [(Q(rate * 1440, 86400) - baseline) / scale] + [Q()] * (
            (order - 1) // 2
        )
        assert all(
            dot(coefficients, true_primal) <= bound for coefficients, bound in zip(a, b)
        )
        assert Q(metadata["additional_epoch_envelope_arcsec"]) == 3600 * epoch


def test_zero_epoch_envelope_is_exactly_the_original_model_and_positive_envelope_is_outer():
    row = read("old-first/A-JD-reference-first.json")["rows"][0]
    for window in [1440, 1080, 810, 600, 450, 330, 240, 180, 130, 90, 60]:
        for order in [3, 5]:
            for axis in [0, 1]:
                old_a, old_b, baseline, scale = system(
                    row, None, window, order, axis, step_seconds=5
                )
                a, b, base, unit, _ = envelope_system(row, window, order, axis, 0, 3600)
                assert (a, b, base, unit) == (old_a, old_b, baseline, scale)
                aa, bb, base, unit, _ = envelope_system(
                    row, window, order, axis, Q(1, 10**9), 3600
                )
                assert aa == old_a and base == baseline and unit == scale
                assert all(
                    v - old == Q(3600, 10**9) / scale for v, old in zip(bb, old_b)
                )


def test_exact_certificates_and_all_original_windows_replay_without_granting_acceptance():
    certs = read("outer-first-certificates.json")
    a = read("old-first/A-JD-reference-first.json")["rows"]
    b = read("old-recovery/recovery-first/B-JD-reference.json")["rows"]
    for row, record in zip(a + b, certs["rows"]):
        result = quality(row, record["fits"], Q(1, 10**9), 3600)
        assert result == record["quality"]
        assert len(record["fits"]) == 22
        assert result["status"] == "outer_reference_quality_unresolved"
        assert (
            result["production_acceptance_status"]
            == "unresolved_epoch_and_model_premises"
        )
        assert result["all_window_checks"][0]["complete_exact_outer_certificates"]
        assert (
            result["all_window_checks"][0]["maximum_outer_radius_arcsec_per_day"]
            > 0.002
        )


def test_clock_certificate_cannot_be_rebound_to_a_smaller_envelope():
    row = read("old-first/A-JD-reference-first.json")["rows"][0]
    fit = read("outer-first-certificates.json")["rows"][0]["fits"][0]
    with pytest.raises(ValueError, match="constraint identity changed"):
        replay_fit(row, fit, Q(1, 2 * 10**9), 3600)


def test_missing_probes_and_narrowed_fit_sets_are_rejected():
    row = read("old-first/A-JD-reference-first.json")["rows"][0]
    fits = read("outer-first-certificates.json")["rows"][0]["fits"]
    altered = copy.deepcopy(row)
    altered["samples"]["1435"] = None
    with pytest.raises(ValueError, match="unavailable point"):
        quality(altered, fits, Q(1, 10**9), 3600)
    with pytest.raises(ValueError, match="windows and orders cannot be narrowed"):
        quality(row, fits[1:], Q(1, 10**9), 3600)


def test_complete_replay_uses_the_frozen_reference_profile_and_exits_unresolved(
    tmp_path,
):
    source = FIXTURE / "frozen-reference-code"
    output = tmp_path / "replayed.json"
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.audit_astrodice_epoch_envelope",
            "--run",
            str(FIXTURE),
            "--certificates",
            str(FIXTURE / "outer-first-certificates.json"),
            "--output",
            str(output),
        ],
        cwd=source,
        env=dict(os.environ, PYTHONPATH=str(source)),
        capture_output=True,
        text=True,
    )
    assert process.returncode == 2, process.stderr
    assert json.loads(output.read_text()) == read("outer-first-result.json")


def test_independent_angular_reconstruction_uses_no_producer_solver_or_candidate(
    tmp_path,
):
    independent = FIXTURE.with_name("astrodice-epoch-envelope-independent-v1")
    assert hashlib.sha256((independent / "manifest.json").read_bytes()).hexdigest() == (
        "10a3dc24d8c9287d0fe15ec8cc70cebc575f09cfef90e9fb6c8aedc3e3bfcd71"
    )
    manifest = json.loads((independent / "manifest.json").read_text())
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((independent / name).read_bytes()).hexdigest() == digest
    verifier = ROOT / "scripts/verify_astrodice_epoch_envelope.py"
    assert verifier.read_bytes() == (independent / "verifier.py.txt").read_bytes()
    output = tmp_path / "independent.json"
    process = subprocess.run(
        [
            sys.executable,
            str(verifier),
            "--fixture",
            str(FIXTURE),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    result = json.loads(output.read_text())
    assert result == json.loads((independent / "first-result.json").read_text())
    assert result["exact_dual_optima_checked"] == 264
    assert result["direct_unscaled_primal_inequalities_checked"] == 25968
    assert result["candidate_accuracy_passes"] == 0


def test_independent_verifier_rejects_modified_primal_without_relying_on_a_manifest(
    tmp_path,
):
    copied = tmp_path / "data"
    shutil.copytree(FIXTURE, copied)
    path = copied / "outer-first-certificates.json"
    data = json.loads(path.read_text())
    certificate = data["rows"][0]["fits"][0]["axes"][0]["certificates"][0]
    certificate["primal"][0] = str(Q(certificate["primal"][0]) + 1)
    certificate["optimum"] = certificate["primal"][0]
    path.write_text(json.dumps(data))
    process = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/verify_astrodice_epoch_envelope.py"),
            "--fixture",
            str(copied),
            "--output",
            str(tmp_path / "bad.json"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert process.returncode != 0
    assert (
        "primal inequality failed" in process.stderr
        or "primal/dual equality failed" in process.stderr
    )
