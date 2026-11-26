"""Consolidated Sukuyo host calendars, T1299 fullmoon calculation, Ryohan/Kuyou day evidence, and rulesets."""

from __future__ import annotations

import json
from bisect import bisect_right
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any, Sequence, cast
from zoneinfo import ZoneInfo

import pytz
from lunardate import LunarDate
from pydantic_core import PydanticCustomError

from fatebridge.core.almanac import localize_datetime
from fatebridge.core.sukuyo.sanjiu import (
    DistanceRule,
    assess_ryohan,
    kuyou_annual_star,
    personal_day_evidence,
)
from fatebridge.core.sukuyo.sukuyo_calendar_basis import (
    DEFAULT_CALENDAR_BASIS,
    HISTORICAL_CALENDAR_BASIS,
    JAPANESE_CALENDAR_BASES,
    JAPANESE_CALENDAR_BASIS,
)
from fatebridge.core.sukuyo.texts import (
    ALIASES,
    SU27_ORDER,
    assess_activity,
    calendar_day_evidence,
    clothing_reference,
    conjunction_doctrine,
    load_source,
    lower_mansion_evidence,
    lower_methods_evidence,
    palace_reference,
    six_palace_reference,
    special_day_evidence,
    taibai_direction_reference,
    travel_direction_evidence,
)
from fatebridge.utils.civil_time import UTCCalendar
from fatebridge.utils.errors import UNRESOLVED_OFFSET_MESSAGE
from fatebridge.utils.iso_clock import parse_microsecond_iso_datetime
from fatebridge.utils.timezones import (
    is_unspecified_local_time,
    parse_timezone_name,
    timezone_rules_metadata,
    validate_local_clock,
)

DEFAULT_PROFILE = "t1299_fullmoon27"
HINOO_PROFILE = "hinoo_t1299_host27"
PROFILES = (DEFAULT_PROFILE, HINOO_PROFILE)
DAY_PARTS = ("first_half", "second_half")
SECOND_MICROSECONDS = 1_000_000
DAY_MICROSECONDS = 86_400 * SECOND_MICROSECONDS

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
PROFILES_SOURCE = _DATA_DIR / "sukuyo_t1299_calendar_profiles.json"
CORRECTIONS_SOURCE = _DATA_DIR / "sukuyo_calendar_corrections.json"
HUTIME_SOURCE = _DATA_DIR / "sukuyo_japanese_daily_v1.json"
NAOJ_SOURCE = _DATA_DIR / "sukuyo_japanese_historical_v1.json"

_MANSION_NATURES: dict[str, str] = {
    m: nature
    for nature, members in (
        ("安重", "毕翼斗壁"),
        ("和善", "觜角房奎"),
        ("毒害", "参柳心尾"),
        ("急速", "鬼轸胃娄"),
        ("猛恶", "星张箕室"),
        ("轻燥", "井亢女虚危"),
        ("刚柔", "昴氐"),
    )
    for m in members
}


def mansion_nature(mansion: str | None) -> str | None:
    return _MANSION_NATURES.get(mansion) if mansion else None


@dataclass(frozen=True)
class _JapaneseTable:
    starts: tuple[int, ...]
    rows: tuple[tuple[int, int, bool, int], ...]
    first: date
    last: date
    error_label: str

    def supported_range(self) -> tuple[date, date]:
        return self.first, self.last

    def lunar_fields(self, civil: date) -> tuple[int, int, int, bool]:
        if not self.first <= civil <= self.last:
            raise ValueError(
                f"{self.error_label}仅支持{self.first}至{self.last}；范围外不回退中国历或外推"
            )
        idx = bisect_right(self.starts, civil.toordinal()) - 1
        year, month, leap, _ = self.rows[idx]
        return year, month, civil.toordinal() - self.starts[idx] + 1, leap


@lru_cache(maxsize=1)
def _hutime_reader() -> _JapaneseTable:
    bundle = load_source(HUTIME_SOURCE)
    starts, rows = [], []
    for civil_text, year, month, leap, length in bundle["months"]:
        starts.append(date.fromisoformat(civil_text).toordinal())
        rows.append((year, month, leap, length))
    first, last = map(date.fromisoformat, bundle["supported_range_inclusive"])
    return _JapaneseTable(tuple(starts), tuple(rows), first, last, "日本旧历参考数据")


@lru_cache(maxsize=1)
def _naoj_reader() -> _JapaneseTable:
    bundle = load_source(NAOJ_SOURCE)
    starts, rows = [], []
    for ordinal, year, month, leap, length in bundle["months"]:
        starts.append(ordinal)
        rows.append((year, month, leap, length))
    first, last = map(date.fromisoformat, bundle["supported_range_inclusive"])
    return _JapaneseTable(tuple(starts), tuple(rows), first, last, "NAOJ日本历史参考")


