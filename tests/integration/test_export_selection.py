"""Explicit export selections never broaden to unrequested sections."""

import pytest
from fastapi.testclient import TestClient

from fatebridge.api import app
from fatebridge.core.export_contracts import normalize_planet_info_setting
from fatebridge.core.export_parser import parse_export_content
from tests.fixtures.surface_payloads import REST_POST_CASES

CONTENT = "[秘密]\nprivate\n\n[公开]\npublic"


def test_unmatched_explicit_export_selection_returns_empty_text() -> None:
    result = parse_export_content(
        technique="generic", content=CONTENT, selected_sections=["不存在"]
    )
    assert result["export_text"] == ""
    assert result["missing_selected_sections"] == ["不存在"]
    assert not any(section["included"] for section in result["sections"])


def test_matching_export_selection_only_contains_requested_section() -> None:
    result = parse_export_content(
        technique="generic", content=CONTENT, selected_sections=["公开"]
    )
    assert result["export_text"] == "[公开]\npublic"


def test_empty_default_selection_keeps_existing_preset_behavior() -> None:
    result = parse_export_content(technique="generic", content=CONTENT)
    assert result["export_text"] == CONTENT


def test_implicit_analysis_receipt_is_in_default_timing_export() -> None:
    receipt = "[分析时刻依据]\n本次分析民用瞬间：2025-02-04T12:37:49.123456+08:00；UTC：2025-02-04T04:37:49.123456+00:00。"
    query = "[查询信息]\n固定快照"
    content = query + "\n\n" + receipt
    for selected in (None, []):
        parsed = parse_export_content(
            technique="liushi_analysis", content=content, selected_sections=selected
        )
        assert parsed["export_text"] == content
        assert parsed["unknown_detected_sections"] == []
        assert (
            parsed["settings_used"]["sections"]["liushi_analysis"][-1] == "分析时刻依据"
        )
    persisted = ["查询信息", "流时信息", "影响摘要", "来源"]
    parsed = parse_export_content(
        technique="liushi_analysis", content=content, selected_sections=persisted
    )
    assert parsed["selected_sections"] == persisted
    assert parsed["export_text"] == query
    absent = parse_export_content(technique="liushi_analysis", content=query)
    assert absent["export_text"] == query
    assert absent["missing_selected_sections"] == [*persisted[1:], "分析时刻依据"]


def test_unmatched_selection_excludes_untitled_preamble() -> None:
    result = parse_export_content(
        technique="generic",
        content="private preamble\n[公开]\npublic",
        selected_sections=["不存在"],
    )
    assert result["export_text"] == ""
    assert not any(section["included"] for section in result["sections"])


def test_matching_selection_excludes_untitled_preamble() -> None:
    result = parse_export_content(
        technique="generic",
        content="private preamble\n[公开]\npublic",
        selected_sections=["公开"],
    )
    assert result["export_text"] == "[公开]\npublic"
    assert result["sections"][0]["included"] is False


def test_no_explicit_selection_preserves_untitled_preamble() -> None:
    content = "private preamble\n[公开]\npublic"
    result = parse_export_content(technique="generic", content=content)
    assert "private preamble" in result["export_text"]


@pytest.mark.parametrize(
    ("technique", "former", "current"),
    [
        ("tongshefa", "互潜", "潜藏"),
        ("tongshefa", "错亲", "亲和"),
        ("tongshefa", "统摄法起盘", "本卦"),
        ("qimen", "八宫", "八宫详解"),
        ("qimen", "演卦", "奇门演卦"),
        ("qimen", "九宫", "九宫方盘"),
        ("qimen", "概览", "盘面要素"),
        ("liureng", "三传(贼克)", "三传"),
        ("sanshiunited", "状态", "概览"),
        ("sanshiunited", "八宫", "八宫详解"),
        ("sanshiunited", "大格", "六壬大格"),
        ("sanshiunited", "小局", "六壬小局"),
        ("sanshiunited", "参考", "六壬参考"),
        ("sanshiunited", "六壬格局概览", "六壬概览"),
        ("sanshiunited", "正北坎宫", "坎一宫"),
        ("sanshiunited", "西南坤宫", "坤二宫"),
        ("sanshiunited", "正东震宫", "震三宫"),
        ("sanshiunited", "东南巽宫", "巽四宫"),
        ("sanshiunited", "西北乾宫", "乾六宫"),
        ("sanshiunited", "正西兑宫", "兑七宫"),
        ("sanshiunited", "东北艮宫", "艮八宫"),
        ("sanshiunited", "正南离宫", "离九宫"),
        ("sixyao", "起卦方式", "卦象"),
        ("sixyao", "卦辞", "卦辞与断语"),
    ],
)
def test_export_titles_match_exactly_without_former_aliases(
    technique: str, former: str, current: str
) -> None:
    result = parse_export_content(
        technique=technique,
        content=f"[{former}]\nformer text\n\n[{current}]\ncurrent text",
        selected_sections=[current],
    )
    assert result["section_titles_detected"] == [former, current]
    assert result["export_text"] == f"[{current}]\ncurrent text"
    assert former in result["unknown_detected_sections"]

    former_selection = parse_export_content(
        technique=technique,
        content=f"[{current}]\ncurrent text",
        selected_sections=[former],
    )
    assert former_selection["selected_sections"] == [former]
    assert former_selection["missing_selected_sections"] == [former]
    assert former_selection["export_text"] == ""


def test_planet_setting_uses_only_current_keys() -> None:
    assert normalize_planet_info_setting({"showHouse": True, "showRuler": True}) == {
        "showHouse": 1,
        "showRuler": 1,
    }
    assert normalize_planet_info_setting({"show_house": True, "show_ruler": True}) == {
        "showHouse": 0,
        "showRuler": 0,
    }


@pytest.mark.parametrize(
    ("path", "technique"),
    [
        ("/api/divination/combine-four-gua", "tongshefa"),
        ("/api/divination/liuyao", "sixyao"),
        ("/api/divination/sanshi", "sanshiunited"),
        ("/api/liuren/chart", "liureng"),
        ("/api/qimen", "qimen"),
    ],
)
def test_current_snapshot_producers_use_registered_section_titles(
    path: str, technique: str
) -> None:
    with TestClient(app) as client:
        response = client.post(path, json=REST_POST_CASES[path]())
    assert response.status_code == 200, response.text
    snapshot_text = response.json()["snapshot_text"]
    exported = parse_export_content(technique=technique, content=snapshot_text)
    assert exported["unknown_detected_sections"] == []
    selected = parse_export_content(
        technique=technique,
        content=snapshot_text,
        selected_sections=exported["section_titles_detected"],
    )
    assert selected["missing_selected_sections"] == []
    assert all(section["included"] for section in selected["sections"])
    assert selected["export_text"] == snapshot_text
