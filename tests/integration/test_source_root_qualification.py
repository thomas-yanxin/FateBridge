"""Root class and actual survival must precede structural capacity decisions."""

from copy import deepcopy
from dataclasses import replace

import pytest
from pydantic import ValidationError

from fatebridge.core.bazi.bazi_evidence import build_natal_evidence
from fatebridge.core.contracts.output_root_qualification import RootQualification
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.root_qualification import root_qualification_snapshot_lines
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


def test_snapshot_reads_supplied_qualifications_instead_of_recomputing_a_chart() -> (
    None
):
    a = evaluate_pillar_strength("乙亥 壬午 甲辰 乙亥")
    text = "\n".join(root_qualification_snapshot_lines(a))
    assert "工程结构政策档：强；数值原判：中和" in text
    assert "至少两处健全根且另有实际通根的透干印比" in text
    assert "阳长生根" in text and "工程约定" in text
    supplied = deepcopy(a)
    supplied["root_qualifications"][0]["qualified_for_structural_rule"] = False
    supplied["root_qualifications"][0]["retention_fraction"] = 0.8
    assert "年支亥（阳长生根，实际藏干根保留80.0%，未计入）" in "\n".join(
        root_qualification_snapshot_lines(supplied)
    )
    assert root_qualification_snapshot_lines({}) == []


def test_snapshot_explains_complete_same_element_bureau() -> None:
    assessment = evaluate_pillar_strength("甲寅 丁卯 甲辰 乙亥")
    assert (
        assessment["structural_decision"]["rule"]
        == "complete_same_element_bureau_with_surviving_vigorous_roots"
    )
    basis_line = root_qualification_snapshot_lines(assessment)[0]
    assert basis_line.endswith(
        "本次依据：同类完整会合局透出目标五行，且至少两处实际根达到保留门槛。"
    )
