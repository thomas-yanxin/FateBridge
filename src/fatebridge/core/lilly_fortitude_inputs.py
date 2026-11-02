"""Coherent daily displacement and dated stars for Lilly's p115 ledger."""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.ephemeris import _swisseph_planet_state
from fatebridge.core.astro.geometry import native_lahiri_ayanamsha
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    assert_physical_configuration,
)
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.fixed_stars import apparent_positions
from fatebridge.core.lilly_fortitudes import ORDER
from fatebridge.utils.errors import EphemerisSourceError


@runtime.preserve_ephemeris_path()
def collect_fortitude_inputs(subject: Any) -> dict[str, Any]:
    """Forward one TT day, with five native positions and one selected source.

    The daily-displacement magnitude and instantaneous direction are separate.
    Historical text's 24h is operationalized as86400TT seconds, not an invented
    printed instantaneous rate or a modern mean fitted to an example.
    """
    at = getattr(subject, "julian_day_tt", None)
    result: dict[str, Any] = {
        "status": "not_computed",
        "reason": "native_epoch_unavailable",
        "epoch_jd_tt": at,
        "motion": {},
        "north_node_longitude": None,
        "node_model": "mean_north_lunar_node_if_supplied_by_native_subject",
        "star_longitudes": {},
        "star_position_policy": "dated_native_apparent_positions",
        "daily_motion_policy": "Magnitude of unwrapped native forward oneTT-day longitude displacement at offsets0,1/4,1/2,3/4,1; instantaneous direction separate; not a physical error bound",
        "day_interval_tt": None,
        "longitude_frame": None,
        "physical_ephemeris_source": None,
        "stars_profile": None,
    }
    if at is None or runtime.swe is None:
        return result
    if not math.isfinite(at):
        raise ValueError("Fortitude epoch must be finite")
    zodiac = getattr(subject, "zodiac_type", None)
    if zodiac not in {"Tropic", "Tropical", "Sidereal"}:
        result["reason"] = "unknown_zodiac_frame"
        return result
    sidereal = zodiac == "Sidereal"
    selected = configured_ephemeris_path()
    trace = PhysicalEphemerisTrace()
    contexts: dict[float, dict[str, Any]] = {}
    models: dict[str, str] = {}
    basis = getattr(subject, "calculation_basis", None) or {}
    expected = (basis.get("physical_ephemeris_source") or {}).get("factors") or {}
    offsets = (0.0, 0.25, 0.5, 0.75, 1.0)
    for planet in ORDER:
        points = []
        nominal_check = "not_supplied"
        coordinate_allowance: float | None = None
        for offset in offsets:
            epoch = at + offset
            sampled = _swisseph_planet_state(
                planet,
                julian_day_tt=epoch,
                source_trace=trace,
                motion_metadata=contexts.setdefault(epoch, {}),
                correct_motion=False,
            )
            assert_physical_configuration(selected)
            if sampled is None:
                break
            state, model = sampled
            expected_model = (expected.get(planet) or {}).get("model")
            if expected_model is not None and model != expected_model:
                raise EphemerisSourceError("model_changed")
            if planet in models and models[planet] != model:
                raise EphemerisSourceError("model_changed")
            models[planet] = model
            # Same epoch-dependent display offset used by NativeSubject.
            offset_angle = (
                native_lahiri_ayanamsha(julian_day_tt=epoch) if sidereal else 0.0
            )
            points.append((Fraction(state["longitude"]) - Fraction(offset_angle)) % 360)
            if offset == 0:
                nominal = getattr(
                    getattr(subject, planet.lower(), None), "abs_pos", None
                )
                if nominal is not None:
                    if not math.isfinite(nominal):
                        raise EphemerisSourceError("coordinate_values_unavailable")
                    discrepancy = abs(
                        (points[-1] - Fraction(nominal) + 180) % 360 - 180
                    )
                    # Rounding of the NativeSubject display subtraction only;
                    # no physical uncertainty or provider error is certified.
                    coordinate_allowance = 8 * max(
                        math.ulp(max(1.0, abs(nominal))),
                        math.ulp(max(1.0, float(points[-1]))),
                    )
                    if discrepancy > coordinate_allowance:
                        raise EphemerisSourceError("coordinate_contract_changed")
                    nominal_check = (
                        "agrees_with_supplied_coordinate_within_arithmetic_allowance"
                    )
        point = getattr(subject, planet.lower(), None)
        speed = getattr(point, "speed", None)
        if speed is not None and not math.isfinite(speed):
            raise EphemerisSourceError("coordinate_motion_unavailable")
        direction = (
            None
            if speed is None
            else "direct" if speed > 0 else "retrograde" if speed < 0 else "stationary"
        )
        steps = [(b - a + 180) % 360 - 180 for a, b in zip(points, points[1:])]
        complete = len(points) == len(offsets) and all(abs(step) < 90 for step in steps)
        result["motion"][planet] = {
            "direction": direction,
            "daily_motion_degrees": float(sum(steps, Fraction())) if complete else None,
            "daily_motion_exact_degrees": (
                str(sum(steps, Fraction())) if complete else None
            ),
            "status": "computed" if complete else "unavailable",
            "samples": [
                {"offset_days": o, "longitude": float(p)}
                for o, p in zip(offsets, points)
            ],
            "instantaneous_speed_degrees_per_day": speed,
            "source_model": models.get(planet),
            "nominal_coordinate_check": nominal_check,
            "nominal_coordinate_roundoff_allowance_degrees": coordinate_allowance,
        }
    node = getattr(subject, "mean_north_lunar_node", None)
    north = getattr(node, "abs_pos", None)
    if north is not None:
        if not math.isfinite(north):
            raise EphemerisSourceError("coordinate_values_unavailable")
        result["north_node_longitude"] = north % 360
    positions, profile = apparent_positions(at, sidereal=sidereal)
    assert_physical_configuration(selected)
    if (
        profile.get("status") == "computed"
        and len(set(models.values())) == 1
        and profile.get("earth_ephemeris_model") not in set(models.values())
    ):
        raise EphemerisSourceError("model_changed")
    result["star_longitudes"] = {
        p: positions[p]["longitude"]
        for p in ("Regulus", "Spica", "Algol")
        if p in positions
    }
    result["stars_profile"] = profile
    result.update(
        status=(
            "computed"
            if all(p["status"] == "computed" for p in result["motion"].values())
            and len(result["star_longitudes"]) == 3
            and result["north_node_longitude"] is not None
            else "partial"
        ),
        reason=None,
        day_interval_tt=[at, at + 1],
        longitude_frame=(
            "sidereal_lahiri" if sidereal else "tropical_true_ecliptic_of_date"
        ),
        physical_ephemeris_source=trace.finish(),
    )
    return result
