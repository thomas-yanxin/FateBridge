"""Civil time and explicitly selected year boundaries, independent of BaZi."""

from collections.abc import Mapping
from datetime import date, datetime, timedelta, timezone, tzinfo
from fractions import Fraction
from typing import Any

from fatebridge.core import almanac
from fatebridge.core.aa1996_solar import MODEL_ID as AA1996_SOLAR_MODEL
from fatebridge.core.analytic_solar import MODEL_ID as ANALYTIC_SOLAR_MODEL
from fatebridge.core.astro.utc_policy import leap_table
from fatebridge.core.de440_solar import MODEL_ID as DE440_SOLAR_MODEL
from fatebridge.core.de441_solar import MODEL_ID as DE441_SOLAR_MODEL
from fatebridge.core.ephemeris_runtime import (
    ephemeris_call,
    ephemeris_model_from_retflag,
)
from fatebridge.core.fengshui.historical_solar import MODEL_ID as HISTORICAL_SOLAR_MODEL
from fatebridge.core.fengshui.historical_solar import historical_solar_resolution
from fatebridge.core.solar_term_clock import native_solar_root_time_policy
from fatebridge.core.vsop2013_solar import MODEL_ID as VSOP2013_SOLAR_MODEL
from fatebridge.utils.civil_time import (
    CivilPoint,
    CivilPointRecord,
    ZonedCalendar,
    nominal_calendar_bracket,
    utc_calendar,
)
from fatebridge.utils.clock_events import clock_offset_changes
from fatebridge.utils.timezones import (
    format_local_time_or_utc,
    is_unspecified_local_time,
    parse_timezone_name,
)

MOSHIER_BOUNDARY_GUARD_SECONDS = 5.0
_MODEL_GUARD_NAMES = {
    "moshier": "moshier",
    DE441_SOLAR_MODEL: "de441_solar",
    AA1996_SOLAR_MODEL: "aa1996_solar",
    VSOP2013_SOLAR_MODEL: "vsop2013_solar",
    ANALYTIC_SOLAR_MODEL: "analytic_solar",
    DE440_SOLAR_MODEL: "de440_solar",
    HISTORICAL_SOLAR_MODEL: "de440_historical_solar",
}


def boundary_model_policy(
    resolution: Mapping[str, object], *, date_only: bool = False
) -> dict[str, Any] | None:
    """Identify a named numerical guard without turning it into an error bound.

    Keep the established five-second operational policy and one-second numeric
    acceptance gate separate. Neither is a claim about real-world prediction.
    """
    model = resolution.get("ephemeris_model")
    if not isinstance(model, str) or resolution.get("approximate") is True:
        return None
    name = _MODEL_GUARD_NAMES.get(model)
    if name is None:
        return None
    guard_name = "moshier_numeric" if model == "moshier" else name
    policy = {
        "ephemeris_model": model,
        "operational_guard_seconds": MOSHIER_BOUNDARY_GUARD_SECONDS,
        "uncertainty_reason": f"{guard_name}_model_guard_not_accuracy_certification",
        "scope": "candidate_preservation_not_numerical_accuracy_acceptance",
    }
    if date_only:
        policy["reason"] = f"{name}_guard_crosses_civil_date_not_fabricated_birth_hour"
    return policy


def resolution_point(record: CivilPointRecord | None, moment: str) -> CivilPoint:
    """Read the retained event, or the label precision of a saved old receipt."""
    if record is None:
        return CivilPoint(ZonedCalendar.from_isoformat(moment).utc.julian_day_exact())
    cap = record["excluded_before"]
    return CivilPoint(
        Fraction(int(record["numerator"]), int(record["denominator"])),
        Fraction(int(cap["numerator"]), int(cap["denominator"])) if cap else None,
    )


def boundary_uncertainty_reason(
    local: datetime, resolution: dict[str, Any]
) -> str | None:
    """Preserve candidates for a weak solver; never relax the raw TT gate.

    The fixed 4812-crossing comparison retained 569 Moshier failures at the
    one-second gate, maximum 2.455s. Five seconds is a conservative operational
    guard, not an asserted error bound or a new accuracy acceptance threshold.
    """
    policy = boundary_model_policy(resolution)
    if policy is None:
        return None
    boundary = resolution_point(resolution.get("civil_point"), resolution["moment"])
    distance = abs(utc_calendar(local).julian_day_exact() - boundary.day) * 86400
    if distance <= policy["operational_guard_seconds"]:
        return str(policy["uncertainty_reason"])
    return None


def boundary_dates(
    resolution: dict[str, Any], timezone_name: str
) -> tuple[date, set[date]] | None:
    """Project a defined event date and dates touched by its closed guard."""
    if resolution.get("local_clock_status") == "undefined":
        return None
    tz = parse_timezone_name(timezone_name)
    point = resolution_point(resolution.get("civil_point"), resolution["moment"])

    def local_date(day: Fraction) -> date:
        # Zone transitions and offsets are on the representable clock grid.
        lower, _ = nominal_calendar_bracket(day)
        return date(*ZonedCalendar(lower, tz).local_parts[:3])

    primary = local_date(point.day)
    policy = boundary_model_policy(resolution)
    if policy is None:
        return primary, {primary}
    guard = Fraction(policy["operational_guard_seconds"]) / 86400
    return primary, {
        local_date(point.day - guard),
        primary,
        local_date(point.day + guard),
    }


