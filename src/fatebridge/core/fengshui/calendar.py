"""Civil time and explicitly selected year boundaries, independent of BaZi."""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fatebridge.core import almanac
from fatebridge.core.aa1996_solar import MODEL_ID as AA1996_SOLAR_MODEL
from fatebridge.core.analytic_solar import MODEL_ID as ANALYTIC_SOLAR_MODEL
from fatebridge.core.de440_solar import MODEL_ID as DE440_SOLAR_MODEL
from fatebridge.core.moshier_solar import MODEL_ID as COMPLETE_MOSHIER_SOLAR_MODEL
from fatebridge.core.vsop2013_solar import MODEL_ID as VSOP2013_SOLAR_MODEL
from fatebridge.utils.timezones import parse_timezone_name

from .historical_solar import MODEL_ID as HISTORICAL_SOLAR_MODEL
from .historical_solar import historical_solar_resolution

MOSHIER_BOUNDARY_GUARD_SECONDS = 5.0
_MODEL_GUARD_REASONS = {
    "moshier": "moshier_numeric_model_guard_not_accuracy_certification",
    COMPLETE_MOSHIER_SOLAR_MODEL: "complete_moshier_solar_model_guard_not_accuracy_certification",
    AA1996_SOLAR_MODEL: "aa1996_solar_model_guard_not_accuracy_certification",
    VSOP2013_SOLAR_MODEL: "vsop2013_solar_model_guard_not_accuracy_certification",
    ANALYTIC_SOLAR_MODEL: "analytic_solar_model_guard_not_accuracy_certification",
    DE440_SOLAR_MODEL: "de440_solar_model_guard_not_accuracy_certification",
    HISTORICAL_SOLAR_MODEL: "de440_historical_solar_model_guard_not_accuracy_certification",
}


