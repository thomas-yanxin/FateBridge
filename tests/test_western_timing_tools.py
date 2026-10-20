import pytest

from fatebridge.core.predictive import western_timing as astrology_predictive
from fatebridge.core.requests.western_timing import WesternTimingModuleRequest
from fatebridge.services.western_timing_tools import (
    calculate_decennials,
    calculate_firdaria,
    calculate_givenyear,
    calculate_lunarreturn,
    calculate_pd,
    calculate_pdchart,
    calculate_profection,
    calculate_solararc,
    calculate_solarreturn,
    calculate_transit,
    calculate_zr,
)
from tests.fixtures.surface_payloads import western_payload
from tests.fixtures.transports import mcp_parameters


def test_western_timing_module_request_accepts_selected_sections():
    request = WesternTimingModuleRequest(
        **western_payload(),
        selected_sections=["起盘信息", "星盘信息"],
    )

    payload = request.model_dump()

    assert payload["analysis_year"] == 2025
    assert payload["analysis_month"] == 5
    assert payload["analysis_day"] == 20
    assert payload["selected_sections"] == ["起盘信息", "星盘信息"]
    assert payload["pd_method"] == "astroapp_alchabitius"
    assert payload["pd_time_key"] == "Naibod"


def test_western_return_and_direction_tools_generate_snapshots():
    solarreturn_result = calculate_solarreturn(
        **western_payload(),
        selected_sections=["起盘信息", "星盘信息"],
    )
    lunarreturn_result = calculate_lunarreturn(**western_payload())
    transit_result = calculate_transit(
        **western_payload(),
        selected_sections=["起盘信息", "相位"],
    )
    solararc_result = calculate_solararc(**western_payload())
    givenyear_result = calculate_givenyear(**western_payload())
    profection_result = calculate_profection(**western_payload())

    assert solarreturn_result["analysis_type"] == "西占太阳返照"
    assert solarreturn_result["solarreturn"]["return_datetime"].startswith(
        "2025-05-17T01:47:24+08:00"
    )
    assert solarreturn_result["snapshot_export"]["technique"]["key"] == "solarreturn"
    assert solarreturn_result["snapshot_export"]["selected_sections"] == [
        "起盘信息",
        "星盘信息",
    ]
    assert "[起盘信息]" in solarreturn_result["snapshot_export"]["export_text"]
    assert "[星盘信息]" in solarreturn_result["snapshot_export"]["export_text"]
    assert "[相位]" not in solarreturn_result["snapshot_export"]["export_text"]

    assert lunarreturn_result["analysis_type"] == "西占月亮返照"
    assert lunarreturn_result["lunarreturn"]["return_datetime"].startswith(
        "2025-05-20T01:30:17+08:00"
    )
    assert lunarreturn_result["snapshot_export"]["technique"]["key"] == "lunarreturn"

    assert transit_result["analysis_type"] == "西占行运盘"
    assert transit_result["transit"]["analysis_datetime"].startswith(
        "2025-05-20T15:30:00+08:00"
    )
    assert transit_result["transit"]["location"]["timezone"] == "Asia/Shanghai"
    assert (
        transit_result["transit"]["transit_reference"]["uranus"]["point_label"]
        == "天王星"
    )
    assert transit_result["snapshot_export"]["technique"]["key"] == "transit"
    assert transit_result["snapshot_export"]["selected_sections"] == [
        "起盘信息",
        "相位",
    ]
    assert "[起盘信息]" in transit_result["snapshot_export"]["export_text"]
    assert "[相位]" in transit_result["snapshot_export"]["export_text"]
    assert "[星盘信息]" not in transit_result["snapshot_export"]["export_text"]

    assert solararc_result["analysis_type"] == "西占太阳弧"
    assert solararc_result["solararc"]["arc_degrees"] == pytest.approx(
        33.5458, abs=0.01
    )
    assert solararc_result["snapshot_export"]["technique"]["key"] == "solararc"

    assert givenyear_result["analysis_type"] == "西占指定年盘"
    assert givenyear_result["givenyear"]["ascendant"]["sign"] == "Libra"
    assert len(givenyear_result["givenyear"]["monthly_profections"]) == 12
    assert givenyear_result["snapshot_export"]["technique"]["key"] == "givenyear"

    assert profection_result["analysis_type"] == "西占年小限"
    assert profection_result["profection"]["activated_house"] == 12
    assert profection_result["profection"]["activated_sign"] == "Virgo"
    assert profection_result["snapshot_export"]["technique"]["key"] == "profection"


def test_solarreturn_skips_unrelated_predictive_modules(monkeypatch):
    def _unexpected_transit(*args, **kwargs):
        raise AssertionError("build_transit_payload should not run for solarreturn")

    def _unexpected_primary_directions(*args, **kwargs):
        raise AssertionError(
            "build_primary_directions_payload should not run for solarreturn"
        )

    monkeypatch.setattr(
        astrology_predictive,
        "build_transit_payload",
        _unexpected_transit,
    )
    monkeypatch.setattr(
        astrology_predictive,
        "build_primary_directions_payload",
        _unexpected_primary_directions,
    )

    result = calculate_solarreturn(**western_payload())

    assert "error" not in result
    assert result["analysis_type"] == "西占太阳返照"
    assert result["solarreturn"]["return_datetime"].startswith(
        "2025-05-17T01:47:24+08:00"
    )


