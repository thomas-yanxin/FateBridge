"""Frozen empty/nonempty conditions and a defeated moving-generator example."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core.liuyao_judgment import build_conditional_analysis
from fatebridge.core.liuyao_void import PROFILE
from fatebridge.core.local_techniques.sixyao import build_sixyao_result
from scripts.liuyao.build_profile import build_profile
from tests.liuyao.test_liuyao_conditions import mounted

REFERENCE = Path(__file__).parents[1] / "fixtures/liuyao_void_v7"
CASES = json.loads((REFERENCE / "cases.json").read_text(encoding="utf-8"))["cases"]


def test_new_scan_readings_do_not_overwrite_frozen_transcription():
    assert build_profile("void") == PROFILE
    previous = json.loads(
        (REFERENCE.parent / "liuyao-zengshan-sources.json").read_text(encoding="utf-8")
    )
    raw = next(
        c["wikitext"] for c in previous["chapters"] if c["title"].endswith("/26")
    )
    assert "有卦不動爲空" in raw and "明夷之豐" in raw
    assert PROFILE["textual_issues"][0]["scan"] == "有氣不動亦爲空"
    assert PROFILE["textual_issues"][1]["scan"] == "又得明夷之小過"


def classical(case):
    info, lines = mounted(case["base_code"], case["changed_code"])
    return build_conditional_analysis(
        lines=lines,
        hidden=case.get("hidden", []),
        month=case["month"],
        day_ganzhi=case["day_ganzhi"],
        palace=info["current_palace_element"],
        moment=datetime.fromisoformat("2000-01-07T12:00:00+08:00"),
        focus_line=case["focus_line"],
        focus_kinship=None,
        focus_kind=case.get("focus_kind"),
        timing_days=0,
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_original_void_branches_keep_horizon_and_conflicts(case):
    result = classical(case)
    focus = result["void_conditions"]["focus"]
    assert focus["branch"] == case["expected_branch"]
    assert focus["is_xunkong"] is case["expected_void"]
    assert focus["changed_is_xunkong"] is case["expected_changed_void"]
    assert focus["classification"] == case["expected_status"]
    assert focus["is_permanently_void"] is None
    assert focus["permanent_void_status"] == "not_adjudicated"
    for rule in focus["not_empty_conditions"] + focus["empty_conditions"]:
        if rule["matched"] is None:
            assert rule["status"] == "unresolved"
    if case["expected_status"] == "not_final_void_pending_use":
        assert focus["is_true_void"] is False
    if case["expected_status"] == "conflicting_or_unresolved_conditions":
        assert focus["is_true_void"] is None


def test_back_controlled_si_generator_is_not_an_unobstructed_support_edge():
    result = classical(CASES[0])
    edge = next(
        e
        for e in result["interaction_edges"]
        if e["source_kind"] == "base"
        and e["source_position"] == 5
        and e["target_position"] == 2
    )
    assert edge["relation"] == "生爻"
    assert edge["effect_status"] == "back_control_obstructs_outgoing_candidate"
    strength = result["classical_assessment"]["focus"]["strength"]
    assert any(s["position"] == 5 for s in strength["blocked_supports"])
    assert all(
        s.get("position") != 5
        for s in strength["supports"] + strength["pending_supports"]
    )
    assert result["lines"][4]["outgoing_obstructions"]
    # The printed example's changed Zi is itself in Xunkong. That does
    # not erase the parent's explicitly stated back-control obstruction.
    assert result["void_conditions"]["lines"][4]["changed_is_xunkong"] is True


def test_first_chart_does_not_invent_the_second_cast_or_source_outcome():
    result = classical(CASES[0])
    void = result["void_conditions"]
    assert "second_cast" not in void and "predicted_success" not in void
    assert void["focus"]["is_permanently_void"] is None


def test_back_controlled_source_is_not_counted_as_moving_help_for_hidden_fire():
    # Dachu to Tai: upper Gen's line 6 Yin changes to Kun's You metal.
    # Hidden Wu fire at line 2 has a real flying Yin; only the moving Yin
    # at line 6 is defeated. This does not cancel all hidden supports.
    case = dict(
        base_code="111001",
        changed_code="111000",
        month="寅",
        day_ganzhi="甲辰",
        focus_line=2,
        focus_kind="hidden",
        hidden=[
            dict(
                position=2, branch="午", element="火", liuqin="父母", flying_branch="寅"
            )
        ],
    )
    result = classical(case)
    hidden = result["hidden_conditions"][0]
    moving = next(
        c
        for c in hidden["supporting_conditions"]
        if c["rule_id"] == "moving_generates_hidden"
    )
    assert moving["matched"] is False
    assert any(
        a["position"] == 6
        and a["effect_status"] == "back_control_obstructs_outgoing_candidate"
        for a in moving["actors"]
    )
    assert (
        next(
            c
            for c in hidden["supporting_conditions"]
            if c["rule_id"] == "flying_generates_hidden"
        )["matched"]
        is True
    )


def test_one_back_controlled_yuan_does_not_cancel_another_eligible_route():
    # Daguo to Weiji: line 3 You -> Wu fire; line 5 You -> Wei earth.
    # Both are Yuan for visible line 4 Hai, but only line 3 is back-controlled.
    bound = classical(
        dict(
            base_code="011110",
            changed_code="010101",
            month="辰",
            day_ganzhi="甲子",
            focus_line=4,
        )
    )
    bound_second = next(
        c for c in bound["role_effects"]["chains"] if c["positions"] == [6, 5, 4]
    )
    assert bound_second["status"] == "yuan_binding_prevents_routing_candidate"
    # Chen month itself binds You. Retain that counterexample, then vary
    # the synthetic month to Si to isolate the back-control distinction.
    result = classical(
        dict(
            base_code="011110",
            changed_code="010101",
            month="巳",
            day_ganzhi="甲子",
            focus_line=4,
        )
    )
    chains = result["role_effects"]["chains"]
    blocked = next(c for c in chains if c["positions"] == [6, 3, 4])
    assert blocked["status"] == "back_control_obstructs_routing_candidate"
    assert blocked["obstructed_positions"] == [3]
    valid = next(c for c in chains if c["positions"] == [6, 5, 4])
    assert valid["status"] == "successive_generation_candidate"
    edge = next(
        e
        for e in result["interaction_edges"]
        if e["source_kind"] == "base"
        and e["source_position"] == 6
        and e["target_position"] == 4
    )
    assert valid["chain_id"] in edge["routing_chain_ids"]
    assert blocked["chain_id"] not in edge["routing_chain_ids"]


def test_modern_snapshot_keeps_void_and_back_control_conditions_from_same_run():
    # A modern synthetic civil date matching Chen month / Yi-Mao day.
    result = build_sixyao_result(
        date="2000-04-27",
        time="12:00:00",
        gua_code="101011",
        changed_code="101001",
        focus_line=2,
    )
    assert result["nongli"]["dayGanZi"] == "乙卯"
    detail = result["liuyao_evidence"]["conditional_analysis"]
    assert (
        detail["void_conditions"]["focus"]["classification"]
        == "conflicting_or_unresolved_conditions"
    )
    assert "第2爻丑：原旬旬空" in result["snapshot_text"]
    assert "回头克受阻爻位：[5]" in result["snapshot_text"]
    assert detail["void_conditions"]["scope"] in result["snapshot_text"]