def boundary_model_policy(resolution: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Identify a named numerical guard without turning it into an error bound.

    Keep the established five-second operational policy and one-second numeric
    acceptance gate separate. Neither is a claim about real-world prediction.
    """
    model = resolution.get("ephemeris_model")
    if resolution.get("approximate") is True or model not in _MODEL_GUARD_REASONS:
        return None
    return {
        "ephemeris_model": model,
        "operational_guard_seconds": MOSHIER_BOUNDARY_GUARD_SECONDS,
        "uncertainty_reason": _MODEL_GUARD_REASONS[model],
        "scope": "candidate_preservation_not_numerical_accuracy_acceptance",
    }


def boundary_uncertainty_reason(
    local: datetime, resolution: Dict[str, Any]
) -> Optional[str]:
    """Preserve candidates for a weak solver; never relax the raw TT gate.

    The fixed 4812-crossing comparison retained 569 Moshier failures at the
    one-second gate, maximum 2.455s. Five seconds is a conservative operational
    guard, not an asserted error bound or a new accuracy acceptance threshold.
    """
    boundary = datetime.fromisoformat(resolution["moment"])
    policy = boundary_model_policy(resolution)
    if (
        policy is not None
        and abs(
            (
                local.astimezone(timezone.utc) - boundary.astimezone(timezone.utc)
            ).total_seconds()
        )
        <= policy["operational_guard_seconds"]
    ):
        return str(policy["uncertainty_reason"])
    return None


def boundary_candidate_dates(
    resolution: Dict[str, Any], timezone_name: str
) -> set[date]:
    """Include dates crossed by the model guard without inventing birth hours."""
    moment = datetime.fromisoformat(resolution["moment"])
    policy = boundary_model_policy(resolution)
    if policy is not None:
        tz = parse_timezone_name(timezone_name)
        utc = moment.astimezone(timezone.utc)
        return {
            (utc + timedelta(seconds=n * policy["operational_guard_seconds"]))
            .astimezone(tz)
            .date()
            for n in (-1, 0, 1)
        }
    return {moment.date()}


def lichun(year: int, timezone_name: str) -> datetime:
    historical = historical_solar_resolution(year, "立春", timezone_name)
    if historical is not None:
        return datetime.fromisoformat(historical["moment"]).astimezone(
            parse_timezone_name(timezone_name)
        )
    return next(
        t.moment
        for t in almanac.get_solar_terms_for_year(year, timezone_name)
        if t.name == "立春"
    )


def lichun_resolution(year: int, timezone_name: str) -> Dict[str, Any]:
    """Report the actual per-term provider, not just Swiss import availability."""
    return solar_term_resolution(year, "立春", timezone_name)


def solar_term_resolution(
    year: int, term_name: str, timezone_name: str
) -> Dict[str, Any]:
    """Keep every selected term's actual clock and ephemeris provenance."""
    historical = historical_solar_resolution(year, term_name, timezone_name)
    if historical is not None:
        return historical
    term = next(
        t
        for t in almanac.get_solar_terms_for_year(year, timezone_name)
        if t.name == term_name
    )
    result: Dict[str, Any] = {
        "moment": term.moment.isoformat(),
        "provider": term.resolution_provider,
        "approximate": False,
        "precision_scope": "engine_computed_not_independently_certified_to_seconds",
    }
    from fatebridge.core.astro.time_scales import ephemeris_time
    from fatebridge.core.astro.utc_policy import leap_table
    from fatebridge.core.ephemeris_runtime import (
        ephemeris_call,
        ephemeris_model_from_retflag,
    )

    clock = ephemeris_time(term.moment)
    # The API name does not prove .se1 files were used. Inspect the actual
    # return flag at this reported TT, rather than installed-file presence.
    if term.resolution_provider == "swisseph":
        _, returned = ephemeris_call(
            "calc", clock.jd_tt, almanac.swe.SUN, almanac.swe.FLG_SWIEPH
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
        "civil_policy": clock.method,
        "historical_ut1_convention": clock.method == "pre_1972_swiss_UT1_delta_t",
        "future_leap_seconds_assumed_unchanged": clock.future_leap_seconds_assumed_unchanged,
        "leap_table_expires_at": leap_table()["expires_at"],
    }
    return result


def _uncertain_year_fields(
    year: int, local: datetime, resolution: Dict[str, Any]
) -> Dict[str, Any]:
    return {
        "effective_year": None,
        "provisional_effective_year": year,
        "effective_year_status": "requires_confirmation",
        "candidate_effective_years": [local.year - 1, local.year],
        "boundary_resolution": resolution,
        "valid_from": None,
        "valid_until": None,
    }


def year_context(
    effective_year: Optional[int],
    moment: Optional[datetime],
    timezone_name: str,
    boundary: str = "lichun",
    *,
    resolve_interval: bool = True,
) -> Dict[str, Any]:
    tz = parse_timezone_name(timezone_name)
    local = moment.astimezone(tz) if moment is not None else None
    if effective_year is None and local is None:
        return {
            "effective_year": None,
            "year_boundary": boundary,
            "timezone_name": timezone_name,
        }
    year = effective_year
    uncertain_boundary = None
    if year is None and local is not None:
        year = local.year
        if boundary == "lichun":
            resolution = lichun_resolution(local.year, timezone_name)
            boundary_moment = datetime.fromisoformat(resolution["moment"])
            # Same-tzinfo datetime comparison ignores fold/offset changes.
            # Compare actual instants, retaining explicitly selected folds.
            year -= int(
                local.astimezone(timezone.utc)
                < boundary_moment.astimezone(timezone.utc)
            )
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
    if boundary == "lichun":
        start_resolution = lichun_resolution(year, timezone_name)
        end_resolution = lichun_resolution(year + 1, timezone_name)
        start = datetime.fromisoformat(start_resolution["moment"])
        end = datetime.fromisoformat(end_resolution["moment"])
        timing = {
            "provider": "fatebridge.core.almanac.get_solar_terms_for_year",
            "runtime_swiss_available": almanac.swe is not None,
            "start_resolution": start_resolution,
            "end_resolution": end_resolution,
            "independent_precision_verification": "no_arbitrary_year_second_certification",
            "source_ids": ["S7", "S8", "S9"],
        }
    else:
        start, end = datetime(year, 1, 1, tzinfo=tz), datetime(
            year + 1, 1, 1, tzinfo=tz
        )
        timing = {"provider": "civil_calendar", "convention": "explicit_january_1"}
    result = {
        "effective_year": year,
        "year_boundary": boundary,
        "input_basis": (
            "effective_year_override"
            if effective_year is not None
            else "aware_datetime"
        ),
        "local_moment": local.isoformat() if local is not None else None,
        "timezone_name": timezone_name,
        "valid_from": start.isoformat(),
        "valid_until": end.isoformat(),
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
