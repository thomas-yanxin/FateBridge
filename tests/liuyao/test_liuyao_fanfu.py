"""Original scan examples distinguish body, region and actual moving lines."""

import json
from pathlib import Path

import pytest

from fatebridge.core.liuyao_fanfu import PROFILE
from fatebridge.core.local_techniques.sixyao import build_sixyao_result
from scripts.liuyao.build_liuyao_fanfu_profile import build

REFERENCE = Path(__file__).parents[1] / "fixtures/liuyao_fanfu_v6"
CASES = json.loads((REFERENCE / "cases.json").read_text(encoding="utf-8"))["cases"]


def test_runtime_rules_match_frozen_scan_clauses_and_pre_implementation_cases():
    assert build() == PROFILE


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_original_body_and_region_cases_without_static_line_transformations(case):
    result = build_sixyao_result(
        date="2000-01-07",
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code=case["base_code"],
        changed_code=case["changed_code"],
    )
    fanfu = result["liuyao_evidence"]["fanfu"]
    assert result["moving_lines"] == case["expected_moving_positions"]
    assert [
        r["region"] for r in fanfu["regions"] if r["nazhi_relation"] == "反吟"
    ] == case["expected_fan_regions"]
    assert [
        r["region"] for r in fanfu["regions"] if r["nazhi_relation"] == "伏吟"
    ] == case["expected_fu_regions"]
    body = fanfu["explicit_body_example"]
    assert (body["kind"] if body else None) == case["expected_body_example"]
    for row in result["lines"]:
        if not row["change"]:
            assert "changed_branch" not in row
    assert [r["position"] for r in fanfu["moving_line_relations"]] == case[
        "expected_moving_positions"
    ]
    assert fanfu["efficacy"] == "requires_focus_strength_and_back_control"


def test_qian_kun_is_not_lost_by_branch_clash_only_detection():
    result = build_sixyao_result(
        date="2000-01-07",
        time="12:00:00",
        gua_code="111111",
        changed_code="000000",
    )
    assert any(p["name"] == "卦体反吟" for p in result["patterns"])


def test_unchanged_trigram_does_not_become_fuyin_due_to_equal_branches():
    result = build_sixyao_result(
        date="2000-01-07",
        time="12:00:00",
        gua_code="011111",
        changed_code="011100",
    )
    inner, outer = result["liuyao_evidence"]["fanfu"]["regions"]
    assert not inner["trigram_changed"] and inner["nazhi_relation"] == "未动"
    assert outer["nazhi_relation"] == "伏吟"


def test_region_chart_comparison_does_not_make_static_branch_an_active_actor():
    result = build_sixyao_result(
        date="2000-01-07",
        time="12:00:00",
        gua_code="000011",
        changed_code="000000",
    )
    fanfu = result["liuyao_evidence"]["fanfu"]
    upper = fanfu["regions"][1]
    assert upper["base_branches"] == ["未", "巳", "卯"]
    assert upper["changed_chart_branches"] == ["丑", "亥", "酉"]
    assert upper["static_comparison_positions"] == [4]
    assert (
        result["lines"][3]["branch"] == "未"
        and "changed_branch" not in result["lines"][3]
    )
    detail = result["liuyao_evidence"]["conditional_analysis"]
    assert not any(
        e["source_kind"] == "changed" and e["source_position"] == 4
        for e in detail["interaction_edges"]
    )


def test_generic_complement_does_not_get_an_invented_source_body_verdict():
    result = build_sixyao_result(
        date="2000-01-07",
        time="12:00:00",
        gua_code="010010",
        changed_code="101101",
    )
    fanfu = result["liuyao_evidence"]["fanfu"]
    assert fanfu["explicit_body_example"] is None
    assert fanfu["body_classification"] == "outside_explicit_example_table"


def test_snapshot_separates_inner_structure_and_keeps_its_scope():
    result = build_sixyao_result(
        date="2000-01-07",
        time="12:00:00",
        gua_code="000010",
        changed_code="011010",
    )
    assert "内卦纳支反吟结构；静爻位置仅作卦盘比较" in result["snapshot_text"]
    assert "外卦纳支反吟结构" not in result["snapshot_text"]
    assert result["liuyao_evidence"]["fanfu"]["scope"] in result["snapshot_text"]
