"""Verify that REST routes and MCP expose the same calculation facts."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from fatebridge.application.tool_spec import ServiceResult
from fatebridge.core.requests.astrology import (
    AstroNatalChartRequest,
    AstroRelativeFlatRequest,
)
from fatebridge.core.requests.compatibility import TwoPersonCompatibilityRequest
from fatebridge.core.requests.metaphysics import (
    JinkouAnalysisRequest,
    QimenAnalysisRequest,
    TaiyiAnalysisRequest,
)
from fatebridge.core.requests.reference import (
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
    WesternFirdariaRequest,
    WesternPrimaryDirectionsChartRequest,
    WesternPrimaryDirectionsRequest,
    WesternReturnTimingRequest,
    WesternTimingBaseRequest,
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
from tests.fixtures.surface_payloads import (
    western_base_payload,
    western_payload,
    western_pd_payload,
)
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
        "tool_name",
        "generated_at",
        "engine",
        "engine_is_approximate",
    }
    assert isinstance(metadata["run_id"], str) and metadata["run_id"]
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
        "knowledge_catalog",
        KnowledgeRegistryRequest(domain="astro"),
        id="knowledge_catalog",
    ),
    pytest.param(
        "knowledge_read",
        KnowledgeReadRequest(
            domain="qimen",
            category="door",
            key="休门",
        ),
        id="knowledge_read",
    ),
    pytest.param(
        "solar_return",
        WesternReturnTimingRequest(**western_base_payload()),
        id="solar_return",
    ),
    pytest.param(
        "primary_directions_chart",
        WesternPrimaryDirectionsChartRequest(**western_payload()),
        id="primary_directions_chart",
    ),
    pytest.param(
        "bazi_compatibility",
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
        id="bazi_compatibility",
    ),
    pytest.param(
        "astrology_chart",
        AstroNatalChartRequest(
            **_build_astro_birth_payload("张三", "男", "上海"),
        ),
        id="astrology_chart",
    ),
    pytest.param(
        "relationship_chart", _relative_request(), id="relationship_chart"
    ),
    pytest.param(
        "bazi_timing",
        TimingAnalysisRequest(
            **_build_birth_payload(name="张三", gender="男", birth_place="上海"),
            analysis_year=2028,
            analysis_month=4,
            analysis_day=6,
            analysis_hour=21,
            analysis_minute=55,
            analysis_age=38,
        ),
        id="bazi_timing",
    ),
    pytest.param(
        "bazi_luck_cycles",
        DayunAnalysisRequest(
            **_build_birth_payload(name="张三", gender="男", birth_place="上海"),
            analysis_age=38,
        ),
        id="bazi_luck_cycles",
    ),
    pytest.param(
        "bazi_yearly_timing",
        LiunianAnalysisRequest(
            **_build_birth_payload(name="张三", gender="男", birth_place="上海"),
            analysis_year=2028,
        ),
        id="bazi_yearly_timing",
    ),
    pytest.param(
        "bazi_hourly_timing",
        LiushiAnalysisRequest(
            **_build_birth_payload(name="张三", gender="男", birth_place="上海"),
            analysis_year=2028,
            analysis_month=4,
            analysis_day=6,
            analysis_hour=21,
            analysis_minute=55,
        ),
        id="bazi_hourly_timing",
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
            }
        ),
        id="jinkou",
    ),
]


def test_catalog_descriptors_cover_reference_and_timing_families() -> None:
    assert {item.name for item in CATALOG if item.family == "knowledge"} == {
        "knowledge_catalog",
        "knowledge_read",
    }
    assert {item.name for item in CATALOG if item.family == "western_timing"} >= {
        "western_timing",
        "solar_return",
        "primary_directions_chart",
    }
    for descriptor in CATALOG:
        if descriptor.family in {"knowledge", "western_timing"}:
            assert descriptor.expose_mcp
            assert descriptor.rest_path.startswith("/api/")
            assert descriptor.request_model
            assert descriptor.summary


@pytest.mark.parametrize(("tool_key", "calculation_request"), PARITY_CASES)
def test_catalog_tools_api_match_fastmcp_output(
    rest: TestClient, tool_key: str, calculation_request: BaseModel
) -> None:
    """HTTP body binding must preserve calculation facts and emit a separate run receipt."""
    spec = SPECS[tool_key]
    assert spec.rest_path is not None
    response = rest.post(
        spec.rest_path,
        json=calculation_request.model_dump(mode="json", by_alias=True),
        params={"detail": "audit"},
    )
    assert response.status_code == 200, response.text
    api_result = response.json()
    mcp_arguments = calculation_request.model_dump(
        exclude={"qimen_options"} if tool_key == "taiyi" else None
    )
    mcp_result = mcp_payload(spec.name, **mcp_arguments)

    _assert_transport_parity(api_result, mcp_result, tool_name=spec.name)
    if tool_key == "bazi_compatibility":
        assert set(api_result["natal_contexts"]) == {"person1", "person2"}
        assert api_result["cross_chart_relations"]["pairs"]
        assert set(api_result["directional_ten_gods"]) == {
            "person1_to_person2",
            "person2_to_person1",
        }
    elif tool_key == "relationship_chart":
        assert api_result["relationship_profile"]["relative_mode_normalized"] == (
            "composite"
        )
        assert api_result["relationship_profile"]["mode_status"] == "implemented"


def test_relative_chart_api_rejects_invalid_relative_mode(rest: TestClient) -> None:
    spec = SPECS["relationship_chart"]
    assert spec.rest_path is not None
    response = rest.post(
        spec.rest_path,
        json=_relative_request("banana").model_dump(mode="json", by_alias=True),
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "validation_error"
    assert "relative_mode" in response.json()["error"]


def test_western_timing_catalog_preserves_service_binding() -> None:
    request = WesternTimingRequest(**western_payload())
    spec = next(spec for spec in CATALOG if spec.name == "western_timing")
    service, args, kwargs = spec.bind(request)
    assert service is service_calculate_western_timing_analysis
    assert args == ()
    assert kwargs["analysis_year"] == 2025
    assert kwargs["birth_latitude"] == 31.2304


def test_western_timing_module_catalog_selects_requested_technique() -> None:
    modules = {
        "solar_return": (WesternReturnTimingRequest, western_base_payload()),
        "lunar_return": (WesternReturnTimingRequest, western_base_payload()),
        "transit_chart": (WesternTimingBaseRequest, western_base_payload()),
        "solar_arc": (WesternTimingBaseRequest, western_base_payload()),
        "chart_for_year": (WesternTimingBaseRequest, western_base_payload()),
        "profection": (WesternTimingBaseRequest, western_base_payload()),
        "primary_directions": (WesternPrimaryDirectionsRequest, western_pd_payload()),
        "primary_directions_chart": (
            WesternPrimaryDirectionsChartRequest,
            western_payload(),
        ),
        "zodiacal_releasing": (WesternTimingBaseRequest, western_base_payload()),
        "firdaria": (WesternFirdariaRequest, western_base_payload()),
        "decennials": (WesternTimingBaseRequest, western_base_payload()),
    }
    executed = {"solar_return", "profection"}
    for tool_name, (model, raw_payload) in modules.items():
        request = model(**raw_payload)
        service, args, kwargs = SPECS[tool_name].bind(request)
        assert args == ()
        assert kwargs["analysis_day"] == 20
        if tool_name in executed:
            result = service(*args, **kwargs)
            assert "error" not in result
            assert result[tool_name]


def test_astro_chart_catalog_preserves_service_binding() -> None:
    request = AstroNatalChartRequest(
        **_build_astro_birth_payload("张三", "男", "上海"),
    )
    spec = next(spec for spec in CATALOG if spec.name == "astrology_chart")
    service, args, kwargs = spec.bind(request)
    assert service is service_calculate_core_chart_analysis
    assert kwargs["apparent_model"] == "native"
    assert kwargs["birth_latitude"] == 31.2304


def test_astro_relative_catalog_preserves_service_binding() -> None:
    request = _relative_request()
    spec = SPECS["relationship_chart"]
    service, args, kwargs = spec.bind(request)
    assert service is service_calculate_relative_chart_analysis
    assert kwargs["inner_payload"]["birth_latitude"] == 31.2304
    assert kwargs["outer_payload"]["birth_longitude"] == 116.4074
    assert kwargs["relative_mode"] == "Composite"
