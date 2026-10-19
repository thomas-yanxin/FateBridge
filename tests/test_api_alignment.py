import asyncio
import json
from datetime import datetime

import pytest
from fastapi import HTTPException

import fatebridge.api as api_module
from fatebridge.core.requests.astrology import (
    AstroChartRequest,
    AstroRelativePartyRequest,
    AstroRelativeRequest,
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
from fatebridge.services.western_timing_tools import calculate_solarreturn
from tests.fixtures.transports import mcp_text, rest_handler

calculate_astro_chart = rest_handler("astro_chart")
calculate_dayun = rest_handler("dayun_analysis")
calculate_liunian = rest_handler("liunian_analysis")
calculate_liushi = rest_handler("liushi_analysis")
calculate_pdchart_module = rest_handler("pdchart")
calculate_relative_chart = rest_handler("astro_relative")
calculate_solarreturn_module = rest_handler("solarreturn")
calculate_timing_analysis = rest_handler("timing_analysis")
calculate_two_person_compatibility = rest_handler("two_person_compatibility")
calculate_western_timing = rest_handler("western_timing_analysis")
export_registry_helper = rest_handler("export_registry")
get_jinkou_analysis = rest_handler("jinkou")
get_qimen_analysis = rest_handler("qimen")
get_taiyi_analysis = rest_handler("taiyi")
knowledge_read_helper = rest_handler("knowledge_read")
knowledge_registry_helper = rest_handler("knowledge_registry")


def _build_birth_payload(name: str, gender: str, birth_place: str) -> dict:
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


def _build_astro_birth_payload(name: str, gender: str, birth_place: str) -> dict:
    return {
        **_build_birth_payload(name, gender, birth_place),
        "birth_latitude": 31.2304 if birth_place == "上海" else 39.9042,
    }


def _build_western_timing_payload() -> dict:
    return {
        "name": "Alice",
        "birth_year": 1990,
        "birth_month": 5,
        "birth_day": 17,
        "birth_hour": 15,
        "birth_minute": 30,
        "birth_place": "上海",
        "birth_timezone": "Asia/Shanghai",
        "birth_longitude": 121.4737,
        "birth_latitude": 31.2304,
        "analysis_year": 2025,
        "analysis_month": 5,
        "analysis_day": 20,
        "pd_method": "astroapp_alchabitius",
        "pd_time_key": "Naibod",
        "pd_aspects": [0, 90, 180],
        "show_pd_bounds": True,
    }


def _build_metaphysics_payload() -> dict:
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


def _payload_without_run_metadata(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if key != "run_metadata"}


def _assert_utc_timestamp(value: str) -> None:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None


def _assert_run_metadata(payload: dict, *, tool_name: str) -> dict:
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
    api_result: dict, mcp_result: dict, *, tool_name: str
) -> None:
    assert _payload_without_run_metadata(api_result) == _payload_without_run_metadata(
        mcp_result
    )

    api_metadata = _assert_run_metadata(api_result, tool_name=tool_name)
    mcp_metadata = _assert_run_metadata(mcp_result, tool_name=tool_name)

    assert api_metadata["engine"] == mcp_metadata["engine"]
    assert api_metadata["run_id"] != mcp_metadata["run_id"]
    assert api_metadata["trace_id"] != mcp_metadata["trace_id"]


def _astro_relative_mcp_kwargs(request: AstroRelativeRequest) -> dict:
    return {
        "inner_birth_year": request.inner.birth_year,
        "inner_birth_month": request.inner.birth_month,
        "inner_birth_day": request.inner.birth_day,
        "inner_birth_hour": request.inner.birth_hour,
        "inner_birth_minute": request.inner.birth_minute,
        "inner_birth_timezone": request.inner.birth_timezone,
        "inner_birth_longitude": request.inner.birth_longitude,
        "inner_birth_latitude": request.inner.birth_latitude,
        "inner_name": request.inner.name,
        "inner_birth_place": request.inner.birth_place,
        "outer_birth_year": request.outer.birth_year,
        "outer_birth_month": request.outer.birth_month,
        "outer_birth_day": request.outer.birth_day,
        "outer_birth_hour": request.outer.birth_hour,
        "outer_birth_minute": request.outer.birth_minute,
        "outer_birth_timezone": request.outer.birth_timezone,
        "outer_birth_longitude": request.outer.birth_longitude,
        "outer_birth_latitude": request.outer.birth_latitude,
        "outer_name": request.outer.name,
        "outer_birth_place": request.outer.birth_place,
        "relative_mode": request.relative_mode,
        "hsys": request.hsys,
        "zodiacal": request.zodiacal,
    }


