import json
from typing import Any

import pytest

from fatebridge.application.examples import example_input
from fatebridge.application.execution import execute_with_receipt
from fatebridge.application.response_delivery import deliver_response
from fatebridge.services.bazi import calculate_bazi_birth
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.birth_input import create_person_info
from tests.fixtures.transports import mcp_payload


def _assert_isomorphic_subset(subset: Any, superset: Any, path: str = "$") -> None:
    if isinstance(subset, dict):
        assert isinstance(
            superset, dict
        ), f"{path}: expected dict, got {type(superset)}"
        for key, value in subset.items():
            assert key in superset, f"{path}.{key}: missing from full canonical payload"
            _assert_isomorphic_subset(value, superset[key], f"{path}.{key}")
    elif isinstance(subset, list):
        assert isinstance(
            superset, list
        ), f"{path}: expected list, got {type(superset)}"
        assert len(subset) == len(
            superset
        ), f"{path}: list length mismatch {len(subset)} != {len(superset)}"
        for index, (sub_item, super_item) in enumerate(zip(subset, superset)):
            _assert_isomorphic_subset(sub_item, super_item, f"{path}[{index}]")
    else:
        assert subset == superset, f"{path}: {subset!r} != {superset!r}"


def _business(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k != "run_metadata"}


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
    )

    assert "bazi_birth" in payload
    assert "snapshot_text" not in payload
    assert "snapshot_export" not in payload


def test_solar_terms_for_year_conditional_emission_and_validation() -> None:
    specs = {spec.name: spec for spec in CATALOG}
    spec = specs["solar_terms_for_year"]

    unfiltered = execute_with_receipt(spec, spec.request_model(year=2026))
    unfiltered_default = deliver_response(unfiltered, spec=spec)
    assert "jieqi_year" in unfiltered_default
    assert len(unfiltered_default["jieqi_year"]) == 24
    assert "selected_jieqi" not in unfiltered_default
    assert unfiltered_default["run_metadata"]["omitted_fields"] == [
        "jieqi_year.*.civil_point",
        "jieqi_year.*.comparison_policy",
    ]

    filtered = execute_with_receipt(
        spec, spec.request_model(year=2026, jieqis=["立春", "冬至"])
    )
    filtered_default = deliver_response(filtered, spec=spec)
    filtered_full = deliver_response(filtered, spec=spec, include=["*"])
    assert "selected_jieqi" in filtered_default
    assert len(filtered_default["selected_jieqi"]) == 2
    assert "jieqi_year" not in filtered_default
    assert filtered_default["run_metadata"]["omitted_fields"] == [
        "selected_jieqi.*.civil_point",
        "selected_jieqi.*.comparison_policy",
    ]
    _assert_isomorphic_subset(_business(filtered_default), _business(filtered_full))

    unknown_only = execute_with_receipt(
        spec, spec.request_model(year=2026, jieqis=["不存在节气"])
    )
    unknown_default = deliver_response(unknown_only, spec=spec)
    assert unknown_default["selected_jieqi"] == []
    assert "jieqi_year" not in unknown_default
    assert unknown_default["warnings"]
    assert "omitted_fields" not in unknown_default["run_metadata"]


def test_bazi_timing_with_timelines_slims_nested_nodes_and_stays_isomorphic() -> None:
    specs = {spec.name: spec for spec in CATALOG}
    spec = specs["bazi_timing"]
    inputs = {**(example_input(spec) or {}), "include_timelines": True}
    canonical = execute_with_receipt(spec, spec.request_model(**inputs))

    default_payload = deliver_response(canonical, spec=spec)
    full_payload = deliver_response(canonical, spec=spec, include=["*"])

    _assert_isomorphic_subset(_business(default_payload), _business(full_payload))
    for item in full_payload["analysis_calendar"]["liuyue_timeline"]:
        if "liuyue" in item:
            assert "solar_term_window" not in item["liuyue"]
    for item in full_payload["analysis_calendar"]["jieqi_timeline"]:
        if "liuyue" in item:
            assert set(item["liuyue"]) == {"pillar", "stem", "branch"}
            assert set(item["liuri"]) == {"pillar", "stem", "branch"}


@pytest.mark.parametrize(
    "extra_inputs",
    [
        {"birth_place": "北京"},
        {
            "name": "测试超长名字边界测试",
            "birth_place": "北京市朝阳区",
            "birth_second": 30,
        },
    ],
)
def test_bazi_timing_before_dayun_adversarial_budget_and_isomorphism(
    extra_inputs: dict[str, Any],
) -> None:
    specs = {spec.name: spec for spec in CATALOG}
    spec = specs["bazi_timing"]
    req = spec.request_model(
        birth_year=2024,
        birth_month=2,
        birth_day=4,
        birth_hour=17,
        birth_minute=0,
        birth_longitude=116.4,
        gender="男",
        analysis_year=2025,
        analysis_month=5,
        analysis_day=1,
        analysis_hour=12,
        **extra_inputs,
    )
    canonical = execute_with_receipt(spec, req)

    default_payload = deliver_response(canonical, spec=spec)
    full_payload = deliver_response(canonical, spec=spec, include=["*"])
    default_bytes = len(json.dumps(default_payload, ensure_ascii=False).encode("utf-8"))

    assert (
        default_bytes <= 9500
    ), f"bazi_timing before_dayun exceeded 9500 B: {default_bytes}"
    assert default_payload["dayun"]["status"] == "before_dayun"
    assert len(default_payload["dayun"]["xiaoyun_timeline"]) == 10
    _assert_isomorphic_subset(_business(default_payload), _business(full_payload))

    omitted = default_payload["run_metadata"]["omitted_fields"]
    assert all(path in spec.default_omit for path in omitted)
    assert (
        "analysis_calendar.analysis_date_context.current_solar_term.civil_point"
        in omitted
    )
    assert (
        "analysis_calendar.analysis_date_context.lunar_calendar.previous_jieqi"
        in omitted
    )
    assert (
        "analysis_calendar.analysis_date_context.lunar_calendar.next_jieqi" in omitted
    )

    restored = deliver_response(
        canonical,
        spec=spec,
        include=[
            "analysis_calendar.analysis_date_context.current_solar_term.civil_point",
            "analysis_calendar.analysis_date_context.lunar_calendar.previous_jieqi",
        ],
    )
    ctx = restored["analysis_calendar"]["analysis_date_context"]
    assert "civil_point" in ctx["current_solar_term"]
    assert "previous_jieqi" in ctx["lunar_calendar"]
    assert (
        "analysis_calendar.analysis_date_context.current_solar_term.civil_point"
        not in restored["run_metadata"]["omitted_fields"]
    )
    assert (
        "analysis_calendar.analysis_date_context.lunar_calendar.previous_jieqi"
        not in restored["run_metadata"]["omitted_fields"]
    )
    _assert_isomorphic_subset(_business(restored), _business(full_payload))


