"""Complete symbolic support is not a new physical prediction experiment."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from fatebridge.core.divination import derive_meihua_hexagram
from fatebridge.validation import meihua_weather_reachability as support
from fatebridge.validation.meihua_weather_policy_v2 import canonical_sha256

FIXTURE = Path(__file__).parents[1] / "fixtures/meihua_weather_reachability_v1"
ARITHMETIC = json.loads((FIXTURE / "modular288.json").read_bytes())["rows"]
TRACES = json.loads((FIXTURE / "producer-trace-commitments1440.json").read_bytes())


@pytest.fixture(scope="module")
def report():
    return support.audit_time_weather_reachability()


def test_reference_provenance_and_distinct_specification_and_python_commitments():
    manifest = json.loads((FIXTURE / "manifest.json").read_bytes())
    assert manifest["modular_reference_precedes_new_module"]
    assert manifest["producer_probe_precedes_new_module"]
    assert manifest["producer_labels_are_not_independent_truth"]
    for name, expected in manifest["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == expected
    assert (
        canonical_sha256(json.loads((FIXTURE / "policy.json").read_bytes()))
        == support.POLICY_SHA256
    )


@pytest.mark.parametrize("index", range(288))
def test_all_independent_modular_geometries_and_a_second_period(index, report):
    expected = ARITHMETIC[index]
    assert report["arithmetic_cases"][index] == expected
    hour = support.BRANCHES[expected["hour_number"] - 1]
    # 亥12 + month12 + day(S) = S+24; nominal dayS is between3 and26.
    second = derive_meihua_hexagram(
        year_branch="亥",
        lunar_month=12,
        lunar_day=expected["representative_s"],
        hour_branch=hour,
    )
    assert second["seed"]["moving_line"] == expected["moving_line"]
    for key, expected_key in [
        ("base_hexagram", "base_code"),
        ("changed_hexagram", "changed_code"),
        ("mutual_hexagram", "mutual_code"),
    ]:
        assert second[key]["binary_code"] == expected[expected_key]


@pytest.mark.parametrize("hour_number", range(1, 13))
def test_every_symbolic_trace_and_decision_matches_frozen_before_probe(
    hour_number, report
):
    actual = [r for r in report["state_cases"] if r["hour_number"] == hour_number]
    expected = [r for r in TRACES if r["hour_number"] == hour_number]
    assert len(actual) == len(expected) == 120
    for a, e in zip(actual, expected):
        assert (a["s_residue"], a["season"]) == (e["s_residue"], e["season"])
        assert a["weather_trace_sha256"] == e["weather_trace_sha256"]
        assert canonical_sha256(a["decision"]) == e["decision_sha256"]
        assert a["decision"]["label"] == e["label"]
        assert (a["rain_exclusion_certificate"] is None) is (e["label"] == "rain")


def test_noon_theorem_has_complete_context_coverage_without_outcome_or_clock_selection(
    report,
):
    noon = [r for r in report["state_cases"] if r["hour_number"] == 7]
    assert len({(r["s_residue"], r["season"]) for r in noon}) == 120
    assert all(r["decision"]["label"] in {"dry", "abstain"} for r in noon)
    assert all(r["rain_exclusion_certificate"] is not None for r in noon)
    gate = report["locked_noon_preflight"]
    assert gate["status"] == "dominated_by_always_dry"
    assert gate["strict_full_cohort_superiority_possible"] is False
    assert not gate["legacy_primary_gate_passed"]
    assert not gate["forecast_or_cohort_modified"]
    assert report["clock_recommendation"] is None
    assert report["new_real_outcomes"] == 0
    assert not report["raw_observation_files_read"]
    assert report["legacy_result_metadata_attached_by_weather_engine"]
    assert not report["legacy_result_metadata_used_for_labels_or_clock_selection"]
    assert not report["outcome_blind_study"]
    assert not report["original_future_v1_trial_modified"]
    assert [
        r["hour_number"]
        for r in report["all_hours_in_natural_order_no_clock_selection"]
    ] == list(range(1, 13))
    assert "overapproximation" in report["calendar_domain_relation"]


@pytest.mark.parametrize(
    "forecast,observed", [(f, o) for f in ["dry", "abstain"] for o in [True, False]]
)
def test_pointwise_credit_dominance_does_not_depend_on_a_sample(forecast, observed):
    model_credit = int(forecast == "dry" and not observed)
    always_dry_credit = int(not observed)
    assert model_credit <= always_dry_credit


def test_attached_legacy_result_metadata_cannot_change_any_trace_or_label(
    monkeypatch, report
):
    from fatebridge.core import meihua_weather

    monkeypatch.setattr(
        meihua_weather,
        "_research_validation",
        lambda: {"score": 100, "label": "rain", "authority_certified": True},
    )
    changed = support.audit_time_weather_reachability()
    assert changed["state_cases"] == report["state_cases"]
    assert changed["locked_noon_preflight"] == report["locked_noon_preflight"]
    assert changed["legacy_result_metadata_attached_by_weather_engine"]


def test_cli_readiness_gate_writes_the_complete_failure_instead_of_turning_it_green(
    tmp_path,
):
    output = tmp_path / "reachability.json"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/meihua/audit_meihua_weather_reachability.py",
            "--output",
            str(output),
            "--require-potential-superiority",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 2, completed.stderr
    result = json.loads(output.read_bytes())
    assert len(result["state_cases"]) == 1440
    assert result["locked_noon_preflight"]["structural_obstruction"]
    assert not result["real_world_predictive_efficacy_established"]