def _basis_parameters(basis: str) -> tuple[int, date, date, str]:
    if basis == DEFAULT_CALENDAR_BASIS:
        return 8, date(1901, 1, 1), date(2099, 12, 31), "中国"
    if basis == JAPANESE_CALENDAR_BASIS:
        first, last = _hutime_reader().supported_range()
        return 9, first, last, "日本旧历参考"
    if basis == HISTORICAL_CALENDAR_BASIS:
        first, last = _naoj_reader().supported_range()
        return 9, first, last, "日本历史历日参考"
    raise ValueError(
        "calendar_basis仅支持chinese_hko_utc08、japanese_hutime_1002_1_utc09或japanese_naoj_historical_utc09"
    )


def _basis_identifiers(basis: str) -> tuple[str, str]:
    if basis == DEFAULT_CALENDAR_BASIS:
        return "modern_chinese_lunisolar", "lunardate"
    if basis == JAPANESE_CALENDAR_BASIS:
        return "japanese_hutime_old_calendar_reference", "frozen_hutime_daily_reference"
    if basis == HISTORICAL_CALENDAR_BASIS:
        return (
            "japanese_naoj_historical_month_start_reference",
            "frozen_naoj_historical_month_starts",
        )
    raise ValueError("未知的宿曜宿主历法标识")


@lru_cache(maxsize=1)
def _fullmoon_anchors() -> dict[int, str]:
    bundle = load_source(PROFILES_SOURCE)
    return {
        row["month"]: row["fullmoon_mansion"].translate(ALIASES)
        for row in bundle["fullmoon_anchors"]
    }


def fullmoon_calculation(month: int, day: int, order: Sequence[str]) -> dict[str, Any]:
    """Compute T1299 full-moon lunar mansion (exact match between direct & shortcut rules)."""
    if type(month) is not int or not 1 <= month <= 12:
        raise ValueError("农历月必须为1..12的整数")
    if type(day) is not int or not 1 <= day <= 30:
        raise ValueError("农历日必须为1..30的整数")
    if len(order) != 27 or len(set(order)) != 27 or "牛" in order:
        raise ValueError("望宿法必须使用不含牛的27宿顺序")
    anchor = _fullmoon_anchors()[month]
    anchor_index = order.index(anchor)
    direct = order[(anchor_index + day - 15) % 27]
    inclusive_count = day + 13
    shortcut = order[(anchor_index + (inclusive_count - 1) % 27) % 27]
    if direct != shortcut:
        raise RuntimeError("原典两种望宿算法不一致，不能静默择一")
    bundle = load_source(PROFILES_SOURCE)
    return {
        "ruleset_id": bundle["id"],
        "lunar_month": month,
        "lunar_day": day,
        "fullmoon_day": 15,
        "fullmoon_mansion": anchor,
        "signed_day_offset": day - 15,
        "direct_mansion": direct,
        "shortcut_inclusive_count": inclusive_count,
        "shortcut_one_based_remainder": (inclusive_count - 1) % 27 + 1,
        "shortcut_mansion": shortcut,
        "methods_agree": True,
    }


def lunar_mansion(month: int, day: int) -> str:
    """Return T1299 27-mansion name for `(lunar_month, lunar_day)`."""
    return cast(str, fullmoon_calculation(month, day, SU27_ORDER)["direct_mansion"])


