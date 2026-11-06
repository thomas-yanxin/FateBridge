"""Faithfulness regressions for actual uncertainty and conditional strengths."""

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish import build_india
from fatebridge.services.astrology import calculate_core_chart_analysis

CUSP = dict(
    birth_year=1990,
    birth_month=4,
    birth_day=6,
    birth_hour=15,
    birth_minute=10,
    birth_timezone="UTC",
    birth_latitude=0,
    birth_longitude=0,
)


def test_real_moon_star_and_pada_variants_survive_with_only_d1_exported():
    result = build_india(
        build_astro_birth_info(**CUSP), divisions=[], birth_time_uncertainty_minutes=2
    )
    options = result["birth_time_sensitivity"]["nakshatra_alternatives"]["Moon"]
    assert {(r["name"], r["lord"], r["pada"]) for r in options} == {
        ("Magha", "Ketu", 4),
        ("Purva Phalguni", "Venus", 1),
    }
    assert (
        sum(r["sample_count"] for r in options)
        == result["birth_time_sensitivity"]["sample_count"]
    )


def test_native_reading_does_not_present_nominal_moon_star_as_unique_for_the_interval():
    result = calculate_core_chart_analysis(
        **CUSP,
        chart_variant="india_chart",
        divisions=[],
        birth_time_uncertainty_minutes=2,
    )
    assert "名义" in result["summary"]
    emotional = result["interpretation"]["vedic"]["emotional_style"]
    assert "Magha" in emotional and "Purva Phalguni" in emotional
    assert "第4足" in emotional and "第1足" in emotional


import copy

import pytest

from fatebridge.core.jyotish_evidence import strength_context, strength_text
from fatebridge.services.jyotish import calculate_vimshottari


@pytest.mark.parametrize(
    "values,summary,status,word",
    [
        ((10.0, 10.0), 10.0, "computed_consensus", "一致"),
        ((10.0, 20.0), None, "conditional_results", "不能当作零或缺项"),
        ((None, None), None, "unavailable", "不能补成零"),
        ((10.0, None), None, "partially_computed", "1/2"),
    ],
)
def test_strength_prose_distinguishes_consensus_conditions_missing_and_partial(
    values, summary, status, word
):
    component = {
        "summary": {"Mercury": summary},
        "scenarios": {k: {"Mercury": v} for k, v in zip(["a", "b"], values)},
    }
    context = strength_context("kala_bala", "Mercury", component)
    assert context["value_status"] == status
    assert word in strength_text(context)
    assert context["computed_scenario_count"] == sum(v is not None for v in values)
    assert (
        context["scenarios"][0]["fact_path"]
        == "india.strengths.kala_bala.scenarios.a.Mercury"
    )


def test_global_component_gap_does_not_misclassify_a_computed_ruler():
    component = {
        "status": "partial_components",
        "summary": {"Sun": 10.0, "Mercury": None},
        "scenarios": {
            "a": {"Sun": 10.0, "Mercury": None},
            "b": {"Sun": 10.0, "Mercury": None},
        },
        "components": {"hora_bala": {"summary": {"Sun": 10.0, "Mercury": None}}},
    }
    sun = strength_context("kala_bala", "Sun", component)
    mercury = strength_context("kala_bala", "Mercury", component)
    assert sun["value_status"] == "computed_consensus" and sun["missing_evidence"] == []
    assert mercury["value_status"] == "unavailable"
    assert mercury["missing_evidence"][0]["missing_value_paths"] == [
        "india.strengths.kala_bala.components.hora_bala.summary.Mercury"
    ]


def test_explanation_refuses_a_summary_that_contradicts_its_own_branches():
    for summary in [0, 10.0, 30.0]:
        component = {
            "summary": {"Sun": summary},
            "scenarios": {"a": {"Sun": 10.0}, "b": {"Sun": 20.0}},
        }
        with pytest.raises(ValueError, match="contradicts"):
            strength_context("drik_bala", "Sun", component)


@pytest.mark.parametrize(
    "uncertainty,mode,expected_status",
    [
        (None, "nominal_only", "not_assessed"),
        (0, "sampled_grid", "no_change_on_sample_grid"),
    ],
)
def test_omitted_range_does_not_turn_into_measured_stability(
    uncertainty, mode, expected_status
):
    result = build_india(
        build_astro_birth_info(**CUSP),
        divisions=[],
        birth_time_uncertainty_minutes=uncertainty,
    )
    basis = result["reading_basis"]
    assert basis["options_basis"] == mode
    assert basis["uncertainty_status"] == expected_status
    assert basis["reference"] == "nominal_birth_instant"
    if uncertainty == 0:
        assert result["birth_time_sensitivity"]["sample_count"] == 1


