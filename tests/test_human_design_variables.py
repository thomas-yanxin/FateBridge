"""Independent visible official facts, inconsistent pairs and joint variants."""

import copy
import json
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.human_design import chart_at, chart_at_tt
from fatebridge.core.human_design_precision import compare_node_backends
from fatebridge.core.human_design_sensitivity import assess_birth_interval
from fatebridge.core.human_design_variables import variables_from_activations
from fatebridge.services.human_design import calculate_human_design
from fatebridge.validation.human_design_official import official_chart_checks

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/human-design-official-charts.json").read_text()
)


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: c["id"])
def test_official_variable_code_and_each_paired_field_quote(case):
    result = calculate_human_design(**case["birth_input"])
    variables = result["variables"]
    assert variables["status"] == "computed"
    if variables["code"] != case["properties"]["Variable"]:
        assert any("moshier" in a["ephemeris_models"] for a in variables["arrows"])
        check = official_chart_checks({**REFERENCE, "cases": [case]})
        assert check["status"] == "failed"
        assert check["cases"][0]["structure_checks"]["variables"] is False
    assert len(variables["arrows"]) == 4
    assert variables["subdivision_accuracy_certified"] is False
    for arrow in variables["arrows"]:
        assert arrow["pair_tones_consistent"]
        assert len(arrow["basis"]) == 2
        quoted_bodies = []
        for quote in arrow["basis"]:
            root, side, index, key = quote["path"].split(".")
            assert root == "activations" and side == arrow["side"] and key == "tone"
            actual = result[root][side][int(index)]
            quoted_bodies.append(actual["body"])
            assert type(quote["value"]) is int and quote["value"] == actual["tone"]
        assert quoted_bodies == arrow["body_pair"]


def test_complete_official_cohort_includes_utc_graph_and_all_208_gate_lines():
    result = official_chart_checks(REFERENCE)
    assert result["charts_checked"] == 8
    assert result["gate_lines_checked"] == result["gate_lines_matched"] == 208
    assert all(
        all(
            v
            for k, v in c["structure_checks"].items()
            if k not in {"variables", "cross_name"}
        )
        for c in result["cases"]
    )
    mismatches = [c for c in result["cases"] if not c["structure_checks"]["variables"]]
    assert all("moshier" in c["observed_ephemeris_models"] for c in mismatches)
    # The newly audited literal names preserve TENSION (4) from the 2001 text.
    # The current calculator omits that number; never silently alias a pass.
    assert result["cross_names_exactly_matched"] == 0
    assert result["charts_with_all_mechanics_matched"] == 8 - len(mismatches)
    assert result["status"] == "failed"
    assert result["charts_matched"] == 0
    assert result["global_node_convention_certified"] is False


@pytest.mark.parametrize(
    "part",
    [
        "body_order",
        "missing_side",
        "duplicate_case",
        "wrong_gate",
        "wrong_utc",
        "wrong_variable",
    ],
)
def test_incomplete_or_wrong_official_reference_does_not_gain_acceptance(part):
    ref = copy.deepcopy(REFERENCE)
    if part == "body_order":
        ref["planet_order"][1] = "Sun"
    elif part == "missing_side":
        ref["cases"][0]["columns"].pop("design")
    elif part == "duplicate_case":
        ref["cases"][1]["id"] = ref["cases"][0]["id"]
    elif part == "wrong_gate":
        ref["cases"][0]["columns"]["design"][0] = "1.1"
    elif part == "wrong_utc":
        ref["cases"][0]["displayed_birth_utc"] = "1900-01-01T13:00:00+00:00"
    else:
        ref["cases"][0]["properties"]["Variable"] = "PRR DRR"
    if part in {"body_order", "missing_side", "duplicate_case"}:
        with pytest.raises(ValueError):
            official_chart_checks(ref)
    else:
        check = official_chart_checks(ref)
        assert check["status"] == "failed"
        assert check["cases"][0]["status"] == "failed"
        if part == "wrong_variable":
            assert check["cases"][0]["structure_checks"]["variables"] is False
        if part == "wrong_utc":
            assert check["cases"][0]["structure_checks"]["birth_utc"] is False
        if part == "wrong_gate":
            assert check["cases"][0]["gate_line_mismatches"]


@pytest.mark.parametrize("bad_tone", [None, True, 0, 7, "3"])
def test_invalid_paired_tone_never_acquires_an_arrow_code(bad_tone):
    chart = chart_at(datetime.fromisoformat("2000-01-01T12:00:00+00:00"))
    earth = next(a for a in chart["activations"]["personality"] if a["body"] == "Earth")
    earth["tone"] = bad_tone
    result = variables_from_activations(chart["activations"])
    assert result["status"] == "incomplete_or_inconsistent"
    assert result["code"] is None


def test_opposite_pair_cannot_be_spliced_even_if_both_tones_point_left():
    chart = chart_at(datetime.fromisoformat("2000-01-01T12:00:00+00:00"))
    for a in chart["activations"]["design"]:
        if a["body"] == "Sun":
            a["tone"] = 1
        if a["body"] == "Earth":
            a["tone"] = 2
    result = variables_from_activations(chart["activations"])
    assert result["code"] is None
    assert result["arrows"][0]["status"] == "inconsistent_pair"


def test_node_backend_diagnostic_rebuilds_variable_and_returns_both_actual_structures(
    monkeypatch,
):
    from tests.golden.runner import golden_ephemeris

    with golden_ephemeris():
        chart = chart_at(datetime.fromisoformat("2000-01-01T12:00:00+00:00"))
    # Simulated 4 arcsecond node shift; not an independent celestial reference.
    assert chart["variables"]["code"] == "PRL DLL"
    by_side = {
        s: next(a for a in acts if a["body"] == "NorthNode")
        for s, acts in chart["activations"].items()
    }

    def reference(operation, jd, body, flags):
        side = (
            "personality"
            if jd == chart["time_scales"]["personality"]["jd_tt"]
            else "design"
        )
        node = by_side[side]
        lon = node["longitude"] + (4.2 / 3600 if side == "personality" else 0)
        return (lon, 0, 0, node["longitude_speed"], 0, 0), flags

    monkeypatch.setattr(runtime, "ephemeris_call", reference)
    result = compare_node_backends(chart, "true")
    assert result["mechanical_comparison"]["variable_changed"] is True
    assert result["selected_structure"]["variable_code"] == "PRL DLL"
    assert result["reference_structure"]["variable_code"] == "PRR DLL"
    assert result["reference_structure"]["authority"] == chart["bodygraph"]["authority"]


def test_birth_interval_returns_joint_variable_witnesses():
    chart = chart_at(datetime.fromisoformat("2000-01-01T12:00:00+00:00"))
    result = assess_birth_interval(chart, 60, "true")
    assert result["sampling"]["continuous_interval_certified"] is False
    codes = {
        row["value"]["variables"]["code"] for row in result["classification_variants"]
    }
    assert len(codes) >= 2
    for row in result["classification_variants"]:
        witness = row["first_observed_witness"]
        replay = chart_at_tt(witness["birth_jd_tt"])
        assert row["value"]["variables"]["code"] == replay["variables"]["code"]
