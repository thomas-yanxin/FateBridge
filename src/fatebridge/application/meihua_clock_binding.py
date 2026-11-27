"""Carry original request presence and check the full clock receipt before projection."""

from __future__ import annotations

from datetime import datetime, timedelta
from fractions import Fraction
from typing import TYPE_CHECKING

from fatebridge.application.bindings import ServiceRef, bind_kwargs
from fatebridge.application.tool_spec import (
    Bind,
    BoundServiceCall,
    ResolvedService,
    ServiceResult,
)

if TYPE_CHECKING:
    from pydantic import BaseModel, JsonValue

    from fatebridge.core.requests.divination import MeihuaAnalysisRequest

COMPONENTS = ("year", "month", "day", "hour", "minute", "second")


def supplied_clock_components(request: MeihuaAnalysisRequest) -> list[str]:
    return [
        n
        for n in COMPONENTS
        if "analysis_" + n in request.model_fields_set
        and getattr(request, "analysis_" + n) is not None
    ]


def bind_meihua_time(service: ServiceRef | ResolvedService) -> Bind:
    bind_service = bind_kwargs(service)

    def bind(request: BaseModel) -> BoundServiceCall:
        from fatebridge.core.requests.divination import MeihuaAnalysisRequest

        assert isinstance(request, MeihuaAnalysisRequest)
        bound_call = BoundServiceCall(*bind_service(request))
        bound_call.keyword_arguments["_clock_supplied_components"] = (
            supplied_clock_components(request)
        )
        assert not bound_call.positional_arguments
        return bound_call

    return bind


def require_meihua_clock_binding(
    result: ServiceResult, request: MeihuaAnalysisRequest
) -> None:
    """Check request presence independently of the producer's receipt builder."""
    from fatebridge.core.meihua.casting import parse_meihua_clock_label

    supplied = supplied_clock_components(request)
    omitted = [n for n in ["minute", "second"] if n not in supplied]
    clock = result["meihua"]["calendar_policy"]["civil_clock_resolution"]
    receipt = clock["input_components"]
    expected = {
        "policy_id": "meihua_clock_components_v1",
        "version": "1.0.0",
        "rule_kind": "software_convention",
        "provenance": "bound_request_model_fields_set",
        "supplied_components": supplied,
        "omitted_components": omitted,
        "calculation_defaults": {n: 0 for n in omitted},
        "nominal_civil_datetime": clock["local_datetime"],
        "nominal_instant_utc": clock["instant_utc"],
        "status": "nominal_defaults" if omitted else "optional_components_supplied",
        "uncertainty_interval": None,
        "calendar_stability": "not_assessed",
        "observed_precision_certified": False,
        "original_text_uniquely_prescribes_this_precision": False,
    }
    if receipt.keys() != expected.keys() | {"statement"}:
        raise ValueError("梅花钟时输入记录的版本或字段范围不符")
    for name, value in expected.items():
        if type(receipt[name]) is not type(value) or receipt[name] != value:
            raise ValueError("梅花钟时输入记录与本次请求不符：" + name)
    if any(type(v) is not int for v in receipt["calculation_defaults"].values()):
        raise ValueError("计算补位必须为整数00")
    nominal = parse_meihua_clock_label(clock["local_datetime"])
    values = [getattr(request, "analysis_" + n) for n in COMPONENTS]
    wanted = [v if v is not None else 0 for v in values]
    if [getattr(nominal, n) for n in COMPONENTS] != wanted:
        raise ValueError("梅花名义钟时与本次请求的计算分量不符")
    if (
        result["calendar_context"]["lunar_calendar"]["meihua"]["calendar_policy"][
            "civil_clock_resolution"
        ]
        != clock
    ):
        raise ValueError("梅花钟时输入记录与时间轨迹不符")
    require_meihua_instant_binding(result, request)


def _same_clock_record(actual: JsonValue, expected: JsonValue, path: str) -> None:
    if type(actual) is not type(expected):
        raise ValueError("梅花钟时记录类型不符：" + path)
    if isinstance(expected, dict) and isinstance(actual, dict):
        if set(actual) != set(expected):
            raise ValueError("梅花钟时记录字段不符：" + path)
        for key, value in expected.items():
            _same_clock_record(actual[key], value, path + "." + key)
    elif actual != expected:
        raise ValueError("梅花钟时记录与请求不符：" + path)


