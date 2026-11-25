"""Decision provenance and causal invariance, not classical accuracy scores."""

import copy
import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.bazi.bazi_evidence import build_natal_evidence
from fatebridge.core.clash_comparison import (
    clash_comparison_snapshot_lines,
)
from fatebridge.core.contracts.output_clash_comparison import ClashComparison
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.strength import DEFAULT_POLICY, evaluate_strength_policy
from tests.support.bazi_strength_reference_v3 import (
    assert_current_assessment_arithmetic,
)


def pillars(text):
    return dict(zip(("year", "month", "day", "hour"), map(tuple, text.split())))


def model(text):
    return ElementAnalysis.analyze_day_master_strength(pillars(text))["assessment"]


def test_tender_wood_counterexample_discloses_physical_proxy_and_current_arithmetic() -> (
    None
):
    a = model("丁丑 壬寅 丙申 壬辰")
    trace = a["clash_comparison"]
    # The old 中和 snapshot used reversed seasonal phases. Audit today's
    # budget independently; the physical proxy still does not adjudicate
    # the source's effective root-force claim.
    assert_current_assessment_arithmetic(["丁丑", "壬寅", "丙申", "壬辰"], a)
    row = trace["events"][0]
    assert row["positions"] == ["month", "day"] and row["distance"] == 1
    wood, metal = row["powers"]
    # Hand arithmetic: 木=寅甲16/7+辰乙4/7; 金=丑辛2/7+申庚8/7.
    assert wood["raw_budget"] == float(Fraction(20, 7))
    assert metal["raw_budget"] == float(Fraction(10, 7))
    assert row["applied_root_retention"] == {"month": 0.9, "day": 0.5}
    assert trace["resource_stage"] == "before_interactions"
    assert "indirect_generation" in trace["not_included_factors"]
    assert "thermal_receiving_capacity" in trace["not_included_factors"]
    assert trace["classical_effective_force"] == "not_adjudicated"
    ClashComparison.model_validate(trace)


@pytest.mark.parametrize(
    "text,expected,checks",
    [
        ("甲子 丁丑 戊子 丙午", {"水": "36/7", "火": "4/3"}, 4),
        ("甲子 丁丑 辛卯 己酉", {"木": "2", "金": "18/7"}, 2),
    ],
)
def test_initial_clash_budgets_are_rounded_once_after_exact_sum(
    text: str, expected, checks: int
) -> None:
    # Literal controls from geometric hidden shares: visible stems do not
    # enter this proxy, and all natal positions contribute to each element.
    trace = model(text)["clash_comparison"]
    powers = [
        power
        for event in trace["events"]
        if event["calculation_branch"] == "initial_hidden_budget"
        for power in event["powers"]
    ]
    assert len(powers) == checks
    assert {power["element"] for power in powers} == set(expected)
    for power in powers:
        assert power["raw_budget"] == float(Fraction(expected[power["element"]]))


def test_trace_and_snapshot_reuse_the_same_receipt_and_do_not_recompute() -> None:
    p = pillars("丁丑 壬寅 丙申 壬辰")
    strength = ElementAnalysis.analyze_day_master_strength(p)
    receipt = strength["assessment"]["clash_comparison"]
    shared = build_natal_evidence(p, strength)["strength_context"]["clash_comparison"]
    assert shared == receipt
    shared["events"][0]["powers"][0]["raw_budget"] = 123
    assert receipt["events"][0]["powers"][0]["raw_budget"] != 123
    assert any(
        "123.000000" in line
        for line in clash_comparison_snapshot_lines({"clash_comparison": shared})
    )
    assert build_natal_evidence(p)["strength_context"]["clash_comparison"] is None


@pytest.mark.parametrize(
    "text,branch",
    [
        ("壬子 己丑 丙午 乙酉", "combination_resolution"),
        ("甲辰 戊戌 丙子 辛酉", "storage_movement"),
    ],
)
def test_non_power_branches_never_fabricate_a_winning_budget(
    text: str, branch: str
) -> None:
    a = model(text)
    row = next(
        r for r in a["clash_comparison"]["events"] if r["calculation_branch"] == branch
    )
    assert row["powers"] is None and row["applied_root_retention"] is None
    ClashComparison.model_validate(a["clash_comparison"])