def test_vimshottari_does_not_silently_omit_candidate_births_later_than_target():
    result = calculate_vimshottari(
        **CUSP,
        divisions=[],
        birth_time_uncertainty_minutes=2,
        analysis_year=1990,
        analysis_month=4,
        analysis_day=6,
        analysis_hour=15,
        analysis_minute=10,
    )
    context = result["vimshottari"]["birth_time_sensitivity"]
    assert context["status"] == "partial_samples_before_analysis"
    assert (
        context["requested_sample_count"] == 9
        and context["evaluated_sample_count"] == 5
    )
    assert context["omitted_samples"] == [
        {"offset_seconds": offset, "reason": "analysis_precedes_candidate_birth"}
        for offset in [30.0, 60.0, 90.0, 120.0]
    ]
    assert len(context["reading_basis"]["moon_nakshatra_options"]) == 2
    assert "名义生时" in result["summary"]


def test_all_embedded_branch_claims_verify_against_the_same_original_run():
    from fatebridge.application.execution import execute_tool
    from fatebridge.core.execution_context import ExecutionOptions
    from fatebridge.services.tool_catalog import CATALOG
    from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims

    spec = next(s for s in CATALOG if s.key == "astro_india")
    body = execute_tool(
        spec,
        spec.request_model.model_validate(
            {**CUSP, "birth_time_uncertainty_minutes": 2}
        ),
        options=ExecutionOptions(
            as_of="2026-10-22T12:00:00+08:00",
        ),
    )
    metadata = body["run_metadata"]
    claims = []
    for topic in body["india"]["topic_evidence"].values():
        for factor in topic["factors"]:
            context = factor.get("calculation_context")
            if not context:
                continue
            for row in [*context["scenarios"], *context["constraints"]]:
                claims.append(
                    CalculationClaim(
                        path=row["fact_path"],
                        value=row["value"],
                        run_id=metadata["run_id"],
                    )
                )
    assert claims
    assert (
        verify_calculation_claims(body, claims)["status"] == "verified_structured_facts"
    )
    tampered = copy.deepcopy(claims)
    tampered[0].value = 999.0
    assert verify_calculation_claims(body, tampered)["status"] == "rejected"


def test_unselected_model_is_unavailable_without_claiming_birth_data_is_missing():
    component = {
        "summary": {"Mars": None},
        "scenarios": {"a": {"Mars": None}},
        "model_context": {
            "selected": "unadjudicated",
            "status": "mean_model_unadjudicated",
        },
    }
    context = strength_context("cheshta_bala", "Mars", component)
    assert context["value_status"] == "unavailable"
    assert context["constraints"] == [
        {
            "fact_path": "india.strengths.cheshta_bala.model_context.selected",
            "value": "unadjudicated",
        },
        {
            "fact_path": "india.strengths.cheshta_bala.model_context.status",
            "value": "mean_model_unadjudicated",
        },
    ]
    assert "不一概当成用户资料不足" in strength_text(context)


@pytest.mark.native_engine_fault
def test_star_change_alone_marks_sensitivity_even_if_discrete_strengths_are_fixed(
    monkeypatch,
):
    from fatebridge.core import jyotish

    birth = build_astro_birth_info(**CUSP)
    fixed = build_india(birth, divisions=[])["strengths"]["sthana_bala"]
    monkeypatch.setattr(
        jyotish,
        "calculate_sthana",
        lambda raw, profile, drekkana_profile: copy.deepcopy(fixed),
    )
    result = build_india(birth, divisions=[], birth_time_uncertainty_minutes=2)
    sensitivity = result["birth_time_sensitivity"]
    assert not any(sensitivity["alternatives"].values())
    assert not sensitivity["physical_condition_alternatives"]
    assert not sensitivity["sthana_discrete_component_alternatives"]
    assert not sensitivity["time_lord_alternatives"]
    assert len(sensitivity["yuddha_states_on_grid"]) == 1
    assert len(sensitivity["drik_moon_nature_options_on_grid"]) == 1
    assert len(sensitivity["cheshta_model_statuses_on_grid"]) == 1
    assert sensitivity["status"] == "changes_detected"
    assert len(sensitivity["nakshatra_alternatives"]["Moon"]) == 2
