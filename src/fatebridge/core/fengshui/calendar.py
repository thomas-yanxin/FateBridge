"""Civil time, Lichun year boundaries, 12-Jie solar months, and ZiBai term brackets."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta, timezone, tzinfo
from fractions import Fraction
from typing import Any

from fatebridge.core import almanac, de440_solar
from fatebridge.core.aa1996_solar import MODEL_ID as AA1996_SOLAR_MODEL
from fatebridge.core.analytic_solar import MODEL_ID as ANALYTIC_SOLAR_MODEL
from fatebridge.core.astro.time_scales import ephemeris_time, utc_point_from_tt
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.utc_policy import leap_table
from fatebridge.core.de440_solar import MODEL_ID as DE440_SOLAR_MODEL
from fatebridge.core.de441_solar import MODEL_ID as DE441_SOLAR_MODEL
from fatebridge.core.ephemeris_runtime import (
    ephemeris_call,
    ephemeris_model_from_retflag,
)
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.core.solar_model_policy import solar_model_policy
from fatebridge.core.solar_term_clock import native_solar_root_time_policy
from fatebridge.core.solar_term_runtime import solar_term_cache_context
from fatebridge.core.vsop2013_solar import MODEL_ID as VSOP2013_SOLAR_MODEL
from fatebridge.utils.civil_clock import clock_offset_changes
from fatebridge.utils.civil_time import (
    CivilPoint,
    CivilPointRecord,
    ZonedCalendar,
    nominal_calendar_bracket,
    utc_calendar,
)
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.timezones import (
    format_local_time_or_utc,
    is_unspecified_local_time,
    parse_timezone_name,
)

HISTORICAL_SOLAR_MODEL = de440_solar.HISTORICAL_MODEL_ID
SOFTWARE_YEARS = (1784, 2204)
BASE_SOFTWARE_YEARS = (1800, 2200)

MOSHIER_BOUNDARY_GUARD_SECONDS = 5.0
MODEL_GUARD_NAMES = {
    "moshier": "moshier",
    DE441_SOLAR_MODEL: "de441_solar",
    AA1996_SOLAR_MODEL: "aa1996_solar",
    VSOP2013_SOLAR_MODEL: "vsop2013_solar",
    ANALYTIC_SOLAR_MODEL: "analytic_solar",
    DE440_SOLAR_MODEL: "de440_solar",
    HISTORICAL_SOLAR_MODEL: "de440_historical_solar",
}

JIE = (
    "立春",
    "惊蛰",
    "清明",
    "立夏",
    "芒种",
    "小暑",
    "立秋",
    "白露",
    "寒露",
    "立冬",
    "大雪",
    "小寒",
)
MONTH_BRANCHES = tuple("寅卯辰巳午未申酉戌亥子丑")


def _aa1996_resolution(year: int, term_name: str, timezone_name: str) -> dict[str, Any]:
    context = solar_term_cache_context(almanac.swe)
    index = almanac.SOLAR_TERM_NAMES.index(term_name)
    moment, provenance = almanac._solar_term_utc_via_analytic(
        year,
        index,
        aa1996=True,
        expected_aa1996_key=context[-1][2],
    )
    receipt = almanac.aa1996_solar.source_receipt()
    if receipt["qualified_solar_term_years"] != list(SOFTWARE_YEARS):
        raise EphemerisSourceError("solar_aa1996_range")
    try:
        unchanged = solar_model_policy() == "aa1996" and (
            solar_term_cache_context(almanac.swe) == context
        )
    except ValueError as error:
        raise EphemerisSourceError("solar_configuration_changed") from error
    if not unchanged:
        raise EphemerisSourceError("solar_configuration_changed")
    calendar = ZonedCalendar(moment, parse_timezone_name(timezone_name))
    clock = ephemeris_time(calendar.utc)
    return {
        "moment": calendar.isoformat(),
        "civil_point": provenance["resolved_civil_point"].to_record(),
        "provider": "moshier_aa1996",
        "approximate": False,
        "ephemeris_model": provenance["ephemeris_model"],
        "time_basis": {
            "root_time_scale": "TT",
            "civil_policy": clock.method,
            "historical_ut1_convention": clock.method == "pre_1972_swiss_UT1_delta_t",
            "future_leap_seconds_assumed_unchanged": clock.future_leap_seconds_assumed_unchanged,
            "leap_table_expires_at": leap_table()["expires_at"],
        },
    }


def historical_solar_resolution(
    year: int, term_name: str, timezone_name: str
) -> dict[str, Any] | None:
    """Resolve DE440/AA1996 crossings only outside the base software years."""
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
    source_key = de440_solar.cache_key(HISTORICAL_SOLAR_MODEL)
    index = almanac.SOLAR_TERM_NAMES.index(term_name)
    month = index // 2 + 1
    low_day, high_day = (1, 12) if index % 2 == 0 else (12, 28)
    low = date(year, month, low_day).toordinal() + 1721424.5
    high = date(year, month, high_day).toordinal() + 1721424.5
    root = de440_solar.longitude_crossing_tt(
        float(almanac.SOLAR_TERM_LONGITUDES[index]),
        low,
        high,
        profile_id=HISTORICAL_SOLAR_MODEL,
    )
    point = utc_point_from_tt(TTInstant.from_float(root["jd_tt"]))
    calendar = ZonedCalendar(point.as_calendar(), parse_timezone_name(timezone_name))
    moment = calendar.require_datetime()
    clock = ephemeris_time(moment)
    try:
        current_configuration = (
            solar_model_policy(),
            configured_jpl_file(),
            de440_solar.cache_key(HISTORICAL_SOLAR_MODEL),
        )
    except ValueError as error:
        raise EphemerisSourceError("solar_configuration_changed") from error
    if current_configuration != (mode, jpl_file, source_key):
        raise EphemerisSourceError("solar_configuration_changed")
    return {
        "moment": moment.isoformat(),
        "civil_point": point.to_record(),
        "provider": "jpl_de440",
        "approximate": False,
        "ephemeris_model": HISTORICAL_SOLAR_MODEL,
        "time_basis": {
            "root_time_scale": "TT",
            "civil_policy": clock.method,
            "historical_ut1_convention": clock.method == "pre_1972_swiss_UT1_delta_t",
            "future_leap_seconds_assumed_unchanged": clock.future_leap_seconds_assumed_unchanged,
            "leap_table_expires_at": leap_table()["expires_at"],
        },
    }


def boundary_model_policy(
    resolution: Mapping[str, object], *, date_only: bool = False
) -> dict[str, Any] | None:
    """Identify a named numerical guard without turning it into an error bound."""
    model = resolution.get("ephemeris_model")
    if not isinstance(model, str) or resolution.get("approximate") is True:
        return None
    name = MODEL_GUARD_NAMES.get(model)
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
    if resolution.get("local_clock_status") == "undefined":
        return None
    tz = parse_timezone_name(timezone_name)
    point = resolution_point(resolution.get("civil_point"), resolution["moment"])

    def local_date(day: Fraction) -> date:
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
    return solar_term_resolution(year, "立春", timezone_name)


def solar_term_resolution(
    year: int, term_name: str, timezone_name: str
) -> dict[str, Any]:
    historical = historical_solar_resolution(year, term_name, timezone_name)
    if historical is not None:
        return historical
    return solar_term_receipt(almanac.get_solar_term(year, term_name, timezone_name))


def solar_term_receipt(term: almanac.SolarTerm) -> dict[str, Any]:
    defined = term.has_defined_local_clock
    result: dict[str, Any] = {
        "moment": (
            term.calendar.isoformat() if defined else term.calendar.utc.isoformat()
        ),
        "civil_point": term.point.to_record(),
        "provider": term.resolution_provider,
        "approximate": False,
        "precision_scope": "engine_computed_not_independently_certified_to_seconds",
    }
    if not defined:
        result["local_clock_status"] = "undefined"
    if term.tt_instant is None:
        raise ValueError("Solar source probe requires the retained TT boundary")
    clock_policy = native_solar_root_time_policy(term.calendar.utc)
    if term.resolution_provider == "swisseph":
        _, returned = ephemeris_call(
            "calc", term.tt_instant.as_float(), almanac.swe.SUN, almanac.swe.FLG_SWIEPH
        )
        result["ephemeris_model"] = ephemeris_model_from_retflag(returned)
    else:
        result["ephemeris_model"] = term.ephemeris_model
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
            "start_resolution": {
                k: v
                for k, v in start_resolution.items()
                if k not in {"civil_point", "time_basis"}
            },
            "end_resolution": {
                k: v
                for k, v in end_resolution.items()
                if k not in {"civil_point", "time_basis"}
            },
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


def _next_month(year: int, month: int, step: int) -> tuple[int, int]:
    index = year * 12 + month - 1 + step
    y, m = divmod(index, 12)
    return y, m + 1


def _month_boundary(
    year: int, month: int, zone: str, *, term: almanac.SolarTerm | None = None
) -> dict[str, Any]:
    name = JIE[month - 1]
    civil_year = year + int(month == 12)
    resolution = (
        solar_term_receipt(term)
        if term is not None
        else solar_term_resolution(civil_year, name, zone)
    )
    return {
        "term_name": name,
        "civil_year": civil_year,
        **resolution,
    }


def solar_month_context(
    effective_year: int | None,
    month_number: int | None,
    moment: datetime | None,
    zone: str,
) -> dict[str, Any]:
    tz = parse_timezone_name(zone)
    local = moment.astimezone(tz) if moment is not None else None
    result: dict[str, Any] = {
        "effective_solar_year": None,
        "solar_month_number": None,
        "month_branch": None,
        "timezone_name": zone,
        **seasonal_query_clock(local),
        "year_boundary": "lichun",
        "month_boundary": "twelve_jie_instants",
        "interval_policy": "start_inclusive_end_exclusive",
    }
    if effective_year is None and local is None:
        return {**result, "input_basis": "missing"}
    start_term = end_term = None
    if local is not None:
        start_term, end_term = almanac.get_jie_boundaries(local, zone)
        month_number = JIE.index(start_term.name) + 1
        source_year = start_term.source_grid_year
        if source_year is None:
            assert start_term.has_defined_local_clock
            source_year = start_term.calendar.local_parts[0]
        effective_year = source_year - int(month_number == 12)
    assert effective_year is not None and month_number is not None
    next_year, next_month = _next_month(effective_year, month_number, 1)
    start = _month_boundary(effective_year, month_number, zone, term=start_term)
    end = _month_boundary(next_year, next_month, zone, term=end_term)
    result.update(
        effective_solar_year=effective_year,
        solar_month_number=month_number,
        month_branch=MONTH_BRANCHES[month_number - 1],
        input_basis="aware_datetime" if local is not None else "confirmed_solar_month",
        valid_from=start["moment"],
        valid_until=end["moment"],
        timing={
            "provider": (
                "fatebridge.core.almanac.get_jie_boundaries"
                if local is not None
                else "fatebridge.core.almanac.get_solar_terms_for_year"
            ),
            "start_resolution": start,
            "end_resolution": end,
        },
        precision_policy={
            "moshier_guard_seconds": MOSHIER_BOUNDARY_GUARD_SECONDS,
            "numeric_acceptance_gate_seconds": 1.0,
        },
    )
    model_policies = []
    for name, resolution in (("start", start), ("end", end)):
        policy = boundary_model_policy(resolution)
        if policy is not None:
            model_policies.append({"boundary": name, **policy})
    if model_policies:
        result["precision_policy"]["boundary_model_policies"] = model_policies
    if local is not None:
        candidates = {(effective_year, month_number)}
        uncertain = []
        for resolution, neighbor in (
            (start, _next_month(effective_year, month_number, -1)),
            (end, (next_year, next_month)),
        ):
            reason = boundary_uncertainty_reason(local, resolution)
            if reason is not None:
                candidates.add(neighbor)
                uncertain.append({**resolution, "uncertainty_reason": reason})
        if uncertain:
            resolutions = {
                (effective_year, month_number): start,
                (next_year, next_month): end,
            }

            def endpoint(y: int, m: int) -> dict[str, Any]:
                key = (y, m)
                if key not in resolutions:
                    resolutions[key] = _month_boundary(y, m, zone)
                return {
                    **resolutions[key],
                    "full_resolution_path": (
                        f"layers.monthly_stars.time_context.candidate_boundary_resolutions.{y}_{m}"
                    ),
                }

            intervals = []
            for y, m in sorted(candidates):
                left = endpoint(y, m)
                right = endpoint(*_next_month(y, m, 1))
                intervals.append(
                    {
                        "effective_solar_year": y,
                        "solar_month_number": m,
                        "month_branch": MONTH_BRANCHES[m - 1],
                        "candidate_only": True,
                        "valid_from": left["moment"],
                        "valid_until": right["moment"],
                        "start_resolution": left,
                        "end_resolution": right,
                    }
                )
            provisional = {
                key: result[key]
                for key in (
                    "effective_solar_year",
                    "solar_month_number",
                    "month_branch",
                    "valid_from",
                    "valid_until",
                )
            }
            result["timing"]["interval_basis"] = "provisional_solar_month"
            result.update(
                month_status="requires_confirmation",
                provisional_effective_solar_year=effective_year,
                provisional_solar_month_number=month_number,
                effective_solar_year=(
                    effective_year if len({y for y, _ in candidates}) == 1 else None
                ),
                solar_month_number=None,
                month_branch=None,
                valid_from=None,
                valid_until=None,
                provisional_interval=provisional,
                candidate_months=intervals,
                candidate_boundary_resolutions={
                    f"{y}_{m}": resolution for (y, m), resolution in resolutions.items()
                },
                uncertain_boundary_resolutions=uncertain,
            )
    return result


# Six ZiBai seasonal anchor segments: (term_name, jiazi_anchor, direction_sign, half)
ZIBAI_DAY_SEGMENTS: tuple[tuple[str, int, int, str], ...] = (
    ("冬至", 1, 1, "yang_dun"),
    ("雨水", 7, 1, "yang_dun"),
    ("谷雨", 4, 1, "yang_dun"),
    ("夏至", 9, -1, "yin_dun"),
    ("处暑", 3, -1, "yin_dun"),
    ("霜降", 6, -1, "yin_dun"),
)
_ZIBAI_ANCHOR_NAMES = frozenset(seg[0] for seg in ZIBAI_DAY_SEGMENTS)
_ZIBAI_SEGMENT_BY_TERM = {seg[0]: seg for seg in ZIBAI_DAY_SEGMENTS}


def zibai_solar_segment(moment: datetime, timezone_name: str) -> dict[str, Any]:
    """Locate the ZiBai anchor segment (冬至/雨水/谷雨/夏至/处暑/霜降) for moment."""
    local = almanac.localize_datetime(moment, timezone_name)
    key = utc_calendar(local).julian_day_exact()
    year = local.year
    terms: list[almanac.SolarTerm] = []
    for y in (year - 1, year):
        for term in almanac.get_solar_terms_for_year(y, timezone_name):
            if term.name in _ZIBAI_ANCHOR_NAMES:
                terms.append(term)
    terms.sort(key=lambda t: t.point.day)
    active = None
    for term in terms:
        if term.point.day <= key:
            active = term
        else:
            break
    if active is None:
        raise ValueError("Unable to locate ZiBai solstice/jieqi segment")
    term_name, jiazi_anchor, step, dun_half = _ZIBAI_SEGMENT_BY_TERM[active.name]
    return {
        "anchor_term": term_name,
        "anchor_moment": active.calendar.isoformat(),
        "jiazi_anchor_star": jiazi_anchor,
        "progression_direction": "ascending" if step > 0 else "descending",
        "step": step,
        "dun_half": dun_half,
    }
