"""Frozen sampling omissions, finite budgets and complete interval replay."""

import json
from pathlib import Path

import pytest

from fatebridge.core import human_design_interval_extrema as extrema
from fatebridge.core.human_design_sensitivity import (
    METHOD,
    assess_birth_interval,
)
from tests.human_design_interval_probe_model import model

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "tests/data/human_design"
CASES = ("maximum", "minimum", "wrap_maximum", "grid_zero_maximum")


@pytest.mark.parametrize("case_id", CASES)
def test_synthetic_reader_matches_every_independently_frozen_binary64_scalar(case_id):
    reference = json.loads((EVIDENCE / "interval-rational-reference.json").read_text())
    case = next(c for c in reference["cases"] if c["id"] == case_id)
    at, _, _, _ = model(case_id)
    for point in case["points"]:
        activation = next(
            a
            for a in at(point["birth_jd_tt"])["activations"]["personality"]
            if a["body"] == "Mercury"
        )
        assert activation["longitude"] == point["longitude"]
        assert activation["longitude_speed"] == point["longitude_speed"]


@pytest.mark.parametrize("case_id", CASES)
def test_frozen_coordinate_states_are_retained_without_supplying_the_peak(case_id):
    at, origin, peak, calls = model(case_id)
    result = assess_birth_interval(at(origin), 1, "true", _chart_reader=at)
    samples = result["evaluation_witnesses"]["samples"]
    evaluated = {r["time_scales"]["personality"]["jd_tt"] for r in samples}
    assert set(calls) == evaluated
    # Read the closed-form peak only after sampling; never seed the search.
    target = next(
        a for a in at(peak)["activations"]["personality"] if a["body"] == "Mercury"
    )
    fields = ("gate", "line", "color", "tone", "base")
    states = {
        tuple(a[k] for k in fields)
        for tt in evaluated
        for a in at(tt)["activations"]["personality"]
        if a["body"] == "Mercury"
    }
    assert tuple(target[k] for k in fields) in states
    assert result["method_id"] == METHOD
    assert result["sampling"]["continuous_interval_certified"] is False
    probes = result["station_coordinate_extremum_assessment"]
    assert probes["parameter_axis"] == "birth_jd_tt"
    assert probes["probe_count"] == 1
    assert not probes["budget_exhausted"]
    probe = probes["probes"][0]
    assert {r[0] for r in probe["observations"]} <= evaluated
    assert not probe["continuous_extremum_certified"]
    assert not probe["physical_station_certified"]
    assert result["summary"]["coordinate_extremum_probes"] == 1


@pytest.mark.parametrize("budget", [0, 1, 2])
def test_budget_exhaustion_retains_every_partial_full_chart(monkeypatch, budget):
    monkeypatch.setattr(extrema, "MAX_ADDITIONAL_EVALUATIONS", budget)
    at, origin, _, calls = model("grid_zero_maximum")
    result = assess_birth_interval(at(origin), 1, "true", _chart_reader=at)
    probes = result["station_coordinate_extremum_assessment"]
    assert probes["budget_exhausted"]
    assert probes["additional_evaluations"] == budget
    assert probes["probes"][0]["status"] == "evaluation_budget_exhausted"
    samples = result["evaluation_witnesses"]["samples"]
    assert set(calls) == {r["time_scales"]["personality"]["jd_tt"] for r in samples}
    assert len(samples) == 13 + budget
    assert result["summary"]["coordinate_probe_budget_exhausted"]


@pytest.mark.parametrize(
    "speeds,kind,component",
    [
        ([1, 0, 0, -1], "maximum", [1.0, 2.0]),
        ([-1, 0, 0, 1], "minimum", [1.0, 2.0]),
        ([0, -1, -1, -1], "maximum", [0.0, 0.0]),
        ([1, 1, 1, 0], "maximum", [3.0, 3.0]),
        ([1, 0, 0, 1], "undirected", [1.0, 2.0]),
        ([0, 0, 0, 0], "undirected", [0.0, 3.0]),
    ],
)
def test_grid_zero_groups_and_search_boundary_do_not_invent_sign_changes(
    speeds, kind, component
):
    rows = extrema.zero_speed_components(
        [0.0, 1.0, 2.0, 3.0],
        "personality",
        "Mercury",
        lambda tt, side, body: {"longitude_speed": speeds[int(tt)]},
    )
    assert len(rows) == 1
    assert rows[0]["kind"] == kind
    assert rows[0]["observed_zero_component_jd_tt"] == component
    assert rows[0]["source"] == "sampled_zero_component"
