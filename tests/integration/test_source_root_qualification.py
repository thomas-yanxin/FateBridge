"""Root class and actual survival must precede structural capacity decisions."""

from dataclasses import replace

import pytest
from pydantic import ValidationError

from fatebridge.core.bazi.bazi_evidence import build_natal_evidence
from fatebridge.core.contracts.output_root_qualification import RootQualification
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.strength import DEFAULT_POLICY
from tests.unit_test.fixtures.bazi_strength import (
    bazi_pillars,
    evaluate_pillar_strength,
)


def root(result, position):
    return next(r for r in result["root_qualifications"] if r["pillar"] == position)


def test_yang_growth_is_a_real_heavy_root_even_when_not_the_branch_primary_qi() -> None:
    result = evaluate_pillar_strength("壬寅 壬寅 庚辰 辛巳")
    seat = root(result, "hour")
    assert seat["kind"] == "yang_growth_root"
    assert seat["matching_hidden_stems"] == ["庚"]
    assert seat["qualification_basis"] == "source_heavy_root"
    assert seat["retention_fraction"] == 1
    assert seat["qualified_for_structural_rule"]
    assert result["structural_decision"]["vigorous_roots"] == ["hour"]
    # One root is not a universal whole-chart strength override.
    assert result["structural_decision"]["rule"] == "weighted_balance"


def test_yin_growth_without_hidden_element_and_minor_root_cannot_be_heavy() -> None:
    result = evaluate_pillar_strength("己巳 癸酉 癸未 庚申")
    assert root(result, "month")["initial_hidden_mass"] == 0
    assert root(result, "hour")["kind"] == "other_hidden_root"
    assert not root(result, "hour")["qualified_for_structural_rule"]
    result = evaluate_pillar_strength("辛酉 丁酉 丁卯 辛酉")
    assert all(
        not r["qualified_for_structural_rule"] for r in result["root_qualifications"]
    )
    assert any(
        r["kind"] == "yin_growth_reference" for r in result["root_qualifications"]
    )


def test_damaged_growth_root_is_not_restored_by_a_source_label() -> None:
    result = evaluate_pillar_strength("壬寅 戊申 壬辰 壬寅")
    seat = root(result, "month")
    assert seat["kind"] == "yang_growth_root"
    assert seat["remaining_hidden_mass"] > 0
    assert seat["retention_fraction"] < seat["minimum_retention_policy"]
    assert not seat["qualified_for_structural_rule"]


def test_two_healthy_growth_roots_now_reach_the_existing_structural_rule() -> None:
    # Synthetic, internally consistent pillars, not an independent source label.
    result = evaluate_pillar_strength("乙亥 壬午 甲辰 乙亥")
    assert result["structural_decision"]["numerical_label"] == "中和"
    assert result["structural_decision"]["vigorous_roots"] == ["year", "hour"]
    assert (
        result["structural_decision"]["rule"]
        == "multiple_vigorous_roots_and_rooted_visible_support"
    )
    assert result["strength_level"] == "强"
    # Controlled engineering damage: an active clash by itself need not
    # reduce these stronger roots below the retained-root threshold.
    damaged = evaluate_pillar_strength(
        "乙亥 壬巳 甲辰 乙亥",
        policy=replace(DEFAULT_POLICY, clash_winner=0.5, clash_loser=0.5),
    )
    assert not damaged["structural_decision"]["vigorous_roots"]


def test_shared_receipt_is_copied_without_recomputing_or_accepting_invented_roots() -> (
    None
):
    chart = bazi_pillars("壬寅 壬寅 庚辰 辛巳")
    strength = ElementAnalysis.analyze_day_master_strength(chart)
    context = build_natal_evidence(chart, strength)["strength_context"]
    assert (
        context["root_qualifications"] == strength["assessment"]["root_qualifications"]
    )
    good = context["root_qualifications"][-1]
    RootQualification.model_validate(good)
    for patch in [
        {"matching_hidden_stems": []},
        {"initial_hidden_mass": 0.0},
        {"qualification_basis": "not_anchored_kind"},
        {"retention_fraction": 0.1},
        {"kind": "yin_growth_reference"},
        {"source_weight_class": "light"},
    ]:
        with pytest.raises(ValidationError):
            RootQualification.model_validate({**good, **patch})
    context["root_qualifications"][0]["kind"] = "changed_by_host"
    assert strength["assessment"]["root_qualifications"][0]["kind"] != "changed_by_host"
    assert (
        build_natal_evidence(chart)["strength_context"]["root_qualifications"] is None
    )


def test_rounded_display_cannot_change_the_raw_root_qualification_gate() -> None:
    initial = 0.7
    remaining = initial * 0.75
    # Division puts this fraction just below 0.75; multiplication still equals
    # the actual threshold. Preserve the decision's original arithmetic.
    assert remaining / initial < 0.75
    RootQualification.model_validate(
        {
            "kind": "yang_growth_root",
            "source_weight_class": "heavy",
            "qualification_basis": "source_heavy_root",
            "matching_hidden_stems": ["甲"],
            "initial_hidden_mass": initial,
            "remaining_hidden_mass": remaining,
            "retention_fraction": remaining / initial,
            "minimum_retention_policy": 0.75,
            "qualified_for_structural_rule": True,
        }
    )
    # Projection is allowed to carry only the fact actually requested.
    RootQualification.model_validate({"qualified_for_structural_rule": True})


def test_complete_same_element_bureau_records_structural_decision() -> None:
    assessment = evaluate_pillar_strength("甲寅 丁卯 甲辰 乙亥")
    assert (
        assessment["structural_decision"]["rule"]
        == "complete_same_element_bureau_with_surviving_vigorous_roots"
    )
    assert assessment["structural_decision"]["vigorous_roots"] == [
        "year",
        "month",
        "hour",
    ]