def _taiyi_mcp_kwargs(request: TaiyiAnalysisRequest) -> dict:
    payload = request.model_dump(exclude={"qimen_options"})
    return payload


PARITY_CASES = [
    (
        "export_registry",
        lambda: ExportRegistryRequest(technique="qimen"),
        export_registry_helper,
        "export_registry",
        lambda request: request.model_dump(),
    ),
    (
        "knowledge_registry",
        lambda: KnowledgeRegistryRequest(
            domain="astro",
            selected_sections=["目录概览", "astro"],
        ),
        knowledge_registry_helper,
        "knowledge_registry",
        lambda request: request.model_dump(),
    ),
    (
        "knowledge_read",
        lambda: KnowledgeReadRequest(
            domain="qimen",
            category="door",
            key="休门",
            selected_sections=["知识正文"],
        ),
        knowledge_read_helper,
        "knowledge_read",
        lambda request: request.model_dump(),
    ),
    (
        "solarreturn",
        lambda: WesternTimingModuleRequest(
            **_build_western_timing_payload(),
            selected_sections=["起盘信息", "星盘信息"],
        ),
        calculate_solarreturn_module,
        "solarreturn",
        lambda request: request.model_dump(),
    ),
    (
        "pdchart",
        lambda: WesternTimingModuleRequest(**_build_western_timing_payload()),
        calculate_pdchart_module,
        "pdchart",
        lambda request: request.model_dump(),
    ),
    (
        "two_person_compatibility",
        lambda: TwoPersonCompatibilityRequest(
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
        calculate_two_person_compatibility,
        "two_person_compatibility",
        lambda request: request.model_dump(),
    ),
    (
        "chart",
        lambda: AstroChartRequest(
            **_build_astro_birth_payload("张三", "男", "上海"),
        ),
        calculate_astro_chart,
        "astro_chart",
        lambda request: request.model_dump(),
    ),
    (
        "astro_relative_chart",
        lambda: AstroRelativeRequest(
            inner=AstroRelativePartyRequest(
                **_build_astro_birth_payload("甲", "男", "上海"),
            ),
            outer=AstroRelativePartyRequest(
                **{
                    **_build_astro_birth_payload("乙", "女", "北京"),
                    "birth_year": 1992,
                    "birth_month": 3,
                    "birth_day": 2,
                    "birth_hour": 8,
                    "birth_minute": 18,
                    "birth_longitude": 116.4074,
                    "birth_latitude": 39.9042,
                }
            ),
            relative_mode="Composite",
            hsys=0,
            zodiacal=0,
        ),
        calculate_relative_chart,
        "astro_relative_chart",
        _astro_relative_mcp_kwargs,
    ),
    (
        "timing_analysis",
        lambda: TimingAnalysisRequest(
            **_build_birth_payload(name="张三", gender="男", birth_place="上海"),
            analysis_year=2028,
            analysis_month=4,
            analysis_day=6,
            analysis_hour=21,
            analysis_minute=55,
            analysis_age=38,
            selected_sections=["查询信息", "综合影响"],
        ),
        calculate_timing_analysis,
        "timing_analysis",
        lambda request: request.model_dump(),
    ),
    (
        "dayun_analysis",
        lambda: DayunAnalysisRequest(
            **_build_birth_payload(name="张三", gender="男", birth_place="上海"),
            analysis_age=38,
            selected_sections=["查询信息", "大运信息"],
        ),
        calculate_dayun,
        "dayun_analysis",
        lambda request: request.model_dump(),
    ),
    (
        "liunian_analysis",
        lambda: LiunianAnalysisRequest(
            **_build_birth_payload(name="张三", gender="男", birth_place="上海"),
            target_year=2028,
        ),
        calculate_liunian,
        "liunian_analysis",
        lambda request: request.model_dump(),
    ),
    (
        "liushi_analysis",
        lambda: LiushiAnalysisRequest(
            **_build_birth_payload(name="张三", gender="男", birth_place="上海"),
            analysis_year=2028,
            analysis_month=4,
            analysis_day=6,
            analysis_hour=21,
            analysis_minute=55,
            selected_sections=["查询信息", "流时信息"],
        ),
        calculate_liushi,
        "liushi_analysis",
        lambda request: request.model_dump(),
    ),
    (
        "qimen",
        lambda: QimenAnalysisRequest(
            **{
                **_build_metaphysics_payload(),
                "qimen_options": {"layout": "rotating"},
            }
        ),
        get_qimen_analysis,
        "qimen",
        lambda request: request.model_dump(),
    ),
    (
        "taiyi",
        lambda: TaiyiAnalysisRequest(
            **{
                **_build_metaphysics_payload(),
                "gender": "男",
                "selected_sections": ["起盘信息", "太乙"],
            }
        ),
        get_taiyi_analysis,
        "taiyi",
        _taiyi_mcp_kwargs,
    ),
    (
        "jinkou",
        lambda: JinkouAnalysisRequest(
            **{
                **_build_metaphysics_payload(),
                "gender": "男",
                "di_fen": "酉",
                "selected_sections": ["起盘信息", "金口诀四位"],
            }
        ),
        get_jinkou_analysis,
        "jinkou",
        lambda request: request.model_dump(),
    ),
]


def test_alignment_request_models_accept_fastmcp_offline_fields():
    compatibility_request = TwoPersonCompatibilityRequest(
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
    )
    timing_request = TimingAnalysisRequest(
        **_build_birth_payload(name="张三", gender="男", birth_place="上海"),
        analysis_year=2028,
        analysis_month=4,
        analysis_day=6,
        analysis_hour=21,
        analysis_minute=55,
        analysis_age=38,
        selected_sections=["查询信息", "综合影响"],
    )
    dayun_request = DayunAnalysisRequest(
        **_build_birth_payload(name="张三", gender="男", birth_place="上海"),
        analysis_age=38,
        selected_sections=["查询信息", "大运信息"],
    )
    liunian_request = LiunianAnalysisRequest(
        **_build_birth_payload(name="张三", gender="男", birth_place="上海"),
        target_year=2028,
    )
    liushi_request = LiushiAnalysisRequest(
        **_build_birth_payload(name="张三", gender="男", birth_place="上海"),
        analysis_year=2028,
        analysis_month=4,
        analysis_day=6,
        analysis_hour=21,
        analysis_minute=55,
        selected_sections=["查询信息", "流时信息"],
    )

    compatibility_payload = compatibility_request.model_dump()
    timing_payload = timing_request.model_dump()
    dayun_payload = dayun_request.model_dump()
    liunian_payload = liunian_request.model_dump()
    liushi_payload = liushi_request.model_dump()

    assert compatibility_payload["person1_birth_minute"] == 30
    assert compatibility_payload["person2_birth_timezone"] == "Asia/Shanghai"
    assert compatibility_payload["person2_birth_longitude"] == 116.4074
    assert compatibility_payload["relationship_type"] == "marriage"
    assert timing_payload["analysis_year"] == 2028
    assert timing_payload["analysis_month"] == 4
    assert timing_payload["analysis_day"] == 6
    assert timing_payload["analysis_hour"] == 21
    assert timing_payload["analysis_minute"] == 55
    assert timing_payload["analysis_age"] == 38
    assert timing_payload["selected_sections"] == ["查询信息", "综合影响"]
    assert dayun_payload["gender"] == "男"
    assert dayun_payload["analysis_age"] == 38
    assert dayun_payload["selected_sections"] == ["查询信息", "大运信息"]
    assert liunian_payload["target_year"] == 2028
    assert liushi_payload["analysis_year"] == 2028
    assert liushi_payload["analysis_month"] == 4
    assert liushi_payload["analysis_day"] == 6
    assert liushi_payload["analysis_hour"] == 21
    assert liushi_payload["analysis_minute"] == 55
    assert liushi_payload["selected_sections"] == ["查询信息", "流时信息"]


def test_catalog_descriptors_cover_reference_and_timing_families():
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
            assert descriptor.mcp_name == descriptor.key
            assert descriptor.rest_path.startswith("/api/")
            assert descriptor.request_model
            assert descriptor.summary


@pytest.mark.parametrize(
    ("tool_name", "request_factory", "api_handler", "mcp_tool", "mcp_kwargs_builder"),
    PARITY_CASES,
    ids=[case[0] for case in PARITY_CASES],
)
def test_catalog_tools_api_match_fastmcp_output(
    tool_name,
    request_factory,
    api_handler,
    mcp_tool,
    mcp_kwargs_builder,
):
    request = request_factory()

    api_result = asyncio.run(api_handler(request))
    mcp_result = json.loads(mcp_text(mcp_tool, **mcp_kwargs_builder(request)))

    _assert_transport_parity(api_result, mcp_result, tool_name=tool_name)


def test_two_person_compatibility_exposes_structured_pattern_fields():
    request = TwoPersonCompatibilityRequest(
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
    )

    api_result = asyncio.run(calculate_two_person_compatibility(request))
    pattern_synergy = api_result["detailed_analysis"]["pattern_synergy"]
    favorable_synergy = api_result["detailed_analysis"]["favorable_synergy"]
    ten_gods_relationship = api_result["detailed_analysis"]["ten_gods_relationship"]

    assert "supportive_patterns" in pattern_synergy
    assert "tension_patterns" in pattern_synergy
    assert "risk_patterns" in pattern_synergy
    assert "score_basis" in pattern_synergy
    assert "score_basis" in favorable_synergy
    assert "useful_ten_gods_support" in favorable_synergy
    assert "useful_ten_gods_support" in ten_gods_relationship
    assert "risk_reasons" in ten_gods_relationship


def test_relative_chart_api_keeps_public_modes_implemented():
    request = AstroRelativeRequest(
        inner=AstroRelativePartyRequest(
            **_build_astro_birth_payload("甲", "男", "上海"),
        ),
        outer=AstroRelativePartyRequest(
            **{
                **_build_astro_birth_payload("乙", "女", "北京"),
                "birth_year": 1992,
                "birth_month": 3,
                "birth_day": 2,
                "birth_hour": 8,
                "birth_minute": 18,
                "birth_longitude": 116.4074,
                "birth_latitude": 39.9042,
            }
        ),
        relative_mode="Composite",
        hsys=0,
        zodiacal=0,
    )

    result = asyncio.run(calculate_relative_chart(request))

    assert result["relationship_profile"]["relative_mode_normalized"] == "composite"
    assert result["relationship_profile"]["mode_status"] == "implemented"
    _assert_run_metadata(result, tool_name="astro_relative_chart")


def test_relative_chart_api_rejects_invalid_relative_mode():
    request = AstroRelativeRequest(
        inner=AstroRelativePartyRequest(
            **_build_astro_birth_payload("甲", "男", "上海"),
        ),
        outer=AstroRelativePartyRequest(
            **{
                **_build_astro_birth_payload("乙", "女", "北京"),
                "birth_year": 1992,
                "birth_month": 3,
                "birth_day": 2,
                "birth_hour": 8,
                "birth_minute": 18,
                "birth_longitude": 116.4074,
                "birth_latitude": 39.9042,
            }
        ),
        relative_mode="banana",
        hsys=0,
        zodiacal=0,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(calculate_relative_chart(request))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error_code"] == "validation_error"
    assert "relative_mode" in exc_info.value.detail["error"]


def test_selected_sections_only_trim_export_text_not_structured_payload():
    request = KnowledgeReadRequest(
        domain="qimen",
        category="door",
        key="休门",
        selected_sections=["知识正文"],
    )

    result = asyncio.run(knowledge_read_helper(request))

    assert result["snapshot_export"]["selected_sections"] == ["知识正文"]
    assert "[知识正文]" in result["snapshot_export"]["export_text"]
    assert "[查询信息]" not in result["snapshot_export"]["export_text"]
    assert "[来源]" not in result["snapshot_export"]["export_text"]
    assert "[查询信息]" in result["snapshot_text"]
    assert result["rendered_text"]
    assert result["key"] == "休门"


def _offloaded_service(captured):
    from fatebridge.application.execution import execute_tool

    assert captured["func"] is execute_tool
    spec, request = captured["args"]
    return spec.bind(request)


def test_western_timing_api_offloads_calculation_to_threadpool(monkeypatch):
    expected = {"analysis_type": "西占推运与返照分析", "summary": "ok"}
    captured = {}

    async def fake_run_in_threadpool(func, *args, **kwargs):
        captured["func"] = func
        captured["args"] = args
        captured["kwargs"] = kwargs
        return expected

    monkeypatch.setattr(
        api_module,
        "run_in_threadpool",
        fake_run_in_threadpool,
        raising=False,
    )

    request = WesternTimingRequest(**_build_western_timing_payload())
    result = asyncio.run(calculate_western_timing(request))

    assert _payload_without_run_metadata(result) == expected
    _assert_run_metadata(result, tool_name="western_timing_analysis")
    service, args, kwargs = _offloaded_service(captured)
    assert service is service_calculate_western_timing_analysis
    assert args == ()
    assert kwargs["analysis_year"] == 2025
    assert kwargs["birth_latitude"] == 31.2304


def test_western_timing_module_api_offloads_calculation_to_threadpool(monkeypatch):
    expected = {"analysis_type": "西占太阳返照", "summary": "ok"}
    captured = {}

    async def fake_run_in_threadpool(func, *args, **kwargs):
        captured["func"] = func
        captured["args"] = args
        captured["kwargs"] = kwargs
        return expected

    monkeypatch.setattr(
        api_module,
        "run_in_threadpool",
        fake_run_in_threadpool,
        raising=False,
    )

    request = WesternTimingModuleRequest(
        **_build_western_timing_payload(),
        selected_sections=["起盘信息"],
    )
    result = asyncio.run(calculate_solarreturn_module(request))

    assert _payload_without_run_metadata(result) == expected
    _assert_run_metadata(result, tool_name="solarreturn")
    service, args, kwargs = _offloaded_service(captured)
    assert service is calculate_solarreturn
    assert args == ()
    assert kwargs["selected_sections"] == ["起盘信息"]
    assert kwargs["analysis_day"] == 20


def test_astro_chart_api_offloads_calculation_to_threadpool(monkeypatch):
    expected = {"analysis_type": "西洋占星本命盘", "summary": "ok"}
    captured = {}

    async def fake_run_in_threadpool(func, *args, **kwargs):
        captured["func"] = func
        captured["args"] = args
        captured["kwargs"] = kwargs
        return expected

    monkeypatch.setattr(
        api_module,
        "run_in_threadpool",
        fake_run_in_threadpool,
        raising=False,
    )

    request = AstroChartRequest(
        **_build_astro_birth_payload("张三", "男", "上海"),
    )
    result = asyncio.run(calculate_astro_chart(request))

    assert _payload_without_run_metadata(result) == expected
    _assert_run_metadata(result, tool_name="chart")
    service, args, kwargs = _offloaded_service(captured)
    assert service is service_calculate_core_chart_analysis
    assert kwargs["chart_variant"] == "chart"
    assert kwargs["birth_latitude"] == 31.2304


def test_astro_relative_api_offloads_calculation_to_threadpool(monkeypatch):
    expected = {"analysis_type": "关系盘", "summary": "ok"}
    captured = {}

    async def fake_run_in_threadpool(func, *args, **kwargs):
        captured["func"] = func
        captured["args"] = args
        captured["kwargs"] = kwargs
        return expected

    monkeypatch.setattr(
        api_module,
        "run_in_threadpool",
        fake_run_in_threadpool,
        raising=False,
    )

    request = AstroRelativeRequest(
        inner=AstroRelativePartyRequest(
            **_build_astro_birth_payload("甲", "男", "上海"),
        ),
        outer=AstroRelativePartyRequest(
            **{
                **_build_astro_birth_payload("乙", "女", "北京"),
                "birth_year": 1992,
                "birth_month": 3,
                "birth_day": 2,
                "birth_hour": 8,
                "birth_minute": 18,
                "birth_longitude": 116.4074,
                "birth_latitude": 39.9042,
            }
        ),
        relative_mode="Composite",
        hsys=0,
        zodiacal=0,
    )
    result = asyncio.run(calculate_relative_chart(request))

    assert _payload_without_run_metadata(result) == expected
    _assert_run_metadata(result, tool_name="astro_relative_chart")
    service, args, kwargs = _offloaded_service(captured)
    assert service is service_calculate_relative_chart_analysis
    assert kwargs["inner_payload"]["birth_latitude"] == 31.2304
    assert kwargs["outer_payload"]["birth_longitude"] == 116.4074
    assert kwargs["relative_mode"] == "Composite"
