"""Actual missed interior variation and continuous-TT interval checks."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.core.astro.geometry import _julian_day
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.human_design import chart_at, chart_at_tt, longitude_activation
from fatebridge.core.human_design_sensitivity import assess_birth_interval
from tests.support.ephemeris_context import moshier_ephemeris

CASE = Path(__file__).parents[1] / "fixtures/human-design-uncertainty-case.json"


@pytest.mark.parametrize(
    "date",
    [
        "1916-05-21T22:18:53+00:00",
        "1965-04-06T01:33:00+00:00",
        "2000-01-01T12:00:00+00:00",
        "2017-01-01T00:00:09+00:00",
    ],
)
def test_tt_sampling_and_civil_nominal_use_identical_physical_activation(date):
    moment = datetime.fromisoformat(date)
    with moshier_ephemeris():
        direct = chart_at(moment)
        sampled = chart_at_tt(ephemeris_time(moment).jd_tt)
    assert direct["activations"] == sampled["activations"]
    assert direct["bodygraph"] == sampled["bodygraph"]
    assert direct["profile"] == sampled["profile"]


def test_actual_interior_node_base_variant_is_not_visible_in_old_three_samples():
    case = json.loads(CASE.read_text())
    with moshier_ephemeris():
        nominal = chart_at(datetime.fromisoformat(case["nominal_birth_utc"]))
        report = assess_birth_interval(nominal, 60, "true")
    assert report["sampling"]["grid_sample_count"] == 721
    assert report["sampling"]["continuous_interval_certified"] is False
    assert all(
        not any(
            a["side"] == "personality" and a["body"] == "NorthNode"
            for a in end["changed_activations"]
        )
        for end in report["comparisons"]
    )
    node = next(
        a
        for a in report["activation_variants"]
        if a["side"] == "personality" and a["body"] == "NorthNode"
    )
    assert node["observed_values"]["base"] == [1, 2]
    assert node["nominal"]["base"] == 2
    assert report["sampling"]["additional_evaluation_count"] > 0
    assert any(
        s["side"] == "personality" and s["body"] == "NorthNode"
        for s in report["station_candidates"]
    )
    for witness in node["first_observed_witness_per_state"]:
        expected = longitude_activation(witness["longitude"])
        assert all(
            expected[k] == witness[k] for k in ("gate", "line", "color", "tone", "base")
        )


def test_mean_node_interval_does_not_invent_true_node_speed_reversal():
    case = json.loads(CASE.read_text())
    with moshier_ephemeris():
        nominal = chart_at(datetime.fromisoformat(case["nominal_birth_utc"]), "mean")
        report = assess_birth_interval(nominal, 60, "mean")
    assert report["node_mode"] == "mean"
    assert not any(s["body"] == "NorthNode" for s in report["station_candidates"])


def test_tt_grid_includes_a_birth_during_an_actual_inserted_utc_second():
    # The half-second nominal time makes one ten-second grid point fall safely
    # within second 60 rather than at a floating-point endpoint.
    nominal = chart_at(datetime(2017, 1, 1, 0, 0, 9, 500000, tzinfo=timezone.utc))
    report = assess_birth_interval(nominal, 1, "true")
    special = [
        s
        for s in report["sampled_nonstandard_civil_labels"]
        if s["side"] == "personality"
    ]
    assert special and special[0]["activation_utc"].startswith("2016-12-31T23:59:60.")
    interval = report["interval"]
    assert (
        interval["end"]["birth_jd_tt"] - interval["start"]["birth_jd_tt"]
    ) * 86400 == pytest.approx(120, abs=0.0001)
    assert report["sampling"]["grid_sample_count"] == 13


def test_tt_grid_keeps_a_historical_fractional_adjustment_without_fake_label():
    nominal = chart_at(datetime(1964, 4, 1, 0, 0, 9, 950000, tzinfo=timezone.utc))
    report = assess_birth_interval(nominal, 1, "true")
    special = [
        s
        for s in report["sampled_nonstandard_civil_labels"]
        if s["side"] == "personality"
    ]
    assert special and special[0]["activation_utc"] is None
    assert (
        special[0]["label_status"]
        == "unrepresentable_historical_fractional_UTC_adjustment"
    )


def test_chart_at_tt_preserves_exact_birth_epoch_in_a_leap_second():
    tt = (
        _julian_day(datetime(2017, 1, 1, tzinfo=timezone.utc))
        + (36 + 32.184 + 0.5) / 86400
    )
    chart = chart_at_tt(tt)
    assert chart["birth_utc"].startswith("2016-12-31T23:59:60.")
    assert chart["time_scales"]["personality"]["jd_tt"] == tt
    assert abs(chart["design_solver"]["residual_degrees"]) < 1e-7


def test_sample_interval_extent_and_variants_use_only_evaluated_tt_witnesses():
    nominal = chart_at(datetime(2024, 3, 20, 6, 30, tzinfo=timezone.utc))
    report = assess_birth_interval(nominal, 2, "true")
    lo = report["interval"]["start"]["birth_jd_tt"]
    hi = report["interval"]["end"]["birth_jd_tt"]
    assert report["sampling"]["target_grid_step_seconds"] == 10
    assert report["sampling"]["maximum_grid_step_seconds"] == pytest.approx(
        10, abs=0.0001
    )
    assert report["sampling"]["grid_sample_count"] == 25
    assert lo < nominal["time_scales"]["personality"]["jd_tt"] < hi
    for variant in report["classification_variants"]:
        assert lo <= variant["first_observed_witness"]["birth_jd_tt"] <= hi
    for activation in report["activation_variants"]:
        for witness in activation["first_observed_witness_per_state"]:
            assert lo <= witness["birth_jd_tt"] <= hi
    assert report["activations_checked_per_sample"] == 26


@pytest.mark.parametrize("bad", [-1, 0, 61, 1.5, True])
def test_invalid_interval_cannot_silently_reduce_the_requested_scope(bad):
    nominal = chart_at(datetime(2000, 1, 1, tzinfo=timezone.utc))
    with pytest.raises(ValueError, match="1至60"):
        assess_birth_interval(nominal, bad, "true")


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_nonfinite_physical_epoch_is_rejected(bad):
    with pytest.raises(ValueError, match="有限"):
        chart_at_tt(bad)


def test_audit_rejects_a_degraded_three_point_checker(monkeypatch):
    from scripts.human_design import audit_human_design as audit

    def degraded(*args, **kwargs):
        return {
            "comparisons": [{"changed_activations": []}, {"changed_activations": []}],
            "activation_variants": [],
            "sampling": {
                "grid_sample_count": 3,
                "continuous_interval_certified": False,
            },
        }

    monkeypatch.setattr(audit, "assess_birth_interval", degraded)
    assert audit.interval_regression_check()["status"] == "failed"


def test_interval_audit_restores_the_ephemeris_operator_configuration():
    import os

    from fatebridge.core import ephemeris_runtime
    from scripts.human_design import audit_human_design as audit

    before = (
        ephemeris_runtime.configured_ephemeris_path(),
        os.environ.get("SE_EPHE_PATH"),
    )
    assert audit.interval_regression_check()["status"] == "observed_regression_passed"
    assert before == (
        ephemeris_runtime.configured_ephemeris_path(),
        os.environ.get("SE_EPHE_PATH"),
    )
