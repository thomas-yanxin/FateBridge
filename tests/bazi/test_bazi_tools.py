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


def test_fastmcp_bazi_birth_omits_deleted_snapshot_fields() -> None:
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
        detail="audit",
    )

    assert "snapshot_text" not in payload
    assert "snapshot_export" not in payload
