"""Complete local-date preimages, without choosing an unknown birth time.

TZif transitions and offsets have integer-second resolution (RFC 9636).
Explicit fixed offsets can have microseconds and use interval algebra below.
Python time-zone offsets are strictly between -24 and +24 hours. Therefore
the 72-hour UTC window below contains the complete preimage of a civil date;
each one-second bin has one local date and one declared UTC+08/+09 reference date.
This is exhaustive enumeration, not hourly sampling or a noon assumption.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from io import BytesIO
from typing import Any
from zoneinfo import ZoneInfo

import pytz

from fatebridge.core.sukuyo_integer_transport import (
    integer_transport_diagnostic,
    integer_transport_reading,
)
from fatebridge.utils.civil_time import UTCCalendar
from fatebridge.utils.timezones import parse_timezone_name, timezone_rules_metadata

METHOD = "complete_local_date_preimage_tzif_seconds_v1"
CHINA = timezone(timedelta(hours=8))
_SECOND_MICROSECONDS = 1000000
_DAY_MICROSECONDS = 86400 * _SECOND_MICROSECONDS


def input_timezone_context(zone_text: str) -> dict[str, str]:
    rules = timezone_rules_metadata(zone_text)
    zone = parse_timezone_name(zone_text)
    if isinstance(zone, timezone):
        offset = zone.utcoffset(None)
        assert offset is not None
        ticks = (
            offset.days * 86400 + offset.seconds
        ) * _SECOND_MICROSECONDS + offset.microseconds
        rules["effective_offset_microseconds"] = str(ticks)
    return rules


def input_timezone_reading(context: dict[str, Any]) -> str:
    rules = context.get("input_timezone_rules") or {}
    if rules.get("decimal_hour_rounding") != "nearest_microsecond_ties_even":
        return ""
    represented = ""
    if "effective_offset_microseconds" in rules:
        ticks = int(rules["effective_offset_microseconds"])
        seconds, fraction = divmod(abs(ticks), _SECOND_MICROSECONDS)
        hours, rest = divmod(seconds, 3600)
        minutes, seconds = divmod(rest, 60)
        suffix = f".{fraction:06d}" if fraction else ""
        represented = (
            f"本次表示后的固定偏移为UTC{'-' if ticks < 0 else '+'}"
            f"{hours:02}:{minutes:02}:{seconds:02}{suffix}。"
        )
    return (
        "输入的小数小时偏移按最近微秒表示，恰在中点时取偶数；"
        f"声明的最大表示舍入误差为{rules['rounding_error_bound_seconds']}秒。"
        + represented
        + "历日原像依本次表示后的偏移计算；这不是出生钟时精度、古代平明或原典半日的测量。"
    )


def support_interval_duration_reading(interval: dict[str, Any]) -> str:
    if "start_utc_epoch_microseconds" in interval:
        ticks = int(interval["end_utc_epoch_microseconds"]) - int(
            interval["start_utc_epoch_microseconds"]
        )
    elif "start_utc_epoch_seconds" in interval:
        ticks = (
            interval["end_utc_epoch_seconds"] - interval["start_utc_epoch_seconds"]
        ) * _SECOND_MICROSECONDS
    else:
        elapsed = datetime.fromisoformat(
            interval["end_utc_exclusive"]
        ) - datetime.fromisoformat(interval["start_utc_inclusive"])
        ticks = (
            elapsed.days * 86400 + elapsed.seconds
        ) * _SECOND_MICROSECONDS + elapsed.microseconds
    if ticks <= 0:
        raise ValueError("历日支持区间须有正长度")
    seconds, fraction = divmod(ticks, _SECOND_MICROSECONDS)
    number = f"{seconds}.{fraction:06d}" if fraction else str(seconds)
    return f"该区间长{number}秒，长度不是出生概率。"


def support_completeness_reading(context: dict[str, Any]) -> str:
    """Describe the actual date and mansion coverage without certifying history."""
    if not context.get("calendar_candidates"):
        return ""
    support = context.get("date_support") or {}
    if support.get("complete_under_loaded_timezone_rules") is not True:
        return "本次未确认当地日期原像已完整覆盖，不能将所列分支称为穷尽。"
    text = (
        f"在本次加载的{context['input_timezone']}时区规则和固定{context['calendar_timezone']}参考日界下，"
        + (
            "固定偏移日期的UTC原像已用微秒整数区间代数完整分段；"
            if support.get("enumeration_resolution_seconds") is None
            else "当地日期的UTC原像已完整枚举；"
        )
    )
    if context.get("out_of_range_calendar_dates"):
        text += "仍有范围外参考日，已算出的宿候选不穷尽。"
    elif (
        context["profile_calculation"].get(
            "candidate_set_complete_under_declared_reconstructions"
        )
        is True
    ):
        text += "没有范围外参考日，已列参考日期及宿候选在本次声明档案内完整。"
    else:
        text += "没有范围外参考日，但当前配宿候选完整性仍未确定。"
    if any(
        "start_utc_epoch_microseconds" in row
        for row in support.get("utc_support_intervals", [])
    ):
        text += (
            "微秒epoch端点用十进制整数字符串保存，读取时按整数处理；"
            "古代大数可能超过JavaScript安全整数范围，转成普通Number可能合并一微秒区间的两个端点。"
        )
    if support.get("integer_transport") is not None:
        text += integer_transport_reading(support["integer_transport"])
    return (
        text
        + "这种完整性不穷尽所有古代时制，也不认证历史地方钟时或出生概率。"
        + input_timezone_reading(context)
    )


def _wall_second_support(
    civil: date, zone: ZoneInfo, reference_hours: int
) -> tuple[tuple, int]:
    """Enumerate local seconds and both PEP495 folds without a UTC datetime.

    The lower Python boundary needs UT labels in astronomical year zero.
    PEP495 reverses the offset ordering in gaps, so neither imaginary instant
    is admitted; in folds both real instants are retained. All integer seconds
    are enumerated, rather than assuming the offset at midnight lasts all day.
    """
    anchor = datetime.combine(civil, datetime.min.time())
    ordinal_start = (civil.toordinal() - 1) * 86400
    instants: set[int] = set()
    for second in range(86400):
        local = (anchor + timedelta(seconds=second)).replace(tzinfo=zone)
        before = local.replace(fold=0).utcoffset()
        after = local.replace(fold=1).utcoffset()
        if before is None or after is None:
            raise ValueError("具名时区未提供本地钟时偏移")
        if after > before:
            continue
        for offset in {before, after}:
            instants.add(ordinal_start + second - int(offset.total_seconds()))
    if not instants:
        raise ValueError("所给当地日期在该时区不存在，不能据此排宿；请核对原始日期。")
    intervals = []
    opened = previous = None
    previous_date = None
    for instant in sorted(instants):
        ordinal = (instant + reference_hours * 3600) // 86400 + 1
        target = "0000-12-31" if ordinal == 0 else date.fromordinal(ordinal).isoformat()
        if target != previous_date or previous is None or instant != previous + 1:
            if opened is not None:
                assert previous is not None
                intervals.append((previous_date, opened, previous + 1))
            opened = instant
            previous_date = target
        previous = instant
    assert opened is not None and previous is not None
    intervals.append((previous_date, opened, previous + 1))
    return tuple(intervals), len(instants)


def _integer_utc_label(seconds: int) -> str:
    day, within_day = divmod(seconds, 86400)
    label = "0000-12-31" if day == -1 else date.fromordinal(day + 1).isoformat()
    hour, remaining = divmod(within_day, 3600)
    minute, second = divmod(remaining, 60)
    return f"{label}T{hour:02}:{minute:02}:{second:02}+00:00"


def _fixed_offset_support(
    civil: date, zone: timezone, reference_hours: int
) -> dict[str, Any]:
    """Split the exact UTC preimage of a fixed-offset local date, without a grid.

    Keep the established upper-boundary rejection; this repair does not extend
    any public host calendar. Lower UTC labels may use astronomical year zero.
    """
    if civil >= date(9999, 12, 30):
        raise ValueError("当地日期超出可枚举的民用日期范围。")
    offset = zone.utcoffset(None)
    assert offset is not None
    offset_us = (
        offset.days * 86400 + offset.seconds
    ) * _SECOND_MICROSECONDS + offset.microseconds
    start = (civil.toordinal() - 1) * _DAY_MICROSECONDS - offset_us
    end = start + _DAY_MICROSECONDS
    reference_us = reference_hours * 3600 * _SECOND_MICROSECONDS
    epoch_us = (date(1970, 1, 1).toordinal() - 1) * _DAY_MICROSECONDS
    lower = civil.year == 1 and civil.month == 1 and civil.day <= 2

    def label(ordinal: int) -> str:
        return UTCCalendar(ordinal, 0).isoformat().split("T")[0]

    def utc_label(microseconds: int) -> str:
        day, within_day = divmod(microseconds, _DAY_MICROSECONDS)
        return UTCCalendar(day + 1, within_day).isoformat()

    intervals = []
    opened = start
    while opened < end:
        reference_ordinal = (opened + reference_us) // _DAY_MICROSECONDS + 1
        finish = min(end, reference_ordinal * _DAY_MICROSECONDS - reference_us)
        row: dict[str, Any] = {
            "calendar_date": label(reference_ordinal),
            "start_utc_inclusive": utc_label(opened),
            "end_utc_exclusive": utc_label(finish),
        }
        if opened % _SECOND_MICROSECONDS or finish % _SECOND_MICROSECONDS:
            row.update(
                # Ancient epochs exceed JSON's common IEEE integer range.
                start_utc_epoch_microseconds=str(opened - epoch_us),
                end_utc_epoch_microseconds=str(finish - epoch_us),
            )
        elif lower:
            row.update(
                start_utc_epoch_seconds=(opened - epoch_us) // _SECOND_MICROSECONDS,
                end_utc_epoch_seconds=(finish - epoch_us) // _SECOND_MICROSECONDS,
            )
        intervals.append(row)
        opened = finish
    return {
        "method_id": (
            "complete_fixed_offset_lower_boundary_preimage_v1"
            if lower
            else "complete_fixed_offset_microsecond_preimage_v1"
        ),
        "local_date": civil.isoformat(),
        "possible_calendar_dates": [row["calendar_date"] for row in intervals],
        "utc_support_intervals": intervals,
        "civil_support_seconds": 86400,
        "enumeration_resolution_seconds": None,
        "interval_resolution_microseconds": 1,
        "fixed_offset_microseconds": offset_us,
        "complete_under_loaded_timezone_rules": True,
        "birth_time_imputed": False,
        "calendar_reference_timezone": f"UTC+{reference_hours:02}:00",
        "utc_endpoints_use_astronomical_year_numbering": True,
        "scope": "固定偏移日期按本次解析的偏移用微秒整数区间代数完整分段，未抽样或补造生时。必要时UTC端点用天文年编号0，不启用年0出生日期输入；不代表历史地方时、古代平明或含闰秒的物理时长。",
    }


@lru_cache(maxsize=256)
def _support(date_text: str, zone_text: str, calendar_offset_hours: int = 8) -> tuple:
    civil = date.fromisoformat(date_text)
    zone = parse_timezone_name(zone_text)
    metadata = {"provider": "datetime.timezone", "database": "explicit_fixed_offset"}
    if isinstance(zone, ZoneInfo):
        # Compute and fingerprint the very same bytes. The shared parser may
        # already hold an older cached ZoneInfo if files changed in-process.
        with pytz.open_resource(zone.key) as resource:
            raw = resource.read()
        zone = ZoneInfo.from_file(BytesIO(raw), key=zone.key)
        metadata = {
            "provider": "zoneinfo.from_file",
            "database": "pytz",
            "package_version": pytz.__version__,
            "iana_version": pytz.OLSON_VERSION,
            "tzif_sha256": hashlib.sha256(raw).hexdigest(),
            "future_policy": "extrapolate_pinned_rules_subject_to_legal_changes",
        }
        if civil.year == 1 and civil.month == 1 and civil.day <= 2:
            boundary_intervals, seconds_found = _wall_second_support(
                civil, zone, calendar_offset_hours
            )
            return boundary_intervals, seconds_found, tuple(metadata.items())
    anchor = datetime.combine(civil, datetime.min.time(), tzinfo=timezone.utc)
    try:
        start = anchor - timedelta(days=1)
        end = anchor + timedelta(days=2)
    except OverflowError as error:
        raise ValueError("当地日期超出可枚举的民用日期范围。") from error
    intervals = []
    opened = None
    previous_date = None
    seconds_found = 0
    for second in range(3 * 86400):
        instant = start + timedelta(seconds=second)
        target = None
        local_date: date | None
        try:
            local_date = instant.astimezone(zone).date()
        except OverflowError:
            # A local label outside Python's representable date range cannot
            # equal this representable target civil date. No target branch is
            # discarded, and the full UTC enumeration window is retained.
            local_date = None
        if local_date == civil:
            target = (
                (instant + timedelta(hours=calendar_offset_hours)).date().isoformat()
            )
            seconds_found += 1
        if target != previous_date:
            if opened is not None:
                intervals.append((previous_date, opened, instant))
            opened = instant if target is not None else None
            previous_date = target
    if opened is not None:
        intervals.append((previous_date, opened, end))
    if not intervals:
        raise ValueError("所给当地日期在该时区不存在，不能据此排宿；请核对原始日期。")
    return tuple(intervals), seconds_found, tuple(metadata.items())


def local_date_support(
    date_text: str, zone_text: str, *, calendar_offset_hours: int = 8
) -> dict[str, Any]:
    if type(calendar_offset_hours) is not int or calendar_offset_hours not in (8, 9):
        raise ValueError("宿曜参考历日只支持固定UTC+08或UTC+09")
    civil = date.fromisoformat(date_text)
    zone = parse_timezone_name(zone_text)
    if isinstance(zone, timezone):
        result = _fixed_offset_support(civil, zone, calendar_offset_hours)
        result["input_timezone"] = zone_text
        result["timezone_rules"] = timezone_rules_metadata(zone_text)
        diagnostic = integer_transport_diagnostic(result["utc_support_intervals"])
        if diagnostic is not None:
            result["integer_transport"] = diagnostic
        return result
    intervals, seconds_found, metadata = _support(
        date_text, zone_text, calendar_offset_hours
    )
    result = {
        "method_id": (
            METHOD
            if calendar_offset_hours == 8
            else "complete_local_date_preimage_tzif_seconds_utc09_v1"
        ),
        "local_date": date_text,
        "input_timezone": zone_text,
        "possible_calendar_dates": list(dict.fromkeys(row[0] for row in intervals)),
        "utc_support_intervals": [
            {
                "calendar_date": chinese_date,
                "start_utc_inclusive": (
                    _integer_utc_label(start)
                    if isinstance(start, int)
                    else start.isoformat()
                ),
                "end_utc_exclusive": (
                    _integer_utc_label(end) if isinstance(end, int) else end.isoformat()
                ),
                **(
                    {
                        "start_utc_epoch_seconds": start - 62135596800,
                        "end_utc_epoch_seconds": end - 62135596800,
                    }
                    if isinstance(start, int)
                    else {}
                ),
            }
            for chinese_date, start, end in intervals
        ],
        "civil_support_seconds": seconds_found,
        "enumeration_resolution_seconds": 1,
        "timezone_rules": dict(metadata),
        "complete_under_loaded_timezone_rules": True,
        "birth_time_imputed": False,
        "scope": "遍历当地日期的完整UTC原像，按固定UTC+08历日分段；各区间是可能时刻集合，不是实际出生时刻或概率。按TZif整数秒及Python民用时间处理，不把POSIX秒数当含闰秒的物理时长；未来法定规则可能变更。",
    }
    if calendar_offset_hours == 9:
        result["calendar_reference_timezone"] = "UTC+09:00"
        result["scope"] = (
            "遍历当地日期的完整UTC原像，按显式固定UTC+09日本旧历参考日期分段；不是历史日本地方时、实际出生时刻或概率。使用同份TZif整数秒规则，未来法定规则可能变更。"
        )
    if isinstance(intervals[0][1], int):
        result["method_id"] = "complete_local_wall_second_fold_preimage_v1"
        result["calendar_reference_timezone"] = f"UTC+{calendar_offset_hours:02}:00"
        result["utc_endpoints_use_astronomical_year_numbering"] = True
        result["scope"] = (
            "逐秒遍历所给当地日期，依同份TZif及PEP495排除跳时、保留重复时刻的两次原像，按所声明固定宿主时区分段；"
            "未猜生时或以午夜偏移替换全天规则。UTC端点必要时用天文年编号0，不开放年0出生输入；"
            "这是加载时区规则的前推参考，不是古代地方钟时、平明或桧尾半日重建，也不把POSIX秒数当含闰秒的物理时长。"
        )
    return result