def _select_profile(
    month: int,
    day: int,
    leap: bool,
    order: Sequence[str],
    *,
    profile: str,
    leap_policy: str,
    day_part: str | None,
    previous_lunar: dict[str, Any] | None,
) -> dict[str, Any]:
    if profile not in PROFILES:
        raise ValueError("calendar_profile仅支持t1299_fullmoon27或hinoo_t1299_host27")
    if day_part is not None and day_part not in DAY_PARTS:
        raise ValueError("calendar_day_part仅支持first_half或second_half")
    if day_part is not None and profile != HINOO_PROFILE:
        raise ValueError("calendar_day_part只适用于明确选择的hinoo_t1299_host27档案")
    if leap_policy not in {"unresolved", "repeat_month"}:
        raise ValueError("闰月政策无效")
    bundle = load_source(PROFILES_SOURCE)

    def _calc(m: int, d: int) -> dict[str, Any]:
        return fullmoon_calculation(m, d, order)

    host = _calc(month, day)
    base = host["direct_mansion"]
    assignment = None
    missing_part = False
    precedence_unresolved = False
    previous_context_unavailable = False
    choices = [base]
    selected = base
    if profile == HINOO_PROFILE and day == 1:
        if previous_lunar is None:
            missing_part = day_part != "second_half"
            previous_context_unavailable = missing_part
        else:
            omitted = (
                _calc(previous_lunar["lunar_month"], 30)
                if previous_lunar["lunar_day"] == 29
                else None
            )
            adjacent_first = omitted["direct_mansion"] if omitted else base
            first_choices = [adjacent_first]
            precedence = None
            if leap:
                before_regular = previous_lunar.get("before_regular_month")
                if before_regular is None:
                    previous_context_unavailable = day_part != "second_half"
                else:
                    repeated_omitted = (
                        _calc(before_regular["lunar_month"], 30)
                        if before_regular["lunar_day"] == 29
                        else None
                    )
                    repeated_first = (
                        repeated_omitted["direct_mansion"] if repeated_omitted else base
                    )
                    first_choices = list(
                        dict.fromkeys([adjacent_first, repeated_first])
                    )
                    precedence = {
                        "kind": "modern_reconstruction_variants_not_two_explicit_source_algorithms",
                        "adjacent_month_first_half": adjacent_first,
                        "repeat_true_month_first_half": repeated_first,
                        "second_half_both_variants": base,
                        "source_rule_priority_established": False,
                        "reconstruction_calculations": [
                            {
                                "id": "adjacent_month_short_day_assignment",
                                "previous_lunar": deepcopy(previous_lunar),
                                "first_half_calculation": deepcopy(omitted or host),
                                "second_half_calculation": deepcopy(host),
                            },
                            {
                                "id": "repeat_regular_month_first_day_assignment",
                                "previous_lunar": deepcopy(before_regular),
                                "first_half_calculation": deepcopy(
                                    repeated_omitted or host
                                ),
                                "second_half_calculation": deepcopy(host),
                            },
                        ],
                    }
            slots = [
                {
                    "day_part": "first_half",
                    "mansion": first_choices[0] if len(first_choices) == 1 else None,
                    "candidate_mansions": first_choices,
                    "origin": (
                        "adjacent_month_or_repeated_true_month_assignment"
                        if leap
                        else (
                            "preceding_month_omitted_day_30"
                            if omitted
                            else "current_month_regular_day_1"
                        )
                    ),
                },
                {
                    "day_part": "second_half",
                    "mansion": base,
                    "candidate_mansions": [base],
                    "origin": "current_month_regular_day_1",
                },
            ]
            choices = (
                list(dict.fromkeys([*first_choices, base]))
                if day_part is None
                else first_choices if day_part == "first_half" else [base]
            )
            missing_part = day_part is None and len(choices) > 1
            precedence_unresolved = day_part == "first_half" and len(first_choices) > 1
            if len(choices) == 1:
                selected = choices[0]
            if omitted or leap:
                assignment = {
                    "previous_lunar": previous_lunar,
                    "omitted_day_calculation": omitted,
                    "slots": slots,
                    "selected_day_part": day_part,
                    "leap_short_month_precedence": precedence,
                }
    effective_leap_policy = "repeat_month" if profile == HINOO_PROFILE else leap_policy
    leap_unresolved = leap and effective_leap_policy == "unresolved"
    resolved = (
        not leap_unresolved
        and not missing_part
        and not precedence_unresolved
        and not previous_context_unavailable
    )
    reason = (
        "leap_month_policy_unresolved"
        if leap_unresolved
        else (
            "hinoo_previous_lunar_context_unavailable"
            if previous_context_unavailable
            else (
                "hinoo_leap_short_month_precedence_unresolved"
                if precedence_unresolved
                else (
                    "hinoo_short_month_day_part_unresolved"
                    if missing_part
                    else "computed_under_declared_profile"
                )
            )
        )
    )
    return {
        "calendar_profile": profile,
        "mansion_method_id": (
            bundle["hinoo_addendum"]["id"] if profile == HINOO_PROFILE else bundle["id"]
        ),
        "ruleset_id": bundle["id"],
        "host_calculation": host,
        "requested_leap_month_policy": leap_policy,
        "effective_leap_month_policy": effective_leap_policy,
        "calendar_day_part": day_part,
        "resolved": resolved,
        "resolution_reason": reason,
        "natal_su27": selected if resolved else None,
        "candidate_su27": choices[0] if not resolved and len(choices) == 1 else None,
        "candidate_su27s": choices if not resolved else [],
        "candidate_set_complete_under_declared_reconstructions": (
            not previous_context_unavailable and not leap_unresolved
        ),
        "short_month_assignment": assignment,
    }


