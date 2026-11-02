"""Explicit LMT/LAT input labels resolved onto the shared physical time axis.

Solar labels are not civil timezones. LMT = UT1 + east longitude/360;
LAT adds the apparent Sun's equation of time. Both the Sun and the UTC
inversion use FateBridge's shared TT/UT1 policy, including historical UTC.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from typing import Any, Dict, Tuple

from fatebridge.core.astro import runtime
from fatebridge.core.astro.iers_ut1 import active_ut1
from fatebridge.core.astro.julian_day import _julian_day
from fatebridge.core.astro.native_coordinates import require_spherical_coordinates
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.solar_sources import SunSourceCohort, sun_source
from fatebridge.core.astro.source_session import (
    coherent_ephemeris_sources,
    current_source_session,
    source_session,
)
from fatebridge.core.astro.time_scales import (
    ephemeris_time,
    tt_from_ut1,
)
from fatebridge.core.astro_models import earth_rotation_policy
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.utils.errors import EphemerisSourceError

RULESET = "fatebridge.local_solar_birth_clock.v1"
SOLAR_BASES = {"local_mean_solar", "local_apparent_solar"}
SOURCE_URL = "https://www.astro.com/swisseph/swephprg.htm"
CODE_URL = "https://github.com/aloistr/swisseph/blob/v2.10.03/sweph.c#L7280-L7333"


def _validate(basis: str, longitude: float, ephemeris_policy: str = "auto") -> None:
    if basis not in SOLAR_BASES:
        raise ValueError(
            "Solar birth clock requires local_mean_solar or local_apparent_solar"
        )
    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("Solar clock longitude must be finite and within -180..180")
    if ephemeris_policy not in {"auto", "require_data_files"}:
        raise ValueError("Unsupported solar clock ephemeris policy")
    if runtime.swe is None:
        raise ValueError("Swiss Ephemeris is required for local solar clock conversion")


@coherent_ephemeris_sources
def _sun_clock(
    jd_ut1: float,
    ephemeris_policy: str = "auto",
    *,
    _julian_day_tt: float | None = None,
) -> Dict[str, Any]:
    """EOT from apparent solar hour angle, evaluated in the shared TT policy.

    Equivalent to the documented Swiss time_equ hour-angle expression. Use
    calc(TT) explicitly: calc_ut's internal Delta T may differ from the civil
    forward policy in historical epochs. No observed Earth-orientation data
    are invented by this model calculation.
    """
    swe = runtime.swe
    assert swe is not None
    # A forward civil conversion already has its primary TT. Do not round-trip
    # that through model UT1 and introduce a second JD rounding at a file edge.
    # Solar-input inversions still obtain TT from their UT1 search coordinate.
    jd_tt = tt_from_ut1(jd_ut1) if _julian_day_tt is None else _julian_day_tt
    coords, flag = runtime.ephemeris_call(
        "calc", jd_tt, swe.SUN, swe.FLG_SWIEPH | swe.FLG_EQUATORIAL
    )
    ra, _, _ = require_spherical_coordinates(coords, flag, native=swe, equatorial=True)
    model = runtime.ephemeris_model_from_retflag(flag)
    session = current_source_session()
    assert session is not None
    session.check()
    row = session.trace.observe("equatorial_Sun", model)
    physical_source = sun_source(session.trace.snapshot(), row)
    sidereal_hours = runtime.ephemeris_call("sidtime", jd_ut1)
    try:
        gast = float(sidereal_hours) * 15
    except (TypeError, ValueError, OverflowError) as error:
        raise EphemerisSourceError("coordinate_values_unavailable") from error
    if not math.isfinite(gast) or not 0 <= gast < 360:
        raise EphemerisSourceError("coordinate_values_unavailable")
    if ephemeris_policy == "require_data_files" and model not in {"swieph", "jpl"}:
        raise ValueError("Local solar clock requires data files; Sun used " + model)
    day_fraction = (Fraction(jd_ut1) + Fraction(1, 2)) % 1
    phase = Fraction(gast) - Fraction(ra) - 360 * day_fraction - 180
    signed = (phase + 180) % 360 - 180
    rotation = earth_rotation_policy(jd_tt, jd_ut1)
    return {
        "equation_of_time_seconds": float(signed * 240),
        "sun_apparent_right_ascension_degrees": ra,
        "greenwich_apparent_sidereal_degrees": gast,
        "solar_ephemeris_model": model,
        "solar_reference": "geocentric_apparent_sun",
        "sidereal_time_model": rotation["sidereal_time_model"],
        "earth_rotation_policy_id": rotation["policy_id"],
        "_physical_source": physical_source,
        "_julian_day_tt": jd_tt,
    }


class _ClockSources:
    def __init__(self) -> None:
        self.cohort = SunSourceCohort()
        self.observations: list[dict[str, Any]] = []

    def add(self, sun: Dict[str, Any], jd_ut1: float, phase: str) -> None:
        try:
            index = self.cohort.add(sun["_physical_source"])
        except EphemerisSourceError as error:
            raise EphemerisSourceError("birth_clock_source_mismatch") from error
        self.observations.append(
            {
                "phase": phase,
                "julian_day_ut1": jd_ut1,
                "julian_day_tt": sun["_julian_day_tt"],
                "source_index": index,
            }
        )

    def result(self) -> dict[str, Any]:
        return {
            "status": (
                "compatible_observed_sun_contexts"
                if self.observations
                else "no_solar_position_dependency"
            ),
            "physical_ephemeris_sources": self.cohort.sources,
            "has_unidentified_sources": any(
                s["has_unidentified_sources"] for s in self.cohort.sources
            ),
            "observations": self.observations,
            "scope": "Actual inversion/final/roundtrip Sun calls; returned models, overlapping observed slot DE editions and same-name hashes compared. New auxiliary contexts do not retroactively establish earlier reads. File endpoints verified by the outer session, not proof of atomic reads, numerical accuracy or measured Earth rotation.",
        }


@coherent_ephemeris_sources
def solar_clock_components(
    moment: datetime,
    longitude: float,
    basis: str,
    *,
    ephemeris_policy: str = "auto",
) -> Dict[str, Any]:
    """One forward physical-time evaluation, before calendar representation.

    The Fraction label is internal arithmetic, not extra measured precision.
    Keeping it separate lets presentation report an unrepresentable label
    without discarding a valid physical instant or its finite correction.
    """
    _validate(basis, longitude, ephemeris_policy)
    if moment.utcoffset() is None:
        raise ValueError("Solar clock display requires an aware physical instant")
    assert runtime.swe is not None
    runtime.swe.set_ephe_path(configured_ephemeris_path() or "")
    scales = ephemeris_time(moment)
    label = Fraction(scales.jd_ut1) + Fraction(longitude) / 360
    sun = (
        _sun_clock(scales.jd_ut1, ephemeris_policy, _julian_day_tt=scales.jd_tt)
        if basis == "local_apparent_solar"
        else None
    )
    if sun is not None:
        label += Fraction(sun["equation_of_time_seconds"]) / 86400
    return {
        "julian_day_solar": label,
        "julian_day_ut1": scales.jd_ut1,
        "julian_day_tt": scales.jd_tt,
        "time_scale_method": scales.method,
        "sun": sun,
    }


def solar_wall_clock(
    moment: datetime,
    longitude: float,
    basis: str,
    *,
    ephemeris_policy: str = "auto",
    _observed_models: list[str] | None = None,
    _source_recorder: _ClockSources | None = None,
) -> datetime:
    """Physical civil instant to a naive solar label; never an IANA timezone."""
    _validate(basis, longitude, ephemeris_policy)
    if moment.utcoffset() is None:
        raise ValueError("Solar clock display requires an aware physical instant")
    with source_session():
        parts = solar_clock_components(
            moment, longitude, basis, ephemeris_policy=ephemeris_policy
        )
        sun = parts["sun"]
        if sun is not None:
            if _source_recorder is not None:
                _source_recorder.add(sun, parts["julian_day_ut1"], "roundtrip")
            if _observed_models is not None:
                _observed_models.append(sun["solar_ephemeris_model"])
        return datetime(1970, 1, 1) + timedelta(
            days=float(parts["julian_day_solar"] - Fraction(4881175, 2))
        )


def resolve_solar_epoch(
    wall: datetime, longitude: float, basis: str, *, ephemeris_policy: str = "auto"
) -> Tuple[PhysicalEpoch, Dict[str, Any]]:
    """A supplied solar label to physical TT/UT1 and an optional UTC carrier.

    The input's calendar is proleptic Gregorian. A UTC-named datetime carries
    UT1 labels before the historical UTC era; it does not assert atomic UTC
    existed then. Unknown original clock bases must not be inferred by fitting
    planetary positions or outcomes.
    """
    _validate(basis, longitude, ephemeris_policy)
    if wall.tzinfo is not None:
        raise ValueError("A local solar birth label must not have a civil timezone")
    label_jd = _julian_day(wall.replace(tzinfo=timezone.utc))
    longitude_days = Fraction(longitude) / 360
    target_ut1 = float(Fraction(label_jd) - longitude_days)
    sun: Dict[str, Any] = {}
    observed_models: list[str] = []
    sources = _ClockSources()

    def sun_at(jd: float, phase: str) -> Dict[str, Any]:
        value = _sun_clock(jd, ephemeris_policy)
        sources.add(value, jd, phase)
        observed_models.append(value["solar_ephemeris_model"])
        return value

    with source_session():
        assert runtime.swe is not None
        runtime.swe.set_ephe_path(configured_ephemeris_path() or "")
        if basis == "local_apparent_solar":
            for _ in range(8):
                sun = sun_at(target_ut1, "inversion")
                updated = float(
                    Fraction(label_jd)
                    - longitude_days
                    - Fraction(sun["equation_of_time_seconds"]) / 86400
                )
                step = abs(updated - target_ut1)
                target_ut1 = updated
                if step <= math.ulp(target_ut1):
                    break
            else:
                raise ValueError(
                    "Local apparent solar clock inversion did not converge"
                )
            sun = sun_at(target_ut1, "final")
        # Exact LMT arithmetic need not introduce JD rounding into an old UT1
        # carrier clock. Modern UTC must still invert the modeled UT1 offset.
        try:
            exact_mean = (
                wall.replace(tzinfo=timezone.utc)
                - timedelta(microseconds=round(Fraction(longitude) * 240 * 1_000_000))
                if basis == "local_mean_solar"
                else None
            )
            if exact_mean is not None and exact_mean < datetime(
                1960, 1, 1, tzinfo=timezone.utc
            ):
                moment = exact_mean
                epoch = PhysicalEpoch(
                    ephemeris_time(moment), moment.isoformat(), moment, False
                )
            else:
                epoch = PhysicalEpoch.from_ut1(target_ut1)
        except OverflowError:
            # A valid solar label can map beyond UTC datetime's bounds.
            # The physical-native API retains it; the datetime compatibility
            # wrapper still rejects an absent carrier without shifting it.
            epoch = PhysicalEpoch.from_ut1(target_ut1)
        scales = epoch.time
        error = (scales.jd_ut1 - target_ut1) * 86400
        if abs(error) > 0.0002:
            raise ValueError(
                "Solar clock inversion did not preserve UT1 within JD resolution"
            )
        if epoch.utc_datetime is not None:
            clock_error = (
                solar_wall_clock(
                    epoch.utc_datetime,
                    longitude,
                    basis,
                    ephemeris_policy=ephemeris_policy,
                    _observed_models=observed_models,
                    _source_recorder=sources,
                )
                - wall
            ).total_seconds()
        else:
            physical_label = Fraction(scales.jd_ut1) + longitude_days
            if basis == "local_apparent_solar":
                check_sun = _sun_clock(
                    scales.jd_ut1, ephemeris_policy, _julian_day_tt=scales.jd_tt
                )
                sources.add(check_sun, scales.jd_ut1, "roundtrip")
                observed_models.append(check_sun["solar_ephemeris_model"])
                physical_label += (
                    Fraction(check_sun["equation_of_time_seconds"]) / 86400
                )
            clock_error = float((physical_label - Fraction(label_jd)) * 86400)
        if abs(clock_error) > 0.0002:
            raise ValueError(
                "Solar clock inversion did not preserve the supplied clock label"
            )
        return epoch, {
            "ruleset_id": RULESET,
            "author": "FateBridge",
            "input_clock_basis": basis,
            "input_calendar": "proleptic_gregorian",
            "input_wall_datetime": wall.isoformat(),
            "longitude_east_degrees": longitude,
            "longitude_offset_seconds": float(Fraction(longitude) * 240),
            "solar_ephemeris_policy": ephemeris_policy,
            "solar_ephemeris_models_observed": sorted(set(observed_models)),
            "solar_model_call_count": len(observed_models),
            **{key: value for key, value in sun.items() if not key.startswith("_")},
            "solar_source_comparison": sources.result(),
            "target_julian_day_ut1": target_ut1,
            "julian_day_ut1": scales.jd_ut1,
            "converted_utc": epoch.utc_label,
            "time_scale_method": scales.method,
            "future_leap_seconds_assumed_unchanged": scales.future_leap_seconds_assumed_unchanged,
            "ut1_roundtrip_error_seconds": error,
            "input_clock_roundtrip_error_seconds": clock_error,
            "numerical_resolution_seconds": max(math.ulp(target_ut1) * 86400, 1e-6),
            "measured_eop_applied": active_ut1.get() is not None,
            "clock_accuracy_certified": False,
            "swisseph_version": str(runtime.swe.version),
            "source_url": SOURCE_URL,
            "source_code_url": CODE_URL,
            "source_sections": "9.2, 9.4; apparent solar hour-angle expression",
        }


def resolve_solar_birth_clock(
    wall: datetime,
    longitude: float,
    basis: str,
    *,
    ephemeris_policy: str = "auto",
) -> Tuple[datetime, Dict[str, Any]]:
    """Compatibility path for consumers that explicitly require datetime.

    Physical-native callers use resolve_solar_epoch instead. This wrapper
    cannot represent second60 and continues to reject it without shifting it.
    """
    epoch, receipt = resolve_solar_epoch(
        wall, longitude, basis, ephemeris_policy=ephemeris_policy
    )
    return epoch.require_datetime(), receipt