@pytest.mark.parametrize(
    "hour,expected_status,expected_source",
    [
        (
            "乙巳",
            "resolved_by_combination",
            "ziping_zi_chou_separated_clash_resolution_v1",
        ),
        (
            "癸卯",
            "resolved_by_combination",
            "ziping_zi_chou_separated_clash_resolution_v1",
        ),
        ("壬寅", "active", "ditian_branch"),
        ("辛亥", "resolved_by_combination", "ziping_7"),
    ],
)
def test_separated_zi_chou_resolves_only_the_uncompeted_clash(
    hour: str, expected_status: str, expected_source: str
) -> None:
    # 秘本子平真詮 PDF25／印16: year 子, month 午, and day 丑 can resolve that clash.
    assessment = model(f"甲子 庚午 丁丑 {hour}")
    trace = assessment["clash_comparison"]
    event = next(
        row for row in trace["events"] if row["positions"] == ["year", "month"]
    )
    assert event["event_status"] == expected_status
    assert event["source_ref"] == expected_source
    if expected_source == "ziping_zi_chou_separated_clash_resolution_v1":
        assert event["powers"] is None
        assert event["applied_root_retention"] is None
        assert [s["pdf_pages"] for s in trace["sources"]] == [[25]]
        assert not any(r["kind"] in {"六合", "半合"} for r in assessment["relations"])
    else:
        pass
    if hour == "癸卯":
        assert any(
            row["kind"] == "刑"
            and row["status"] == "active"
            and row["positions"] == ["year", "hour"]
            for row in assessment["relations"]
        )
    else:
        pass


def test_no_clash_has_no_comparison_events() -> None:
    empty = model("甲寅 乙卯 丙辰 丁未")["clash_comparison"]
    assert empty["events"] == []


@pytest.mark.parametrize(
    "damage", ["total", "double", "imaginary_root", "position", "branch_mode", "force"]
)
def test_contract_rejects_fabricated_calculation_facts(damage: str) -> None:
    trace = copy.deepcopy(model("丁丑 壬寅 丙申 壬辰")["clash_comparison"])
    row = trace["events"][0]
    if damage == "total":
        row["powers"][0]["raw_budget"] = 999
    elif damage == "double":
        row["powers"][0]["contributors"].append(row["powers"][0]["contributors"][0])
    elif damage == "imaginary_root":
        row["powers"][0]["contributors"][0]["stem"] = "丁"
    elif damage == "position":
        row["distance"] = 3
    elif damage == "branch_mode":
        row["calculation_branch"] = "combination_resolution"
    else:
        trace["classical_effective_force"] = "verified"
    with pytest.raises(ValidationError):
        ClashComparison.model_validate(trace)


def test_parameters_not_used_in_the_proxy_do_not_silently_enter_its_explanation() -> (
    None
):
    p = pillars("丁丑 壬寅 丙申 壬辰")
    phases = ElementAnalysis.seasonal_phases(p["month"][1])
    values = []
    for policy in [
        DEFAULT_POLICY,
        replace(DEFAULT_POLICY, seasonal_spread=0, reveal_multiplier=1),
    ]:
        a = evaluate_strength_policy(p, phases, policy)
        values.append(
            next(e["power_comparison"] for e in a["relations"] if e["kind"] == "六冲")
        )
    assert values[0] == values[1]


def test_all_retained_inputs_have_valid_clash_trace_and_current_exact_arithmetic() -> (
    None
):
    cases = json.loads(
        (Path(__file__).parents[1] / "data/bazi/clash-inputs.json").read_text()
    )
    assert len(cases) == 228
    for values in cases:
        p = dict(zip(("year", "month", "day", "hour"), map(tuple, values)))
        after = ElementAnalysis.analyze_day_master_strength(p)
        ClashComparison.model_validate(after["assessment"]["clash_comparison"])
        assert_current_assessment_arithmetic(values, after["assessment"])