def lichun(year: int, timezone_name: str) -> datetime:
    historical = historical_solar_resolution(year, "立春", timezone_name)
    if historical is not None:
        return datetime.fromisoformat(historical["moment"]).astimezone(
            parse_timezone_name(timezone_name)
        )
    return almanac.get_solar_term(year, "立春", timezone_name).moment


def lichun_resolution(year: int, timezone_name: str) -> dict[str, Any]:
    """Report the actual per-term provider, not just Swiss import availability."""
    return solar_term_resolution(year, "立春", timezone_name)


def solar_term_resolution(
    year: int, term_name: str, timezone_name: str
) -> dict[str, Any]:
    """Keep every selected term's actual clock and ephemeris provenance."""
    historical = historical_solar_resolution(year, term_name, timezone_name)
    if historical is not None:
        return historical
    return solar_term_receipt(almanac.get_solar_term(year, term_name, timezone_name))


def solar_term_receipt(term: almanac.SolarTerm) -> dict[str, Any]:
    """Present the selected boundary without fetching another year grid."""
    defined = term.has_defined_local_clock
    result: dict[str, Any] = {
        "moment": (
            term.calendar.isoformat() if defined else term.calendar.utc.isoformat()
        ),
        "civil_point": term.point.to_record(),
        "comparison_policy": "retained_nominal_civil_point_v1",
        "provider": term.resolution_provider,
        "approximate": False,
        "precision_scope": "engine_computed_not_independently_certified_to_seconds",
    }
    if not defined:
        result["local_clock_status"] = "undefined"
    if term.tt_instant is None:
        raise ValueError("Solar source probe requires the retained TT boundary")
    clock_policy = native_solar_root_time_policy(term.calendar.utc)
    # The API name does not prove .se1 files were used. Inspect the actual
    # return flag at the selected root, not its re-encoded civil display.
    if term.resolution_provider == "swisseph":
        _, returned = ephemeris_call(
            "calc", term.tt_instant.as_float(), almanac.swe.SUN, almanac.swe.FLG_SWIEPH
        )
        result["ephemeris_model"] = ephemeris_model_from_retflag(returned)
        result["ephemeris_model_scope"] = "sun_position_at_reported_TT"
    else:
        # A native probe here would describe a different Sun model.
        result["ephemeris_model"] = term.ephemeris_model
        result["ephemeris_model_scope"] = (
            "named_analytic_solar_crossing"
            if term.resolution_provider == "fatebridge_analytic"
            else "named_ephemeris_solar_crossing"
        )
        result["solar_model_details"] = term.as_dict()["solar_model_details"]
    result["time_basis"] = {
        "root_time_scale": "TT",
        "civil_policy": clock_policy["civil_time_policy"],
        "historical_ut1_convention": clock_policy["historical_ut1_convention"],
        "future_leap_seconds_assumed_unchanged": clock_policy[
            "future_leap_seconds_assumed_unchanged"
        ],
        "leap_table_expires_at": leap_table()["expires_at"],
    }
    return result


def seasonal_query_clock(local: datetime | None) -> dict[str, str | None]:
    """Preserve the actual instant when the selected local clock is undefined."""
    if local is not None and is_unspecified_local_time(local):
        return {
            "local_moment": None,
            "local_clock_status": "undefined",
            "utc_moment": format_local_time_or_utc(local),
        }
    return {"local_moment": local.isoformat() if local is not None else None}


def _uncertain_year_fields(
    year: int, local: datetime, resolution: dict[str, Any]
) -> dict[str, Any]:
    return {
        "effective_year": None,
        "provisional_effective_year": year,
        "effective_year_status": "requires_confirmation",
        "candidate_effective_years": [local.year - 1, local.year],
        "boundary_resolution": resolution,
        "valid_from": None,
        "valid_until": None,
    }


def _january_query_interval(
    local: datetime, zone: tzinfo, start: datetime, end: datetime
) -> tuple[str | None, str | None]:
    """Find the query's connected interval between defined January year cuts."""
    query = local.astimezone(timezone.utc)
    year = local.year
    starts: list[tuple[datetime, str]] = []
    stops: list[tuple[datetime, str]] = []
    for midnight in (start, end):
        if is_unspecified_local_time(midnight):
            continue
        later = midnight.replace(fold=1)
        first = midnight.astimezone(timezone.utc)
        last = later.astimezone(timezone.utc)
        if first == last or is_unspecified_local_time(later):
            (starts if midnight.year == year else stops).append(
                (first, midnight.isoformat())
            )
            continue
        lower, upper = sorted((first, last))
        # The fold coordinates bracket the relevant offset change. Some
        # coordinates are synthetic in a gap, so check both sides on UTC.
        cuts = {lower, upper}
        cuts.update(at for at, _, _ in clock_offset_changes(zone, lower, upper))
        for at in cuts:
            previous = (at - timedelta(microseconds=1)).astimezone(zone)
            current = at.astimezone(zone)
            if is_unspecified_local_time(previous) or is_unspecified_local_time(
                current
            ):
                continue
            if previous.year != year == current.year:
                starts.append((at, current.isoformat()))
            elif previous.year == year != current.year:
                stops.append((at, current.isoformat()))
    left = max((cut for cut in starts if cut[0] <= query), default=None)
    right = min((cut for cut in stops if cut[0] > query), default=None)
    return (left[1] if left else None, right[1] if right else None)


