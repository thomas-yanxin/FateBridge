"""Preserve base clock choices and compare explicit hypothetical minute endpoints."""

from __future__ import annotations

from datetime import timedelta, timezone
from typing import Any

from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.solar_time import (
    SOLAR_TIME_STRATEGY_APPARENT,
    NormalizedBirthTime,
    calculate_solar_time_adjustment,
)
from fatebridge.utils.timezones import parse_timezone_name, timezone_rules_metadata


def _minute_sensitivity(normalized: NormalizedBirthTime) -> dict[str, Any]:
    """Two hypothetical seconds within the input minute, not guessed birth data.

    The base calculation keeps second zero. Re-evaluate solar correction at
    the other physical instant; do not add a frozen EOT across the minute.
    This is an endpoint comparison, not an uncertainty bound or a posterior.
    """
    start = normalized.corrected_datetime.replace(tzinfo=None)
    if normalized.applied:
        zone = parse_timezone_name(normalized.timezone)
        first = normalized.input_datetime.replace(tzinfo=zone).astimezone(timezone.utc)
        last = (first + timedelta(seconds=59.999999)).astimezone(zone)
        assert normalized.longitude is not None
        adjustment = calculate_solar_time_adjustment(
            last,
            normalized.timezone,
            normalized.longitude,
            strategy=normalized.solar_time_strategy or SOLAR_TIME_STRATEGY_APPARENT,
        )
        end = last.replace(tzinfo=None) + timedelta(
            minutes=adjustment["total_correction_minutes"]
        )
    elif normalized.input_datetime.utcoffset() is not None:
        end = (
            (
                normalized.input_datetime.astimezone(timezone.utc)
                + timedelta(seconds=59.999999)
            )
            .astimezone(normalized.input_datetime.tzinfo)
            .replace(tzinfo=None)
        )
    else:
        end = normalized.input_datetime + timedelta(seconds=59.999999)
    branches = "子丑寅卯辰巳午未申酉戌亥"
    hours = [branches[((label.hour + 1) // 2) % 12] for label in (start, end)]
    return dict(
        method_id="ziwei_input_minute_endpoint_sensitivity_v1",
        assumption="hypothetical_seconds_0_and_59_999999_within_the_given_civil_minute",
        birth_seconds_supplied=False,
        base_second=0,
        endpoint_seconds=[0, 59.999999],
        endpoint_placement_datetimes=[
            label.isoformat(sep=" ") for label in (start, end)
        ],
        endpoint_hour_branches=hours,
        crosses_hour_branch=hours[0] != hours[1],
        crosses_placement_date=start.date() != end.date(),
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
        seconds_are_derived_not_birth_accuracy=True,
        minute_sensitivity=_minute_sensitivity(normalized),
        advisories=advisories,
        precision_scope="conditional_on_resolved_inputs_not_verified_birthplace_or_historical_clock",
        source_basis={
            "civil_time": "https://www.iana.org/time-zones/theory",
            "solar_time": "https://aa.usno.navy.mil/faq/eqtime",
        },
    )
    return result
