"""Solar-time strategies and birth-clock normalization with place and timezone provenance."""

import math
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fatebridge.utils.birth_input import PersonInfo, create_birth_datetime
from fatebridge.utils.civil_clock import resolve_civil_clock, utc_instant
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE, resolve_birth_place_context
from fatebridge.utils.timezones import (
    invalid_timezone_message as _invalid_timezone_message,
)
from fatebridge.utils.timezones import (
    parse_timezone_name,  # Shared parsing for civil and astronomical calculations.
)
from fatebridge.utils.timezones import validate_local_clock

SOLAR_TIME_STRATEGY_APPARENT = "apparent"


SOLAR_TIME_STRATEGY_LONGITUDE_ONLY = "longitude_only"
EQUATION_OF_TIME_METHOD = "swiss_time_equ_utc_instant_v1"


# the astrology engine would reject an address the BaZi engine happily accepts.


@dataclass(frozen=True)
class NormalizedBirthTime:
    """Normalized birth-time details used across calculation services."""

    input_datetime: datetime
    corrected_datetime: datetime
    timezone: str
    longitude: Optional[float]
    longitude_source: Optional[str]
    resolved_place: Optional[str]
    resolution_level: Optional[str]
    longitude_correction_minutes: float
    equation_of_time_minutes: float
    daylight_saving_minutes: float
    total_correction_minutes: float
    applied: bool
    # 仅当经度是从 birth_place 推断、且只匹配到省级中心点（而非具体市县）时填充：
    # 告知调用方此次校正用的是省级代表经度，未量化实际出生点的误差界。
    resolution_advisory: Optional[str] = None
    equation_of_time_method: Optional[str] = None
    solar_time_strategy: Optional[str] = None
    timezone_source: Optional[str] = None
    timezone_resolved_place: Optional[str] = None

    def as_dict(self, *, include_timezone_resolution: bool = False) -> Dict[str, Any]:
        """Return a JSON-safe summary for API responses."""
        summary: Dict[str, Any] = {
            "applied": self.applied,
            "timezone": self.timezone,
            "longitude": self.longitude,
            "longitude_source": self.longitude_source,
            "resolved_place": self.resolved_place,
            "resolution_level": self.resolution_level,
            "longitude_correction_minutes": round(self.longitude_correction_minutes, 2),
            "equation_of_time_minutes": round(self.equation_of_time_minutes, 2),
            "daylight_saving_minutes": round(self.daylight_saving_minutes, 2),
            "total_correction_minutes": round(self.total_correction_minutes, 2),
        }
        # 仅在有提示时才加入此键：保持无歧义场景（用户显式传经度、市县级匹配）
        # 的输出结构不变，避免给既有消费者凭空多一个 null 字段。
        if self.resolution_advisory is not None:
            summary["resolution_advisory"] = self.resolution_advisory
        if self.equation_of_time_method is not None:
            summary["equation_of_time_method"] = self.equation_of_time_method
            summary["equation_of_time_time_scale"] = "UTC_as_UT1"
        if self.solar_time_strategy is not None:
            summary["solar_time_strategy"] = self.solar_time_strategy
        if include_timezone_resolution:
            summary["timezone_source"] = self.timezone_source
            summary["timezone_resolved_place"] = self.timezone_resolved_place
        return summary


def calculate_equation_of_time_minutes(
    target_datetime: datetime, *, julian_day_ut1: Optional[float] = None
) -> float:
    """Apparent minus mean solar time at an explicit civil instant.

    Swiss Ephemeris expects UT and returns days. UTC is used as an
    approximation to UT1 by default. A domain with a resolved physical clock
    may supply that instant's explicit UT1 instead. Neither mode certifies
    measured DUT1. Never substitute a seasonal sinusoid silently.
    """
    from fatebridge.core import ephemeris_runtime as runtime

    if target_datetime.utcoffset() is None:
        raise ValueError("均时差计算需要带时区的真实时刻")
    if runtime.swe is None:
        raise ImportError("真太阳时均时差计算需要 Swiss Ephemeris")
    if julian_day_ut1 is None:
        instant = target_datetime.astimezone(timezone.utc)
        hour = (
            instant.hour
            + instant.minute / 60
            + (instant.second + instant.microsecond / 1e6) / 3600
        )
        julian_day = runtime.ephemeris_call(
            "julday",
            instant.year,
            instant.month,
            instant.day,
            hour,
            runtime.swe.GREG_CAL,
        )
    else:
        if not math.isfinite(julian_day_ut1):
            raise ValueError("Equation-of-time UT1 Julian day must be finite")
        julian_day = julian_day_ut1
    return float(runtime.ephemeris_call("time_equ", julian_day)) * 1440


