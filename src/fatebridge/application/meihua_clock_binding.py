"""Carry original request presence and check the full clock receipt before projection."""

import inspect
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from pydantic import BaseModel

from fatebridge.application.bindings import raw_invoke
from fatebridge.application.tool_spec import Bind, ServiceResult
from fatebridge.core.meihua_clock_iso import parse_meihua_clock_label
from fatebridge.core.meihua_clock_resolution import (
    resolve_meihua_civil_clock as resolve_civil_clock,
)
from fatebridge.utils.civil_clock import (
    format_utc_offset,
    utc_instant,
)
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE
from fatebridge.utils.timezones import timezone_rules_metadata

COMPONENTS = ("year", "month", "day", "hour", "minute", "second")


def supplied_clock_components(request: BaseModel) -> list[str]:
    return [
        n
        for n in COMPONENTS
        if "analysis_" + n in request.model_fields_set
        and getattr(request, "analysis_" + n) is not None
    ]


def meihua_time_invoke(service: Callable[..., ServiceResult]) -> Bind:
    base = raw_invoke(service)

    def bind(
        request: BaseModel,
    ) -> tuple[Callable[..., ServiceResult], tuple[Any, ...], dict[str, Any]]:
        resolved, args, kwargs = base(request)
        if "_clock_supplied_components" in inspect.signature(resolved).parameters:
            kwargs["_clock_supplied_components"] = supplied_clock_components(request)
        return resolved, args, kwargs

    return bind


def require_meihua_clock_binding(result: dict[str, Any], request: BaseModel) -> None:
    """Check request presence independently of the producer's receipt builder."""
    supplied = supplied_clock_components(request)
    omitted = [n for n in ["minute", "second"] if n not in supplied]
    clock = result["meihua"]["calendar_policy"]["civil_clock_resolution"]
    receipt = clock["input_components"]
    labels = {"minute": "分钟", "second": "秒数"}
    statement = (
        f"钟时计算参考为{clock['local_datetime']}；"
        + "、".join(f"{labels[n]}未提供，计算补00" for n in omitted)
        + "。季令等解释仅对应此参考时刻；未知钟时范围未评估，不据补位推定记录精度、误差区间或稳定性。"
        if omitted
        else "已提供分、秒分量；输入位数不认证记录的实际精度，也未声明测量误差区间。"
    )
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
        "statement": statement,
    }
    if set(receipt) != set(expected):
        raise ValueError("梅花钟时输入记录的版本或字段范围不符")
    for name, value in expected.items():
        if (
            name not in receipt
            or type(receipt[name]) is not type(value)
            or receipt[name] != value
        ):
            raise ValueError("梅花钟时输入记录与本次请求不符：" + name)
    if any(type(v) is not int for v in receipt["calculation_defaults"].values()):
        raise ValueError("计算补位必须为整数00")
    nominal = parse_meihua_clock_label(clock["local_datetime"])
    values = [getattr(request, "analysis_" + n, None) for n in COMPONENTS]
    wanted = [v if v is not None else 0 for v in values]
    if [getattr(nominal, n) for n in COMPONENTS] != wanted:
        raise ValueError("梅花名义钟时与本次请求的计算分量不符")
    traces = [
        s["result"]
        for s in result["meihua"]["rule_trace"]
        if s["rule_id"] == "civil_clock_resolution"
    ]
    if (
        traces != [clock]
        or result["calendar_context"]["lunar_calendar"]["meihua"]["calendar_policy"][
            "civil_clock_resolution"
        ]
        != clock
    ):
        raise ValueError("梅花钟时输入记录与时间轨迹不符")
    text = result["interpretation"]["comprehensive_judgement"]
    if result["summary"] != text:
        raise ValueError("梅花摘要与解释不一致")
    if text.count(receipt["statement"]) != (1 if omitted else 0):
        raise ValueError("梅花摘要没有如实说明计算补位")
    scope = result["interpretation"]["evidence_scope"]["clock_input"]
    if (
        scope["path"]
        != "meihua.calendar_policy.civil_clock_resolution.input_components"
        or scope["status"] != receipt["status"]
        or scope["calendar_basis"] != "nominal_reference_only"
        or scope["calendar_stability"] != "not_assessed"
        or scope["observed_precision_certified"] is not False
    ):
        raise ValueError("梅花解释的钟时依据与输入记录不符")
    require_meihua_instant_binding(result, request)


def _same_clock_record(actual: Any, expected: Any, path: str) -> None:
    if type(actual) is not type(expected):
        raise ValueError("梅花钟时记录类型不符：" + path)
    if isinstance(expected, dict):
        if set(actual) != set(expected):
            raise ValueError("梅花钟时记录字段不符：" + path)
        for key, value in expected.items():
            _same_clock_record(actual[key], value, path + "." + key)
    elif actual != expected:
        raise ValueError("梅花钟时记录与请求不符：" + path)


def _clock_datetime(value: Any, path: str, *, aware: bool) -> datetime:
    if type(value) is not str:
        raise ValueError("梅花时刻须为字符串：" + path)
    parsed = parse_meihua_clock_label(value)
    if (parsed.utcoffset() is not None) is not aware:
        raise ValueError("梅花时刻的时区信息不符：" + path)
    return parsed


def _local_clock_matches(value: Any, expected: datetime, path: str) -> None:
    actual = _clock_datetime(value, path, aware=True)
    if (
        actual.replace(tzinfo=None) != expected.replace(tzinfo=None)
        or actual.utcoffset() != expected.utcoffset()
        or utc_instant(actual) != utc_instant(expected)
    ):
        raise ValueError("梅花本地钟时或实际时刻与请求不符：" + path)