def _clock_datetime(value: JsonValue, path: str, *, aware: bool) -> datetime:
    from fatebridge.core.meihua.casting import parse_meihua_clock_label

    if type(value) is not str:
        raise ValueError("梅花时刻须为字符串：" + path)
    parsed = parse_meihua_clock_label(value)
    if (parsed.utcoffset() is not None) is not aware:
        raise ValueError("梅花时刻的时区信息不符：" + path)
    return parsed


def _local_clock_matches(value: JsonValue, expected: datetime, path: str) -> None:
    from fatebridge.utils.civil_clock import utc_instant

    actual = _clock_datetime(value, path, aware=True)
    if (
        actual.replace(tzinfo=None) != expected.replace(tzinfo=None)
        or actual.utcoffset() != expected.utcoffset()
        or utc_instant(actual) != utc_instant(expected)
    ):
        raise ValueError("梅花本地钟时或实际时刻与请求不符：" + path)


def _utc_clock_matches(value: JsonValue, expected: datetime, path: str) -> None:
    from fatebridge.utils.civil_clock import utc_instant

    actual = _clock_datetime(value, path, aware=True)
    if actual.utcoffset() != timedelta(0) or utc_instant(actual) != expected:
        raise ValueError("梅花UTC时刻与请求不符：" + path)


def _elapsed_matches(
    actual: JsonValue, expected: float, path: str, *, tol: float = 1e-4
) -> None:
    if (
        not isinstance(actual, (int, float))
        or isinstance(actual, bool)
        or abs(actual - expected) > tol
    ):
        raise ValueError("梅花UTC钟面间隔不符：" + path)


def _solar_term_day(record: dict[str, JsonValue], path: str) -> Fraction:
    """Derive exact Julian day directly from the returned solar-term timestamp."""
    from fatebridge.utils.civil_time import utc_calendar

    display = record.get("datetime_utc") or record.get("datetime_with_offset")
    if not isinstance(display, str):
        raise ValueError("梅花节气缺少有效时间戳：" + path)
    calendar = utc_calendar(_clock_datetime(display, path, aware=True))
    return calendar.julian_day_exact()