def calculate_solar_time_adjustment(
    input_datetime: datetime,
    timezone_name: str,
    longitude: float,
    *,
    strategy: str = SOLAR_TIME_STRATEGY_APPARENT,
    equation_of_time_jd_ut1: Optional[float] = None,
) -> Dict[str, float]:
    """Calculate solar-time correction details for a local civil datetime."""
    timezone_info = parse_timezone_name(timezone_name)
    if input_datetime.utcoffset() is None:
        aware_datetime = input_datetime.replace(tzinfo=timezone_info)
        validate_local_clock(aware_datetime)
    else:
        aware_datetime = input_datetime.astimezone(timezone_info)
    utc_offset = aware_datetime.utcoffset()
    if utc_offset is None:
        raise ValueError(_invalid_timezone_message(timezone_name))

    daylight_saving = aware_datetime.dst() or timedelta(0)
    standard_offset = utc_offset - daylight_saving
    standard_meridian = (standard_offset.total_seconds() / 3600) * 15
    longitude_correction_minutes = 4 * (longitude - standard_meridian)
    # Chinese metaphysics conventions use 标准时 (standard civil time) as the
    # base before applying longitude / equation-of-time corrections. When the
    # user's wall-clock input was recorded during a DST period (e.g. China's
    # 夏令时 1986-1991, historic European/US DST dates), the naive clock is an
    # hour ahead of standard time. We subtract the DST amount here so that the
    # resulting normalized datetime reflects true solar time anchored at the
    # standard meridian — otherwise users born near 时辰 boundaries during a
    # DST period land in the wrong hour pillar.
    dst_offset_minutes = daylight_saving.total_seconds() / 60

    if strategy == SOLAR_TIME_STRATEGY_APPARENT:
        equation_of_time_minutes = (
            calculate_equation_of_time_minutes(aware_datetime)
            if equation_of_time_jd_ut1 is None
            else calculate_equation_of_time_minutes(
                aware_datetime, julian_day_ut1=equation_of_time_jd_ut1
            )
        )
        total_correction_minutes = (
            longitude_correction_minutes + equation_of_time_minutes - dst_offset_minutes
        )
    elif strategy == SOLAR_TIME_STRATEGY_LONGITUDE_ONLY:
        # Some local metaphysics techniques use a longitude-only civil-time
        # correction without the equation-of-time term. The sign of the
        # longitude correction must match the SOLAR_TIME_STRATEGY_APPARENT
        # branch: east of the standard meridian -> solar time runs AHEAD of
        # the wall clock, so we ADD longitude_correction_minutes (which is
        # positive east of meridian) and subtract the DST offset to rebase
        # onto standard time before applying the longitude delta.
        equation_of_time_minutes = 0.0
        total_correction_minutes = longitude_correction_minutes - dst_offset_minutes
    else:
        raise ValueError(f"Unsupported solar time strategy: {strategy}")

    return {
        "standard_meridian": standard_meridian,
        "longitude_correction_minutes": longitude_correction_minutes,
        "equation_of_time_minutes": equation_of_time_minutes,
        "daylight_saving_minutes": dst_offset_minutes,
        "total_correction_minutes": total_correction_minutes,
    }