def _lunar_fields(
    civil: date, calendar_basis: str = DEFAULT_CALENDAR_BASIS
) -> tuple[int, int, int, bool]:
    if calendar_basis == JAPANESE_CALENDAR_BASIS:
        return _hutime_reader().lunar_fields(civil)
    if calendar_basis == HISTORICAL_CALENDAR_BASIS:
        return _naoj_reader().lunar_fields(civil)
    if calendar_basis != DEFAULT_CALENDAR_BASIS:
        raise ValueError("未知的宿曜宿主历法，不能回退中国历")
    correction = load_source(CORRECTIONS_SOURCE)["corrections"].get(civil.isoformat())
    if correction is not None:
        return (
            int(correction[0]),
            int(correction[1]),
            int(correction[2]),
            bool(correction[3]),
        )
    lunar = LunarDate.from_solar_date(civil.year, civil.month, civil.day)
    return lunar.year, lunar.month, lunar.day, bool(lunar.is_leap_month)


def _input_timezone_context(zone_text: str) -> dict[str, str]:
    rules = timezone_rules_metadata(zone_text)
    zone = parse_timezone_name(zone_text)
    if isinstance(zone, timezone):
        offset = zone.utcoffset(None)
        assert offset is not None
        ticks = (
            offset.days * 86400 + offset.seconds
        ) * SECOND_MICROSECONDS + offset.microseconds
        rules["effective_offset_microseconds"] = str(ticks)
    return rules


def _integer_utc_label(seconds: int) -> str:
    day, within_day = divmod(seconds, 86400)
    label = "0000-12-31" if day == -1 else date.fromordinal(day + 1).isoformat()
    hour, remaining = divmod(within_day, 3600)
    minute, second = divmod(remaining, 60)
    return f"{label}T{hour:02}:{minute:02}:{second:02}+00:00"


def _fixed_offset_support(
    civil: date, zone: timezone, reference_hours: int
) -> dict[str, Any]:
    if civil >= date(9999, 12, 30):
        raise ValueError("当地日期超出可枚举的民用日期范围。")
    offset = zone.utcoffset(None)
    assert offset is not None
    offset_us = (
        offset.days * 86400 + offset.seconds
    ) * SECOND_MICROSECONDS + offset.microseconds
    start = (civil.toordinal() - 1) * DAY_MICROSECONDS - offset_us
    end = start + DAY_MICROSECONDS
    reference_us = reference_hours * 3600 * SECOND_MICROSECONDS
    epoch_us = (date(1970, 1, 1).toordinal() - 1) * DAY_MICROSECONDS
    lower = civil.year == 1 and civil.month == 1 and civil.day <= 2

    def label(ordinal: int) -> str:
        return UTCCalendar(ordinal, 0).isoformat().split("T")[0]

    def utc_label(microseconds: int) -> str:
        day, within_day = divmod(microseconds, DAY_MICROSECONDS)
        return UTCCalendar(day + 1, within_day).isoformat()

    intervals = []
    opened = start
    while opened < end:
        reference_ordinal = (opened + reference_us) // DAY_MICROSECONDS + 1
        finish = min(end, reference_ordinal * DAY_MICROSECONDS - reference_us)
        row: dict[str, Any] = {
            "calendar_date": label(reference_ordinal),
            "start_utc_inclusive": utc_label(opened),
            "end_utc_exclusive": utc_label(finish),
        }
        if opened % SECOND_MICROSECONDS or finish % SECOND_MICROSECONDS:
            row.update(
                start_utc_epoch_microseconds=str(opened - epoch_us),
                end_utc_epoch_microseconds=str(finish - epoch_us),
            )
        elif lower:
            row.update(
                start_utc_epoch_seconds=(opened - epoch_us) // SECOND_MICROSECONDS,
                end_utc_epoch_seconds=(finish - epoch_us) // SECOND_MICROSECONDS,
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
    }


