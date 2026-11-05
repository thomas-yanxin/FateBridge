"""Unchanged primary-source grades and ablations of the adopted premises."""

import pytest

from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.strength import DEFAULT_POLICY, _evaluate


def evaluate(text, policy=DEFAULT_POLICY):
    pillars = dict(zip(("year", "month", "day", "hour"), map(tuple, text.split())))
    return _evaluate(
        pillars, ElementAnalysis.seasonal_phases(pillars["month"][1]), policy
    )


@pytest.mark.parametrize(
    "case,text,expected",
    [
        ("TG01_PDF199", "癸酉 甲子 丁卯 丙午", "强"),
        ("GS01_PDF203", "己酉 丙寅 庚申 庚辰", "强"),
        ("GS03_PDF205", "戊子 甲寅 戊午 甲寅", "强"),
        ("DZ12_PDF91", "戊辰 辛酉 丙午 癸巳", "强"),
        ("ML02_PDF172_173", "甲戌 丙寅 戊辰 庚申", "强"),
        ("JH02_PDF386", "甲子 丙子 甲申 己巳", "弱"),
    ],
)
def test_existing_source_grade_without_regrading_the_reference(case, text, expected):
    assert evaluate(text)["strength_level"] == expected


def test_full_generation_path_preserves_roots_without_inventing_energy():
    result = evaluate("癸酉 甲子 丁卯 丙午")
    clashes = [r for r in result["relations"] if r["kind"] == "六冲"]
    assert [r["positions"] for r in clashes] == [["year", "day"], ["month", "hour"]]
    assert [r["intermediary_positions"] for r in clashes] == [["month"], ["day"]]
    assert {r["status"] for r in clashes} == {"resolved_by_ordered_generation_path"}
    assert all("root_multipliers" not in r for r in clashes)
    assert sum(b["remaining"] for b in result["branch_budgets"].values()) <= 10
    assert (
        result["structural_decision"]["rule"]
        == "aligned_four_branch_generation_and_time_lu"
    )


@pytest.mark.parametrize("control", ["癸酉 庚子 丁卯 丙午", "癸酉 甲子 丁丑 丙午"])
def test_missing_visible_or_branch_intermediary_does_not_resolve_the_clash(control):
    result = evaluate(control)
    assert not result["structural_decision"]["source_premises"][
        "uncontested_full_generation_path"
    ]
    assert not any(
        r["status"] == "resolved_by_ordered_generation_path"
        for r in result["relations"]
    )


def test_a_real_wood_root_disables_the_winter_rootless_rule():
    control = evaluate("甲子 丙子 甲申 丁卯")
    assert not control["structural_decision"]["source_premises"]["winter_rootless_wood"]
    assert (
        control["structural_decision"]["rule"]
        != "winter_rootless_wood_cannot_receive_water"
    )


def test_structural_grade_does_not_certify_ordinary_balance_preferences():
    pillars = dict(
        zip(("year", "month", "day", "hour"), map(tuple, "癸酉 甲子 丁卯 丙午".split()))
    )
    result = ElementAnalysis.analyze_day_master_strength(pillars)
    assessment = result["assessment"]
    assert result["strength_level"] == "强"
    assert assessment["threshold_arithmetic"]["numerical_label"] == "弱"
    assert assessment["status"] == "rule_based"
    assert assessment["ordinary_fuyi_requires_review"] is True
    assert ElementAnalysis.get_favorable_elements(result) == []
