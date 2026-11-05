"""Known birth clocks and explicit longitude for the two birth numerologies."""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, time, timedelta, timezone
from typing import TYPE_CHECKING, Any

from fatebridge.core.numerology_clock_policy import (
    CLOCK_POLICY_ID,
)
from fatebridge.core.numerology_clock_policy import (
    require_birth_clock as require_birth_clock,
)
from fatebridge.utils.civil_clock import format_utc_offset, resolve_civil_clock
from fatebridge.utils.coordinates import parse_geo_coordinate
from fatebridge.utils.timezones import parse_timezone_name, timezone_rules_metadata

if TYPE_CHECKING:
    from fatebridge.core.metaphysics.common import MetaphysicsSeed

NUMEROLOGY_DEFAULT_TIMEZONE = "+08:00"
TIMEZONE_POLICY_ID = "numerology_fixed_default_explicit_region_v1"
BIRTH_OFFSET_POLICY_ID = "numerology_confirmed_civil_offset_v1"
BIRTH_OFFSET_DESCRIPTION = (
    "Optional confirmed birth UTC offset ±HH:MM[:SS]. With an IANA zone, verifies "
    "or selects the occurrence of a repeated birth clock while retaining regional "
    "rules for later boundaries. Never infer an unknown offset; cannot make a "
    "nonexistent local time valid or replace birth-record precision."
)
NUMEROLOGY_DATE_DESCRIPTION = (
    "Birth date YYYY-MM-DD in the proleptic Gregorian calendar, including before "
    "1582; no automatic Julian/Gregorian cutover or historical lunar/era conversion. "
    "Historical source dates require a separately evidenced conversion."
)
NUMEROLOGY_TIME_DESCRIPTION = (
    "Known birth local time HH:MM[:SS[.ffffff]], up to six fractional digits; "
    "required, blank is not midnight; timezone goes in zone. Supplied components "
    "are retained separately from zero calculation defaults. Textual digits "
    "do not certify birth-record precision or imply an uncertainty interval."
)


def resolve_numerology_timezone(value: object) -> str:
    """Keep omitted/null zones consistent with the published fixed-offset default.

    A named historical zone can have a different UTC offset from +08:00.
    Never infer it from a missing zone or silently replace a blank/invalid one.
    """
    if value is None:
        return NUMEROLOGY_DEFAULT_TIMEZONE
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            "出生时区zone须为非空IANA名称或UTC偏移；未知时区不能用空白代替。"
        )
    zone = value.strip()
    parse_timezone_name(zone)
    return zone


def normalize_numerology_utc_offset(value: object) -> str | None:
    """Accept a separately confirmed offset, without inferring a birth region."""
    if value is None:
        return None
    match = (
        re.fullmatch(r"([+-])([0-9]{2}):([0-9]{2})(?::([0-9]{2}))?", value.strip())
        if type(value) is str
        else None
    )
    if match is None:
        raise ValueError("birth_utc_offset须为已确认的±HH:MM或±HH:MM:SS；未知时不填。")
    sign, hour, minute, second = match.groups()
    h, m, s = int(hour), int(minute), int(second or 0)
    # A confirmed regional offset is not a new fixed-zone specification.
    # IANA contains historical offsets beyond +/-15h, on both sides of UTC.
    if h >= 24 or m >= 60 or s >= 60:
        raise ValueError("birth_utc_offset超出有效UTC偏移范围。")
    return format_utc_offset(
        timedelta(hours=h, minutes=m, seconds=s) * (1 if sign == "+" else -1)
    )


def numerology_seed_time(
    date_text: str, clock: str, zone: str, birth_utc_offset: str | None
) -> str:
    """Feed a verified instant to the shared seed while keeping its named zone.

    The existing naive path continues to reject folds with unknown offsets.
    A selected aware clock must still round-trip under the regional rules;
    appending an unchecked offset would incorrectly accept gaps or mismatches.
    """
    if birth_utc_offset is None:
        return clock
    wall = datetime.fromisoformat(f"{date_text}T{clock}")
    selected = resolve_civil_clock(
        wall, zone, birth_utc_offset, offset_field="birth_utc_offset"
    )
    # timetz().isoformat() loses ZoneInfo's date-dependent offset.
    return selected.isoformat().partition("T")[2]


def resolve_numerology_longitude(
    lon: Any, gps_lon: Any, use_true_solar_time: bool
) -> tuple[float | None, str | None]:
    """Match the existing GPS priority without supplying a birthplace.

    Longitude zero is a real coordinate. The two numeric interfaces cannot
    turn missing longitude into the shared chart substrate's Shanghai default.
    """
    if type(use_true_solar_time) is not bool:
        raise ValueError("use_true_solar_time须为布尔值。")
    source = "gps_lon" if gps_lon is not None else "lon"
    value = gps_lon if gps_lon is not None else lon
    longitude = parse_geo_coordinate(value, axis="longitude")
    if longitude is None and use_true_solar_time:
        raise ValueError(
            "河洛与参评的真太阳时需要明确出生地经度lon或gps_lon，不能套用上海经度。"
            "不使用太阳时请明确设use_true_solar_time=false。"
        )
    return longitude, source if longitude is not None else None


