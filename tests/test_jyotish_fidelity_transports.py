"""Actual REST/MCP/CLI preservation of nominal and conditional evidence."""

import pytest

from tests.test_jyotish_fidelity import CUSP
from tests.test_jyotish_transports import call_surfaces


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari"])
def test_uncertainty_and_star_candidates_survive_three_surfaces(
    monkeypatch, capsys, key
):
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        {**CUSP, "divisions": [], "birth_time_uncertainty_minutes": 2},
        [
            "summary",
            "india.reading_basis",
            "india.birth_time_sensitivity",
            "india.topic_evidence",
        ],
    )
    assert "名义生时" in result["summary"]
    basis = result["india"]["reading_basis"]
    assert basis["reference"] == "nominal_birth_instant"
    assert basis["options_basis"] == "sampled_grid"
    assert {x["name"] for x in basis["moon_nakshatra_options"]} == {
        "Magha",
        "Purva Phalguni",
    }
    sensitivity = result["india"]["birth_time_sensitivity"]
    assert len(sensitivity["nakshatra_sampled_points"]) == 10
    assert (
        sum(x["sample_count"] for x in sensitivity["nakshatra_alternatives"]["Moon"])
        == sensitivity["sample_count"]
    )
    for topic in result["india"]["topic_evidence"].values():
        for factor in topic["factors"]:
            context = factor.get("calculation_context")
            if not context:
                continue
            assert context["computed_scenario_count"] <= context["scenario_count"]
            if context["value_status"] == "conditional_results":
                assert factor["fact"] is None
                assert "不能当作零或缺项" in factor["traditional_interpretation"]


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari"])
def test_nested_reading_basis_projection_keeps_both_padas(monkeypatch, capsys, key):
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        {**CUSP, "birth_time_uncertainty_minutes": 2},
        [
            "india.reading_basis.moon_nakshatra_options",
        ],
    )
    assert {
        x["pada"] for x in result["india"]["reading_basis"]["moon_nakshatra_options"]
    } == {1, 4}


def test_published_native_prose_preserves_candidates_and_unassessed_state(
    monkeypatch, capsys
):
    for uncertainty in [None, 2]:
        payload = {**CUSP}
        if uncertainty is not None:
            payload["birth_time_uncertainty_minutes"] = uncertainty
        result = call_surfaces(
            monkeypatch,
            capsys,
            "astro_india",
            payload,
            [
                "interpretation.vedic",
                "india.reading_basis",
            ],
        )
        text = result["interpretation"]["vedic"]
        assert "名义生时" in text["core_identity"]
        if uncertainty is None:
            assert "未提供" in text["uncertainty_note"]
            assert result["india"]["reading_basis"]["options_basis"] == "nominal_only"
        else:
            assert all(
                name in text["emotional_style"] for name in ["Magha", "Purva Phalguni"]
            )


def test_near_birth_partial_period_sampling_is_visible_across_surfaces(
    monkeypatch, capsys
):
    payload = {
        **CUSP,
        "birth_time_uncertainty_minutes": 2,
        "analysis_year": 1990,
        "analysis_month": 4,
        "analysis_day": 6,
        "analysis_hour": 15,
        "analysis_minute": 10,
    }
    result = call_surfaces(
        monkeypatch,
        capsys,
        "astro_vimshottari",
        payload,
        [
            "vimshottari.birth_time_sensitivity",
            "summary",
        ],
    )
    context = result["vimshottari"]["birth_time_sensitivity"]
    assert (
        context["requested_sample_count"] == 9
        and context["evaluated_sample_count"] == 5
    )
    assert (
        context["omitted_samples"][0]["reason"] == "analysis_precedes_candidate_birth"
    )
    assert context["status"] == "partial_samples_before_analysis"
    assert len(context["omitted_samples"]) == 4
    assert context["endpoint_subset_requested_count"] == 3
    assert context["endpoint_subset_evaluated_count"] == 2


def test_intermediate_stage_and_matched_contexts_survive_three_surfaces(
    monkeypatch, capsys
):
    from tests.test_jyotish_dasha_grid import BIRTH, TARGET

    result = call_surfaces(
        monkeypatch,
        capsys,
        "astro_vimshottari",
        {**BIRTH, **TARGET, "divisions": [30], "birth_time_uncertainty_minutes": 120},
        [
            "vimshottari.birth_time_sensitivity.stage_variants",
            "vimshottari.birth_time_sensitivity.requested_sample_count",
            "vimshottari.birth_time_sensitivity.adjacent_stage_change_brackets",
        ],
    )
    sensitivity = result["vimshottari"]["birth_time_sensitivity"]
    variant = next(
        v
        for v in sensitivity["stage_variants"]
        if (v["major_lord"], v["sub_lord"]) == ("Rahu", "Mars")
    )
    assert sensitivity["requested_sample_count"] == 481
    assert len(sensitivity["adjacent_stage_change_brackets"]) == 2
    assert variant["natal_ruler_contexts"]
    for context in variant["natal_ruler_contexts"]:
        assert context["sample_segments"]
        if context["chart"] == "D30":
            assert "longitude" not in context["sampled_numeric_ranges"]
