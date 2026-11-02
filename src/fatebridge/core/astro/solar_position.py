"""Describe native solar-disc extensions without changing a coordinate.

Swiss Appendix A defines virtual positions inside a transparent model Sun.
Continuity must not be inferred from that prose for the inspected mass table.
A finite unbent ray distinguishes a background body from a transit.
This receipt is not an occultation, lensing, limb-contact or visibility solver.
"""

from __future__ import annotations

import math
from importlib.metadata import version
from typing import Any, Dict, Optional, Sequence

from fatebridge.core.astro import runtime
from fatebridge.core.astro.native_coordinates import COORDINATE_FLAGS
from fatebridge.core.astro.native_identity import binding_distribution_version
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    assert_physical_configuration,
)
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.utils.errors import EphemerisSourceError

METHOD_ID = "native_apparent_solar_disc_conventions_v2"
SOURCE_URL = "https://www.astro.com/swisseph/swisseph.htm"
NATIVE_SOURCE_URL = "https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/sweph.c#L3742"
# SUN_RADIUS in the inspected source is an angular radius at one AU. This is
# its physical model sphere, not a fitted radius or a measured solar limb.
SOLAR_RADIUS_AU = math.radians(959.63 / 3600)
SOURCE_VERSION = ("2.10.03", "2.10.3.2")
TARGETS = frozenset(
    {"Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"}
)


def finite_solar_ray(
    ray: Sequence[float], earth_helio: Sequence[float]
) -> Dict[str, Any]:
    """Classify an unbent geocentric ray against the source's model sphere."""
    if any(
        len(v) != 3 or not all(math.isfinite(x) for x in v) for v in (ray, earth_helio)
    ):
        raise EphemerisSourceError("coordinate_values_unavailable")
    distance, solar_distance = math.hypot(*ray), math.hypot(*earth_helio)
    if (
        not all(math.isfinite(x) for x in (distance, solar_distance))
        or distance <= 0
        or solar_distance <= SOLAR_RADIUS_AU
    ):
        raise EphemerisSourceError("coordinate_values_unavailable")
    u = tuple(x / distance for x in ray)
    along = -math.fsum(a * b for a, b in zip(u, earth_helio))
    cross = (
        u[1] * earth_helio[2] - u[2] * earth_helio[1],
        u[2] * earth_helio[0] - u[0] * earth_helio[2],
        u[0] * earth_helio[1] - u[1] * earth_helio[0],
    )
    impact = math.hypot(*cross) / SOLAR_RADIUS_AU
    # Only a floating-arithmetic margin; physical ephemeris/limb uncertainty
    # is not bounded by this number. Never infer optical contact from it.
    margin = 64 * math.ulp(max(distance, solar_distance)) / SOLAR_RADIUS_AU
    if along <= 0:
        domain = "sun_behind_observer"
    elif impact > 1 + margin:
        domain = "outside_solar_disc"
    elif impact >= 1 - margin:
        domain = "solar_limb_ambiguous"
    else:
        half_chord = SOLAR_RADIUS_AU * math.sqrt(max(0, 1 - impact * impact))
        gap = distance - along
        if abs(abs(gap) - half_chord) <= margin * SOLAR_RADIUS_AU:
            domain = "target_on_model_sphere_ambiguous"
        elif gap > half_chord:
            domain = "behind_solar_disc"
        elif gap < -half_chord:
            domain = "foreground_of_solar_disc"
        else:
            domain = "target_inside_model_sphere"
    return {
        "status": "computed",
        "unbent_ray_domain": domain,
        "impact_solar_radius_fraction": impact,
        "target_distance_au": distance,
        "solar_distance_au": solar_distance,
        "solar_projection_distance_au": along,
        "arithmetic_margin_fraction": margin,
        "position_interpretation": (
            "virtual_native_solar_disc_extension"
            if domain == "behind_solar_disc"
            else (
                "unresolved_boundary"
                if "ambiguous" in domain
                else (
                    "unresolved_model_geometry"
                    if domain == "target_inside_model_sphere"
                    else "native_apparent_direction"
                )
            )
        ),
        "observational_accuracy_certified": False,
        "maximum_physical_error_arcseconds": None,
    }


