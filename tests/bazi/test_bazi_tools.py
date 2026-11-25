from fatebridge.services.bazi import calculate_bazi_birth
from fatebridge.utils.birth_input import create_person_info
from tests.fixtures.transports import mcp_payload


def _build_person():
    return create_person_info(
        birth_year=1994,
        birth_month=8,
        birth_day=23,
        birth_hour=14,
        name="张三",
        gender="男",
        birth_place="上海",
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
    )


def test_calculate_bazi_birth_returns_snapshot_sections() -> None:
    result = calculate_bazi_birth(
        _build_person(),
        analysis_year=2028,
        analysis_month=4,
        analysis_day=1,
    )

    assert result["analysis_type"] == "八字命盘"
    assert result["bazi_birth"]["engine"] == "fatebridge-offline"
    assert result["bazi_birth"]["time_algorithm"] in {"直接时间", "真太阳时"}
    assert set(result["bazi_birth"]["four_pillars"]) == {"year", "month", "day", "hour"}
    assert set(result["bazi_birth"]["three_origins"]) == {
        "taiyuan",
        "minggong",
        "shengong",
    }
    assert "structure_profile" in result["bazi_birth"]
    assert "dominant_structure" in result["bazi_birth"]["structure_profile"]
    assert result["bazi_birth"]["timing_overview"]["liunian"]["pillar"] == "戊申"
    assert result["bazi_birth"]["timing_overview"]["liushi"]["pillar"]
    assert "[起盘信息]" in result["snapshot_text"]
    assert "[四柱与三元]" in result["snapshot_text"]
    assert "[流年行运概略]" in result["snapshot_text"]
    assert "[神煞（四柱与三元）]" in result["snapshot_text"]
    assert result["snapshot_export"]["export_text"] == result["snapshot_text"]


def test_calculate_bazi_birth_supports_selected_export_sections() -> None:
    result = calculate_bazi_birth(
        _build_person(),
        analysis_year=2028,
        analysis_month=4,
        analysis_day=1,
        selected_sections=["起盘信息", "流年行运概略"],
    )

    assert result["analysis_type"] == "八字命盘"
    assert result["bazi_birth"]["engine"] == "fatebridge-offline"
    assert result["bazi_birth"]["analysis_date"] == "2028-04-01"
    assert result["bazi_birth"]["timing_overview"]["liuyue"]["pillar"] == "乙卯"
    assert result["bazi_birth"]["timing_overview"]["liuri"]["pillar"] == "丙辰"
    assert result["bazi_birth"]["timing_overview"]["liushi"]["pillar"]
    assert "structure_profile" in result["bazi_birth"]
    assert result["snapshot_export"]["selected_sections"] == [
        "起盘信息",
        "流年行运概略",
    ]
    assert "[起盘信息]" in result["snapshot_export"]["export_text"]
    assert "[流年行运概略]" in result["snapshot_export"]["export_text"]
    assert "[四柱与三元]" not in result["snapshot_export"]["export_text"]


def test_fastmcp_bazi_birth_can_drop_snapshot_text() -> None:
    payload = mcp_payload(
        "bazi_birth_chart",
        birth_year=1994,
        birth_month=8,
        birth_day=23,
        birth_hour=14,
        name="张三",
        gender="男",
        birth_place="上海",
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        analysis_year=2028,
        analysis_month=4,
        analysis_day=1,
        include_snapshot_text=False,
    )

    assert "snapshot_text" not in payload
    assert "snapshot_export" in payload


def test_fastmcp_bazi_birth_can_include_snapshot_text() -> None:
    payload = mcp_payload(
        "bazi_birth_chart",
        birth_year=1994,
        birth_month=8,
        birth_day=23,
        birth_hour=14,
        name="张三",
        gender="男",
        birth_place="上海",
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        analysis_year=2028,
        analysis_month=4,
        analysis_day=1,
        include_snapshot_text=True,
    )

    assert "snapshot_text" in payload