def test_bazi_birth_chart_and_monthly_timing_adversarial_budget_and_isomorphism() -> (
    None
):
    specs = {spec.name: spec for spec in CATALOG}
    birth_spec = specs["bazi_birth_chart"]
    birth_req = birth_spec.request_model(
        name="测试超长名字边界",
        birth_year=2024,
        birth_month=2,
        birth_day=4,
        birth_hour=17,
        birth_minute=0,
        birth_second=30,
        birth_place="北京市朝阳区",
        birth_longitude=116.4,
        gender="男",
    )
    birth_canonical = execute_with_receipt(birth_spec, birth_req)
    birth_default = deliver_response(birth_canonical, spec=birth_spec)
    birth_full = deliver_response(birth_canonical, spec=birth_spec, include=["*"])
    birth_bytes = len(json.dumps(birth_default, ensure_ascii=False).encode("utf-8"))

    assert birth_bytes <= 9500, f"bazi_birth_chart exceeded 9500 B: {birth_bytes}"
    assert "shensha_triggered" not in birth_default["bazi_birth"]
    assert (
        "bazi_birth.shensha_triggered"
        in birth_default["run_metadata"]["omitted_fields"]
    )
    _assert_isomorphic_subset(_business(birth_default), _business(birth_full))

    birth_with_triggered = deliver_response(
        birth_canonical, spec=birth_spec, include=["bazi_birth.shensha_triggered"]
    )
    assert "shensha_triggered" in birth_with_triggered["bazi_birth"]
    assert (
        "bazi_birth.shensha_triggered"
        not in birth_with_triggered["run_metadata"]["omitted_fields"]
    )

    monthly_spec = specs["bazi_monthly_timing"]
    monthly_req = monthly_spec.request_model(
        name="测试超长名字边界测试",
        birth_year=1984,
        birth_month=2,
        birth_day=4,
        birth_hour=23,
        birth_minute=30,
        birth_second=15,
        birth_place="北京市朝阳区",
        birth_longitude=116.4,
        gender="男",
        analysis_year=2025,
        analysis_month=5,
        analysis_day=1,
    )
    monthly_canonical = execute_with_receipt(monthly_spec, monthly_req)
    monthly_default = deliver_response(monthly_canonical, spec=monthly_spec)
    monthly_full = deliver_response(monthly_canonical, spec=monthly_spec, include=["*"])
    monthly_bytes = len(json.dumps(monthly_default, ensure_ascii=False).encode("utf-8"))

    assert (
        monthly_bytes <= 9500
    ), f"bazi_monthly_timing exceeded 9500 B: {monthly_bytes}"
    _assert_isomorphic_subset(_business(monthly_default), _business(monthly_full))


@pytest.mark.parametrize(
    ("analysis_year", "birth_timezone"),
    [
        (1900, "Asia/Shanghai"),
        (2024, "America/New_York"),
        (2100, "Asia/Shanghai"),
    ],
)
def test_solar_term_timeline_historical_and_future_years_isomorphic_budget(
    analysis_year: int,
    birth_timezone: str,
) -> None:
    specs = {spec.name: spec for spec in CATALOG}
    spec = specs["solar_term_timeline"]
    ex = example_input(spec) or {}
    req = spec.request_model(
        **{
            **ex,
            "name": "测试超长名字边界测试",
            "birth_place": "北京市朝阳区",
            "birth_second": 15,
            "analysis_year": analysis_year,
            "birth_timezone": birth_timezone,
        }
    )
    canonical = execute_with_receipt(spec, req)
    default_payload = deliver_response(canonical, spec=spec)
    full_payload = deliver_response(canonical, spec=spec, include=["*"])
    default_bytes = len(json.dumps(default_payload, ensure_ascii=False).encode("utf-8"))

    assert (
        default_bytes <= 10240
    ), f"solar_term_timeline {analysis_year} {birth_timezone} exceeded 10 KiB: {default_bytes}"
    _assert_isomorphic_subset(_business(default_payload), _business(full_payload))
    omitted = default_payload["run_metadata"]["omitted_fields"]
    assert isinstance(omitted, list) and len(omitted) > 0
    assert all(path in spec.default_omit for path in omitted)