@runtime.preserve_ephemeris_path()
def apparent_position_policy(
    epoch: Optional[float], models: Dict[str, str], trace: PhysicalEphemerisTrace
) -> Dict[str, Any]:
    """Nominal-epoch source convention and finite-ray geometry for planets.

    Unverified native versions/backends keep explicit unknown geometry.
    Frame, model, configuration and value contradictions remain fatal.
    """
    swe = runtime.swe
    native_version = str(getattr(swe, "version", "unavailable"))
    binding_version = binding_distribution_version(swe, version)
    selected = configured_ephemeris_path()
    if epoch is None:
        if swe is not None:
            raise EphemerisSourceError("coordinate_values_unavailable")
    elif not math.isfinite(epoch):
        raise EphemerisSourceError("coordinate_values_unavailable")
    verified = (native_version, binding_version) == SOURCE_VERSION
    mask = sum(getattr(swe, name) for name in COORDINATE_FLAGS) if swe else 0
    fixed = (
        (
            swe.FLG_SWIEPH
            | swe.FLG_XYZ
            | swe.FLG_ICRS
            | swe.FLG_J2000
            | swe.FLG_EQUATORIAL
        )
        if swe
        else 0
    )
    contexts: Dict[str, Any] = {}
    physical: Dict[str, tuple] = {}

    def state(body: int, flags: int, model: str, label: str) -> tuple:
        values, returned = runtime.ephemeris_call("calc", epoch, body, flags)
        assert_physical_configuration(selected)
        expected = flags | swe.FLG_NONUT
        if flags & swe.FLG_TRUEPOS:
            expected |= swe.FLG_NOGDEFL | swe.FLG_NOABERR
        if returned < 0 or returned & mask != expected & mask:
            raise EphemerisSourceError("coordinate_contract_changed")
        if runtime.ephemeris_model_from_retflag(returned) != model:
            raise EphemerisSourceError("model_changed")
        if len(values) != 6 or not all(math.isfinite(x) for x in values):
            raise EphemerisSourceError("coordinate_values_unavailable")
        contexts[label] = trace.observe(label, model, record_factor=False)
        return tuple(float(x) for x in values[:3])

    bodies: Dict[str, Any] = {}
    for planet, model in models.items():
        if planet not in TARGETS:
            continue
        if not verified or model not in {"swieph", "jpl"}:
            bodies[planet] = {
                "status": "not_evaluated",
                "unbent_ray_domain": None,
                "reason": (
                    "unverified_native_version"
                    if not verified
                    else "unsupported_ephemeris_model"
                ),
                "observational_accuracy_certified": False,
            }
            continue
        if model not in physical:
            flags = fixed | swe.FLG_BARYCTR | swe.FLG_TRUEPOS
            earth = state(swe.EARTH, flags, model, f"{model}_solar_policy_earth")
            sun = state(swe.SUN, flags, model, f"{model}_solar_policy_sun")
            physical[model] = tuple(a - b for a, b in zip(earth, sun))
        ray = state(
            PLANET_SWISSEPH_IDS[planet],
            fixed | swe.FLG_NOGDEFL | swe.FLG_NOABERR,
            model,
            f"{planet}_solar_policy_unbent_ray",
        )
        bodies[planet] = finite_solar_ray(ray, physical[model])
    return {
        "method_id": METHOD_ID,
        "epoch_jd_tt": epoch,
        "native_version": native_version,
        "binding_version": binding_version,
        "solar_deflection_model": (
            "native_extended_solar_mass" if verified else "unverified_native_model"
        ),
        "source_url": SOURCE_URL,
        "source_section": "Appendix A",
        "native_source_url": NATIVE_SOURCE_URL,
        "native_model_solar_radius_au": SOLAR_RADIUS_AU,
        "source_model_regularity": (
            {
                "profile": "native_eff_arr_linear_interpolation_v1",
                "source_profile_sha256": "ad8dd7126d5e1a4b2e6cbcef6aa13d5a4bbc51778db0c037f430a3fac50e8b36",
                "axis_continuity_certified": False,
                "unique_rate_at_mass_knots_certified": False,
                "scope": "Inspected source-formula mass profile only. Nonzero first-cell mass slope and unequal adjacent slopes do not certify global axis continuity or a unique knot-crossing derivative. No binary64, individual planetary rate or physical error bound follows.",
            }
            if verified
            else None
        ),
        "coordinate_origin": "geocenter",
        "geometry_frame": "ICRS_before_deflection_and_aberration",
        "bodies": bodies,
        "excluded_factors": {
            p: "native_solar_disc_extension_not_covered"
            for p in models
            if p not in TARGETS
        },
        "source_contexts": contexts,
        "displayed_native_positions_changed": False,
        "observational_accuracy_certified": False,
        "scope": "Nominal-epoch finite unbent ray against the inspected native model Sun. Background solar-disc positions use a virtual native extension without a global continuity or unique-rate certification. Foreground transits are distinct. No optical lensing, limb-contact, atmosphere, horizon, detectability or physical-error-bound certification; not a full event-window policy.",
    }