def rebase_birth_clock(
    template: NormalizedBirthTime, civil_instant: datetime
) -> NormalizedBirthTime:
    """Evaluate a derived uncertainty instant in the confirmed clock policy.

    This does not replace a confirmed birth record. The caller supplies an
    aware actual instant inside its separately declared assessment range.
    Fractional probes remain derived calculation points, not record precision.
    """
    civil = utc_instant(civil_instant).astimezone(
        parse_timezone_name(template.timezone)
    )
    if not template.applied:
        return replace(template, input_datetime=civil, corrected_datetime=civil)
    if template.longitude is None or template.solar_time_strategy is None:
        raise ValueError("已生效的出生钟校正缺少经度或策略，不能推定派生时刻口径")
    adjustment = calculate_solar_time_adjustment(
        civil,
        template.timezone,
        template.longitude,
        strategy=template.solar_time_strategy,
    )
    return replace(
        template,
        input_datetime=civil,
        corrected_datetime=civil.replace(tzinfo=None)
        + timedelta(minutes=adjustment["total_correction_minutes"]),
        longitude_correction_minutes=adjustment["longitude_correction_minutes"],
        equation_of_time_minutes=adjustment["equation_of_time_minutes"],
        daylight_saving_minutes=adjustment["daylight_saving_minutes"],
        total_correction_minutes=adjustment["total_correction_minutes"],
    )


