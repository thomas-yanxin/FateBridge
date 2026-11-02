"""Frozen classical counterexamples plus activation and day-clock boundaries."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.liuyao_judgment import (
    MANIFEST,
    STAGES,
    build_conditional_analysis,
    kinship,
    month_strength,
    role_against_focus,
)
from fatebridge.core.local_techniques.sixyao import (
    _build_sixyao_enrichment,
    _lines_from_codes,
    build_sixyao_result,
)
from fatebridge.core.requests.divination import SixYaoRequest
from fatebridge.utils.timezones import parse_timezone_name

ROOT = Path(__file__).parent / "fixtures"
REFERENCE = json.loads((ROOT / "liuyao-conditional-reference-v2.json").read_text())
INPUT = {"date": "2026-10-22", "time": "12:00:00", "zone": "Asia/Shanghai"}


def mounted(code, changed):
    info, enrichment = _build_sixyao_enrichment(code, changed, "甲")
    lines = _lines_from_codes(code, changed)
    for line, extra in zip(lines, enrichment):
        line.update(extra)
        if line["change"]:
            line["changed_branch"] = extra["changed_branch"] or extra["branch"]
    return info, lines


def conditional_case(case, **overrides):
    info, lines = mounted(case["base_code"], case["changed_code"])
    # No civil date was provided by these excerpts. Timing is disabled in
    # source comparisons; this clock is test infrastructure, not a recovered date.
    args = dict(
        lines=lines,
        hidden=[],
        month=case["month_branch"],
        day_ganzhi=case["day_ganzhi"],
        palace=info["current_palace_element"],
        moment=datetime(2026, 10, 22, 12, tzinfo=parse_timezone_name("Asia/Shanghai")),
        focus_line=case["focus_line"],
        focus_kinship=None,
        timing_days=0,
    )
    return build_conditional_analysis(**{**args, **overrides})


def test_frozen_depth_sources_match_runtime_revision_hashes():
    raw = json.loads((ROOT / "liuyao-zengshan-depth-v2.json").read_text())
    for record in raw["chapters"]:
        assert (
            hashlib.sha256(record["wikitext"].encode()).hexdigest()
            == record["wikitext_sha256"]
        )
        saved = MANIFEST["sources_by_chapter"][record["title"].split("/")[1]]
        assert saved["revision"] == record["revision"]
        assert saved["wikitext_sha256"] == record["wikitext_sha256"]


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda case: case["id"])
def test_classical_structures_and_conditional_edges(case):
    result = conditional_case(case)
    assert result["focus"]["selected"]["branch"] == case["expected_focus_branch"]
    roles = {str(r["position"]): r["role"] for r in result["focus"]["roles"]}
    for key, value in case.get(
        "expected_roles", case.get("expected_roles_subset", {})
    ).items():
        assert roles[key] == value
    base_edges = {
        (e["source_position"], e["target_position"]): e
        for e in result["interaction_edges"]
        if e["source_kind"] == "base"
    }
    if "expected_held_edge" in case:
        assert (
            base_edges[tuple(case["expected_held_edge"])]["effect_status"]
            == "combination_holds_outgoing_candidate"
        )
    if "expected_base_edge" in case:
        assert tuple(case["expected_base_edge"]) in base_edges
    for pair in case.get("expected_base_edges", []):
        assert tuple(pair) in base_edges
    for edge in result["interaction_edges"]:
        if edge["source_kind"] == "changed":
            assert edge["target_kind"] == "base"
            assert edge["target_position"] == edge["source_position"]
            if "expected_transform_parent" in case:
                assert (
                    edge["relation"]
                    == case["expected_transform_parent"][str(edge["source_position"])]
                )
    if "expected_hidden_moving_position" in case:
        row = result["lines"][case["expected_hidden_moving_position"] - 1]
        assert row["monthly_strength"]["category"] == "休囚"
        assert row["activity"] == "暗动条件匹配"
        assert row["supporting_moving_positions"] == [
            case["expected_supporting_position"]
        ]
    assert all(row["efficacy"] == "not_adjudicated" for row in result["lines"])
    assert result["timing_candidates"]["status"] == "not_requested"


def test_chapter9_combination_release_changes_permission_not_external_outcome():
    case = REFERENCE["cases"][0]
    held = conditional_case(case)
    released = conditional_case(case, day_ganzhi="乙丑")  # 丑冲未

    def edge(result):
        return next(
            e
            for e in result["interaction_edges"]
            if e["source_kind"] == "base"
            and (e["source_position"], e["target_position"]) == (4, 3)
        )

    assert edge(held)["effect_status"] == "combination_holds_outgoing_candidate"
    assert edge(released)["effect_status"] == "conditional"
    assert held["lines"][1]["activity"] == "冲空条件匹配"


@pytest.mark.parametrize("month", "子丑寅卯辰巳午未申酉戌亥")
def test_month_strength_keeps_clash_above_same_element(month):
    from fatebridge.core.liuyao_judgment import clash

    assert month_strength(month, month)["category"] == "临月建"
    assert month_strength(clash(month), month)["category"] == "月破"
    assert not month_strength(clash(month), month)["monthly_supported"]


def test_four_earth_months_and_residual_qi_follow_excerpt_not_three_month_seasons():
    assert month_strength("申", "辰")["category"] == "相"
    assert month_strength("午", "未")["category"] == "休囚"
    assert month_strength("午", "未")["residual_qi"]
    assert month_strength("亥", "丑")["residual_qi"]
    assert (
        month_strength("巳", "寅")["category"] == "相"
    )  # transcription's repeated 火 typo is disclosed


def test_all_five_element_focus_roles_are_not_palace_kinship_labels():
    # Columns 金木水火土; rows focus 金木水火土. Hand-derived from chapter9.
    elements = "金木水火土"
    expected = [
        ["同类", "仇神", "用神所生", "忌神", "元神"],
        ["忌神", "同类", "元神", "用神所生", "仇神"],
        ["元神", "用神所生", "同类", "仇神", "忌神"],
        ["仇神", "元神", "忌神", "同类", "用神所生"],
        ["用神所生", "忌神", "仇神", "元神", "同类"],
    ]
    for focus, row in zip(elements, expected):
        assert [role_against_focus(element, focus) for element in elements] == row
    assert kinship("金", "木") == "妻财"
    assert role_against_focus("木", "金") == "仇神"


def test_focus_is_explicit_and_multiple_visible_candidates_stay_open():
    unresolved = build_sixyao_result(
        **INPUT, gua_code="111111", focus_kinship="父母", timing_days=12
    )
    focus = unresolved["liuyao_evidence"]["conditional_analysis"]["focus"]
    assert (
        focus["status"] == "multiple_visible_candidates" and focus["selected"] is None
    )
    assert [row["position"] for row in focus["candidates"]] == [3, 6]
    assert (
        unresolved["liuyao_evidence"]["conditional_analysis"]["timing_candidates"][
            "windows"
        ]
        == []
    )
    unspecified = build_sixyao_result(
        **INPUT, gua_code="111111", question="我要取得项目收入，父母是否帮忙？"
    )
    assert (
        unspecified["liuyao_evidence"]["conditional_analysis"]["focus"]["status"]
        == "not_requested"
    )


def test_day_month_candidates_take_priority_over_hidden_when_kinship_absent():
    case = {
        "base_code": "100000",
        "changed_code": "100000",
        "month_branch": "巳",
        "day_ganzhi": "甲子",
        "focus_line": None,
    }
    result = conditional_case(
        case,
        focus_kinship="父母",
        hidden=[{"position": 2, "branch": "巳", "element": "火", "liuqin": "父母"}],
    )
    assert result["focus"]["status"] == "day_month_candidates_before_hidden"
    assert [r["location"] for r in result["focus"]["candidates"]] == ["month"]
    assert result["focus"]["selected"] is None


def test_stage_names_preserve_elemental_conflicts_and_do_not_mean_effective():
    info, lines = mounted("111111", "111111")
    result = build_conditional_analysis(
        lines=lines,
        hidden=[],
        month="午",
        day_ganzhi="己巳",
        palace=info["current_palace_element"],
        moment=datetime(2026, 6, 1),
        focus_line=None,
        focus_kinship=None,
        timing_days=0,
    )
    gold = result["lines"][4]  # 申金
    earth = result["lines"][2]  # 辰土
    assert gold["day_stage"] == "长生" and gold["stage_cautions"]
    assert earth["day_stage"] == "绝" and earth["stage_cautions"]
    assert gold["efficacy"] == earth["efficacy"] == "not_adjudicated"
    assert STAGES["土"] == STAGES["水"]
    assert "亥" not in STAGES["火"]  # omitted 火 table is not invented


def test_day_level_candidates_cross_xun_at_23_hours_without_event_ranking():
    # Shared standard day calendar: 2000-01-07 甲子. The test checks the
    # candidate-window boundary, not an empirical event.
    result = build_sixyao_result(
        date="2000-01-07",
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code="111111",
        focus_line=6,
        timing_days=11,
    )
    timing = result["liuyao_evidence"]["conditional_analysis"]["timing_candidates"]
    assert timing["status"] == "condition_windows_only"
    exit_day = next(
        w for w in timing["windows"] if "离开起卦日所在旬" in w["matched_rules"]
    )
    assert exit_day["effective_date"] == "2000-01-17"
    assert exit_day["day_ganzhi"] == "甲戌"
    assert exit_day["start_at"] == "2000-01-16T23:00:00+08:00"
    assert "旬空填实" in exit_day["matched_rules"]
    assert all("probability" not in w and "score" not in w for w in timing["windows"])


def test_late_zi_and_offset_timezone_produce_same_effective_day_windows():
    args = dict(date="2000-01-16", gua_code="111111", focus_line=6, timing_days=3)
    before = build_sixyao_result(**args, time="22:59:59", zone="+08:00")
    after = build_sixyao_result(**args, time="23:00:00", zone="Asia/Shanghai")
    old = before["liuyao_evidence"]["conditional_analysis"]["timing_candidates"][
        "windows"
    ]
    new = after["liuyao_evidence"]["conditional_analysis"]["timing_candidates"][
        "windows"
    ]
    assert old[0]["day_ganzhi"] == new[0]["day_ganzhi"] == "甲戌"
    assert old[0]["start_at"] == new[0]["start_at"]


@pytest.mark.parametrize(
    "date,time", [("2026-03-08", "02:30:00"), ("2026-11-01", "01:30:00")]
)
def test_unqualified_dst_gap_and_fold_are_rejected(date, time):
    with pytest.raises(ValueError, match="nonexistent local time|ambiguous local time"):
        build_sixyao_result(
            date=date, time=time, zone="America/New_York", gua_code="111111"
        )


def test_explicit_offset_disambiguates_repeated_hour_without_changing_instant():
    result = build_sixyao_result(
        date="2026-11-01",
        time="01:30:00-04:00",
        zone="America/New_York",
        gua_code="111111",
    )
    assert (
        result["liuyao_evidence"]["calendar_conventions"]["cast_at"]
        == "2026-11-01T01:30:00-04:00"
    )


def test_civil_day_candidate_keeps_dst_offset_and_rechecks_changed_solar_month():
    dst = build_sixyao_result(
        date="2000-04-01",
        time="12:00:00",
        zone="America/New_York",
        gua_code="111111",
        focus_line=2,
        timing_days=2,
    )
    window = next(
        w
        for w in dst["liuyao_evidence"]["conditional_analysis"]["timing_candidates"][
            "windows"
        ]
        if w["effective_date"] == "2000-04-02"
    )
    start, end = (datetime.fromisoformat(window[k]) for k in ("start_at", "end_at"))
    assert window["day_ganzhi"] == "庚寅"
    assert end.timestamp() - start.timestamp() == 23 * 3600
    month = build_sixyao_result(
        date="2000-01-07",
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code="111111",
        focus_line=6,
        timing_days=32,
    )
    crossing = next(
        w
        for w in month["liuyao_evidence"]["conditional_analysis"]["timing_candidates"][
            "windows"
        ]
        if w["effective_date"] == "2000-02-04"
    )
    assert crossing["requires_month_reassessment"]


def test_snapshot_and_replay_inputs_preserve_explicit_analysis_premise():
    result = build_sixyao_result(
        **INPUT, gua_code="111111", focus_line=3, focus_kinship="父母", timing_days=12
    )
    assert {
        k: result["input_normalized"][k]
        for k in ("focus_line", "focus_kinship", "timing_days")
    } == {"focus_line": 3, "focus_kinship": "父母", "timing_days": 12}
    assert "明确用爻：第3爻父母辰" in result["snapshot_text"]
    assert (
        "条件候选" in result["snapshot_text"] or "日级候选" in result["snapshot_text"]
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"focus_line": True},
        {"focus_line": 0},
        {"focus_line": 7},
        {"focus_kinship": "财运"},
        {"focus_line": 3, "focus_kinship": "妻财"},
        {"timing_days": 1},
        {"focus_line": 3, "timing_days": -1},
        {"focus_line": 3, "timing_days": 61},
        {"focus_line": 3, "timing_days": 1.5},
    ],
)
def test_invalid_or_conflicting_focus_requests_fail_closed(bad):
    with pytest.raises(ValueError):
        build_sixyao_result(**INPUT, gua_code="111111", **bad)


@pytest.mark.parametrize(
    "bad",
    [
        {"focus_line": "3"},
        {"focus_line": False},
        {"timing_days": True},
        {"focus_line": 2, "timing_days": 61},
        {"timing_days": 2},
    ],
)
def test_focus_and_window_request_contract_does_not_coerce(bad):
    with pytest.raises(ValidationError):
        SixYaoRequest.model_validate({**INPUT, **bad})
