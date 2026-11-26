"""Fast Lichun boundary solver via shared ephemeris (swe.solcross / almanac)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from typing import Any, Literal

from fatebridge.core import almanac, analytic_solar, de440_solar, vsop2013_solar
from fatebridge.core.astro.time_scales import utc_point_from_tt
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.core.solar_model_policy import (
    VALIDATED_SOFTWARE_YEARS,
    VSOP2013_SOFTWARE_YEARS,
    solar_model_policy,
)
from fatebridge.core.solar_term_runtime import solar_term_cache_context
from fatebridge.utils.civil_time import ZonedCalendar, utc_calendar
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.timezones import parse_timezone_name

POLICY_ID = "canping_lichun_projection_context_v1"
EXTENDED_POLICY_ID = "canping_lichun_extended_projection_context_v1"
VSOP2013_POLICY_ID = "canping_lichun_vsop2013_projection_context_v1"


@dataclass(frozen=True)
class ResolvedProjectionBoundary:
    """A resolved Lichun solar-term boundary."""

    year: int
    term: almanac.SolarTerm
    selection: Literal["ordinary_public_year_grid", "bounded_derived_lichun_event"]

    def to_record(self) -> dict[str, object]:
        return {
            "year": self.year,
            "record": self.term.as_dict(),
            "instant_utc": self.term.calendar.utc.isoformat(),
            "selection": self.selection,
        }


@lru_cache(maxsize=256)
def _fallback_lichun_term(
    year: int, zone: str, mode: str, profile: str, _env: tuple[Any, ...]
) -> almanac.SolarTerm:
    """Fallback solver only when year lies outside Swiss Ephemeris / public grid."""
    low = date(year, 2, 1).toordinal() + 1721424.5
    high = date(year, 2, 12).toordinal() + 1721424.5
    if mode == "vsop2013":
        root = vsop2013_solar.longitude_crossing_tt(
            315.0, low, high, expected_source_key=vsop2013_solar.cache_key()
        )
        provider = "vsop2013"
    elif mode == "analytic":
        root = analytic_solar.longitude_crossing_tt(315.0, low, high)
        provider = "fatebridge_analytic"
    else:
        root = de440_solar.longitude_crossing_tt(315.0, low, high, profile_id=profile)
        provider = "jpl_de440"
    point = TTInstant.from_float(root["jd_tt"])
    civil_point = utc_point_from_tt(point)
    calendar = ZonedCalendar(civil_point.as_calendar(), parse_timezone_name(zone))
    return almanac.SolarTerm(
        name="立春",
        calendar=calendar,
        resolution_provider=provider,
        ephemeris_model=str(root["model"]["model_id"]),
        tt_instant=point,
        civil_point=civil_point,
    )


def resolve_projection_boundary(
    year: int, zone: str, *, origin_civil_year: int, origin_bazi_year: int, horizon: int
) -> ResolvedProjectionBoundary:
    """Resolve Lichun (term_index=2) using fast almanac/solcross path."""
    if (
        any(
            type(v) is not int
            for v in (year, origin_civil_year, origin_bazi_year, horizon)
        )
        or not 1 <= horizon <= 120
        or origin_bazi_year not in {origin_civil_year, origin_civil_year - 1}
        or not origin_bazi_year <= year <= origin_bazi_year + horizon
    ):
        raise ValueError("投影边界必须属于已给出生年与原有1至120年范围。")
    mode, jpl = solar_model_policy(), configured_jpl_file()
    low_year, high_year = (
        VSOP2013_SOFTWARE_YEARS if mode == "vsop2013" else VALIDATED_SOFTWARE_YEARS
    )
    in_public_range = low_year <= year <= high_year
    # Fast path: almanac._solar_terms_for_context_year(term_index=2) uses swe.solcross_tt (~0.05ms)
    # for all Swiss Ephemeris years (1800..2420) when mode is auto/swiss/native!
    if mode in {"auto", "swiss", "native"} and jpl is None and 1800 <= year <= 2420:
        context_year = (
            year if in_public_range else (low_year if year < low_year else high_year)
        )
        try:
            (term,) = almanac._solar_terms_for_context_year(
                year,
                zone,
                year if abs(year - context_year) <= 1 else year,
                term_index=2,
            )
            almanac.require_calculated_solar_term(term)
            return ResolvedProjectionBoundary(
                year,
                term,
                (
                    "ordinary_public_year_grid"
                    if in_public_range
                    else "bounded_derived_lichun_event"
                ),
            )
        except (ValueError, EphemerisSourceError):
            if mode == "swiss":
                raise
    if in_public_range or (
        abs(year - origin_civil_year) <= 1 and (year in {low_year - 1, high_year + 1})
    ):
        context_year = almanac._solar_term_source_year(year, origin_civil_year)
        (term,) = almanac._solar_terms_for_context_year(
            year, zone, context_year, term_index=2
        )
        almanac.require_calculated_solar_term(term)
        return ResolvedProjectionBoundary(
            year,
            term,
            (
                "bounded_derived_lichun_event"
                if year != context_year
                else "ordinary_public_year_grid"
            ),
        )
    if mode == "swiss":
        raise EphemerisSourceError("solar_swiss_range")
    if mode == "vsop2013":
        solar_term_cache_context(almanac.swe, year=origin_civil_year)
    profile = (
        vsop2013_solar.MODEL_ID
        if mode == "vsop2013"
        else (
            de440_solar.CANPING_EXTENDED_MODEL_ID
            if 2201 <= origin_civil_year <= 2300 and 2301 <= year <= 2420
            else (
                de440_solar.EXTENDED_MODEL_ID
                if origin_civil_year == 1700 and year == 1699
                else (
                    de440_solar.MODEL_ID
                    if year == 1799
                    else de440_solar.CANPING_MODEL_ID
                )
            )
        )
    )
    env = (mode, jpl, profile)
    term = _fallback_lichun_term(year, zone, mode, profile, env)
    if (solar_model_policy(), configured_jpl_file(), profile) != env:
        raise EphemerisSourceError("solar_configuration_changed")
    return ResolvedProjectionBoundary(year, term, "bounded_derived_lichun_event")


def projection_boundary(
    year: int, zone: str, *, origin_civil_year: int, origin_bazi_year: int, horizon: int
) -> dict[str, Any]:
    """JSON/SDK adapter for a single resolved Lichun event."""
    return resolve_projection_boundary(
        year,
        zone,
        origin_civil_year=origin_civil_year,
        origin_bazi_year=origin_bazi_year,
        horizon=horizon,
    ).to_record()


def boundary_context(
    birth: datetime, zone: str, origin: int, horizon: int, boundaries: list[dict]
) -> dict[str, Any]:
    birth_clock = ZonedCalendar(utc_calendar(birth), parse_timezone_name(zone))
    models = sorted(
        {b["record"]["ephemeris_model"] for b in boundaries if b.get("record")}
    )
    vsop = vsop2013_solar.MODEL_ID in models
    ctx: dict[str, Any] = {
        "policy_id": VSOP2013_POLICY_ID if vsop else POLICY_ID,
        "origin_civil_year": birth_clock.local_parts[0],
        "origin_bazi_year": origin,
        "birth_instant_utc": birth_clock.utc.isoformat(),
        "timezone": zone,
        "horizon_years": horizon,
        "observed_models": models,
        "public_model_years_extended": False,
        "not_a_lifespan_estimate": True,
    }
    if boundaries:
        ctx["boundary_count"] = len(boundaries)
    return ctx
