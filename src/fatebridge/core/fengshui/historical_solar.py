"""Actual DE440 crossings for the previously fixed historical endpoint span."""

from datetime import date
from typing import Any

from fatebridge.core import almanac, de440_solar
from fatebridge.core.astro.time_scales import datetime_from_tt, ephemeris_time
from fatebridge.core.astro.utc_policy import leap_table
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.core.solar_model_policy import solar_model_policy
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.timezones import parse_timezone_name

MODEL_ID = de440_solar.HISTORICAL_MODEL_ID
SOFTWARE_YEARS = (1784, 2204)
BASE_SOFTWARE_YEARS = (1800, 2200)


def historical_solar_resolution(
    year: int, term_name: str, timezone_name: str
) -> dict[str, Any] | None:
    """Use the extension only outside the default profile's software years.

    Explicit native/analytic/SPK choices and strict JPL selection keep their
    original behavior. Data or configuration failure never silently picks a
    weaker source. Public request year limits are separate and unchanged.
    """
    if not SOFTWARE_YEARS[0] <= year <= SOFTWARE_YEARS[1] or (
        BASE_SOFTWARE_YEARS[0] <= year <= BASE_SOFTWARE_YEARS[1]
    ):
        return None
    mode = solar_model_policy()
    if mode == "aa1996":
        return _aa1996_resolution(year, term_name, timezone_name)
    if mode not in {"auto", "de440"}:
        return None
    jpl_file = configured_jpl_file()
    if mode == "auto" and jpl_file is not None:
        return None
    source_key = de440_solar.cache_key(MODEL_ID)
    index = almanac.SOLAR_TERM_NAMES.index(term_name)
    month = index // 2 + 1
    low_day, high_day = (1, 12) if index % 2 == 0 else (12, 28)
    low = date(year, month, low_day).toordinal() + 1721424.5
    high = date(year, month, high_day).toordinal() + 1721424.5
    root = de440_solar.longitude_crossing_tt(
        float(almanac.SOLAR_TERM_LONGITUDES[index]), low, high, profile_id=MODEL_ID
    )
    moment = datetime_from_tt(root["jd_tt"]).astimezone(
        parse_timezone_name(timezone_name)
    )
    clock = ephemeris_time(moment)
    try:
        current_configuration = (
            solar_model_policy(),
            configured_jpl_file(),
            de440_solar.cache_key(MODEL_ID),
        )
    except ValueError as error:
        # The initial configuration was valid. An invalid value/source now
        # is a changed runtime configuration, not a fault in the request.
        raise EphemerisSourceError("solar_configuration_changed") from error
    if current_configuration != (mode, jpl_file, source_key):
        raise EphemerisSourceError("solar_configuration_changed")
    return {
        "moment": moment.isoformat(),
        "provider": "jpl_de440",
        "approximate": False,
        "precision_scope": "engine_computed_not_independently_certified_to_seconds",
        "ephemeris_model": MODEL_ID,
        "ephemeris_model_scope": "named_ephemeris_solar_crossing",
        "solar_model_details": {
            **root["model"],
            "root_bracket_tt": root["bracket_tt"],
            "root_bracket_seconds": root["bracket_seconds"],
            "root_time_scale": "TT",
            "selected_crossing_jd_tt": root["jd_tt"],
            "numerical_resolution_is_physical_accuracy": False,
            "civil_time_method": clock.method,
            "historical_ut1_convention": clock.method == "pre_1972_swiss_UT1_delta_t",
            "future_leap_seconds_assumed_unchanged": clock.future_leap_seconds_assumed_unchanged,
            "selection_policy": "fengshui_complete_historical_period_endpoints_v1",
            "software_solar_term_years": list(SOFTWARE_YEARS),
            "selected_civil_year": year,
            "selected_term_name": term_name,
        },
        "time_basis": {
            "root_time_scale": "TT",
            "civil_policy": clock.method,
            "historical_ut1_convention": clock.method == "pre_1972_swiss_UT1_delta_t",
            "future_leap_seconds_assumed_unchanged": clock.future_leap_seconds_assumed_unchanged,
            "leap_table_expires_at": leap_table()["expires_at"],
        },
    }


def _aa1996_resolution(year: int, term_name: str, timezone_name: str) -> dict[str, Any]:
    """Resolve a qualified internal endpoint with the explicitly selected model."""
    from fatebridge.core.solar_term_runtime import solar_term_cache_context

    # No invented in-range input year: this internal range was independently
    # qualified before extending v1.1's working interval. Public year grids
    # continue to enforce their original input range.
    context = solar_term_cache_context(almanac.swe)
    index = almanac.SOLAR_TERM_NAMES.index(term_name)
    moment, provenance = almanac._solar_term_utc_via_analytic(
        year,
        index,
        {},
        aa1996=True,
        expected_aa1996_key=context[-1][2],
    )
    details = provenance["solar_model_details"]
    if details["qualified_solar_term_years"] != list(SOFTWARE_YEARS):
        raise EphemerisSourceError("solar_aa1996_range")
    try:
        unchanged = solar_model_policy() == "aa1996" and (
            solar_term_cache_context(almanac.swe) == context
        )
    except ValueError as error:
        raise EphemerisSourceError("solar_configuration_changed") from error
    if not unchanged:
        raise EphemerisSourceError("solar_configuration_changed")
    return {
        "moment": moment.astimezone(parse_timezone_name(timezone_name)).isoformat(),
        "provider": "moshier_aa1996",
        "approximate": False,
        "precision_scope": "engine_computed_not_independently_certified_to_seconds",
        "ephemeris_model": provenance["ephemeris_model"],
        "ephemeris_model_scope": "named_ephemeris_solar_crossing",
        "solar_model_details": {
            **details,
            "selection_policy": "fengshui_aa1996_internal_period_endpoints_v1",
            "software_solar_term_years": list(SOFTWARE_YEARS),
            "selected_civil_year": year,
            "selected_term_name": term_name,
        },
        "time_basis": {
            "root_time_scale": "TT",
            "civil_policy": details["civil_time_method"],
            "historical_ut1_convention": details["historical_ut1_convention"],
            "future_leap_seconds_assumed_unchanged": details[
                "future_leap_seconds_assumed_unchanged"
            ],
            "leap_table_expires_at": leap_table()["expires_at"],
        },
    }
