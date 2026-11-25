"""Explicit LMT/LAT input labels resolved onto the shared physical time axis.

Solar labels are not civil timezones. LMT = UT1 + east longitude/360;
LAT adds the apparent Sun's equation of time. Both the Sun and the UTC
inversion use FateBridge's shared TT/UT1 policy, including historical UTC.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.earth_attitude import earth_attitude
from fatebridge.core.astro.iers_ut1 import active_ut1
from fatebridge.core.astro.native_coordinates import require_spherical_coordinates
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.reference_frames import rotate_spherical
from fatebridge.core.astro.rotation_policy import earth_rotation_policy
from fatebridge.core.astro.solar_sources import SunSourceCohort, sun_source
from fatebridge.core.astro.source_session import (
    coherent_ephemeris_sources,
    current_source_session,
    source_session,
)
from fatebridge.core.astro.time_scales import (
    ephemeris_time,
    historical_mean_solar_time,
    resolve_tt_from_ut1,
)
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.utils.civil_time import CivilPoint, utc_calendar
from fatebridge.utils.errors import EphemerisSourceError

RULESET = "fatebridge.local_solar_birth_clock.v1"
SOLAR_BASES = {"local_mean_solar", "local_apparent_solar"}
_PRE_ATOMIC_END = utc_calendar(
    datetime(1960, 1, 1, tzinfo=timezone.utc)
).julian_day_exact()
SOURCE_URL = "https://www.astro.com/swisseph/swephprg.htm"
CODE_URL = "https://github.com/aloistr/swisseph/blob/v2.10.03/sweph.c#L7280-L7333"


@dataclass(frozen=True, init=False)
class SolarClockContext:
    ut1: UT1Instant
    tt: TTInstant

    def __init__(self, ut1: UT1Instant | float, tt: TTInstant) -> None:
        object.__setattr__(self, "ut1", UT1Instant.from_value(ut1))
        object.__setattr__(self, "tt", tt)

    @property
    def jd_ut1(self) -> float:
        """Scalar native-query/display adapter of the retained UT1 point."""
        return self.ut1.as_float()


def _validate(basis: str, longitude: float, ephemeris_policy: str = "auto") -> None:
    if basis not in SOLAR_BASES:
        raise ValueError(
            "Solar birth clock requires local_mean_solar or local_apparent_solar"
        )
    else:
        pass
    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("Solar clock longitude must be finite and within -180..180")
    else:
        pass
    if ephemeris_policy not in {"auto", "require_data_files"}:
        raise ValueError("Unsupported solar clock ephemeris policy")
    else:
        pass
    if runtime.swe is None:
        raise ValueError("Swiss Ephemeris is required for local solar clock conversion")
    else:
        pass


@coherent_ephemeris_sources
def _sun_clock(
    context: SolarClockContext,
    ephemeris_policy: str = "auto",
) -> dict[str, Any]:
    """EOT from apparent solar hour angle, evaluated in the shared TT policy.

    Uses the documented Swiss time_equ hour-angle expression in the selected
    physical equator. Transport the source solar ray before subtracting RA.
    Use
    calc(TT) explicitly: calc_ut's internal Delta T may differ from the civil
    forward policy in historical epochs. No observed Earth-orientation data
    are invented by this model calculation.
    """
    swe = runtime.swe
    assert swe is not None
    # Forward civil clocks retain their primary TT. Solar-input inversions
    # construct this same context from their represented UT1 search coordinate.
    ut1 = context.ut1
    tt = context.tt
    coords, flag = runtime.ephemeris_call(
        "calc", tt.as_float(), swe.SUN, swe.FLG_SWIEPH | swe.FLG_EQUATORIAL
    )
    ra, dec, _ = require_spherical_coordinates(
        coords, flag, native=swe, equatorial=True
    )
    attitude = earth_attitude(swe, ut1, julian_day_tt=tt)
    ra, _ = rotate_spherical(attitude.reduction.native_to_target, ra, dec)
    model = runtime.ephemeris_model_from_retflag(flag)
    session = current_source_session()
    assert session is not None
    session.check()
    row = session.trace.observe("equatorial_Sun", model)
    physical_source = sun_source(session.trace.snapshot(), row)
    gast = attitude.equator.greenwich_sidereal_degrees
    if ephemeris_policy == "require_data_files" and model not in {"swieph", "jpl"}:
        raise ValueError("Local solar clock requires data files; Sun used " + model)
    else:
        pass
    day_fraction = (ut1.days + Fraction(1, 2)) % 1
    phase = Fraction(gast) - Fraction(ra) - 360 * day_fraction - 180
    signed = (phase + 180) % 360 - 180
    rotation = earth_rotation_policy(tt, ut1)
    return {
        "equation_of_time_seconds": float(signed * 240),
        "sun_apparent_right_ascension_degrees": ra,
        "greenwich_apparent_sidereal_degrees": gast,
        "solar_ephemeris_model": model,
        "solar_reference": "geocentric_apparent_sun",
        "equatorial_frame": "selected_physical_equator_and_equinox_of_date",
        "sidereal_time_model": rotation["sidereal_time_model"],
        "earth_rotation_policy_id": rotation["policy_id"],
        "_physical_source": physical_source,
        "_julian_day_tt": tt.as_float(),
    }


class _ClockSources:
    def __init__(self) -> None:
        self.cohort = SunSourceCohort()
        self.observations: list[dict[str, Any]] = []

    def add(self, sun: dict[str, Any], jd_ut1: float, phase: str) -> None:
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
    moment: datetime | PhysicalEpoch,
    longitude: float,
    basis: str,
    *,
    ephemeris_policy: str = "auto",
) -> dict[str, Any]:
    """One forward physical-time evaluation, before calendar representation.

    The Fraction label is internal arithmetic, not extra measured precision.
    Keeping it separate lets presentation report an unrepresentable label
    without discarding a valid physical instant or its finite correction.
    """
    _validate(basis, longitude, ephemeris_policy)
    if isinstance(moment, PhysicalEpoch):
        scales = moment.time
    else:
        if moment.utcoffset() is None:
            raise ValueError("Solar clock display requires an aware physical instant")
        else:
            pass
        scales = ephemeris_time(moment)
    assert runtime.swe is not None
    runtime.swe.set_ephe_path(configured_ephemeris_path() or "")
    label = scales.ut1.days + Fraction(longitude) / 360
    sun = None
    if basis == "local_apparent_solar":
        assert scales.tt is not None
        sun = _sun_clock(SolarClockContext(scales.ut1, scales.tt), ephemeris_policy)
    else:
        pass
    if sun is not None:
        label += Fraction(sun["equation_of_time_seconds"]) / 86400
    else:
        pass
    return {
        "julian_day_solar": label,
        "julian_day_ut1": scales.jd_ut1,
        "julian_day_tt": scales.jd_tt,
        "time_scale_method": scales.method,
        "sun": sun,
    }


def solar_wall_clock(
    moment: datetime | PhysicalEpoch,
    longitude: float,
    basis: str,
    *,
    ephemeris_policy: str = "auto",
    _observed_models: list[str] | None = None,
    _source_recorder: _ClockSources | None = None,
) -> datetime:
    """Physical civil instant to a naive solar label; never an IANA timezone."""
    with source_session():
        parts = solar_clock_components(
            moment, longitude, basis, ephemeris_policy=ephemeris_policy
        )
        sun = parts["sun"]
        if sun is not None:
            if _source_recorder is not None:
                _source_recorder.add(sun, parts["julian_day_ut1"], "roundtrip")
            else:
                pass
            if _observed_models is not None:
                _observed_models.append(sun["solar_ephemeris_model"])
            else:
                pass
        else:
            pass
        label = CivilPoint(parts["julian_day_solar"]).as_calendar().as_datetime()
        if label is None:
            raise OverflowError("date value out of range")
        else:
            pass
        return label.replace(tzinfo=None)


def resolve_solar_epoch(
    wall: datetime, longitude: float, basis: str, *, ephemeris_policy: str = "auto"
) -> tuple[PhysicalEpoch, dict[str, Any]]:
    """A supplied solar label to physical TT/UT1 and an optional UTC carrier.

    The input's calendar is proleptic Gregorian. A UTC-named datetime carries
    UT1 labels before the historical UTC era; it does not assert atomic UTC
    existed then. Unknown original clock bases must not be inferred by fitting
    planetary positions or outcomes.
    """
    _validate(basis, longitude, ephemeris_policy)
    if wall.tzinfo is not None:
        raise ValueError("A local solar birth label must not have a civil timezone")
    else:
        pass
    label_jd = utc_calendar(wall.replace(tzinfo=timezone.utc)).julian_day_exact()
    longitude_days = Fraction(longitude) / 360
    nominal_mean = label_jd - longitude_days
    target_ut1 = UT1Instant(nominal_mean)
    sun: dict[str, Any] = {}
    observed_models: list[str] = []
    sources = _ClockSources()

    def sun_at(point: UT1Instant, phase: str) -> dict[str, Any]:
        value = _sun_clock(
            SolarClockContext(point, resolve_tt_from_ut1(point)),
            ephemeris_policy,
        )
        sources.add(value, point.as_float(), phase)
        observed_models.append(value["solar_ephemeris_model"])
        return value

    with source_session():
        assert runtime.swe is not None
        runtime.swe.set_ephe_path(configured_ephemeris_path() or "")
        if basis == "local_apparent_solar":
            selected = active_ut1.get()
            bounds = selected.ut1_bounds if selected is not None else None
            for _ in range(8):
                trial = target_ut1
                if bounds is not None:
                    trial = UT1Instant(min(max(trial.days, bounds[0]), bounds[1]))
                else:
                    pass
                sun = sun_at(trial, "inversion")
                updated = nominal_mean - (
                    Fraction(sun["equation_of_time_seconds"]) / 86400
                )
                target_ut1 = UT1Instant(updated)
                if bounds is not None:
                    bounded = min(max(updated, bounds[0]), bounds[1])
                    if updated != bounded:
                        # The next trial would return to the same endpoint.
                        if trial.days == bounded:
                            raise ValueError(
                                "Local apparent solar clock is outside the IERS C04 source bounds"
                            )
                        else:
                            pass
                        continue
                    else:
                        pass
                else:
                    pass
                if abs(updated - trial.days) <= math.ulp(target_ut1.as_float()):
                    break
                else:
                    pass
            else:
                raise ValueError(
                    "Local apparent solar clock inversion did not converge"
                )
            sun = sun_at(target_ut1, "final")
        else:
            pass
        try:
            if basis == "local_mean_solar" and nominal_mean < _PRE_ATOMIC_END:
                point = CivilPoint(nominal_mean)
                # Keep the established rounded label and the exact UT1 input.
                display = wall.replace(tzinfo=timezone.utc) - timedelta(
                    microseconds=round(Fraction(longitude) * 240 * 1_000_000)
                )
                epoch = PhysicalEpoch(
                    historical_mean_solar_time(point, utc_calendar(display)),
                    display.isoformat(),
                    display,
                    False,
                    point,
                )
            else:
                epoch = PhysicalEpoch.from_ut1(target_ut1)
        except OverflowError:
            # A valid solar label can map beyond UTC datetime's bounds.
            # The physical-native API retains it; the datetime compatibility
            # wrapper still rejects an absent carrier without shifting it.
            epoch = PhysicalEpoch.from_ut1(target_ut1)
        scales = epoch.time
        error = float((scales.ut1.days - target_ut1.days) * 86400)
        if abs(error) > 0.0002:
            raise ValueError(
                "Solar clock inversion did not preserve UT1 within JD resolution"
            )
        else:
            pass
        if epoch.utc_datetime is not None:
            clock_error = (
                solar_wall_clock(
                    epoch if epoch.source_calendar is not None else epoch.utc_datetime,
                    longitude,
                    basis,
                    ephemeris_policy=ephemeris_policy,
                    _observed_models=observed_models,
                    _source_recorder=sources,
                )
                - wall
            ).total_seconds()
        else:
            physical_label = scales.ut1.days + longitude_days
            if basis == "local_apparent_solar":
                assert scales.tt is not None
                check_sun = _sun_clock(
                    SolarClockContext(scales.ut1, scales.tt), ephemeris_policy
                )
                sources.add(check_sun, scales.jd_ut1, "roundtrip")
                observed_models.append(check_sun["solar_ephemeris_model"])
                physical_label += (
                    Fraction(check_sun["equation_of_time_seconds"]) / 86400
                )
            else:
                pass
            clock_error = float((physical_label - label_jd) * 86400)
        if abs(clock_error) > 0.0002:
            raise ValueError(
                "Solar clock inversion did not preserve the supplied clock label"
            )
        else:
            pass
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
            "target_julian_day_ut1": target_ut1.as_float(),
            "julian_day_ut1": scales.jd_ut1,
            "converted_utc": epoch.utc_label,
            "time_scale_method": scales.method,
            "future_leap_seconds_assumed_unchanged": scales.future_leap_seconds_assumed_unchanged,
            "ut1_roundtrip_error_seconds": error,
            "input_clock_roundtrip_error_seconds": clock_error,
            "numerical_resolution_seconds": max(
                math.ulp(target_ut1.as_float()) * 86400, 1e-6
            ),
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
) -> tuple[datetime, dict[str, Any]]:
    """Compatibility path for consumers that explicitly require datetime.

    Physical-native callers use resolve_solar_epoch instead. This wrapper
    cannot represent second60 and continues to reject it without shifting it.
    """
    epoch, receipt = resolve_solar_epoch(
        wall, longitude, basis, ephemeris_policy=ephemeris_policy
    )
    return epoch.require_datetime(), receipt
