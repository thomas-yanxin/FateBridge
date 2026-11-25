"""Local source principles are distinct from fitted labels or life outcomes."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.bazi.bazi_evidence import (
    build_natal_evidence,
    build_topic_evidence,
)
from fatebridge.core.bazi.bazi_root_context import hidden_roots, wealth_rule_context
from fatebridge.core.classical_roots import build_classical_root_profile
from tests.unit_test.fixtures.prediction_study import AS_OF, forecast, outcome, plan
from validation.predictions import StudyPlan, evaluate_study


def pillars(values):
    return dict(zip(("year", "month", "day", "hour"), map(tuple, values)))


def test_shared_hidden_root_positions_match_the_external_column_matrix() -> None:
    reference = json.loads(
        (
            Path(__file__).parents[1] / "data/bazi_pillar_facts_v1/reference.json"
        ).read_text()
    )
    positions = ("year", "month", "day", "hour")
    for literal, column in reference["column_matrix"].items():
        chart = dict(reversed([(name, tuple(literal)) for name in positions]))
        assert hidden_roots(literal[0], chart) == [
            {
                "pillar": name,
                "branch": literal[1],
                "stem": row["stem"],
                "hidden_rank": row["hidden_rank"],
                "kind": "same_stem" if row["stem"] == literal[0] else "same_element",
            }
            for name in positions
            for row in column["hidden_relations"]
            if row["relation"] == "same_element"
        ]


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
    stem: str, branch: str, category: str
) -> None:
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
    else:
        pass


def test_original_food_wealth_case_exposes_financial_root_without_fitting_body_strength() -> (
    None
):
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


def test_timing_storage_branch_without_a_natal_storage_branch_is_not_a_natal_hit() -> (
    None
):
    chart = pillars(["甲寅", "甲子", "丙子", "甲子"])
    topic = build_topic_evidence(
        build_natal_evidence(chart), chart, "wealth", None, ("辛", "丑"), None
    )
    assert topic["storage_matches"] == []


def test_hidden_wealth_root_clash_is_not_lost_when_branch_primary_qi_is_earth() -> None:
    chart = pillars(["辛丑", "丁巳", "丙子", "乙未"])
    topic = build_topic_evidence(
        build_natal_evidence(chart), chart, "wealth", None, None, ("辛", "未")
    )
    assert any(
        row["pillar"] == "year"
        and row["stem"] == "辛"
        and row["location"] == "地支藏干"
        for row in topic["stars"]["正财"]
    )
    (storage,) = topic["storage_matches"]
    assert storage["pillar"] == "year" and storage["branch"] == "丑"
    assert [row["positions"] for row in storage["clashes"]] == [["year", "hour"]]
    assert any(
        row["kind"] == "六冲" and row["positions"] == ["liunian", "year"]
        for row in topic["timing"]["layers"][0]["natal_relations"]
    )


def test_absent_wealth_stars_have_no_occurrences() -> None:
    chart = pillars(["庚申", "辛酉", "辛丑", "己酉"])
    topic = build_topic_evidence(
        build_natal_evidence(chart), chart, "wealth", None, None, None
    )
    assert topic["stars"]["正财"] == topic["stars"]["偏财"] == []


@pytest.mark.parametrize(
    "missing",
    [
        "interpretation_policy_sha256",
        "baseline_frozen_at",
        "training_subject_ids",
        "registration_reference",
    ],
)
def test_perfect_metrics_cannot_pass_incomplete_registered_protocol(
    missing: str,
) -> None:
    payload = plan(100).model_dump()
    payload.pop(missing)
    study = StudyPlan.model_validate(payload)
    forecasts = [forecast(i, float(i % 2)) for i in range(100)]
    if missing == "interpretation_policy_sha256":
        forecasts = [
            f.model_copy(update={"interpretation_policy_sha256": None})
            for f in forecasts
        ]
    else:
        pass
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


def test_unregistered_interpretation_change_is_rejected_even_with_same_calculation_model() -> (
    None
):
    changed = forecast(0, 0.5).model_copy(
        update={"interpretation_policy_sha256": "e" * 64}
    )
    with pytest.raises(ValueError, match="解释政策"):
        evaluate_study(plan(), [changed], [], as_of=AS_OF)
    data = plan().model_dump()
    data["baseline_frozen_at"] = "2026-10-23T00:00:00Z"
    with pytest.raises(ValidationError, match="基线必须"):
        StudyPlan.model_validate(data)
