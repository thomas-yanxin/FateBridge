"""Primary-text direction checks plus causal ablations, not score snapshots."""

import json
import math
from dataclasses import replace
from pathlib import Path

import pytest

from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.strength import DEFAULT_POLICY, _evaluate
from fatebridge.utils.data import Element

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/bazi-strength-reference.json").read_text()
)


def pillars(text):
    return dict(zip(("year", "month", "day", "hour"), map(tuple, text.split())))


def score(text, **changes):
    p = pillars(text)
    return _evaluate(
        p,
        ElementAnalysis.seasonal_phases(p["month"][1]),
        replace(DEFAULT_POLICY, **changes),
    )


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: c["id"])
def test_primary_text_twenty_cases(case):
    p = {k: tuple(v) for k, v in case["pillars"].items()}
    a = ElementAnalysis.analyze_day_master_strength(p)["assessment"]
    assert a["strength_level"] == case["expected_strength"]
    assert a["sensitivity"]["candidate_strengths"] == [case["expected_strength"]]
    # These extremes are not used as generic 扶抑 prescriptions.
    if a["requires_special_structure_review"]:
        assert ElementAnalysis.comprehensive_analysis(p)["favorable_elements"] == []


def test_month_command_not_equivalent_to_strength():
    in_season = score("辛酉 辛卯 甲申 辛酉")
    out_of_season = score("甲寅 癸酉 甲寅 乙亥")
    assert in_season["strength_level"] != "强"
    assert out_of_season["strength_level"] != "弱"


def test_month_season_root_and_revelation_change_actual_scores():
    text = "甲寅 乙卯 甲子 丁丑"
    nominal = score(text)
    assert (
        nominal["support_strength"]
        > score(text, month_multiplier=1)["support_strength"]
    )
    assert (
        nominal["support_strength"] > score(text, branch_budget=0)["support_strength"]
    )
    assert (
        nominal["support_strength"]
        > score(text, reveal_multiplier=1)["support_strength"]
    )
    assert nominal["support_share"] != score(text, seasonal_spread=0)["support_share"]


def test_branch_budget_does_not_count_main_qi_twice():
    a = score("庚辰 戊子 壬寅 乙巳")
    assert sum(b["initial"] for b in a["branch_budgets"].values()) == 10
    assert sum(b["remaining"] for b in a["branch_budgets"].values()) <= 10
    assert a["relations"][0]["kind"] == "半合"
    assert a["relations"][0]["status"] == "partial_tendency"


def test_yin_birth_stage_without_hidden_same_element_is_not_a_root():
    a = score("戊戌 己丑 丁酉 庚申")
    assert not any(
        r["pillar"] == "day" for r in a["roots"]
    )  # 丁长生酉 cannot invent 丁根.


def test_clash_direction_uses_seasonal_resources_not_fixed_element_winner():
    winter = score("庚申 壬子 丙午 丁酉")
    summer = score("庚申 丙午 壬子 丁酉")
    cw = next(
        e
        for e in winter["relations"]
        if e["kind"] == "六冲" and "month" in e["positions"]
    )
    cs = next(
        e
        for e in summer["relations"]
        if e["kind"] == "六冲" and "month" in e["positions"]
    )
    assert cw["root_multipliers"]["month"] > cw["root_multipliers"]["day"]
    assert cs["root_multipliers"]["month"] > cs["root_multipliers"]["day"]
    assert (
        winter["support_share"]
        != score("庚申 壬子 丙午 丁酉", clash_winner=1, clash_loser=1)["support_share"]
    )


def test_combination_can_resolve_clash_and_contested_claim_cannot():
    resolved = score("壬子 己丑 丙午 乙酉")
    c = next(e for e in resolved["relations"] if e["kind"] == "六冲")
    assert c["status"] == "resolved_by_combination"
    contested = score("壬子 己丑 丙午 丁未")
    c = next(
        e
        for e in contested["relations"]
        if e["kind"] == "六冲" and "year" in e["positions"]
    )
    assert c["status"] == "active"  # both sides have claims; no unconditional 解冲.


def test_full_bureau_requires_in_command_and_revelation():
    transformed = score("壬申 壬子 甲辰 丁未")
    without_revelation = score("丙申 丙子 甲辰 丁未")
    merely_generated = score("壬申 己酉 庚子 庚辰")
    assert any(
        e["status"] == "conditioned_transformation" for e in transformed["relations"]
    )
    assert not any(
        e["status"] == "conditioned_transformation"
        for e in without_revelation["relations"]
    )
    assert not any(
        e["status"] == "conditioned_transformation"
        for e in merely_generated["relations"]
    )
    assert (
        transformed["effective_elements"]
        != score("壬申 壬子 甲辰 丁未", transformation_transfer=0)["effective_elements"]
    )


