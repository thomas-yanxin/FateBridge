"""Selected scan passages, source examples and counterexamples to overreach."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.liuyao_complex import SCAN
from fatebridge.core.liuyao_judgment import build_conditional_analysis
from fatebridge.core.local_techniques.sixyao import build_sixyao_result
from fatebridge.core.requests.divination import SixYaoRequest
from fatebridge.utils.timezones import parse_timezone_name
from scripts.liuyao.build_liuyao_scan_profile import build
from tests.liuyao.test_liuyao_conditions import mounted

REFERENCE = Path(__file__).parents[1] / "fixtures/liuyao_scan_v3"
CASES = json.loads((REFERENCE / "cases.json").read_text())["cases"]
INPUT = {"date": "2000-01-07", "time": "12:00:00", "zone": "Asia/Shanghai"}


def classical(case, **overrides):
    info, lines = mounted(case["base_code"], case["changed_code"])
    # No civil year is asserted for these printed examples. The clock is
    # test infrastructure only; candidate dates must remain disabled.
    inputs = dict(
        lines=lines,
        hidden=[],
        month=case["month_branch"],
        day_ganzhi=case["day_ganzhi"],
        palace=info["current_palace_element"],
        moment=datetime(2000, 1, 7, 12, tzinfo=parse_timezone_name("Asia/Shanghai")),
        focus_line=case["focus_line"],
        focus_kinship=case.get("focus_kinship"),
        focus_kind=case.get("focus_kind"),
        timing_days=0,
    )
    return build_conditional_analysis(**{**inputs, **overrides})


def test_original_scan_hash_and_reviewed_claims_are_frozen():
    assert build() == SCAN
    freeze = json.loads((REFERENCE / "freeze.json").read_text())
    for name, expected in freeze["sha256"].items():
        assert hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() == expected
    claims = {row["id"]: row for row in SCAN["collations"]}
    assert claims["ji-advance-correction"]["quote"] == "忌神動化回頭生化進神者二也"
    assert "金水土" in claims["spring-residual-correction"]["quote"]
    assert (
        claims["three-harmony-conditions"]["finding"]
        == "selected_scan_collated_with_condition_ambiguity"
    )
    assert (
        claims["four-stages-bounded-table"]["finding"]
        == "scan_also_omits_full_fire_table"
    )


def test_original_changed_official_is_not_the_original_same_position_line():
    case = CASES[0]
    result = classical(case)
    assert {
        k: result["focus"]["selected"][k] for k in case["expected_selected"]
    } == case["expected_selected"]
    assert (
        result["focus"]["roles"][0]["branch"] == case["original_same_position_branch"]
    )
    assert result["focus"]["roles"][0]["role"] != "用神"
    assert result["focus"]["status"] == "explicit_changed_line"
    ambiguous = classical(case, focus_line=None, focus_kind=None)
    assert ambiguous["focus"]["selected"] is None
    assert ambiguous["focus"]["status"] == "multiple_visible_and_changed_candidates"
    assert {c["location"] for c in ambiguous["focus"]["candidates"]} == {
        "visible",
        "changed",
    }


def test_actual_changed_parent_prevents_premature_hidden_search():
    result = build_sixyao_result(
        **INPUT, gua_code="100000", changed_code="100100", focus_kinship="父母"
    )
    assert result["liuyao_evidence"]["hidden_spirits"] == []
    focus = result["liuyao_evidence"]["conditional_analysis"]["focus"]
    assert focus["status"] == "changed_candidates_before_hidden"
    assert [
        (c["location"], c["position"], c["branch"]) for c in focus["candidates"]
    ] == [("changed", 4, "午")]
    selected = build_sixyao_result(
        **INPUT,
        gua_code="100000",
        changed_code="100100",
        focus_kind="changed",
        focus_line=4,
        focus_kinship="父母",
        timing_days=12,
    )
    detail = selected["liuyao_evidence"]["conditional_analysis"]
    assert detail["focus"]["selected"]["branch"] == "午"
    assert all(
        "动逢合" not in w["matched_rules"]
        for w in detail["timing_candidates"]["windows"]
    )
    assert any(
        "变爻逢值" in w["matched_rules"] for w in detail["timing_candidates"]["windows"]
    )


def test_printed_inner_wood_and_outer_metal_keep_scoped_mixed_members():
    case = CASES[1]
    harmony = classical(case)["three_harmony"]
    for pattern, expected in case["expected_formations"].items():
        candidate = next(r for r in harmony["candidates"] if r["pattern"] == pattern)
        assert [m["branch"] for m in candidate["members"]] == expected
        assert [m["location"] for m in candidate["members"]] == [
            "visible",
            "visible",
            "changed",
        ]
        assert candidate["members"][2]["position"] in {
            candidate["members"][0]["position"],
            candidate["members"][1]["position"],
        }
    assert harmony["relations"][0]["relation"] == case["expected_outer_to_inner"]
    outer = next(r for r in harmony["candidates"] if r["pattern"] == "outer_changed")
    assert outer["status"] == "awaiting_fill_or_tomb_review"
    assert any(
        r["branch"] == "丑" and r["condition"] == "旬空待填"
        for r in outer["obstructions"]
    )
    assert "score" not in harmony and "auspicious" not in harmony


def test_static_three_branches_are_not_activated_by_their_names():
    water = next(
        r
        for r in classical(CASES[2])["three_harmony"]["candidates"]
        if r["element"] == "水"
    )
    assert water["active_positions"] == []
    assert water["status"] == CASES[2]["expected_water_status"]


def test_two_active_missing_branch_retains_calendar_completion_condition():
    case = CASES[3]
    result = classical(case)
    water = next(
        r
        for r in result["three_harmony"]["candidates"]
        if r["pattern"] == "two_base_branches_waiting" and r["element"] == "水"
    )
    assert water["group_branches"] == case["expected_missing_group"]
    assert water["missing_branches"] == [case["expected_missing_branch"]]
    assert water["active_positions"] == [2, 5]
    assert water["status"] == "awaiting_missing_branch"
    supplemented = classical(case, day_ganzhi="甲子")
    candidate = next(
        r
        for r in supplemented["three_harmony"]["candidates"]
        if r["candidate_id"] == water["candidate_id"]
    )
    assert candidate["calendar_completions"] == [{"location": "day", "branch": "子"}]
    assert candidate["status"] == "day_month_completion_candidate"


def test_scoped_changed_completion_does_not_keep_claiming_missing_only():
    result = build_sixyao_result(**INPUT, gua_code="100000", changed_code="001000")
    candidates = result["liuyao_evidence"]["conditional_analysis"]["three_harmony"][
        "candidates"
    ]
    water = next(
        r
        for r in candidates
        if r["pattern"] == "two_base_branches_waiting" and r["element"] == "水"
    )
    assert water["completion_paths"]
    assert water["status"] in (
        "completed_by_scoped_changed_path",
        "changed_completion_requires_fill_or_review",
    )
    assert set(water["completion_paths"]) <= {r["candidate_id"] for r in candidates}


def test_flying_and_hidden_conditions_remain_separate_from_final_use():
    # Printed 姤 structure on PDF109: 寅财伏于亥水之下, 飞来生伏.
    result = build_sixyao_result(
        **INPUT,
        gua_code="011111",
        focus_kind="hidden",
        focus_line=2,
        focus_kinship="妻财",
        timing_days=3,
    )
    conditional = result["liuyao_evidence"]["conditional_analysis"]
    hidden = conditional["hidden_conditions"][0]
    assert (hidden["branch"], hidden["flying_branch"]) == ("寅", "亥")
    assert len(hidden["supporting_conditions"]) == 6
    assert len(hidden["obstructing_conditions"]) == 5
    flying = next(
        r
        for r in hidden["supporting_conditions"]
        if r["rule_id"] == "flying_generates_hidden"
    )
    assert flying["matched"] is True
    assert conditional["focus"]["selected"]["location"] == "hidden"
    assert conditional["focus"]["roles"][1]["role"] == "元神"
    assert (
        hidden["adjudication"] == "requires_total_strength_and_interaction_resolution"
    )
    assert (
        conditional["timing_candidates"]["status"]
        == "nonvisible_focus_requires_separate_timing_rules"
    )
    assert conditional["timing_candidates"]["windows"] == []


@pytest.mark.parametrize("kind", ["month", "day"])
def test_explicit_calendar_focus_has_no_fake_line_position(kind):
    result = build_sixyao_result(
        **INPUT, gua_code="111111", focus_kind=kind, timing_days=2
    )
    conditional = result["liuyao_evidence"]["conditional_analysis"]
    assert conditional["focus"]["selected"]["position"] is None
    assert conditional["focus"]["selected"]["location"] == kind
    assert "第None爻" not in result["snapshot_text"]
    assert (
        conditional["timing_candidates"]["status"]
        == "nonvisible_focus_requires_separate_timing_rules"
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"focus_kind": "changed", "focus_line": 2},
        {"focus_kind": "hidden", "focus_line": 6},
        {"focus_kind": "day", "focus_line": 1},
        {
            "focus_kind": "month",
            "focus_kinship": "妻财",
        },  # 乾宫金，丑土为父母，不是妻财
        {"focus_kind": "visible"},
        {"focus_kind": "change"},
    ],
)
def test_bad_or_unavailable_focus_does_not_fall_back_to_another_location(bad):
    with pytest.raises(ValueError):
        build_sixyao_result(**INPUT, gua_code="111111", **bad)


@pytest.mark.parametrize(
    "bad",
    [
        {"focus_kind": "day", "focus_line": 2},
        {"focus_kind": "changed"},
        {"focus_kind": True},
        {"focus_kind": "unknown"},
    ],
)
def test_focus_location_contract_is_strict(bad):
    with pytest.raises(ValidationError):
        SixYaoRequest.model_validate({**INPUT, **bad})


def test_scan_profile_return_is_not_a_mutable_global():
    result = build_sixyao_result(**INPUT, gua_code="111111")
    result["liuyao_evidence"]["conditional_analysis"]["classical_scan"]["source"][
        "sha256"
    ] = "changed"
    assert (
        build_sixyao_result(**INPUT, gua_code="111111")["liuyao_evidence"][
            "conditional_analysis"
        ]["classical_scan"]
        == SCAN
    )


def test_zero_coordinates_are_reported_as_supplied_not_as_missing():
    result = build_sixyao_result(**INPUT, gua_code="111111", lon=0, lat=0)
    assert "经纬度：0 0" in result["snapshot_text"]
    assert result["input_normalized"]["lon"] == 0
    assert result["input_normalized"]["lat"] == 0
