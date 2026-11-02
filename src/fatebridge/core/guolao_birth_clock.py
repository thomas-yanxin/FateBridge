"""Explicit solar input labels, retained epochs and Guolao hour policy.

These are declared modern input conventions, not a historical clock attribution
to Lu Wei. The nominal label supplies its ordinal hour; inverse JD resolution
does not rewrite that recorded label at a two-hour boundary.
"""

from __future__ import annotations

import math
from datetime import datetime
from fractions import Fraction
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.birth_clock import (
    SOLAR_BASES,
    resolve_solar_birth_clock,
    resolve_solar_epoch,
)
from fatebridge.core.astro.solar_sources import SunSourceCohort, sun_source
from fatebridge.core.astro.source_session import source_session
from fatebridge.core.guolao_classical import BRANCHES
from fatebridge.core.guolao_epoch import birth_utc_label, native_birth_epoch
from fatebridge.utils.civil_time import utc_ordering_key
from fatebridge.utils.errors import EphemerisSourceError

RULE_ID = "guolao.explicit_solar_input.v1"
_P = ParamSpec("_P")
_R = TypeVar("_R")


def solar_input_basis(birth: AstroBirthInfo) -> str | None:
    if birth.clock_conversion is None:
        return None
    basis = birth.clock_conversion.get("input_clock_basis")
    if basis not in SOLAR_BASES:
        raise ValueError("果老太阳钟输入须明确LMT或LAT，不能推定未知钟制")
    return str(basis)


def apparent_clock_required(birth: AstroBirthInfo) -> bool:
    return (
        birth.applied_true_solar or solar_input_basis(birth) == "local_apparent_solar"
    )


def coherent_guolao_solar_call(function: Callable[_P, _R]) -> Callable[_P, _R]:
    @wraps(function)
    def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        if (
            kwargs.get("chart_variant") == "guolao_chart"
            and kwargs.get("birth_clock_basis", "civil") != "civil"
        ):
            with source_session():
                return function(*args, **kwargs)
        return function(*args, **kwargs)

    return wrapped


