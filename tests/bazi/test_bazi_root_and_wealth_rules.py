"""Local source principles are distinct from fitted labels or life outcomes."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.analysis.personality as personality_module
from fatebridge.analysis.personality import PersonalityAnalysis
from fatebridge.analysis.wealth import WealthAnalysis
from fatebridge.core.bazi_root_context import wealth_rule_context
from fatebridge.core.classical_roots import build_classical_root_profile
from fatebridge.utils.data import TenGod
from fatebridge.validation.predictions import StudyPlan, evaluate_study
from tests.evaluation.test_prediction_validation import AS_OF, forecast, outcome, plan


def pillars(values):
    return dict(zip(("year", "month", "day", "hour"), map(tuple, values)))


@pytest.mark.parametrize(
    "stem,branch,category",
    [
        ("甲", "亥", "yang_growth_root"),
        ("甲", "寅", "lu_root"),
        ("甲", "卯", "yang_blade_root"),
        ("甲", "未", "storage_root"),
        ("丙", "戌", "storage_root"),
        ("乙", "辰", "residual_root"),
        ("丁", "未", "residual_root"),
        ("乙", "午", "yin_growth_reference"),
        ("丁", "酉", "yin_growth_reference"),
    ],
)
def test_root_categories_follow_pdf22_23_without_creating_stems_or_coefficients(
    stem, branch, category
):
    # Local stem/branch probes from the chapter, not historical birth charts.
    chart = {name: (stem, branch) for name in ("year", "month", "day", "hour")}
    result = build_classical_root_profile(chart)
    assert {o["kind"] for o in result["roots"]} == {category}
    assert result["global_strength_status"] == "not_adjudicated"
    if category == "yin_growth_reference":
        assert (
            not result["heavy_root_positions"]
            and not result["light_hidden_root_positions"]
        )
        assert all(not o["matching_hidden_stems"] for o in result["roots"])


def test_original_food_wealth_case_exposes_financial_root_without_fitting_body_strength():
    chart = pillars(["丁未", "癸卯", "癸亥", "癸丑"])
    result = wealth_rule_context(chart)
    assert result["path"] == "food_generates_wealth_prerequisites"
    assert result["visible_wealth"][0]["stem"] == "丁"
    assert any(
        r["pillar"] == "year" and r["stem"] == "丁"
        for r in result["visible_wealth"][0]["hidden_roots"]
    )
    assert result["checks"]["body_food_wealth_relative_force"] == "unknown"
    assert result["formation_status"] == "not_adjudicated"
    # The source strength label stays unchanged; our root facts do not invent it.
    source = json.loads(
        (Path(__file__).parents[1] / "data/bazi_classical_v1/cases.json").read_text()
    )
    assert (
        next(c for c in source if c["id"] == "ZP37-LIANG")["adjudication"]["strength"]
        == "强"
    )


def test_storage_appearance_without_natal_clash_cannot_be_reported_as_opening():
    chart = pillars(["甲寅", "甲子", "丙子", "甲子"])
    result = WealthAnalysis.analyze_wealth(chart, dayun_pillar=("壬", "丑"))
    assert result["wealth_storage"]["has_storage"] is False
    assert result["wealth_timing"]["storage_events"] == []
    assert result["wealth_structure"]["score_kind"] == "uncalibrated_rule_index"
    assert not any("主进大财" in s for s in result["wealth_timing"]["timing_signals"])


def test_hidden_wealth_root_clash_is_not_lost_when_branch_primary_qi_is_earth():
    chart = pillars(["辛丑", "丁巳", "丙子", "乙未"])
    result = WealthAnalysis.analyze_wealth(chart, liunian_pillar=("辛", "未"))
    relation = next(
        r
        for r in result["wealth_risk"]["relations"]
        if r["wealth_pillar"] == "year" and r["other_pillar"] == "hour"
    )
    assert relation["wealth_hidden_stems"] == ["辛"]
    storage = result["wealth_storage"]["storage_hits"][0]
    assert storage["clash_present"] and storage["opened"] is None
    assert any(
        e["natal_pillar"] == "year" and e["storage_branch"] == "丑"
        for e in result["wealth_timing"]["storage_events"]
    )
    assert not any("财务相对安稳" in r for r in result["wealth_risk"]["risks"])


def test_zero_wealth_count_cannot_claim_it_is_hidden():
    result = WealthAnalysis._locate_wealth_stars(
        pillars(["庚申", "辛酉", "辛丑", "己酉"]), "辛"
    )
    assert result["total_weight"] == 0 and result["positions"] == []
    assert "藏而不露" not in result["visibility"]


def test_personality_ties_are_all_retained_without_arbitrary_primary(monkeypatch):
    monkeypatch.setattr(
        personality_module, "count_ten_gods", lambda *a: {god: 1.0 for god in TenGod}
    )
    result = PersonalityAnalysis._dominant_traits(
        pillars(["甲子", "丙寅", "戊辰", "壬戌"]), "戊"
    )
    assert len(result["top_gods"]) == 10
    assert set(result["tied_primary_gods"]) == {god.value for god in TenGod}
    assert result["primary"].startswith("并列：")


@pytest.mark.parametrize(
    "missing",
    [
        "interpretation_policy_sha256",
        "baseline_frozen_at",
        "training_subject_ids",
        "registration_reference",
    ],
)
def test_perfect_metrics_cannot_pass_incomplete_registered_protocol(missing):
    payload = plan(100).model_dump()
    payload.pop(missing)
    study = StudyPlan.model_validate(payload)
    forecasts = [forecast(i, float(i % 2)) for i in range(100)]
    if missing == "interpretation_policy_sha256":
        forecasts = [
            f.model_copy(update={"interpretation_policy_sha256": None})
            for f in forecasts
        ]
    result = evaluate_study(
        study, forecasts, [outcome(i, bool(i % 2)) for i in range(100)], as_of=AS_OF
    )
    assert result["metrics"]["accuracy"] == 1 and result["registered_numeric_gate_met"]
    assert not result["preregistered_performance_gate_met"]
    assert (
        result["statistical_evidence"]["lower_bound_excess_over_registered_threshold"]
        > 0
    )
    assert not result["statistical_evidence_gate_met"]
    assert result["protocol_status"] == "incomplete" and result["protocol_blockers"]


def test_unregistered_interpretation_change_is_rejected_even_with_same_calculation_model():
    changed = forecast(0, 0.5).model_copy(
        update={"interpretation_policy_sha256": "e" * 64}
    )
    with pytest.raises(ValueError, match="解释政策"):
        evaluate_study(plan(), [changed], [], as_of=AS_OF)
    data = plan().model_dump()
    data["baseline_frozen_at"] = "2026-10-23T00:00:00Z"
    with pytest.raises(ValidationError, match="基线必须"):
        StudyPlan.model_validate(data)
