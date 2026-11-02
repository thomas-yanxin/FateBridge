"""Current sensitivity must vary parameters without switching arithmetic modes."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tarfile
from copy import deepcopy
from dataclasses import fields, replace
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core import strength
from fatebridge.core.elements import ElementAnalysis
from tests.bazi_refactor_reference import assert_assessment_matches_before_repair
from tests.test_bazi_seasonal_studies import frozen

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "tests/fixtures/bazi_strength_diagnostic_v1"


def diagnostic_script():
    spec = importlib.util.spec_from_file_location(
        "strength_diagnostic", ROOT / "scripts/validate_bazi_strength.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_original_diagnostic_is_reproducible_under_its_archived_source(tmp_path):
    manifest = frozen(ARCHIVE / "source-before-manifest.json")
    archive = ARCHIVE / "source-before.tar.gz"
    assert (
        hashlib.sha256(archive.read_bytes()).hexdigest() == manifest["archive_sha256"]
    )
    with tarfile.open(archive) as handle:
        handle.extractall(tmp_path, filter="data")
    for relative, expected in manifest["files"].items():
        assert (
            hashlib.sha256((tmp_path / relative).read_bytes()).hexdigest() == expected
        )
    output = tmp_path / "before.json"
    process = subprocess.run(
        [
            sys.executable,
            str(tmp_path / "scripts/validate_bazi_strength.py"),
            "--output",
            str(output),
        ],
        env={**os.environ, "PYTHONPATH": str(tmp_path / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert json.loads(output.read_text()) == frozen(ARCHIVE / "report-before.json")
    code = """
import json
from pathlib import Path
from fatebridge.core.strength import assess_strength
from fatebridge.core.elements import ElementAnalysis
cases = json.loads(Path('tests/fixtures/bazi-strength-reference.json').read_text())
results = {}
for case in cases['cases'] + cases['additional_cases']:
    p = {k: tuple(v) for k, v in case['pillars'].items()}
    results[case['id']] = assess_strength(p, ElementAnalysis.seasonal_phases(p['month'][1]))
