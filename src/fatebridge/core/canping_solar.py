"""Only the derived Lichun events needed by the existing120-year schedule."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date, datetime, timezone
from functools import lru_cache
from typing import Any

from fatebridge.core import (
    aa1996_solar,
    almanac,
    analytic_solar,
    de440_solar,
    vsop2013_solar,
)
from fatebridge.core.astro.time_scales import (
    datetime_from_tt,
    datetime_from_tt_point,
    ephemeris_time,
)
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.utc_policy import leap_table
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.core.solar_model_policy import (
    VALIDATED_SOFTWARE_YEARS,
    VSOP2013_SOFTWARE_YEARS,
    solar_model_policy,
)
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.timezones import parse_timezone_name

POLICY_ID = "canping_lichun_projection_context_v1"
EXTENDED_POLICY_ID = "canping_lichun_extended_projection_context_v1"
VSOP2013_POLICY_ID = "canping_lichun_vsop2013_projection_context_v1"


@lru_cache(maxsize=128)
def _extended_root(year: int, profile: str, identity: tuple) -> dict[str, Any]:
    """Newly qualified events use explicit two-part TT, never event tables."""
    low = date(year, 2, 1).toordinal() + 1721424.5
    high = date(year, 2, 12).toordinal() + 1721424.5
    return de440_solar.longitude_crossing_tt_parts(315.0, low, high, profile_id=profile)


def _extended_event_profile(
    year: int, origin: int, mode: str, jpl: str | None
) -> str | None:
    if mode != "de440" and not (mode == "auto" and jpl is None):
        return None
    if origin == 1700 and year == 1699:
        return de440_solar.EXTENDED_MODEL_ID
    if 2201 <= origin <= 2300 and 2301 <= year <= 2420:
        return de440_solar.CANPING_EXTENDED_MODEL_ID
    return None


def _extended_event(
    year: int,
    zone: str,
    origin: int,
    bazi: int,
    horizon: int,
    mode: str,
    jpl: str | None,
    profile: str,
) -> dict[str, Any]:
    key = _source_key(mode, profile)
    root = deepcopy(_extended_root(year, profile, key))
    moment = datetime_from_tt_point(TTInstant.from_parts(*root["tt_parts"])).astimezone(
        parse_timezone_name(zone)
    )
    clock = ephemeris_time(moment)
    try:
        after = solar_model_policy(), configured_jpl_file(), _source_key(mode, profile)
    except ValueError as exc:
        raise EphemerisSourceError("solar_configuration_changed") from exc
    if after != (
        mode,
        jpl,
        key,
    ):
        raise EphemerisSourceError("solar_configuration_changed")
    details = {
        **root["model"],
        "root_bracket_tt": [sum(p) for p in root["tt_bracket_parts"]],
        "tt_parts": root["tt_parts"],
        "tt_bracket_parts": root["tt_bracket_parts"],
        "numerical_epoch_representation": "explicit_two_part_tt",
        "root_bracket_seconds": root["bracket_seconds"],
        "root_time_scale": "TT",
        "selected_crossing_jd_tt": root["jd_tt"],
        "numerical_resolution_is_physical_accuracy": False,
        "civil_time_method": clock.method,
        "historical_ut1_convention": clock.method == "pre_1972_swiss_UT1_delta_t",
        "future_leap_seconds_assumed_unchanged": clock.future_leap_seconds_assumed_unchanged,
        "projection_origin_civil_year": origin,
        "projection_origin_bazi_year": bazi,
        "projection_horizon_years": horizon,
        "public_model_years_extended": False,
        "selection_policy": EXTENDED_POLICY_ID,
    }
    term = almanac.SolarTerm(
        name="立春",
        moment=moment,
        date_key=moment.strftime("%Y%m%d"),
        day_ganzhi=almanac.get_day_ganzhi(moment.year, moment.month, moment.day),
        resolution_provider="jpl_de440",
        ephemeris_model=profile,
        ephemeris_library_version="fatebridge.canping_solar/extended_projection_1.0.0",
        solar_model_details=details,
    )
    return {
        "year": year,
        "record": term.as_dict(),
        "instant_utc": moment.astimezone(timezone.utc).isoformat(),
        "ephemeris_retflags": [],
        "ephemeris_library_version": term.ephemeris_library_version,
        "selection": "bounded_derived_lichun_event",
    }


@lru_cache(maxsize=256)
def _root(year: int, mode: str, profile: str, identity: tuple) -> dict[str, Any]:
    """TT roots depend on loaded source identity, never on a stored event oracle."""
    low = date(year, 2, 1).toordinal() + 1721424.5
    high = date(year, 2, 12).toordinal() + 1721424.5
    if mode == "vsop2013":
        return vsop2013_solar.longitude_crossing_tt(
            315.0, low, high, expected_source_key=identity
        )
    if mode == "aa1996":
        return aa1996_solar.longitude_crossing_tt(
            315.0, low, high, expected_source_key=identity
        )
    if mode == "analytic":
        return analytic_solar.longitude_crossing_tt(315.0, low, high)
    return de440_solar.longitude_crossing_tt(315.0, low, high, profile_id=profile)


def _source_key(mode: str, profile: str) -> tuple:
    if mode == "vsop2013":
        return vsop2013_solar.cache_key()
    if mode == "aa1996":
        return aa1996_solar.cache_key()
    if mode == "analytic":
        return (analytic_solar.profile()["loaded_sha256"],)
    return de440_solar.cache_key(profile)


def projection_boundary(
    year: int, zone: str, *, origin_civil_year: int, origin_bazi_year: int, horizon: int
) -> dict[str, Any]:
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
    if mode == "vsop2013":
        from .solar_term_runtime import solar_term_cache_context

        # Validate the real origin and strict-JPL policy before any derived cache.
        solar_term_cache_context(almanac.swe, year=origin_civil_year)
    extended = _extended_event_profile(year, origin_civil_year, mode, jpl)
    if extended is not None:
        return _extended_event(
            year,
            zone,
            origin_civil_year,
            origin_bazi_year,
            horizon,
            mode,
            jpl,
            extended,
        )
    low_year, high_year = (
        VSOP2013_SOFTWARE_YEARS if mode == "vsop2013" else VALIDATED_SOFTWARE_YEARS
    )
    # Canping needs one Lichun per annual interval, not every solar term.
    # The explicit VSOP origin and complete horizon were checked above.
    extension = mode == "vsop2013" or (
        low_year <= origin_civil_year <= high_year
        and not low_year <= year <= high_year
        and (
            mode in {"de440", "analytic", "aa1996", "vsop2013"}
            or (mode == "auto" and jpl is None)
        )
    )
    if not extension:
        if mode == "swiss" and not low_year <= year <= high_year:
            if year not in {low_year - 1, high_year + 1}:
                raise EphemerisSourceError("solar_swiss_range")
            terms = almanac._solar_terms_for_context_year(
                year, zone, low_year if year < low_year else high_year
            )
            selection = "bounded_derived_lichun_event"
        else:
            terms = almanac.get_solar_terms_for_year(year, zone)
            selection = "ordinary_public_year_grid"
        term = next(t for t in terms if t.name == "立春")
        almanac.require_calculated_solar_term(term)
    else:
        if (
            not low_year <= year <= high_year
            and year != low_year - 1
            and not high_year + 1 <= year <= high_year + 120
        ):
            raise ValueError("该立春不在已冻结的有界派生事件范围内。")
        profile = (
            vsop2013_solar.MODEL_ID
            if mode == "vsop2013"
            else (
                aa1996_solar.MODEL_ID
                if mode == "aa1996"
                else (
                    de440_solar.MODEL_ID
                    if year == 1799
                    else de440_solar.CANPING_MODEL_ID
                )
            )
        )
        key = _source_key(mode, profile)
        root = deepcopy(_root(year, mode, profile, key))
        moment = (
            datetime_from_tt_point(TTInstant.from_float(root["jd_tt"]))
            if mode == "vsop2013"
            else datetime_from_tt(root["jd_tt"])
        ).astimezone(parse_timezone_name(zone))
        clock = ephemeris_time(moment)
        try:
            after = (
                solar_model_policy(),
                configured_jpl_file(),
                _source_key(mode, profile),
            )
        except ValueError as exc:
            raise EphemerisSourceError("solar_configuration_changed") from exc
        if after != (mode, jpl, key):
            raise EphemerisSourceError("solar_configuration_changed")
        details = {
            **root["model"],
            "root_bracket_tt": root["bracket_tt"],
            "root_bracket_seconds": root["bracket_seconds"],
            "root_time_scale": "TT",
            "selected_crossing_jd_tt": root["jd_tt"],
            "numerical_resolution_is_physical_accuracy": False,
            "civil_time_method": clock.method,
            "historical_ut1_convention": clock.method == "pre_1972_swiss_UT1_delta_t",
            "future_leap_seconds_assumed_unchanged": clock.future_leap_seconds_assumed_unchanged,
            "projection_origin_civil_year": origin_civil_year,
            "projection_origin_bazi_year": origin_bazi_year,
            "projection_horizon_years": horizon,
            "public_model_years_extended": False,
            "selection_policy": VSOP2013_POLICY_ID if mode == "vsop2013" else POLICY_ID,
        }
        term = almanac.SolarTerm(
            name="立春",
            moment=moment,
            date_key=moment.strftime("%Y%m%d"),
            day_ganzhi=almanac.get_day_ganzhi(moment.year, moment.month, moment.day),
            resolution_provider=(
                "vsop2013"
                if mode == "vsop2013"
                else (
                    "moshier_aa1996"
                    if mode == "aa1996"
                    else ("fatebridge_analytic" if mode == "analytic" else "jpl_de440")
                )
            ),
            ephemeris_model=str(root["model"]["model_id"]),
            ephemeris_library_version="fatebridge.canping_solar/1.0.0",
            solar_model_details=details,
        )
        selection = "bounded_derived_lichun_event"
    return {
        "year": year,
        "record": term.as_dict(),
        "instant_utc": term.moment.astimezone(timezone.utc).isoformat(),
        "ephemeris_retflags": list(term.ephemeris_retflags),
        "ephemeris_library_version": term.ephemeris_library_version,
        "selection": selection,
    }


def boundary_context(
    birth: datetime, zone: str, origin: int, horizon: int, boundaries: list[dict]
) -> dict[str, Any]:
    receipts = json.dumps(
        boundaries,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    extended = any(
        b["record"].get("solar_model_details", {}).get("selection_policy")
        == EXTENDED_POLICY_ID
        for b in boundaries
    )
    vsop = any(
        b["record"]["ephemeris_model"] == vsop2013_solar.MODEL_ID for b in boundaries
    )
    return {
        "policy_id": (
            VSOP2013_POLICY_ID
            if vsop
            else EXTENDED_POLICY_ID if extended else POLICY_ID
        ),
        **(
            {
                "registered_public_input_years": list(VSOP2013_SOFTWARE_YEARS),
            }
            if vsop
            else {}
        ),
        "origin_civil_year": birth.astimezone(parse_timezone_name(zone)).year,
        "origin_bazi_year": origin,
        "birth_instant_utc": birth.astimezone(timezone.utc).isoformat(),
        "timezone": zone,
        "horizon_years": horizon,
        "boundary_count": len(boundaries),
        "boundary_receipts_sha256": hashlib.sha256(receipts).hexdigest(),
        "observed_models": sorted({b["record"]["ephemeris_model"] for b in boundaries}),
        "derived_event_years": [
            b["year"]
            for b in boundaries
            if b["selection"] == "bounded_derived_lichun_event"
        ],
        "de440_projection_profile_used": any(
            b["record"]["ephemeris_model"]
            in {de440_solar.CANPING_MODEL_ID, de440_solar.CANPING_EXTENDED_MODEL_ID}
            for b in boundaries
        ),
        "public_model_years_extended": False,
        **(
            {
                "registered_public_input_years": [1700, 2300],
                "qualified_origin_civil_year_ranges": [[1700, 1799], [2201, 2300]],
                "de440_extended_projection_profile_used": any(
                    b["record"]["ephemeris_model"]
                    == de440_solar.CANPING_EXTENDED_MODEL_ID
                    for b in boundaries
                ),
            }
            if extended
            else {}
        ),
        "not_a_lifespan_estimate": True,
        "leap_table_expires_at": leap_table()["expires_at"],
        "scope": "Complete original horizon, actual Lichun receipts and same-run selection. Future UTC/leap seconds and IANA rules remain conditional; event coverage is not classical or real-world prediction certification.",
    }


def projection_snapshot(context: dict[str, Any]) -> str:
    return (
        "[参平年序·实际立春来源]\n"
        f"出生民用年{context['origin_civil_year']}，干支年标签{context['origin_bazi_year']}；"
        f"保留{context['horizon_years']}年序及{context['boundary_count']}个边界。\n"
        f"实际模型：{'、'.join(context['observed_models'])}。派生立春许可不扩大公开模型年份；"
        "未来UTC与时区仍按所列条件，120年范围不是寿命估计。"
    )