def normalize_birth_time(
    person: PersonInfo,
    *,
    solar_time_strategy: str = SOLAR_TIME_STRATEGY_APPARENT,
    birth_utc_offset: Optional[str] = None,
) -> NormalizedBirthTime:
    """Normalize birth time and optionally apply true solar time correction."""
    input_datetime = create_birth_datetime(
        person.birth_year,
        person.birth_month,
        person.birth_day,
        person.birth_hour,
        person.birth_minute,
        person.birth_second if person.birth_second is not None else 0,
    )

    inferred_place = resolve_birth_place_context(person.birth_place)

    explicit_timezone = person.birth_timezone or inferred_place.timezone
    timezone_name = explicit_timezone or DEFAULT_BIRTH_TIMEZONE
    timezone_source = (
        "birth_timezone"
        if person.birth_timezone
        else "birth_place" if inferred_place.timezone else "default_timezone"
    )
    timezone_resolved_place = (
        inferred_place.canonical_name if timezone_source == "birth_place" else None
    )

    longitude = person.birth_longitude
    longitude_source = "birth_longitude" if longitude is not None else None
    resolved_place = None if longitude is not None else inferred_place.canonical_name
    resolution_level = None if longitude is not None else inferred_place.level
    if longitude is None and inferred_place.longitude is not None:
        longitude = inferred_place.longitude
        longitude_source = inferred_place.source

    # When no timezone is explicitly supplied but a longitude is known, assume the
    # given wall-clock time is local standard time at the zone nearest that
    # longitude — rather than defaulting to Asia/Shanghai's 120°E meridian, which
    # makes true-solar-time correction badly wrong for non-China longitudes.
    if explicit_timezone is None and longitude is not None:
        zone_hours = max(-12, min(14, int(round(longitude / 15.0))))
        timezone_name = f"{'+' if zone_hours >= 0 else '-'}{abs(zone_hours):02d}:00"
        timezone_source = "longitude_standard_meridian_assumption"

    resolved_clock = resolve_civil_clock(
        input_datetime,
        timezone_name,
        birth_utc_offset,
        offset_field="birth_utc_offset",
        recorded_offset=person.birth_utc_offset,
    )
    if birth_utc_offset is not None or person.birth_utc_offset is not None:
        input_datetime = resolved_clock

    if not person.use_true_solar_time:
        return NormalizedBirthTime(
            input_datetime=input_datetime,
            corrected_datetime=input_datetime,
            timezone=timezone_name,
            longitude=longitude,
            longitude_source=longitude_source,
            resolved_place=resolved_place,
            resolution_level=resolution_level,
            longitude_correction_minutes=0.0,
            equation_of_time_minutes=0.0,
            daylight_saving_minutes=0.0,
            total_correction_minutes=0.0,
            applied=False,
            timezone_source=timezone_source,
            timezone_resolved_place=timezone_resolved_place,
        )

    if longitude is None:
        place = person.birth_place
        if place and place != "未提供":
            uncatalogued_msg = (
                f"True solar time correction needs a longitude, but birth_place "
                f"{place!r} is not in the offline place catalog. Pass "
                "birth_longitude explicitly (east positive, e.g. 108.71 for 咸阳), "
                "or use a catalogued city name."
            )
        else:
            uncatalogued_msg = (
                "True solar time correction needs a longitude. Pass birth_longitude "
                "explicitly (east positive), or a catalogued birth_place city name."
            )
        # 显式请求真太阳时却无经度可用 → fail-loud（与用户显式无效请求的处理一致）。
        if person.true_solar_explicit:
            raise ValueError(uncatalogued_msg)
        # 真太阳时是「默认开」而非显式要求，且无经度可解 → 降级为钟表时间，并透明
        # 提示精度损失（与省级 fallback 的 advisory 同一模式），而不是让默认路径报错。
        return NormalizedBirthTime(
            input_datetime=input_datetime,
            corrected_datetime=input_datetime,
            timezone=timezone_name,
            longitude=longitude,
            longitude_source=longitude_source,
            resolved_place=resolved_place,
            resolution_level=resolution_level,
            longitude_correction_minutes=0.0,
            equation_of_time_minutes=0.0,
            daylight_saving_minutes=0.0,
            total_correction_minutes=0.0,
            applied=False,
            timezone_source=timezone_source,
            timezone_resolved_place=timezone_resolved_place,
            resolution_advisory=(
                "未提供可解析的出生地或 birth_longitude，真太阳时校正未生效，结果按"
                "钟表（标准时区）时间计算；补出生地或经度即可启用真太阳时（经度东正）。"
            ),
        )

    adjustment = calculate_solar_time_adjustment(
        input_datetime,
        timezone_name,
        longitude,
        strategy=solar_time_strategy,
    )
    longitude_correction_minutes = adjustment["longitude_correction_minutes"]
    equation_of_time_minutes = adjustment["equation_of_time_minutes"]
    daylight_saving_minutes = adjustment.get("daylight_saving_minutes", 0.0)
    total_correction_minutes = adjustment["total_correction_minutes"]
    # Apparent-solar output is a clock label, not another civil instant.
    corrected_datetime = input_datetime.replace(tzinfo=None) + timedelta(
        minutes=total_correction_minutes
    )

    # 经度来自 birth_place 且只匹配到省级中心点时，校正用的是省级近似经度（如
    # 「江苏省南通市海安市」只识别出省份「江苏」119.42°，与海安实际 ~120.47° 相差
    # 约 1°≈4 分钟）。此时给出明确提示，让调用方知道精度限制并可改传 birth_longitude，
    # 而不是把省级近似当成市县级精度静默使用。
    resolution_advisory = None
    if longitude_source != "birth_longitude" and resolution_level == "province":
        resolution_advisory = (
            f"出生地『{person.birth_place}』未匹配到具体市县，仅按省级"
            f"（{resolved_place}）经度 {longitude:.2f}° 做真太阳时校正，"
            "未确认实际出生点经度，误差界未量化；如需细分时辰请改传 birth_longitude。"
        )

    return NormalizedBirthTime(
        input_datetime=input_datetime,
        corrected_datetime=corrected_datetime,
        timezone=timezone_name,
        longitude=longitude,
        longitude_source=longitude_source,
        resolved_place=resolved_place,
        resolution_level=resolution_level,
        longitude_correction_minutes=longitude_correction_minutes,
        equation_of_time_minutes=equation_of_time_minutes,
        daylight_saving_minutes=daylight_saving_minutes,
        total_correction_minutes=total_correction_minutes,
        applied=True,
        timezone_source=timezone_source,
        timezone_resolved_place=timezone_resolved_place,
        resolution_advisory=resolution_advisory,
        equation_of_time_method=(
            EQUATION_OF_TIME_METHOD
            if solar_time_strategy == SOLAR_TIME_STRATEGY_APPARENT
            else None
        ),
        solar_time_strategy=solar_time_strategy,
    )
