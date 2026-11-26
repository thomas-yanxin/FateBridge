"""Preserve base clock choices and compare explicit hypothetical minute endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta, timezone
from typing import Any

from fatebridge.core.almanac import get_lunar_context, lunar_supported_range_message
from fatebridge.core.calendar import LATE_ZI_HOUR, BaZiCalendar
from fatebridge.core.metaphysics.common import MetaphysicsSeed, require_lunar_month_day
from fatebridge.core.ziwei.ziwei_rulesets import ZiweiDayDivide
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.civil_time import NominalClockLabel
from fatebridge.utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS
from fatebridge.utils.solar_time import (
    SOLAR_TIME_STRATEGY_APPARENT,
    NormalizedBirthTime,
    calculate_solar_time_adjustment,
)
from fatebridge.utils.timezones import (
    is_unspecified_local_time,
    parse_timezone_name,
    timezone_rules_metadata,
)


def _minute_sensitivity(
    normalized: NormalizedBirthTime, birth_second: int | None
) -> dict[str, Any]:
    """Two hypothetical seconds within the input minute, not guessed birth data.

    The base calculation keeps second zero. Re-evaluate solar correction at
    the other physical instant; do not add a frozen EOT across the minute.
    This is an endpoint comparison, not an uncertainty bound or a posterior.
    """
    if birth_second is not None:
        return {
            "method_id": "ziwei_input_minute_endpoint_sensitivity_v1",
            "clock_stage": "after_normalization_before_day_divide",
            "assumption": "birth_second_supplied_no_hypothetical_minute_endpoints",
            "birth_seconds_supplied": True,
            "base_second": birth_second,
            "observed_birth_precision_certified": False,
        }
    start = normalized.corrected_datetime.replace(tzinfo=None)
    civil = normalized.input_datetime
    zone = parse_timezone_name(normalized.timezone)
    elapsed = timedelta(seconds=59, microseconds=999999)
    last = (civil.replace(tzinfo=zone).astimezone(timezone.utc) + elapsed).astimezone(
        zone
    )
    last_wall = last.replace(tzinfo=None)
    # An offset transition can occur inside a historical civil minute. Follow
    # the selected physical member and check that it still supplies the label.
    requested_wall = civil.replace(tzinfo=None) + elapsed
    has_endpoint = last_wall == requested_wall and not is_unspecified_local_time(last)
    placement = [start]
    seconds: list[int | float] = [0]
    if has_endpoint:
        if normalized.applied:
            assert normalized.longitude is not None
            adjustment = calculate_solar_time_adjustment(
                last,
                normalized.timezone,
                normalized.longitude,
                strategy=normalized.solar_time_strategy or SOLAR_TIME_STRATEGY_APPARENT,
            )
            last_wall += timedelta(minutes=adjustment["total_correction_minutes"])
        placement.append(last_wall)
        seconds.append(59.999999)
    branches = "子丑寅卯辰巳午未申酉戌亥"
    hours = [branches[((label.hour + 1) // 2) % 12] for label in placement]
    return dict(
        method_id="ziwei_input_minute_endpoint_sensitivity_v1",
        clock_stage="after_normalization_before_day_divide",
        assumption=(
            "hypothetical_seconds_0_and_59_999999_within_the_given_civil_minute"
            if has_endpoint
            else "second_0_only_upper_endpoint_not_in_selected_civil_minute"
        ),
        birth_seconds_supplied=False,
        base_second=0,
        endpoint_seconds=seconds,
        endpoint_placement_datetimes=[label.isoformat(sep=" ") for label in placement],
        endpoint_hour_branches=hours,
        crosses_hour_branch=hours[0] != hours[1] if has_endpoint else None,
        crosses_placement_date=(
            start.date() != placement[1].date() if has_endpoint else None
        ),
        endpoints_are_alternative_birth_facts=False,
        observed_birth_precision_certified=False,
        scope="endpoint_sensitivity_only_not_a_global_error_bound_or_all_possible_birth_times",
    )


def birth_clock_receipt(
    person: PersonInfo, normalized: NormalizedBirthTime
) -> dict[str, Any]:
    result = normalized.as_dict(include_timezone_resolution=True)
    requested = bool(person.use_true_solar_time)
    assumed_zone = normalized.timezone_source in {
        "default_timezone",
        "longitude_standard_meridian_assumption",
        None,
    }
    coarse = normalized.applied and normalized.resolution_level == "province"
    if requested and not normalized.applied:
        status = "solar_unavailable"
    elif assumed_zone:
        status = "timezone_assumed"
    elif coarse:
        status = "province_longitude"
    else:
        status = "solar_applied" if normalized.applied else "civil_clock_selected"
    advisories = []
    if normalized.resolution_advisory:
        advisories.append(normalized.resolution_advisory)
    if normalized.timezone_source == "longitude_standard_meridian_assumption":
        advisories.append(
            "未从地点确认时区，当前仅按经度邻近的整数UTC偏移作假设，未据此确认当地历史夏令时；请核对birth_timezone。"
        )
    elif normalized.timezone_source == "default_timezone":
        advisories.append(
            "未从输入或地点确认时区，当前采用默认Asia/Shanghai；请核对出生钟表记录的实际时区。"
        )
    if not normalized.applied:
        # Zero applied correction is not evidence that the astronomical
        # equation of time or historical daylight saving offset was zero.
        for key in (
            "longitude_correction_minutes",
            "equation_of_time_minutes",
            "daylight_saving_minutes",
        ):
            result[key] = None
    result.update(
        method_id="ziwei_birth_clock_receipt_v1",
        status=status,
        requested=requested,
        explicitly_requested=bool(requested and person.true_solar_explicit),
        components_computed=normalized.applied,
        timezone_assumed=assumed_zone,
        timezone_rules=timezone_rules_metadata(normalized.timezone),
        applied_delta_seconds=round(
            (
                normalized.corrected_datetime.replace(tzinfo=None)
                - normalized.input_datetime.replace(tzinfo=None)
            ).total_seconds(),
            6,
        ),
        seconds_are_derived_not_birth_accuracy=person.birth_second is None
        or normalized.applied,
        minute_sensitivity=_minute_sensitivity(normalized, person.birth_second),
        advisories=advisories,
        precision_scope="conditional_on_resolved_inputs_not_verified_birthplace_or_historical_clock",
        source_basis={
            "civil_time": "IANA Time Zone Database",
            "solar_time": "USNO Equation of Time",
        },
    )
    return result


def lunar_year_ganzhi(lunar_year: int) -> tuple[str, str]:
    """Use the first lunar day of the year as the year-pillar boundary."""
    return (
        HEAVENLY_STEMS[(lunar_year - 4) % len(HEAVENLY_STEMS)],
        EARTHLY_BRANCHES[(lunar_year - 4) % len(EARTHLY_BRANCHES)],
    )


@dataclass(frozen=True, kw_only=True)
class ZiweiClockState:
    placement_label: NominalClockLabel
    lunar: dict[str, object]
    lunar_year: int
    lunar_month: int
    lunar_day: int
    is_leap_month: bool
    hour_branch: str
    day_stem: str
    day_branch: str
    hour_stem: str
    is_late_zi: bool


def resolve_ziwei_clock_state(
    seed: MetaphysicsSeed, day_divide: ZiweiDayDivide, *, technique: str
) -> ZiweiClockState:
    """Resolve the placement label, lunar date and day/hour pillars together."""
    placement_label = seed.clock
    year, month, day = seed.clock.date_parts
    hour = seed.clock.time_parts[0]
    is_late_zi = hour >= LATE_ZI_HOUR
    rollover = is_late_zi and day_divide == "forward"
    if rollover:
        placement_label = NominalClockLabel(seed.clock.ordinal + 1, 0)
        lunar = get_lunar_context(
            placement_label,
            timezone_name=seed.timezone,
            civil_datetime=seed.input_datetime,
        )
        if lunar is None:
            raise ValueError(
                f"{technique}需要农历月日，无法起盘：{lunar_supported_range_message()}"
            )
        lunar_month, lunar_day = lunar["month"], lunar["day"]
        assert isinstance(lunar_month, int) and isinstance(lunar_day, int)
    else:
        lunar, lunar_month, lunar_day = require_lunar_month_day(seed, technique)
    if is_late_zi:
        day_stem, day_branch = BaZiCalendar.calculate_day_pillar(
            year,
            month,
            day,
            hour=hour,
            apply_late_zi_rollover=rollover,
        )
        hour_stem, hour_branch = BaZiCalendar.calculate_hour_pillar(
            year,
            month,
            day,
            hour,
            apply_late_zi_rollover=rollover,
        )
    else:
        day_stem, day_branch = seed.pillars["day"]
        hour_stem, hour_branch = seed.pillars["hour"]
    lunar_year = lunar.get("year")
    if not isinstance(lunar_year, int):
        raise ValueError(f"{technique}需要完整农历年月日，无法起盘：农历年缺失")
    return ZiweiClockState(
        placement_label=placement_label,
        lunar=lunar,
        lunar_year=lunar_year,
        lunar_month=lunar_month,
        lunar_day=lunar_day,
        is_leap_month=bool(lunar.get("is_leap_month")),
        hour_branch=hour_branch,
        day_stem=day_stem,
        day_branch=day_branch,
        hour_stem=hour_stem,
        is_late_zi=is_late_zi,
    )
