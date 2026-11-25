"""Verify that REST routes and MCP expose the same calculation facts."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from fatebridge.application.tool_spec import ServiceResult
from fatebridge.core.requests.astrology import (
    AstroChartPolyRequest,
    AstroRelativeFlatRequest,
)
from fatebridge.core.requests.compatibility import TwoPersonCompatibilityRequest
from fatebridge.core.requests.metaphysics import (
    JinkouAnalysisRequest,
    QimenAnalysisRequest,
    TaiyiAnalysisRequest,
)
from fatebridge.core.requests.reference import (
    ExportRegistryRequest,
    KnowledgeReadRequest,
    KnowledgeRegistryRequest,
)
from fatebridge.core.requests.timing import (
    DayunAnalysisRequest,
    LiunianAnalysisRequest,
    LiushiAnalysisRequest,
    TimingAnalysisRequest,
)
from fatebridge.core.requests.western_timing import (
    WesternTimingModuleRequest,
    WesternTimingRequest,
)
from fatebridge.services.astrology import (
    calculate_core_chart_analysis as service_calculate_core_chart_analysis,
)
from fatebridge.services.astrology import (
    calculate_relative_chart_analysis as service_calculate_relative_chart_analysis,
)
from fatebridge.services.run_metadata import resolve_runtime_engine
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.services.western_timing import (
    calculate_western_timing_analysis as service_calculate_western_timing_analysis,
)
from tests.fixtures.surface_payloads import western_payload
from tests.fixtures.transports import mcp_payload
from tests.support.transports import SPECS


def _build_birth_payload(name: str, gender: str, birth_place: str) -> ServiceResult:
    return {
        "name": name,
        "gender": gender,
        "birth_year": 1990,
        "birth_month": 5,
        "birth_day": 15,
        "birth_hour": 10,
        "birth_minute": 30,
        "birth_timezone": "Asia/Shanghai",
        "birth_longitude": 121.4737,
        "birth_place": birth_place,
        "use_true_solar_time": False,
    }


def _build_astro_birth_payload(
    name: str, gender: str, birth_place: str
) -> ServiceResult:
    return {
        **_build_birth_payload(name, gender, birth_place),
        "birth_latitude": 31.2304 if birth_place == "上海" else 39.9042,
    }


def _build_metaphysics_payload() -> ServiceResult:
    return {
        "analysis_year": 2026,
        "analysis_month": 4,
        "analysis_day": 8,
        "analysis_hour": 9,
        "analysis_minute": 30,
        "analysis_timezone": "Asia/Shanghai",
        "analysis_longitude": 121.4737,
        "selected_sections": ["起盘信息", "九宫方盘"],
        "use_true_solar_time": False,
    }


def _payload_without_run_metadata(payload: ServiceResult) -> ServiceResult:
    return {key: value for key, value in payload.items() if key != "run_metadata"}


def _assert_utc_timestamp(value: str) -> None:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None


def _assert_run_metadata(payload: ServiceResult, *, tool_name: str) -> ServiceResult:
    metadata = payload.get("run_metadata")

    assert isinstance(metadata, dict)
    assert set(metadata) >= {
        "run_id",
        "trace_id",
        "tool_name",
        "generated_at",
        "engine",
        "engine_is_approximate",
    }
    assert isinstance(metadata["run_id"], str) and metadata["run_id"]
    assert isinstance(metadata["trace_id"], str) and metadata["trace_id"]
    assert metadata["tool_name"] == tool_name
    assert isinstance(metadata["engine"], str) and metadata["engine"]
    assert isinstance(metadata["engine_is_approximate"], bool)
    _assert_utc_timestamp(metadata["generated_at"])
    assert metadata["engine"] == resolve_runtime_engine(
        _payload_without_run_metadata(payload)
    )

    return metadata


def _assert_transport_parity(
    api_result: ServiceResult, mcp_result: ServiceResult, *, tool_name: str
) -> None:
    assert _payload_without_run_metadata(api_result) == _payload_without_run_metadata(
        mcp_result
    )

    api_metadata = _assert_run_metadata(api_result, tool_name=tool_name)
    mcp_metadata = _assert_run_metadata(mcp_result, tool_name=tool_name)

    assert api_metadata["engine"] == mcp_metadata["engine"]
    assert api_metadata["run_id"] != mcp_metadata["run_id"]
    assert api_metadata["trace_id"] != mcp_metadata["trace_id"]


def _relative_request(mode: str = "Composite") -> AstroRelativeFlatRequest:
    inner = _build_astro_birth_payload("甲", "男", "上海")
    outer = {
        **_build_astro_birth_payload("乙", "女", "北京"),
        "birth_year": 1992,
        "birth_month": 3,
        "birth_day": 2,
        "birth_hour": 8,
        "birth_minute": 18,
        "birth_longitude": 116.4074,
    }
    return AstroRelativeFlatRequest.model_validate(
        {
            f"{side}_{key}": value
            for side, party in (("inner", inner), ("outer", outer))
            for key, value in party.items()
            if key != "gender"
        }
        | {"relative_mode": mode, "hsys": 0, "zodiacal": 0}
    )


PARITY_CASES = [
    pytest.param(
        "export_registry",
        ExportRegistryRequest(technique="qimen"),
        id="export_registry",
    ),
    pytest.param(
        "knowledge_registry",
        KnowledgeRegistryRequest(
            domain="astro",
            selected_sections=["目录概览", "astro"],
        ),
        id="knowledge_registry",
    ),
    pytest.param(
        "knowledge_read",
        KnowledgeReadRequest(
            domain="qimen",
            category="door",
            key="休门",
            selected_sections=["知识正文"],
        ),
        id="knowledge_read",
    ),
    pytest.param(
        "solarreturn",
        WesternTimingModuleRequest(
            **western_payload(),
            selected_sections=["起盘信息", "星盘信息"],
        ),
        id="solarreturn",
    ),
    pytest.param(
        "pdchart", WesternTimingModuleRequest(**western_payload()), id="pdchart"
    ),
    pytest.param(
        "two_person_compatibility",
        TwoPersonCompatibilityRequest(
            person1_name="甲",
            person1_birth_year=1990,
            person1_birth_month=5,
            person1_birth_day=15,
            person1_birth_hour=10,
            person1_gender="男",
            person1_birth_place="上海",
            person1_birth_minute=30,
            person1_birth_timezone="Asia/Shanghai",
            person1_birth_longitude=121.4737,
            person2_name="乙",
            person2_birth_year=1992,
            person2_birth_month=3,
            person2_birth_day=2,
            person2_birth_hour=8,
            person2_gender="女",
            person2_birth_place="北京",
            person2_birth_minute=18,
            person2_birth_timezone="Asia/Shanghai",
            person2_birth_longitude=116.4074,
            relationship_type="marriage",
        ),
        id="two_person_compatibility",
    ),
    pytest.param(
        "astro_chart",
        AstroChartPolyRequest(
            **_build_astro_birth_payload("张三", "男", "上海"),
        ),
        id="chart",
    ),
    pytest.param(
        "astro_relative_chart", _relative_request(), id="astro_relative_chart"
    ),
    pytest.param(
        "timing_analysis",
        TimingAnalysisRequest(
            **_build_birth_payload(name="张三", gender="男", birth_place="上海"),
            analysis_year=2028,
            analysis_month=4,
            analysis_day=6,
            analysis_hour=21,
            analysis_minute=55,
            analysis_age=38,
            selected_sections=["查询信息", "综合影响"],
        ),
        id="timing_analysis",
    ),
    pytest.param(
        "dayun_analysis",
        DayunAnalysisRequest(
            **_build_birth_payload(name="张三", gender="男", birth_place="上海"),
            analysis_age=38,
            selected_sections=["查询信息", "大运信息"],
        ),
        id="dayun_analysis",
    ),
    pytest.param(
        "liunian_analysis",
        LiunianAnalysisRequest(
            **_build_birth_payload(name="张三", gender="男", birth_place="上海"),
            target_year=2028,
        ),
        id="liunian_analysis",
    ),
    pytest.param(
        "liushi_analysis",
        LiushiAnalysisRequest(
            **_build_birth_payload(name="张三", gender="男", birth_place="上海"),
            analysis_year=2028,
            analysis_month=4,
            analysis_day=6,
            analysis_hour=21,
            analysis_minute=55,
            selected_sections=["查询信息", "流时信息"],
        ),
        id="liushi_analysis",
    ),
    pytest.param(
        "qimen",
        QimenAnalysisRequest(
            **{
                **_build_metaphysics_payload(),
                "qimen_options": {"layout": "rotating"},
            }
        ),
        id="qimen",
    ),
    pytest.param(
        "taiyi",
        TaiyiAnalysisRequest(
            **{
                **_build_metaphysics_payload(),
                "gender": "男",
                "selected_sections": ["起盘信息", "太乙"],
            }
        ),
        id="taiyi",
    ),
    pytest.param(
        "jinkou",
        JinkouAnalysisRequest(
            **{
                **_build_metaphysics_payload(),
                "gender": "男",
                "di_fen": "酉",
                "selected_sections": ["起盘信息", "金口诀四位"],
            }
        ),
        id="jinkou",
    ),
]


def test_catalog_descriptors_cover_reference_and_timing_families() -> None:
    assert {item.key for item in CATALOG if item.family == "export"} == {
        "export_registry",
        "export_parse",
    }
    assert {item.key for item in CATALOG if item.family == "knowledge"} == {
        "knowledge_registry",
        "knowledge_read",
    }
    assert {item.key for item in CATALOG if item.family == "western_timing_tool"} >= {
        "solarreturn",
        "pdchart",
    }
    for descriptor in CATALOG:
        if descriptor.family in {"export", "knowledge", "western_timing_tool"}:
            assert descriptor.mcp_name
            assert descriptor.rest_path.startswith("/api/")
            assert descriptor.request_model
            assert descriptor.summary
        else:
            pass


@pytest.mark.parametrize(("tool_key", "calculation_request"), PARITY_CASES)
def test_catalog_tools_api_match_fastmcp_output(
    rest: TestClient, tool_key: str, calculation_request: BaseModel
) -> None:
    """HTTP body binding must preserve calculation facts and emit a separate run receipt."""
    spec = SPECS[tool_key]
    assert spec.rest_path is not None
    response = rest.post(
        spec.rest_path, json=calculation_request.model_dump(mode="json", by_alias=True)
    )
    assert response.status_code == 200, response.text
    api_result = response.json()
    mcp_arguments = calculation_request.model_dump(
        exclude={"qimen_options"} if tool_key == "taiyi" else None
    )
    mcp_result = mcp_payload(spec.tool_name, **mcp_arguments)

    _assert_transport_parity(api_result, mcp_result, tool_name=spec.tool_name)
    if tool_key == "two_person_compatibility":
        assert set(api_result["natal_contexts"]) == {"person1", "person2"}
        assert api_result["cross_chart_relations"]["pairs"]
        assert set(api_result["directional_ten_gods"]) == {
            "person1_to_person2",
            "person2_to_person1",
        }
    elif tool_key == "astro_relative_chart":
        assert api_result["relationship_profile"]["relative_mode_normalized"] == (
            "composite"
        )
        assert api_result["relationship_profile"]["mode_status"] == "implemented"
    else:
        pass


def test_relative_chart_api_rejects_invalid_relative_mode(rest: TestClient) -> None:
    spec = SPECS["astro_relative_chart"]
    assert spec.rest_path is not None
    response = rest.post(
        spec.rest_path,
        json=_relative_request("banana").model_dump(mode="json", by_alias=True),
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "validation_error"
    assert "relative_mode" in response.json()["error"]


def test_selected_sections_only_trim_export_text_not_structured_payload(
    rest: TestClient,
) -> None:
    spec = SPECS["knowledge_read"]
    assert spec.rest_path is not None
    response = rest.post(
        spec.rest_path,
        json={
            "domain": "qimen",
            "category": "door",
            "key": "休门",
            "selected_sections": ["知识正文"],
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()

    assert result["snapshot_export"]["selected_sections"] == ["知识正文"]
    assert "[知识正文]" in result["snapshot_export"]["export_text"]
    assert "[查询信息]" not in result["snapshot_export"]["export_text"]
    assert "[来源]" not in result["snapshot_export"]["export_text"]
    assert "[查询信息]" in result["snapshot_text"]
    assert result["rendered_text"]
    assert result["key"] == "休门"


def test_western_timing_catalog_preserves_service_binding() -> None:
    request = WesternTimingRequest(**western_payload())
    spec = next(spec for spec in CATALOG if spec.key == "western_timing_analysis")
    service, args, kwargs = spec.bind(request)
    assert service is service_calculate_western_timing_analysis
    assert args == ()
    assert kwargs["analysis_year"] == 2025
    assert kwargs["birth_latitude"] == 31.2304


def test_western_timing_module_catalog_selects_requested_technique() -> None:
    modules = (
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
    )
    executed = {"solarreturn", "profection"}
    request = WesternTimingModuleRequest(
        **western_payload(),
        selected_sections=["起盘信息"],
    )
    specs = {spec.key: spec for spec in CATALOG}
    for tool_name in modules:
        service, args, kwargs = specs[tool_name].bind(request)
        assert args == ()
        assert kwargs["selected_sections"] == ["起盘信息"]
        assert kwargs["analysis_day"] == 20
        if tool_name in executed:
            result = service(*args, **kwargs)
            assert "error" not in result
            assert result[tool_name]
            assert result["snapshot_export"]["selected_sections"] == ["起盘信息"]
        else:
            pass


def test_astro_chart_catalog_preserves_service_binding() -> None:
    request = AstroChartPolyRequest(
        **_build_astro_birth_payload("张三", "男", "上海"),
    )
    spec = next(spec for spec in CATALOG if spec.key == "astro_chart")
    service, args, kwargs = spec.bind(request)
    assert service is service_calculate_core_chart_analysis
    assert kwargs["chart_variant"] == "chart"
    assert kwargs["birth_latitude"] == 31.2304


def test_astro_relative_catalog_preserves_service_binding() -> None:
    request = _relative_request()
    spec = SPECS["astro_relative_chart"]
    service, args, kwargs = spec.bind(request)
    assert service is service_calculate_relative_chart_analysis
    assert kwargs["inner_payload"]["birth_latitude"] == 31.2304
    assert kwargs["outer_payload"]["birth_longitude"] == 116.4074
    assert kwargs["relative_mode"] == "Composite"