def numerology_birth_clock(
    seed: MetaphysicsSeed,
    longitude: float | None,
    source: str | None,
    *,
    birth_utc_offset: str | None = None,
    input_clock: str | None = None,
) -> dict[str, Any]:
    offset_seconds = (seed.input_datetime.utcoffset() or timedelta(0)).total_seconds()
    clock = {
        "policy_id": CLOCK_POLICY_ID,
        "mode": "apparent_solar" if seed.applied_true_solar else "civil",
        "calendar_policy": {
            "input_calendar": "proleptic_gregorian",
            "automatic_reform_cutover": False,
            "historical_lunar_date_conversion": False,
            "historical_official_calendar_reconstruction": False,
        },
        "timezone_policy_id": TIMEZONE_POLICY_ID,
        "timezone_spec": seed.timezone,
        "timezone_default_policy": "omitted_or_null_fixed_+08:00; explicit_region_uses_historical_rules; no_place_inference",
        "timezone_rules": timezone_rules_metadata(seed.timezone),
        "civil_utc_offset_seconds": (
            int(offset_seconds) if offset_seconds.is_integer() else offset_seconds
        ),
        "civil_daylight_saving_seconds": int(
            (seed.input_datetime.dst() or timedelta(0)).total_seconds()
        ),
        "civil_datetime": seed.input_datetime.isoformat(),
        "birth_instant_utc": seed.input_datetime.astimezone(timezone.utc).isoformat(),
        # A solar wall-clock is a calculation coordinate, not a new UTC instant.
        "calculation_wall_clock": seed.corrected_datetime.replace(
            tzinfo=None
        ).isoformat(sep=" "),
        "longitude": longitude,
        "longitude_source": source,
        "longitude_used": seed.applied_true_solar,
        "longitude_selection_policy": "gps_lon_preferred_over_lon; missing_not_invented",
        "total_correction_minutes": seed.total_correction_minutes,
        "pillar_clock_policy": "civil_instant_for_year_month; selected_wall_clock_for_day_hour; late_zi_day_rollover",
        "precision_scope": "计算精度不提升所给出生钟时或经度的实际精度；视太阳钟面不是新的物理瞬间。",
    }
    if input_clock is not None:
        from fatebridge.core.numerology_clock_input import clock_input_representation

        representation = clock_input_representation(input_clock)
        if seed.input_datetime.time() != time.fromisoformat(
            representation["normalized_clock"]
        ):
            raise ValueError("所给出生钟时与实际计算参考钟面不一致。")
        clock["input_representation"] = representation
    if birth_utc_offset is not None:
        civil = seed.input_datetime
        clock.update(
            birth_utc_offset_policy_id=BIRTH_OFFSET_POLICY_ID,
            requested_utc_offset=birth_utc_offset,
            civil_utc_offset=format_utc_offset(civil.utcoffset() or timedelta(0)),
            civil_fold=civil.fold,
            civil_time_ambiguous=(
                civil.replace(fold=0).utcoffset() != civil.replace(fold=1).utcoffset()
            ),
            offset_selection_scope=(
                "已确认偏移仅核对或选择出生瞬间，保留地区规则；"
                "不推定出生地、记录精度、古代颁历或未来时区立法。"
            ),
        )
    return clock


def attach_birth_clock(evidence: dict, clock: dict) -> None:
    evidence["birth_clock"] = deepcopy(clock)
    evidence["rule_trace"].append(
        {
            "rule_id": CLOCK_POLICY_ID,
            "source_section": "输入来源与现代民用／视太阳时换算；不是原典术数断语",
            "facts": deepcopy(clock),
        }
    )


def birth_clock_snapshot(clock: dict) -> str:
    longitude = (
        f"{clock['longitude']}°（来源{clock['longitude_source']}）"
        if clock["longitude"] is not None
        else "未提供，未用于钟表时计算"
    )
    mode = "真太阳时" if clock["mode"] == "apparent_solar" else "钟表时"
    zone_kind = (
        "固定偏移"
        if clock["timezone_rules"]["database"] == "explicit_fixed_offset"
        else "地区历史规则"
    )
    selected = (
        f"已确认出生偏移：{clock['requested_utc_offset']}；"
        f"重复钟时：{'是' if clock['civil_time_ambiguous'] else '否'}；"
        f"fold={clock['civil_fold']}（0为回拨前、1为回拨后）；地区时区仍保留。\n"
        if clock.get("birth_utc_offset_policy_id") == BIRTH_OFFSET_POLICY_ID
        else ""
    )
    return (
        "[出生钟时与经度]\n"
        "日期历制：推算格里历（含1582年前），不自动切换儒略历；"
        "年号或历史阴历须另有转换依据，当前节气计算不构成古代颁历复原。\n"
        f"民用时刻：{clock['civil_datetime']}；UTC瞬间：{clock['birth_instant_utc']}。\n"
        f"时区：{clock['timezone_spec']}（{zone_kind}）；未提供时区仅约定固定+08:00，不推定出生地。\n"
        f"{selected}"
        f"计算钟面：{clock['calculation_wall_clock']}（{mode}）；经度：{longitude}。\n"
        "年、月及太阳交节用民用时刻的绝对瞬间；日、时柱用所选钟面。"
        + (
            "\n" + clock["input_representation"]["statement"]
            if "input_representation" in clock
            else ""
        )
    )