def _wall_second_support(
    civil: date, zone: ZoneInfo, reference_hours: int
) -> tuple[tuple[tuple[str, int, int], ...], int]:
    anchor = datetime.combine(civil, datetime.min.time())
    ordinal_start = (civil.toordinal() - 1) * 86400
    instants: set[int] = set()
    has_unspecified_support = False
    for second in range(86400):
        early = (anchor + timedelta(seconds=second)).replace(tzinfo=zone)
        late = early.replace(fold=1)
        before = early.utcoffset()
        after = late.utcoffset()
        if before is None or after is None:
            raise ValueError("具名时区未提供本地钟时偏移")
        if after > before:
            continue
        folds = (
            ((early, before), (late, after)) if after < before else ((early, before),)
        )
        for local, offset in folds:
            if is_unspecified_local_time(local):
                has_unspecified_support = True
            else:
                instants.add(ordinal_start + second - int(offset.total_seconds()))
    if not instants:
        if has_unspecified_support:
            raise PydanticCustomError(
                "unresolved_timezone_offset", UNRESOLVED_OFFSET_MESSAGE
            )
        raise ValueError("所给当地日期在该时区不存在，不能据此排宿；请核对原始日期。")
    intervals: list[tuple[str, int, int]] = []
    opened = previous = None
    previous_date = None
    for instant in sorted(instants):
        ordinal = (instant + reference_hours * 3600) // 86400 + 1
        target = "0000-12-31" if ordinal == 0 else date.fromordinal(ordinal).isoformat()
        if target != previous_date or previous is None or instant != previous + 1:
            if opened is not None:
                assert previous is not None
                assert previous_date is not None
                intervals.append((previous_date, opened, previous + 1))
            opened = instant
            previous_date = target
        previous = instant
    assert opened is not None and previous is not None and previous_date is not None
    intervals.append((previous_date, opened, previous + 1))
    return tuple(intervals), len(instants)