def test_seasonal_bureau_does_not_double_use_internal_six_combination():
    a = score("壬亥 壬子 甲丑 丁未")
    # 外冲 may prevent 化, but no 子丑六合 is counted a second time within 亥子丑.
    assert any(e["kind"] == "三会" for e in a["relations"])
    assert not any(e["kind"] == "六合" for e in a["relations"])


def test_full_punishment_changes_energy_without_erasing_root():
    text = "甲寅 丁巳 庚申 壬子"
    penalized, unpenalized = score(text), score(text, punishment=1)
    assert any(e["kind"] == "刑" for e in penalized["relations"])
    assert penalized["effective_elements"] != unpenalized["effective_elements"]
    assert all(b["remaining"] > 0 for b in penalized["branch_budgets"].values())


def test_stem_binding_changes_score_but_day_master_is_not_erased():
    text = "甲子 己丑 丙寅 壬申"
    nominal = score(text)
    assert any(
        e["kind"] == "天干合" and e["status"] == "binding" for e in nominal["relations"]
    )
    assert nominal["effective_elements"] != score(text, binding=1)["effective_elements"]
    own = score("甲子 戊午 癸亥 丁巳")
    assert any(
        e["kind"] == "天干合" and e["status"] == "day_master_or_contested_review"
        for e in own["relations"]
    )


def test_chart_dict_order_does_not_select_different_combination():
    p = pillars("壬申 壬子 甲辰 丁未")
    assert ElementAnalysis.analyze_day_master_strength(
        p
    ) == ElementAnalysis.analyze_day_master_strength(dict(reversed(list(p.items()))))


@pytest.mark.parametrize("day_stem", "甲乙丙丁戊己庚辛壬癸")
@pytest.mark.parametrize("month_branch", "子丑寅卯辰巳午未申酉戌亥")
def test_finite_scores_conservation_and_json_for_every_stem_month(
    day_stem, month_branch
):
    p = pillars("庚辰 戊子 壬寅 乙巳")
    p["day"] = (day_stem, "寅")
    p["month"] = ("戊", month_branch)
    result = ElementAnalysis.analyze_day_master_strength(p)
    a = result["assessment"]
    assert all(
        math.isfinite(a[k])
        for k in ("support_strength", "weaken_strength", "support_share")
    )
    assert 0 <= a["support_share"] <= 1
    assert all(
        0 <= b["remaining"] <= b["initial"] + 1e-9 for b in a["branch_budgets"].values()
    )
    assert math.isclose(
        sum(a["effective_elements"].values()),
        a["support_strength"] + a["weaken_strength"],
        abs_tol=1e-5,
    )
    json.dumps(result, allow_nan=False)


def test_rooted_wealth_officer_chain_can_overturn_in_season_score():
    case = REFERENCE["additional_cases"][0]
    p = {k: tuple(v) for k, v in case["pillars"].items()}
    a = ElementAnalysis.analyze_day_master_strength(p)["assessment"]
    assert a["strength_level"] == case["expected_strength"]
    assert (
        a["structural_decision"]["rule"]
        == "rooted_wealth_officer_front_without_visible_support"
    )
    assert a["month_command"]["phase"] == "旺"
    # Comparison removes the exposed wealth-to-officer front, not the season.
    p["year"] = ("辛", "酉")
    changed = ElementAnalysis.analyze_day_master_strength(p)["assessment"]
    assert changed["structural_decision"]["rule"] != a["structural_decision"]["rule"]
    assert changed["strength_level"] != a["strength_level"]


def test_reference_directions_and_policy_sensitivity():
    from scripts.validate_bazi_strength import build_report

    report = build_report()
    assert report["summary"]["direction_matches"] == 21
    assert report["summary"]["stress_trials"] == 630
    assert report["summary"]["stress_label_changes"] == 0


def test_shared_peak_does_not_pick_arbitrary_half_combination():
    a = score("甲辰 丁卯 甲子 戊辰")
    halves = [event for event in a["relations"] if event["kind"] == "半合"]
    assert len(halves) == 2
    assert {event["status"] for event in halves} == {"contested"}
    assert not a["combination_contributions"]