def _utc_clock_matches(value: Any, expected: datetime, path: str) -> None:
    actual = _clock_datetime(value, path, aware=True)
    if actual.utcoffset() != timedelta(0) or utc_instant(actual) != expected:
        raise ValueError("梅花UTC时刻与请求不符：" + path)


def _elapsed_matches(actual: Any, expected: float, path: str) -> None:
    # Exclude bool; NaN/inf also cannot equal the finite datetime difference.
    if type(actual) not in {int, float} or actual != expected:
        raise ValueError("梅花UTC钟面间隔不符：" + path)


def require_meihua_instant_binding(result: dict[str, Any], request: BaseModel) -> None:
    """Bind the declared request to every published civil-moment consumer.

    Resolve only the input clock, not the producer's self-reported UTC and not
    astronomy or lunar rules. These are nominal UTC-label differences; datetime
    omits leap seconds, so this is not a TAI/TT elapsed-time certificate.
    """
    values: list[Any] = [getattr(request, "analysis_" + n, None) for n in COMPONENTS]
    wall = datetime(
        values[0],
        values[1],
        values[2],
        values[3],
        values[4] if values[4] is not None else 0,
        values[5] if values[5] is not None else 0,
    )
    zone = getattr(request, "analysis_timezone", None) or DEFAULT_BIRTH_TIMEZONE
    offset = getattr(request, "analysis_utc_offset", None)
    local = resolve_civil_clock(wall, zone, offset)
    actual_utc = utc_instant(local)
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
    expected_clock = {
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
        # Equivalent ISO separators and UTC Z notation retain the same facts.
        "local_datetime": clock["local_datetime"],
        "instant_utc": clock["instant_utc"],
        "fold": local.fold,
        "timezone_rules": timezone_rules_metadata(zone),
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
    ac, cc = result["analysis_context"], result["calendar_context"]
    for path, value in [
        ("analysis_context.analysis_datetime", ac["analysis_datetime"]),
        ("calendar_context.solar_datetime", cc["solar_datetime"]),
    ]:
        if _clock_datetime(value, path, aware=False) != wall:
            raise ValueError("梅花民用钟面与请求不符：" + path)
    for label, context in [("analysis_context", ac), ("calendar_context", cc)]:
        _same_clock_record(context["timezone"], zone, label + ".timezone")
    _same_clock_record(
        ac["civil_utc_offset"], offset_label, "analysis_context.civil_utc_offset"
    )
    _utc_clock_matches(
        ac["civil_instant_utc"], actual_utc, "analysis_context.civil_instant_utc"
    )
    for cast in [result["meihua"], cc["lunar_calendar"]["meihua"]]:
        traces = [
            r for r in cast["rule_trace"] if r["rule_id"] == "civil_clock_resolution"
        ]
        if len(traces) != 1:
            raise ValueError("梅花钟时轨迹缺失或重复")
        _same_clock_record(traces[0]["result"], clock, "rule_trace.result")
        _same_clock_record(
            traces[0]["inputs"],
            {"timezone": zone, "utc_offset": offset},
            "rule_trace.inputs",
        )
    month = cc["bazi_month_boundary"]
    _local_clock_matches(
        month["comparison_datetime"], local, "bazi_month_boundary.comparison_datetime"
    )
    _same_clock_record(
        month["elapsed_basis"],
        "utc_instant_seconds",
        "bazi_month_boundary.elapsed_basis",
    )
    start = _clock_datetime(
        month["start_term"]["datetime_with_offset"], "month.start_term", aware=True
    )
    end = _clock_datetime(
        month["next_term"]["datetime_with_offset"], "month.next_term", aware=True
    )
    before, after = utc_instant(start), utc_instant(end)
    if not before <= actual_utc < after:
        raise ValueError("梅花实际时刻不在所列节月区间")
    elapsed = (actual_utc - before).total_seconds()
    remaining = (after - actual_utc).total_seconds()
    _elapsed_matches(
        month["elapsed_seconds_since_start"], elapsed, "month.elapsed_since"
    )
    _elapsed_matches(
        month["elapsed_seconds_until_next"], remaining, "month.elapsed_until"
    )
    _elapsed_matches(
        month["days_since_start"], round(elapsed / 86400, 4), "month.days_since"
    )
    _elapsed_matches(
        month["days_until_next"], round(remaining / 86400, 4), "month.days_until"
    )
    previous, upcoming = cc["current_solar_term"], cc["next_solar_term"]
    previous_utc = utc_instant(
        _clock_datetime(
            previous["datetime_with_offset"], "current_solar_term", aware=True
        )
    )
    next_utc = utc_instant(
        _clock_datetime(upcoming["datetime_with_offset"], "next_solar_term", aware=True)
    )
    if not previous_utc <= actual_utc < next_utc:
        raise ValueError("梅花实际时刻不在所列相邻节气区间")
    _same_clock_record(
        ac["current_jieqi"], previous["name"], "analysis_context.current_jieqi"
    )
    _same_clock_record(
        ac["next_jieqi"], upcoming["name"], "analysis_context.next_jieqi"
    )
    delta = cc["solar_term_delta"]
    _elapsed_matches(
        delta["days_since_current"],
        round((actual_utc - previous_utc).total_seconds() / 86400, 4),
        "solar_term_delta.days_since_current",
    )
    _elapsed_matches(
        delta["days_until_next"],
        round((next_utc - actual_utc).total_seconds() / 86400, 4),
        "solar_term_delta.days_until_next",
    )