def require_meihua_instant_binding(
    result: ServiceResult, request: MeihuaAnalysisRequest
) -> None:
    """Verify all retained civil clock consumers against the original request."""
    from fatebridge.core.meihua.casting import resolve_meihua_civil_clock
    from fatebridge.utils.civil_clock import format_utc_offset, utc_instant
    from fatebridge.utils.civil_time import utc_calendar
    from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE
    from fatebridge.utils.timezones import timezone_rules_metadata

    wall = datetime(
        request.analysis_year,
        request.analysis_month,
        request.analysis_day,
        request.analysis_hour,
        request.analysis_minute if request.analysis_minute is not None else 0,
        request.analysis_second if request.analysis_second is not None else 0,
    )
    zone = request.analysis_timezone or DEFAULT_BIRTH_TIMEZONE
    offset = request.analysis_utc_offset
    local = resolve_meihua_civil_clock(wall, zone, offset)
    actual_utc = utc_instant(local)
    actual_day = utc_calendar(local).julian_day_exact()
    resolved_offset = local.utcoffset()
    if resolved_offset is None:
        raise ValueError("梅花请求没有有效UTC偏移")
    offset_label = format_utc_offset(resolved_offset)
    supplied = supplied_clock_components(request)
    minute_known, second_known = "minute" in supplied, "second" in supplied
    precision = (
        "supplied_civil_second; historical_offset_seconds_preserved"
        if second_known and minute_known
        else (
            "supplied_civil_minute; historical_offset_seconds_preserved"
            if minute_known
            else (
                "hour_and_second_supplied; minute_00_calculation_default; historical_offset_seconds_preserved"
                if second_known
                else "supplied_civil_hour; minute_and_second_00_calculation_defaults; historical_offset_seconds_preserved"
            )
        )
    )
    clock = result["meihua"]["calendar_policy"]["civil_clock_resolution"]
    _local_clock_matches(clock["local_datetime"], local, "clock.local_datetime")
    _utc_clock_matches(clock["instant_utc"], actual_utc, "clock.instant_utc")
    expected_clock: dict[str, JsonValue] = {
        "ruleset_id": "meihua_civil_clock_v1",
        "version": "1.0.0",
        "rule_kind": "software_convention",
        "method": (
            "explicit_offset_verified_against_timezone"
            if offset is not None
            else "unambiguous_timezone_clock"
        ),
        "timezone": zone,
        "input_utc_offset": offset,
        "resolved_utc_offset": offset_label,
        "local_datetime": clock["local_datetime"],
        "instant_utc": clock["instant_utc"],
        "fold": local.fold,
        "timezone_rules": {
            name: identity for name, identity in timezone_rules_metadata(zone).items()
        },
        "calendar_zone_replaced_by_offset": False,
        "clock_label_precision": precision,
        "original_text_uniquely_prescribes_IANA_or_fold": False,
    }
    if second_known:
        expected_clock["input_second"] = {
            "ruleset_id": "meihua_civil_second_input_v1",
            "version": "1.0.0",
            "rule_kind": "software_convention",
            "value": wall.second,
            "seconds_enter_cast_seed": False,
            "input_precision_certifies_accuracy": False,
            "original_text_uniquely_prescribes_seconds": False,
        }
    _same_clock_record(
        {k: v for k, v in clock.items() if k != "input_components"},
        expected_clock,
        "civil_clock_resolution",
    )
    analysis_context = result["analysis_context"]
    calendar_context = result["calendar_context"]
    for path, value in [
        ("analysis_context.analysis_datetime", analysis_context["analysis_datetime"]),
        ("calendar_context.solar_datetime", calendar_context["solar_datetime"]),
    ]:
        if _clock_datetime(value, path, aware=False) != wall:
            raise ValueError("梅花民用钟面与请求不符：" + path)
    for label, context in [
        ("analysis_context", analysis_context),
        ("calendar_context", calendar_context),
    ]:
        _same_clock_record(context["timezone"], zone, label + ".timezone")
    _same_clock_record(
        analysis_context["civil_utc_offset"],
        offset_label,
        "analysis_context.civil_utc_offset",
    )
    _utc_clock_matches(
        analysis_context["civil_instant_utc"],
        actual_utc,
        "analysis_context.civil_instant_utc",
    )
    for cast in [result["meihua"], calendar_context["lunar_calendar"]["meihua"]]:
        _same_clock_record(
            cast["calendar_policy"]["civil_clock_resolution"],
            clock,
            "calendar_policy.civil_clock_resolution",
        )
    month = calendar_context["bazi_month_boundary"]
    _local_clock_matches(
        month["comparison_datetime"], local, "bazi_month_boundary.comparison_datetime"
    )
    _same_clock_record(
        month["elapsed_basis"],
        "utc_instant_seconds",
        "bazi_month_boundary.elapsed_basis",
    )
    before = _solar_term_day(month["start_term"], "month.start_term")
    after = _solar_term_day(month["next_term"], "month.next_term")
    if not before <= actual_day < after:
        raise ValueError("梅花实际时刻不在所列节月区间")
    elapsed = actual_day - before
    remaining = after - actual_day
    _elapsed_matches(
        month["elapsed_seconds_since_start"],
        float(elapsed * 86400),
        "month.elapsed_since",
    )
    _elapsed_matches(
        month["elapsed_seconds_until_next"],
        float(remaining * 86400),
        "month.elapsed_until",
    )
    _elapsed_matches(
        month["days_since_start"], round(float(elapsed), 4), "month.days_since"
    )
    _elapsed_matches(
        month["days_until_next"], round(float(remaining), 4), "month.days_until"
    )
    previous, upcoming = (
        calendar_context["current_solar_term"],
        calendar_context["next_solar_term"],
    )
    previous_day = _solar_term_day(previous, "current_solar_term")
    next_day = _solar_term_day(upcoming, "next_solar_term")
    if not previous_day <= actual_day < next_day:
        raise ValueError("梅花实际时刻不在所列相邻节气区间")
    _same_clock_record(
        analysis_context["current_jieqi"],
        previous["name"],
        "analysis_context.current_jieqi",
    )
    _same_clock_record(
        analysis_context["next_jieqi"], upcoming["name"], "analysis_context.next_jieqi"
    )
    delta = calendar_context["solar_term_delta"]
    _elapsed_matches(
        delta["days_since_current"],
        round(float(actual_day - previous_day), 4),
        "solar_term_delta.days_since_current",
    )
    _elapsed_matches(
        delta["days_until_next"],
        round(float(next_day - actual_day), 4),
        "solar_term_delta.days_until_next",
    )