@lru_cache(maxsize=256)
def _tzif_support(
    date_text: str, zone_text: str, calendar_offset_hours: int = 8
) -> tuple[Any, int, tuple[tuple[str, str], ...]]:
    civil = date.fromisoformat(date_text)
    zone = parse_timezone_name(zone_text)
    metadata = {"provider": "datetime.timezone", "database": "explicit_fixed_offset"}
    if isinstance(zone, ZoneInfo):
        with pytz.open_resource(zone.key) as resource:
            raw = resource.read()
        zone = ZoneInfo.from_file(BytesIO(raw), key=zone.key)
        metadata = {
            "provider": "zoneinfo.from_file",
            "database": "pytz",
            "package_version": pytz.__version__,
            "iana_version": pytz.OLSON_VERSION,
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
    has_unspecified_support = False
    for second in range(3 * 86400):
        instant = start + timedelta(seconds=second)
        target = None
        try:
            local = instant.astimezone(zone)
        except OverflowError:
            local = None
        if local is not None and local.date() == civil:
            if is_unspecified_local_time(local):
                has_unspecified_support = True
            else:
                target = (
                    (instant + timedelta(hours=calendar_offset_hours))
                    .date()
                    .isoformat()
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
        if has_unspecified_support:
            raise PydanticCustomError(
                "unresolved_timezone_offset", UNRESOLVED_OFFSET_MESSAGE
            )
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
        return result
    intervals, seconds_found, metadata = _tzif_support(
        date_text, zone_text, calendar_offset_hours
    )
    return {
        "method_id": (
            "complete_local_date_preimage_tzif_seconds_v1"
            if calendar_offset_hours == 8
            else "complete_local_date_preimage_tzif_seconds_utc09_v1"
        ),
        "local_date": date_text,
        "input_timezone": zone_text,
        "possible_calendar_dates": list(dict.fromkeys(row[0] for row in intervals)),
        "utc_support_intervals": [
            {
                "calendar_date": c_date,
                "start_utc_inclusive": (
                    _integer_utc_label(start)
                    if isinstance(start, int)
                    else start.isoformat()
                ),
                "end_utc_exclusive": (
                    _integer_utc_label(end) if isinstance(end, int) else end.isoformat()
                ),
            }
            for c_date, start, end in intervals
        ],
        "civil_support_seconds": seconds_found,
        "enumeration_resolution_seconds": 1,
        "timezone_rules": dict(metadata),
        "complete_under_loaded_timezone_rules": True,
        "birth_time_imputed": False,
    }


def _date_uncertain_calendar(
    civil_date: date,
    zone: str,
    support: dict[str, Any],
    *,
    leap_month_policy: str,
    calendar_profile: str,
    calendar_day_part: str | None,
    calendar_basis: str = DEFAULT_CALENDAR_BASIS,
) -> dict[str, Any]:
    offset, first_date, last_date, calendar_label = _basis_parameters(calendar_basis)
    calendar_system, calendar_backend = _basis_identifiers(calendar_basis)
    candidates = []
    excluded = []
    for value in support["possible_calendar_dates"]:
        if not first_date.isoformat() <= value <= last_date.isoformat():
            excluded.append(value)
            continue
        candidate = calendar_mansion(
            value,
            zone=f"+{offset:02}:00",
            leap_month_policy=leap_month_policy,
            calendar_profile=calendar_profile,
            calendar_day_part=calendar_day_part,
            calendar_basis=calendar_basis,
        )
        candidate["input_origin"] = (
            "derived_calendar_date_candidate_not_observed_birth_date"
        )
        candidates.append(candidate)
    if not candidates:
        raise ValueError(
            f"所有可能{calendar_label}历日均超出{first_date}至{last_date}的支持范围。"
        )
    complete = not excluded and all(
        c["profile_calculation"][
            "candidate_set_complete_under_declared_reconstructions"
        ]
        for c in candidates
    )
    names = list(
        dict.fromkeys(
            name
            for c in candidates
            for name in ([c["natal_su27"]] if c["natal_su27"] else c["candidate_su27s"])
        )
    )
    resolved = complete and len(names) == 1 and all(c["natal_su27"] for c in candidates)
    primary = names[0] if resolved else None

    def common(key: str) -> Any:
        first = candidates[0][key]
        return (
            deepcopy(first)
            if not excluded and all(c[key] == first for c in candidates)
            else None
        )

    profile = {
        "calendar_profile": calendar_profile,
        "mansion_method_id": candidates[0]["mansion_method_id"],
        "resolved": resolved,
        "resolution_reason": (
            "local_date_spans_japanese_reference_dates"
            if calendar_basis in JAPANESE_CALENDAR_BASES
            else "local_date_spans_chinese_calendar_dates"
        ),
        "natal_su27": primary,
        "candidate_su27s": [] if resolved else names,
        "candidate_set_complete_under_declared_reconstructions": complete,
    }
    result: dict[str, Any] = {
        "status": "partial",
        "input_date": civil_date.isoformat(),
        "input_datetime": None,
        "input_timezone": zone,
        "input_timezone_rules": _input_timezone_context(zone),
        "birth_time_known": False,
        "calendar_date": None,
        "calendar_timezone": f"UTC+{offset:02}:00",
        "calendar_system": calendar_system,
        "calendar_backend": calendar_backend,
        "calendar_correction": common("calendar_correction"),
        **{
            k: common(k)
            for k in ("lunar_year", "lunar_month", "lunar_day", "is_leap_month")
        },
        "leap_month_policy": common("leap_month_policy"),
        "calendar_profile": calendar_profile,
        "mansion_method_id": candidates[0]["mansion_method_id"],
        "calendar_day_part": calendar_day_part,
        "resolution_reason": profile["resolution_reason"],
        "natal_su27": primary,
        "candidate_su27": names[0] if not resolved and len(names) == 1 else None,
        "candidate_su27s": [] if resolved else names,
        "profile_calculation": profile,
        "date_support": support,
        "calendar_candidates": candidates,
        "out_of_range_calendar_dates": excluded,
    }
    if calendar_basis in JAPANESE_CALENDAR_BASES:
        result["calendar_basis"] = calendar_basis
    return result


def calendar_mansion(
    date_text: str,
    time_text: str | None = None,
    zone: str | None = None,
    *,
    leap_month_policy: str = "unresolved",
    calendar_profile: str = DEFAULT_PROFILE,
    calendar_day_part: str | None = None,
    calendar_basis: str = DEFAULT_CALENDAR_BASIS,
) -> dict[str, Any]:
    """Resolve civil date/time -> host lunar date -> T1299 27-mansion."""
    offset, first_date, last_date, calendar_label = _basis_parameters(calendar_basis)
    calendar_system, calendar_backend = _basis_identifiers(calendar_basis)
    timezone_label = f"UTC+{offset:02}:00"
    if leap_month_policy not in {"unresolved", "repeat_month"}:
        raise ValueError("leap_month_policy仅支持unresolved或repeat_month")
    civil_date = date.fromisoformat(date_text.replace("/", "-"))
    selected_zone = zone or "+08:00"
    input_moment = None
    date_support = None
    if time_text:
        naive, _ = parse_microsecond_iso_datetime(
            f"{civil_date.isoformat()}T{time_text}"
        )
        if naive.tzinfo is not None:
            raise ValueError("time不得内嵌时区；请使用zone")
        moment = localize_datetime(naive, selected_zone)
        input_moment = moment.isoformat()
        try:
            validate_local_clock(moment)
            input_offset = moment.utcoffset()
            assert input_offset is not None
            calendar_date = (naive + timedelta(hours=offset) - input_offset).date()
        except OverflowError as error:
            raise ValueError(
                "所给钟时的日界换算超出可表示的民用日期范围；未替换时区或回退其他历法。"
            ) from error
    else:
        zone_info = parse_timezone_name(selected_zone)
        if isinstance(zone_info, timezone) and zone_info.utcoffset(None) == timedelta(
            hours=offset
        ):
            calendar_date = civil_date
        else:
            date_support = local_date_support(
                civil_date.isoformat(), selected_zone, calendar_offset_hours=offset
            )
            if len(date_support["possible_calendar_dates"]) > 1:
                return _date_uncertain_calendar(
                    civil_date,
                    selected_zone,
                    date_support,
                    leap_month_policy=leap_month_policy,
                    calendar_profile=calendar_profile,
                    calendar_day_part=calendar_day_part,
                    calendar_basis=calendar_basis,
                )
            calendar_date = date.fromisoformat(
                date_support["possible_calendar_dates"][0]
            )
    if not first_date <= calendar_date <= last_date:
        raise ValueError(
            f"宿曜{calendar_label}历法支持{first_date}至{last_date}；范围外不回退其他历法或外推。"
        )
    year, month, day, leap = _lunar_fields(calendar_date, calendar_basis)
    correction = (
        load_source(CORRECTIONS_SOURCE)["corrections"].get(calendar_date.isoformat())
        if calendar_basis == DEFAULT_CALENDAR_BASIS
        else None
    )
    previous = None
    if calendar_profile == HINOO_PROFILE and day == 1 and calendar_date > first_date:
        previous_date = calendar_date - timedelta(days=1)
        py, pm, pd, pl = _lunar_fields(previous_date, calendar_basis)
        previous = {
            "calendar_date": previous_date.isoformat(),
            "lunar_year": py,
            "lunar_month": pm,
            "lunar_day": pd,
            "is_leap_month": pl,
        }
        if leap:
            before_regular_date = calendar_date - timedelta(days=pd + 1)
            if before_regular_date >= first_date:
                ry, rm, rd, rl = _lunar_fields(before_regular_date, calendar_basis)
                previous["before_regular_month"] = {
                    "calendar_date": before_regular_date.isoformat(),
                    "lunar_year": ry,
                    "lunar_month": rm,
                    "lunar_day": rd,
                    "is_leap_month": rl,
                }
    selection = _select_profile(
        month,
        day,
        leap,
        SU27_ORDER,
        profile=calendar_profile,
        leap_policy=leap_month_policy,
        day_part=calendar_day_part,
        previous_lunar=previous,
    )
    resolved = selection["resolved"]
    result: dict[str, Any] = {
        "status": "computed" if resolved else "partial",
        "input_date": civil_date.isoformat(),
        "input_datetime": input_moment,
        "input_timezone": selected_zone,
        "input_timezone_rules": _input_timezone_context(selected_zone),
        "birth_time_known": bool(time_text),
        "calendar_date": calendar_date.isoformat(),
        "calendar_timezone": timezone_label,
        "calendar_system": calendar_system,
        "calendar_backend": calendar_backend,
        "calendar_correction": (
            "sukuyo_hko_corrections_v1" if correction is not None else None
        ),
        "lunar_year": year,
        "lunar_month": month,
        "lunar_day": day,
        "is_leap_month": leap,
        "leap_month_policy": selection["effective_leap_month_policy"],
        "calendar_profile": calendar_profile,
        "mansion_method_id": selection["mansion_method_id"],
        "calendar_day_part": calendar_day_part,
        "resolution_reason": selection["resolution_reason"],
        "natal_su27": selection["natal_su27"],
        "candidate_su27": selection["candidate_su27"],
        "candidate_su27s": selection["candidate_su27s"],
        "month_start_mansion": lunar_mansion(month, 1),
        "profile_calculation": selection,
    }
    if date_support is not None:
        result["date_support"] = date_support
    if calendar_basis in JAPANESE_CALENDAR_BASES:
        result["calendar_basis"] = calendar_basis
    return result


def civil_weekday(calendar_date: str, calendar_timezone: str) -> dict[str, Any]:
    if calendar_timezone not in {"UTC+08:00", "UTC+09:00"}:
        raise ValueError("宿曜七曜须明确已支持的UTC+08或UTC+09宿主历日")
    weekday = (date.fromisoformat(calendar_date).weekday() + 1) % 7
    return {
        "index_sunday_zero": weekday,
        "luminary": "日月火水木金土"[weekday],
        "basis": (
            "modern_utc_plus09_civil_midnight"
            if calendar_timezone == "UTC+09:00"
            else "modern_utc_plus08_civil_midnight"
        ),
    }


_ACTIVITIES_BY_NATURE = {
    "安重": ["长期营建", "园林仓储", "结交与婚礼"],
    "和善": ["问学技艺", "音乐礼仪", "求婚与冠带出行"],
    "急速": ["买卖交关", "进路出行", "入学受业"],
    "轻燥": ["使节往来", "舟行", "礼乐与种植"],
    "刚柔": ["金属与器具工艺", "买卖", "入宅与盟会"],
    "毒害": [],
    "猛恶": [],
}


def day_evidence(
    context: dict[str, Any],
    *,
    natal_mansion: str | None = None,
    activity: str | None = None,
    activity_details: Sequence[str] | None = None,
    textual_pada: int | None = None,
    distance_rule: DistanceRule = "symmetric",
    birth_year: int | None = None,
    target_year: int | None = None,
    urgent: bool = False,
) -> dict[str, Any]:
    """Assemble compact daily Sukuyo evidence with Sanjiu, Ryohan, 甘露/金刚峰/罗刹, and Kuyou."""
    if not context.get("natal_su27") and context.get("calendar_candidates"):
        alternatives = [
            day_evidence(
                candidate,
                natal_mansion=natal_mansion,
                activity=activity,
                activity_details=activity_details,
                textual_pada=textual_pada,
                distance_rule=distance_rule,
                birth_year=birth_year,
                target_year=target_year,
                urgent=urgent,
            )
            for candidate in context["calendar_candidates"]
        ]
        return {
            "calendar": context,
            "six_palace_reference": six_palace_reference(natal_mansion),
            "personal_day": None,
            "day_mansion": None,
            "palace_reference": palace_reference(context, textual_pada),
            "candidate_days": alternatives,
        }

    mansion = context["natal_su27"]
    personal_day = personal_day_evidence(
        natal_mansion, mansion, distance_rule=distance_rule
    )
    nature = mansion_nature(mansion)
    day = context["lunar_day"]
    weekday_ref = civil_weekday(
        context["calendar_date"], context.get("calendar_timezone", "UTC+08:00")
    )
    weekday = weekday_ref["index_sunday_zero"]
    special_ev = special_day_evidence(
        mansion,
        weekday,
        context.get("candidate_su27s", []),
        weekday_basis=weekday_ref["basis"],
    )
    special_labels = special_ev["primary"]["matched_labels"]

    first_day_civil = (
        date.fromisoformat(context["calendar_date"]) - timedelta(days=day - 1)
    ).isoformat()
    month_start_luminary = civil_weekday(
        first_day_civil, context.get("calendar_timezone", "UTC+08:00")
    )["luminary"]
    rel_name = personal_day["relation"]["relation"] if personal_day else None
    ryohan = assess_ryohan(
        context["lunar_month"],
        day,
        month_start_luminary,
        relation=rel_name,
        special_labels=special_labels,
        urgent=urgent,
    )

    result: dict[str, Any] = {
        "calendar": context,
        "six_palace_reference": six_palace_reference(natal_mansion),
        "personal_day": personal_day,
        "ryohan": ryohan,
        "day_mansion": mansion,
        "weekday": weekday_ref,
        "lunar_half": "白" if day <= 15 else "黑",
        "half_day": (day - 1) % 15 + 1,
        "nature": nature,
        "traditional_activity_examples": (
            _ACTIVITIES_BY_NATURE.get(nature, []) if nature else []
        ),
        "special_day_labels": special_labels,
        "special_day_evidence": special_ev,
        "calendar_day": calendar_day_evidence(day),
        "taibai_direction_reference": taibai_direction_reference(day),
        "lower_mansion_day": lower_mansion_evidence(mansion),
        "lower_methods": lower_methods_evidence(
            mansion,
            weekday_ref["luminary"],
            nature,
            weekday_basis=weekday_ref["basis"],
        ),
        "directional_travel": travel_direction_evidence(
            mansion, context.get("candidate_su27s", [])
        ),
        "conjunction_doctrine": conjunction_doctrine(
            mansion, context.get("candidate_su27s", [])
        ),
        "palace_reference": palace_reference(context, textual_pada),
    }
    if birth_year is not None:
        result["kuyou_annual"] = kuyou_annual_star(
            birth_year,
            target_year if target_year is not None else context["lunar_year"],
        )
    if activity == "clothing":
        result["clothing_reference"] = clothing_reference(context)
    result["activity_assessment"] = assess_activity(result, activity, activity_details)
    return result


def rulesets(
    calendar_profile: str = DEFAULT_PROFILE,
    calendar_basis: str = DEFAULT_CALENDAR_BASIS,
) -> dict[str, Any]:
    source = load_source(PROFILES_SOURCE)
    return {
        "calendar": {
            "id": (
                source["hinoo_addendum"]["id"]
                if calendar_profile == HINOO_PROFILE
                else source["id"]
            ),
            "calendar_profile": calendar_profile,
            "calendar_basis": calendar_basis,
        },
        "relations": {"id": "t1299_sanjiu_v1"},
        "ryohan": {"id": "kenyu_nijl100159236_selected_lingbi_v1"},
        "kuyou": {"id": "sukuyo_kuyou_annual_star_v1"},
    }
