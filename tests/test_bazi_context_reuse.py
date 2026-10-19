import asyncio
from datetime import datetime

import pytest

import fatebridge.services.bazi as bazi_module
import fatebridge.services.birth_context as birth_context_module
from fatebridge.analysis.timing_effects import TimingEffectsAnalysis
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.timing import TimingAnalysis
from fatebridge.utils.birth_input import create_person_info
from tests.fixtures.transports import rest_handler


def _build_person():
    return create_person_info(
        birth_year=2028,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        name="性能测试",
        gender="男",
        birth_place="上海",
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4667,
    )


@pytest.mark.parametrize(
    "service",
    [bazi_module.calculate_bazi_birth],
)
def test_bazi_services_reuse_shared_birth_context(monkeypatch, service):
    person = _build_person()
    call_counts = {
        "normalize_birth_time": 0,
        "get_four_pillars": 0,
    }

    original_normalize_birth_time = birth_context_module.normalize_birth_time
    original_get_four_pillars = (
        birth_context_module.BaZiCalendar.get_four_pillars.__func__
    )

    def counting_normalize_birth_time(*args, **kwargs):
        call_counts["normalize_birth_time"] += 1
        return original_normalize_birth_time(*args, **kwargs)

    def counting_get_four_pillars(cls, *args, **kwargs):
        call_counts["get_four_pillars"] += 1
        return original_get_four_pillars(cls, *args, **kwargs)

    monkeypatch.setattr(
        birth_context_module,
        "normalize_birth_time",
        counting_normalize_birth_time,
    )
    monkeypatch.setattr(
        birth_context_module.BaZiCalendar,
        "get_four_pillars",
        classmethod(counting_get_four_pillars),
    )

    result = service(
        person,
        analysis_year=2028,
        analysis_month=4,
        analysis_day=6,
    )

    assert "error" not in result
    assert call_counts["normalize_birth_time"] == 1
    assert call_counts["get_four_pillars"] == 1


def test_analyze_element_strength_changes_skips_full_comprehensive_analysis(
    monkeypatch,
):
    birth_pillars = {
        "year": ("戊", "辰"),
        "month": ("丙", "辰"),
        "day": ("甲", "子"),
        "hour": ("己", "巳"),
    }
    timing_pillars = {
        "liuyue": {"stem": "乙", "branch": "卯"},
        "liuri": {"stem": "丙", "branch": "辰"},
    }

    def fail_if_called(*args, **kwargs):
        raise AssertionError("comprehensive_analysis should not be used here")

    monkeypatch.setattr(
        ElementAnalysis,
        "comprehensive_analysis",
        fail_if_called,
    )

    result = TimingEffectsAnalysis.analyze_element_strength_changes(
        birth_pillars,
        timing_pillars,
    )

    assert result["overall_effect"]
    assert result["element_changes"]["木"]["change_type"] in {"增强", "减弱", "无变化"}


def test_analyze_liuyue_effects_reuses_precomputed_liuyue(monkeypatch):
    birth_pillars = {
        "year": ("戊", "辰"),
        "month": ("丙", "辰"),
        "day": ("甲", "子"),
        "hour": ("己", "巳"),
    }
    target_date = datetime(2028, 4, 6, 21, 55)
    liuyue_info = TimingAnalysis.calculate_liuyue(
        2028,
        4,
        target_day=6,
        timezone_name="Asia/Shanghai",
        target_date=target_date,
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("calculate_liuyue should reuse precomputed liuyue_info")

    monkeypatch.setattr(TimingAnalysis, "calculate_liuyue", fail_if_called)

    result = TimingEffectsAnalysis.analyze_liuyue_effects(
        birth_pillars,
        2028,
        4,
        target_day=6,
        timezone_name="Asia/Shanghai",
        target_date=target_date,
        liuyue_info=liuyue_info,
    )

    assert result["liuyue_info"]["pillar"] == liuyue_info["pillar"]
    assert result["enhanced_summary"]


def test_analyze_liuri_effects_reuses_precomputed_liuri(monkeypatch):
    birth_pillars = {
        "year": ("戊", "辰"),
        "month": ("丙", "辰"),
        "day": ("甲", "子"),
        "hour": ("己", "巳"),
    }
    target_date = datetime(2028, 4, 6, 21, 55)
    liuri_info = TimingAnalysis.calculate_liuri(
        target_date,
        timezone_name="Asia/Shanghai",
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("calculate_liuri should reuse precomputed liuri_info")

    monkeypatch.setattr(TimingAnalysis, "calculate_liuri", fail_if_called)

    result = TimingEffectsAnalysis.analyze_liuri_effects(
        birth_pillars,
        target_date,
        timezone_name="Asia/Shanghai",
        liuri_info=liuri_info,
    )

    assert result["liuri_info"]["pillar"] == liuri_info["pillar"]
    assert result["enhanced_summary"]


@pytest.mark.asyncio
async def test_heavy_api_routes_honor_shared_concurrency_limit(monkeypatch):
    import fatebridge.api as api_module
    from fatebridge.core.requests.timing import TimingAnalysisRequest

    api_module._reset_runtime_state_for_tests()
    api_module.HEAVY_CALC_SEMAPHORE = asyncio.Semaphore(2)
    api_module.HEAVY_CALC_SEMAPHORE_LOOP = None

    in_flight = 0
    max_in_flight = 0

    async def fake_run_in_threadpool(func, *args, **kwargs):
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return {
            "analysis_type": "综合时运分析",
            "summary": "ok",
        }

    monkeypatch.setattr(api_module, "run_in_threadpool", fake_run_in_threadpool)

    request = TimingAnalysisRequest(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=10,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4667,
        birth_place="上海",
        analysis_year=2028,
        analysis_month=4,
        analysis_day=6,
        analysis_hour=21,
        analysis_minute=55,
    )

    results = await asyncio.gather(
        *(rest_handler("timing_analysis")(request) for _ in range(5))
    )

    assert max_in_flight <= 2
    assert all(result["analysis_type"] == "综合时运分析" for result in results)
    assert all("run_metadata" in result for result in results)