def year_context(
    effective_year: int | None,
    moment: datetime | None,
    timezone_name: str,
    boundary: str = "lichun",
    *,
    resolve_interval: bool = True,
) -> dict[str, Any]:
    tz = parse_timezone_name(timezone_name)
    local = moment.astimezone(tz) if moment is not None else None
    if effective_year is None and local is None:
        return {
            "effective_year": None,
            "year_boundary": boundary,
            "timezone_name": timezone_name,
        }
    query_clock = seasonal_query_clock(local)
    year = effective_year
    uncertain_boundary = None
    if year is None and local is not None:
        if (
            boundary == "january_1"
            and query_clock.get("local_clock_status") == "undefined"
        ):
            return {
                "effective_year": None,
                "effective_year_status": "requires_confirmation",
                "year_boundary": boundary,
                "input_basis": "aware_datetime",
                "timezone_name": timezone_name,
                **query_clock,
                "valid_from": None,
                "valid_until": None,
            }
        year = local.year
        if boundary == "lichun":
            resolution = lichun_resolution(local.year, timezone_name)
            point = resolution_point(
                resolution.get("civil_point"), resolution["moment"]
            )
            year -= int(utc_calendar(local).julian_day_exact() < point.day)
            reason = boundary_uncertainty_reason(local, resolution)
            if reason is not None:
                uncertain_boundary = {**resolution, "uncertainty_reason": reason}
                policy = boundary_model_policy(resolution)
                if policy is not None:
                    uncertain_boundary["operational_guard_seconds"] = policy[
                        "operational_guard_seconds"
                    ]
    assert year is not None
    if not resolve_interval:
        result = {
            "effective_year": year,
            "year_boundary": boundary,
            "input_basis": (
                "effective_year_override"
                if effective_year is not None
                else "aware_datetime"
            ),
            "timezone_name": timezone_name,
            "valid_from": None,
            "valid_until": None,
            "interval_scope": (
                "not_needed_for_confirmed_effective_birth_year"
                if effective_year is not None
                else "year_interval_resolution_not_requested"
            ),
        }
        if uncertain_boundary is not None:
            assert local is not None
            result.update(_uncertain_year_fields(year, local, uncertain_boundary))
        return result
    valid_from: str | None
    valid_until: str | None
    if boundary == "lichun":
        start_resolution = lichun_resolution(year, timezone_name)
        end_resolution = lichun_resolution(year + 1, timezone_name)
        valid_from = datetime.fromisoformat(start_resolution["moment"]).isoformat()
        valid_until = datetime.fromisoformat(end_resolution["moment"]).isoformat()
        timing = {
            "provider": "fatebridge.core.almanac.get_solar_term",
            "runtime_swiss_available": almanac.swe is not None,
            "start_resolution": start_resolution,
            "end_resolution": end_resolution,
            "independent_precision_verification": "no_arbitrary_year_second_certification",
            "source_ids": ["S7", "S8", "S9"],
        }
    else:
        start, end = (
            datetime(year, 1, 1, tzinfo=tz),
            datetime(year + 1, 1, 1, tzinfo=tz),
        )
        if local is not None and effective_year is None:
            valid_from, valid_until = _january_query_interval(local, tz, start, end)
        else:
            valid_from = None if is_unspecified_local_time(start) else start.isoformat()
            valid_until = None if is_unspecified_local_time(end) else end.isoformat()
        timing = {"provider": "civil_calendar", "convention": "explicit_january_1"}
    result = {
        "effective_year": year,
        "year_boundary": boundary,
        "input_basis": (
            "effective_year_override"
            if effective_year is not None
            else "aware_datetime"
        ),
        **query_clock,
        "timezone_name": timezone_name,
        "valid_from": valid_from,
        "valid_until": valid_until,
        "interval_policy": "start_inclusive_end_exclusive",
        "timing": timing,
    }
    if uncertain_boundary is not None:
        assert local is not None
        result.update(_uncertain_year_fields(year, local, uncertain_boundary))
        result["interval_scope"] = "candidate_years_only_no_confirmed_year_validity"
        result["timing"] = {**timing, "interval_basis": "provisional_effective_year"}
        intervals = []
        for candidate in (local.year - 1, local.year):
            first = lichun_resolution(candidate, timezone_name)
            last = lichun_resolution(candidate + 1, timezone_name)
            intervals.append(
                {
                    "effective_year": candidate,
                    "valid_from": first["moment"],
                    "valid_until": last["moment"],
                    "start_resolution": first,
                    "end_resolution": last,
                }
            )
        result["candidate_year_intervals"] = intervals
    return result