def solar_input_context(
    birth: AstroBirthInfo, raw: dict[str, Any]
) -> dict[str, Any] | None:
    basis = solar_input_basis(birth)
    if basis is None:
        return None
    conversion = birth.clock_conversion
    assert conversion is not None
    if runtime.swe is None:
        raise ValueError("果老太阳钟换算需要Swiss Ephemeris")
    wall = datetime.fromisoformat(conversion["input_wall_datetime"])
    if wall.tzinfo is not None or birth.timezone_source != "solar_clock_conversion":
        raise EphemerisSourceError("birth_clock_source_mismatch")
    native = native_birth_epoch(birth)
    if native is not None:
        replay_epoch, replay_receipt = resolve_solar_epoch(
            wall,
            birth.longitude,
            basis,
            ephemeris_policy=conversion["solar_ephemeris_policy"],
        )
        assert native.time.jd_tt is not None and replay_epoch.time.jd_tt is not None
        if (
            conversion["converted_utc"] != native.utc_label
            or replay_epoch.utc_label != native.utc_label
            or replay_epoch.utc_is_leap_second != native.utc_is_leap_second
            or abs(replay_epoch.time.jd_tt - native.time.jd_tt) * 86400 > 0.0002
            or abs(raw["julian_day_tt"] - native.time.jd_tt) * 86400 > 0.0002
        ):
            raise EphemerisSourceError("birth_clock_source_mismatch")
        difference = (replay_epoch.time.jd_ut1 - native.time.jd_ut1) * 86400
    else:
        original = datetime.fromisoformat(conversion["converted_utc"])
        if utc_ordering_key(original) != utc_ordering_key(birth.physical_datetime):
            raise EphemerisSourceError("birth_clock_source_mismatch")
        replay, replay_receipt = resolve_solar_birth_clock(
            wall,
            birth.longitude,
            basis,
            ephemeris_policy=conversion["solar_ephemeris_policy"],
        )
        replay_key, birth_key = utc_ordering_key(replay), utc_ordering_key(
            birth.physical_datetime
        )
        difference = (
            (replay_key[0] - birth_key[0]) * 86_400_000_000
            + replay_key[1]
            - birth_key[1]
        ) / 1_000_000
    # This is the existing inverse's numerical contract, not an accuracy bound.
    if abs(difference) > 0.0002 or conversion.get("swisseph_version") != str(
        runtime.swe.version
    ):
        raise EphemerisSourceError("birth_clock_source_mismatch")
    if (
        not math.isfinite(float(conversion["julian_day_ut1"]))
        or abs((conversion["julian_day_ut1"] - raw["julian_day_ut1"]) * 86400) > 0.0002
    ):
        raise EphemerisSourceError("birth_clock_source_mismatch")

    cohort = SunSourceCohort()
    original_sources = conversion["solar_source_comparison"][
        "physical_ephemeris_sources"
    ]
    if basis == "local_apparent_solar":
        model = raw["ephemeris_provenance"]["by_body"]["Sun"]["equatorial_model"]
        if (
            not original_sources
            or conversion["solar_ephemeris_model"] != model
            or set(conversion["solar_ephemeris_models_observed"]) != {model}
        ):
            raise EphemerisSourceError("birth_clock_source_mismatch")
        try:
            for source in [
                *original_sources,
                *replay_receipt["solar_source_comparison"][
                    "physical_ephemeris_sources"
                ],
            ]:
                cohort.add(source)
            natal_source = raw["longitude_motion"]["physical_ephemeris_source"]
            cohort.add(sun_source(natal_source, natal_source["by_factor"]["Sun"]))
        except EphemerisSourceError as error:
            raise EphemerisSourceError("birth_clock_source_mismatch") from error
        if any(source["has_unidentified_sources"] for source in cohort.sources):
            raise EphemerisSourceError("birth_clock_source_mismatch")

    if basis == "local_apparent_solar":
        clock = raw["solar_clock"]
        if (
            clock["julian_day_ut1"] != raw["julian_day_ut1"]
            or clock["sun_apparent_right_ascension"]
            != raw["states"]["Sun"]["right_ascension"]
        ):
            raise EphemerisSourceError("birth_clock_source_mismatch")
        actual = (
            Fraction(
                birth.local_datetime.toordinal() + clock["solar_day_offset_from_civil"]
            )
            * 86400
            + Fraction(clock["apparent_day_fraction_exact"]) * 86400
        )
    else:
        actual = (
            Fraction(raw["julian_day_ut1"])
            + Fraction(birth.longitude) / 360
            + Fraction(1, 2)
            - 1721425
        ) * 86400
    requested = Fraction(wall.toordinal() * 86400) + Fraction(
        ((wall.hour * 60 + wall.minute) * 60 + wall.second) * 1_000_000
        + wall.microsecond,
        1_000_000,
    )
    residual = float(actual - requested)
    if abs(residual) > 0.0002:
        raise EphemerisSourceError("birth_clock_source_mismatch")
    input_branch = BRANCHES[((wall.hour + 1) // 2) % 12]
    use_label = basis == "local_apparent_solar" or not birth.applied_true_solar
    forward = raw["solar_clock"]
    return {
        "ruleset_id": RULE_ID,
        "input_clock_basis": basis,
        "input_wall_datetime": wall.isoformat(),
        "input_calendar": "proleptic_gregorian",
        "carrier_datetime": None if native else birth.physical_datetime.isoformat(),
        "converted_utc": birth_utc_label(birth),
        "birth_timezone_role": (
            "no_datetime_carrier_primary_TT_UT1_not_a_recorded_civil_zone"
            if native
            else "UTC_computation_carrier_not_a_recorded_civil_zone"
        ),
        "true_solar_requested": birth.applied_true_solar,
        "apparent_clock_used": apparent_clock_required(birth),
        "hour_from_input_label": use_label,
        "input_hour_branch": input_branch,
        "forward_apparent_hour_branch": (
            forward["birth_hour_branch"] if forward else None
        ),
        "input_label_and_forward_hour_differ": (
            input_branch != forward["birth_hour_branch"] if forward else None
        ),
        "hour_clock_basis": (
            "recorded_" + basis + "_clock" if use_label else "apparent_solar_display"
        ),
        "physical_instant_shifted": False,
        "additional_correction_to_input_seconds": (
            0.0 if use_label else forward["equation_of_time_seconds"]
        ),
        "original_conversion": conversion,
        "nominal_utc_replay_difference_seconds": None if native else difference,
        **(
            {
                "native_epoch": native.representation(),
                "primary_julian_day_tt": native.time.jd_tt,
                "primary_julian_day_ut1": native.time.jd_ut1,
                "native_UT1_replay_difference_seconds": difference,
            }
            if native
            else {}
        ),
        "same_natal_sky_label_residual_seconds": residual,
        "source_comparison": {
            "status": (
                "compatible_observed_sun_contexts"
                if basis == "local_apparent_solar"
                else "replayed_mean_solar_mapping_no_Sun_position_in_inverse"
            ),
            "original_sun_identity_recorded": bool(original_sources),
            "physical_ephemeris_sources": list(cohort.sources),
            "has_unidentified_sources": any(
                s["has_unidentified_sources"] for s in cohort.sources
            ),
            "scope": "Original inverse, same-label replay and natal Sun contexts; matching models, overlapping observed editions and same-name hashes. Endpoint evidence, not an exclusive or atomic read set, measured Earth rotation or astronomical accuracy certification.",
        },
        "calendar_reference": "converted_physical_instant_UTC_reference_LiChun_and_explicit_month_policy",
        "weekday_date_basis": "input_solar_label_proleptic_gregorian_date_not_UTC_carrier",
        "hour_policy_attribution": "FateBridge_declared_input_convention_not_original_clock_adjudication",
        "recording_precision_certified": False,
        "classical_clock_mapping_accepted": False,
        "event_probability_estimated": False,
    }