def test_primary_direction_and_time_lord_tools_support_selected_sections():
    pd_result = calculate_pd(
        **western_payload(),
        selected_sections=["出生时间", "主/界限法设置", "主/界限法表格"],
    )
    pdchart_result = calculate_pdchart(**western_payload())
    zr_result = calculate_zr(
        **western_payload(),
        selected_sections=["起盘信息", "基于X点推运"],
    )
    firdaria_result = calculate_firdaria(**western_payload())
    decennials_result = calculate_decennials(**western_payload())

    assert pd_result["analysis_type"] == "西占主限"
    assert pd_result["pd"]["method"] == "astroapp_alchabitius"
    assert pd_result["pd"]["time_key"] == "Naibod"
    assert pd_result["snapshot_export"]["technique"]["key"] == "primarydirect"
    assert pd_result["snapshot_export"]["selected_sections"] == [
        "出生时间",
        "主/界限法设置",
        "主/界限法表格",
    ]
    assert "[出生时间]" in pd_result["snapshot_export"]["export_text"]
    assert "[主/界限法设置]" in pd_result["snapshot_export"]["export_text"]
    assert "[主/界限法表格]" in pd_result["snapshot_export"]["export_text"]
    assert "[星盘信息]" not in pd_result["snapshot_export"]["export_text"]

    assert pdchart_result["analysis_type"] == "西占主限法盘"
    assert pdchart_result["pdchart"]["show_pd_bounds"] is True
    assert pdchart_result["snapshot_export"]["technique"]["key"] == "primarydirchart"

    assert zr_result["analysis_type"] == "西占黄道释放"
    assert zr_result["zr"]["spirit"]["current_level_1"]["sign"] == "Aquarius"
    assert zr_result["snapshot_export"]["technique"]["key"] == "zodialrelease"
    assert zr_result["snapshot_export"]["selected_sections"] == [
        "起盘信息",
        "基于X点推运",
    ]
    assert "[星盘信息]" not in zr_result["snapshot_export"]["export_text"]

    assert firdaria_result["analysis_type"] == "西占法达星限"
    assert firdaria_result["firdaria"]["current_major"]["planet"] == "Moon"
    assert firdaria_result["snapshot_export"]["technique"]["key"] == "firdaria"

    assert decennials_result["analysis_type"] == "西占十年星限"
    assert decennials_result["decennials"]["current_level_1"]["planet"] == "Moon"
    assert decennials_result["snapshot_export"]["technique"]["key"] == "decennials"


def test_fastmcp_western_timing_tools_expose_parameters():
    tools = [
        "solarreturn",
        "lunarreturn",
        "transit",
        "solararc",
        "givenyear",
        "profection",
        "pd",
        "pdchart",
        "zr",
        "firdaria",
        "decennials",
    ]

    for tool in tools:
        properties = mcp_parameters(tool)["properties"]
        assert "analysis_year" in properties
        assert "analysis_month" in properties
        assert "analysis_day" in properties
        assert "selected_sections" in properties


def _count_decennial_nodes(node) -> int:
    """Total nodes in a decennial subtree (node + all descendants)."""
    if not node:
        return 0
    total = 1
    for child in node.get("sublevel", []) or []:
        total += _count_decennial_nodes(child)
    return total


def test_decennials_payload_is_bounded_for_agent_consumption():
    """The decennial tree is 4 levels deep (7^4 ≈ 2400 leaves). Serialising it
    whole produced a ~14 MB response that no agent context (or MCP/HTTP
    transport) can hold. The active drill-down is exposed via
    current_level_1/2/3, so the timeline only needs the decade overview and each
    current_level only its immediate children. Guard the bound."""
    import json

    result = calculate_decennials(**western_payload())
    payload = result["decennials"]

    # Whole tool response must stay comfortably agent-readable.
    serialized = json.dumps(result, ensure_ascii=False, default=str)
    assert (
        len(serialized) < 200_000
    ), f"decennials response too large: {len(serialized)}"

    # Timeline is a decade overview: 7 level-1 nodes, no deep subtree.
    timeline = payload["timeline"]
    assert len(timeline) == 7
    for node in timeline:
        assert node["level"] == 1
        assert node.get("sublevel", []) == []

    # The active path is preserved: each current_level carries its immediate
    # children only (one level deep), not the full tree.
    cl1 = payload["current_level_1"]
    cl2 = payload["current_level_2"]
    cl3 = payload["current_level_3"]
    assert cl1 and cl1["level"] == 1
    assert cl2 and cl2["level"] == 2
    assert cl3 and cl3["level"] == 3
    # Immediate children present, but no grandchildren (bounded depth).
    for cur, child_level in ((cl1, 2), (cl2, 3), (cl3, 4)):
        children = cur.get("sublevel", [])
        assert children, "active level should expose its immediate children"
        for child in children:
            assert child["level"] == child_level
            assert child.get("sublevel", []) == []
