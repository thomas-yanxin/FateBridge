"""Capture the actual solar correction, without computing astronomy again."""

import math
from datetime import datetime
from typing import Any

from fatebridge.utils.civil_time import NominalClockLabel, ZonedCalendar, utc_calendar
from fatebridge.utils.solar_time import EQUATION_OF_TIME_METHOD, SolarTimeAdjustment
from fatebridge.utils.timezones import parse_timezone_name


def solar_time_receipt(
    *,
    civil_instant: datetime,
    corrected_label: NominalClockLabel,
    timezone_name: str,
    longitude: float,
    adjustment: SolarTimeAdjustment,
) -> dict[str, Any]:
    """Bind the decomposed correction to its physical input and solar label."""
    if civil_instant.utcoffset() is None:
        raise ValueError("太阳时修正依据须保留带时区的原民用实际时刻")
    local = ZonedCalendar(
        utc_calendar(civil_instant), parse_timezone_name(timezone_name)
    ).require_datetime()
    civil_label = NominalClockLabel.from_local_datetime(local)
    longitude_correction = adjustment["longitude_correction_minutes"]
    equation_of_time = adjustment["equation_of_time_minutes"]
    daylight_saving = adjustment["daylight_saving_minutes"]
    total = adjustment["total_correction_minutes"]
    parts = longitude_correction + equation_of_time - daylight_saving
    actual_delta = (
        (corrected_label.ordinal - civil_label.ordinal) * 86400 * 1000000
        + corrected_label.microseconds_of_day
        - civil_label.microseconds_of_day
    ) / 1000000
    if not all(
        math.isfinite(value)
        for value in (
            adjustment["standard_meridian"],
            longitude_correction,
            equation_of_time,
            daylight_saving,
            total,
            longitude,
        )
    ) or not (abs(parts - total) < 1e-9 and abs(actual_delta - total * 60) < 2e-6):
        raise ValueError("太阳时分项、总修正与实际钟表标签不一致；不能生成不实依据")
    hour, minute, second, microsecond = corrected_label.time_parts
    seconds = hour * 3600 + minute * 60 + second + microsecond / 1e6
    hour_distance = (seconds - 3600) % 7200
    day_distance = (seconds - 23 * 3600) % 86400
    return {
        "status": "captured_at_seed_calculation",
        "applied": True,
        "strategy": "apparent",
        "equation_of_time_method": EQUATION_OF_TIME_METHOD,
        "equation_of_time_time_scale": "UTC_as_UT1",
        "civil_input_instant_utc": utc_calendar(civil_instant).isoformat(),
        "civil_timezone": timezone_name,
        "longitude": longitude,
        **adjustment,
        "apparent_solar_label": corrected_label.isoformat(),
        "correction_basis": "civil_wall_clock_to_solar_label_not_elapsed_time",
        "physical_input_instant_shifted": False,
        "subsecond_accuracy_certified": False,
        "boundary_distances_seconds": {
            "nearest_double_hour_boundary": min(hour_distance, 7200 - hour_distance),
            "day_boundary_23": min(day_distance, 86400 - day_distance),
            "certainty_inferred_from_distance": False,
        },
        "scope": "均时差按UTC近似UT1；未引入实测DUT1，太阳标签不是转换后的另一个物理时刻",
    }
