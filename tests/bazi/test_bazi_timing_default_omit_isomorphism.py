"""Isomorphism, default_omit, omitted_fields, and payload budget tests for BaZi & Timing tools."""

from __future__ import annotations

import json
from typing import Any

import pytest

from fatebridge.application.examples import evidence_views, example_input
from fatebridge.application.execution import execute_with_receipt
from fatebridge.application.response_delivery import deliver_response
from fatebridge.services.tool_catalog import CATALOG

BAZI_AND_TIMING_TOOLS = (
    "bazi_overview",
    "bazi_birth_chart",
    "bazi_marriage",
    "bazi_career",
    "bazi_wealth",
    "bazi_health",
    "bazi_children",
    "bazi_education",
    "bazi_personality",
    "bazi_relatives",
    "bazi_romance",
    "compare_bazi_sources",
    "bazi_timing",
    "bazi_luck_cycles",
    "bazi_yearly_timing",
    "bazi_monthly_timing",
    "bazi_daily_timing",
    "bazi_hourly_timing",
    "solar_term_timeline",
    "solar_terms_for_year",
    "lunar_calendar_time",
)

SPECS = {spec.name: spec for spec in CATALOG}


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


@pytest.mark.parametrize("tool_name", BAZI_AND_TIMING_TOOLS)
def test_bazi_and_timing_default_omit_isomorphic_budget_and_views(
    tool_name: str,
) -> None:
    spec = SPECS[tool_name]
    raw_inputs = example_input(spec)
    assert raw_inputs is not None
    req = spec.request_model(**raw_inputs)
    canonical = execute_with_receipt(spec, req)

    default_payload = deliver_response(canonical, spec=spec)
    full_payload = deliver_response(canonical, spec=spec, include=["*"])

    default_bytes = len(json.dumps(default_payload, ensure_ascii=False).encode("utf-8"))
    assert (
        default_bytes <= 10240
    ), f"{tool_name} default exceeded 10 KiB: {default_bytes}"

    _assert_isomorphic_subset(_business(default_payload), _business(full_payload))

    assert "omitted_fields" not in full_payload["run_metadata"]
    if spec.default_omit:
        omitted = default_payload["run_metadata"].get("omitted_fields")
        assert isinstance(omitted, list) and len(omitted) > 0
        assert all(path in spec.default_omit for path in omitted)
    else:
        assert "omitted_fields" not in default_payload["run_metadata"]

    views = evidence_views(spec) or {}
    for view_name in views:
        expanded = deliver_response(canonical, spec=spec, include=[view_name])
        assert "error" not in expanded
        _assert_isomorphic_subset(_business(expanded), _business(full_payload))


def test_compare_bazi_sources_has_no_omitted_fields() -> None:
    spec = SPECS["compare_bazi_sources"]
    assert spec.default_omit == ()
    req = spec.request_model(**(example_input(spec) or {}))
    canonical = execute_with_receipt(spec, req)
    default_payload = deliver_response(canonical, spec=spec)
    full_payload = deliver_response(canonical, spec=spec, include=["*"])
    assert _business(default_payload) == _business(full_payload)
    assert "omitted_fields" not in default_payload["run_metadata"]


def test_bazi_include_evidence_view_and_dotted_path_unomission() -> None:
    overview_spec = SPECS["bazi_overview"]
    overview_canonical = execute_with_receipt(
        overview_spec,
        overview_spec.request_model(**(example_input(overview_spec) or {})),
    )
    overview_with_cal = deliver_response(
        overview_canonical, spec=overview_spec, include=["calendar_context"]
    )
    assert "calendar_context" in overview_with_cal
    assert "patterns" not in overview_with_cal
    assert overview_with_cal["run_metadata"]["omitted_fields"] == ["patterns"]
    overview_with_roots = deliver_response(
        overview_canonical, spec=overview_spec, include=["roots"]
    )
    assert "day_master" in overview_with_roots
    assert overview_with_roots["run_metadata"]["omitted_fields"] == [
        "calendar_context",
        "patterns",
    ]

    birth_spec = SPECS["bazi_birth_chart"]
    birth_canonical = execute_with_receipt(
        birth_spec, birth_spec.request_model(**(example_input(birth_spec) or {}))
    )
    birth_with_cal = deliver_response(
        birth_canonical, spec=birth_spec, include=["calendar_basis"]
    )
    assert "calendar_context" in birth_with_cal["bazi_birth"]
    assert (
        "bazi_birth.calendar_context"
        not in birth_with_cal["run_metadata"]["omitted_fields"]
    )

    career_spec = SPECS["bazi_career"]
    career_canonical = execute_with_receipt(
        career_spec, career_spec.request_model(**(example_input(career_spec) or {}))
    )
    career_with_cal = deliver_response(
        career_canonical, spec=career_spec, include=["calendar_basis"]
    )
    assert "calendar_context" in career_with_cal["career_analysis"]
    assert "omitted_fields" not in career_with_cal["run_metadata"]

    timing_spec = SPECS["bazi_timing"]
    timing_canonical = execute_with_receipt(
        timing_spec, timing_spec.request_model(**(example_input(timing_spec) or {}))
    )
    timing_with_interactions = deliver_response(
        timing_canonical, spec=timing_spec, include=["interactions"]
    )
    assert "interaction_analysis" in timing_with_interactions
    assert (
        "interaction_analysis"
        not in timing_with_interactions["run_metadata"]["omitted_fields"]
    )
    timing_with_cal = deliver_response(
        timing_canonical, spec=timing_spec, include=["calendar_context"]
    )
    assert "calendar_context" in timing_with_cal
    assert "calendar_context" not in timing_with_cal["run_metadata"]["omitted_fields"]


def test_solar_terms_for_year_conditional_emission_and_validation() -> None:
    spec = SPECS["solar_terms_for_year"]

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
    spec = SPECS["bazi_timing"]
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
    spec = SPECS["bazi_timing"]
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
    birth_spec = SPECS["bazi_birth_chart"]
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

    monthly_spec = SPECS["bazi_monthly_timing"]
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
    spec = SPECS["solar_term_timeline"]
    req = (
        spec.request_model(
            **(example_input(spec) or {}),
            name="测试超长名字边界测试",
            birth_place="北京市朝阳区",
            birth_second=15,
            analysis_year=analysis_year,
            birth_timezone=birth_timezone,
        )
        if "name" not in (example_input(spec) or {})
        else spec.request_model(
            **{
                **(example_input(spec) or {}),
                "name": "测试超长名字边界测试",
                "birth_place": "北京市朝阳区",
                "birth_second": 15,
                "analysis_year": analysis_year,
                "birth_timezone": birth_timezone,
            }
        )
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