print(json.dumps(results, ensure_ascii=False))
"""
    original = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert original.returncode == 0, original.stderr
    expected = json.loads(original.stdout)
    cases = json.loads(
        (ROOT / "tests/fixtures/bazi-strength-reference.json").read_text()
    )
    for case in cases["cases"] + cases["additional_cases"]:
        p = {k: tuple(v) for k, v in case["pillars"].items()}
        actual = strength.assess_strength(
            p, ElementAnalysis.seasonal_phases(p["month"][1])
        )
        assert_assessment_matches_before_repair(
            ["".join(p[k]) for k in ("year", "month", "day", "hour")], actual
        )
        precise = actual["effective_elements_unrounded"]
        assert {
            element: round(value, 6) for element, value in precise.items()
        } == actual["effective_elements"]
        assert sum(precise.values()) == pytest.approx(
            actual["support_strength"] + actual["weaken_strength"], rel=0, abs=1e-12
        )


def test_policy_evaluation_and_public_default_keep_the_same_numbers_and_receipt():
    cases = json.loads(
        (ROOT / "tests/fixtures/bazi-strength-reference.json").read_text()
    )
    for case in cases["cases"] + cases["additional_cases"]:
        pillars = {k: tuple(v) for k, v in case["pillars"].items()}
        phases = ElementAnalysis.seasonal_phases(pillars["month"][1])
        raw = strength.evaluate_strength_policy(
            pillars, phases, strength.DEFAULT_POLICY
        )
        actual = strength.assess_strength(pillars, phases)
        for key in (
            "support_share",
            "support_strength",
            "weaken_strength",
            "strength_level",
        ):
            assert raw[key] == actual[key]
        assert (
            raw["stem_effects"]["ledger"] == actual["stem_energy_accounting"]["ledger"]
        )


def test_active_binding_has_a_rational_arithmetic_witness_beyond_the_old_extreme_cases():
    # Synthetic arithmetic witness, not a new source label or prediction case.
    pillars = dict(
        zip(
            ("year", "month", "day", "hour"),
            map(tuple, ["甲戌", "己巳", "壬辰", "庚子"]),
        )
    )
    phases = ElementAnalysis.seasonal_phases("巳")
    current = strength.evaluate_strength_policy(
        pillars, phases, strength.DEFAULT_POLICY
    )
    old = strength._evaluate(pillars, phases, strength.DEFAULT_POLICY)
    year = next(r for r in current["stem_effects"]["ledger"] if r["pillar"] == "year")
    # 甲 effective root 4/7, activation 1/4 + 3/4 * 4/7 = 19/28;
    # 休 factor 1, binding 17/20, so energy is 323/560 before display rounding.
    assert year["activation_root_mass"] == pytest.approx(float(Fraction(4, 7)))
    assert year["energy"] == pytest.approx(float(Fraction(323, 560)), rel=0, abs=1e-14)
    assert abs(current["weaken_strength"] - old["weaken_strength"]) > 1e-8
    assert current["strength_level"] == old["strength_level"]


def test_diagnostic_trials_retain_unrounded_results_of_the_public_policy(
    monkeypatch, tmp_path
):
    module = diagnostic_script()
    synthetic = {
        "protocol": "Synthetic arithmetic witness; no classical or predictive label.",
        "cases": [
            {
                "id": "binding-budget-witness",
                "pillars": dict(
                    zip(
                        ("year", "month", "day", "hour"),
                        ["甲戌", "己巳", "壬辰", "庚子"],
                    )
                ),
                "expected_strength": None,
            }
        ],
        "additional_cases": [],
    }
    path = tmp_path / "synthetic.json"
    path.write_text(json.dumps(synthetic))
    monkeypatch.setattr(module, "FIXTURE", path)
    report = module.build_report()
    row = report["cases"][0]
    assert row["direction_matches"] is None
    assert report["summary"]["unadjudicated_reference_cases"] == 1
    assert report["summary"]["adjudicated_reference_cases"] == 0
    assert row["stress_trials"] == 2 * len(fields(strength.DEFAULT_POLICY))
    pillars = {k: tuple(v) for k, v in synthetic["cases"][0]["pillars"].items()}
    phases = ElementAnalysis.seasonal_phases("巳")
    public_policy = strength.DEFAULT_POLICY
    witnessed_different_legacy_arithmetic = False
    for trial in row["stress_trial_details"]:
        value = getattr(public_policy, trial["parameter"]) * trial["scale"]
        if trial["parameter"] in {
            "clash_winner",
            "clash_loser",
            "clash_equal",
            "punishment",
            "binding",
            "transformation_transfer",
            "partial_transfer",
        }:
            value = min(1.0, value)
        policy = replace(public_policy, **{trial["parameter"]: value})
        with monkeypatch.context() as context:
            context.setattr(strength, "DEFAULT_POLICY", policy)
            actual = strength.assess_strength(pillars, phases)
        assert trial["support_share"] == actual["support_share"]
        assert trial["strength"] == actual["strength_level"]
        old = strength._evaluate(pillars, phases, policy)
        witnessed_different_legacy_arithmetic |= (
            abs(old["support_share"] - trial["support_share"]) > 1e-10
        )
    assert witnessed_different_legacy_arithmetic


def test_repaired_default_keeps_old_twenty_one_case_results_without_promoting_them():
    before = frozen(ARCHIVE / "report-before.json")
    after = diagnostic_script().build_report()
    assert {k: after["summary"][k] for k in before["summary"]} == before["summary"]
    assert after["summary"]["reference_cases"] == 21
    assert after["summary"]["stress_trials"] == 630
    for old, new in zip(before["cases"], after["cases"]):
        comparable = {k: new[k] for k in old}
        if comparable != old:
            previous = deepcopy(old)
            assert previous.pop("decision_rule") == "weighted_balance"
            assert (
                comparable.pop("decision_rule")
                == "complete_same_element_bureau_with_surviving_vigorous_roots"
            )
            assert comparable == previous
            pillars = {k: tuple(v) for k, v in new["pillars"].items()}
            assessment = strength.assess_strength(
                pillars, ElementAnalysis.seasonal_phases(pillars["month"][1])
            )
            assert len(assessment["structural_decision"]["vigorous_roots"]) >= 2
            day_element = ElementAnalysis.analyze_day_master_strength(pillars)[
                "day_element"
            ]
            assert any(
                e.get("kind") in {"三合", "三会"}
                and e.get("target") == day_element
                and e.get("target_revealed")
                and e.get("status") in {"binding", "conditioned_transformation"}
                for e in assessment["relations"]
            )
        assert len(new["stress_trial_details"]) == 30
