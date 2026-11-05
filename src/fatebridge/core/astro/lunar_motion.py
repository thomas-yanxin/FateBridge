"""Source-derived lunar light-time and spatial aberration rate corrections.

The installed2.10.03 Moon position uses tau=|Moon(t)-Earth(t)|/c. Its
derivative needs -V_moon(t-tau)*tau'. Propagate that term through the
aberration position Jacobian; never fit a residual or change a position.
"""

from __future__ import annotations

import math
from importlib.metadata import version
from typing import Any, Dict, Optional, Sequence, Tuple

from fatebridge.core import ephemeris_runtime
from fatebridge.core.astro import runtime
from fatebridge.core.astro.aberration_math import (
    LIGHT_SPEED_AU_PER_DAY,
)
from fatebridge.core.astro.aberration_math import (
    aberration_beta_jvp as aberration_beta_jvp,
)
from fatebridge.core.astro.aberration_math import (
    aberration_position_jvp,
    dot,
    longitude_rate_change,
)
from fatebridge.core.astro.native_identity import binding_distribution_version
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    assert_physical_configuration,
)
from fatebridge.core.compressed_ephemeris import preserve_native_dependency_context
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.utils.errors import EphemerisSourceError

METHOD_ID = "fatebridge_lunar_fixed_frame_source_derivative_v3"
NATIVE_ABERRATION_STEP_DAYS = 0.0001  # PLAN_SPEED_INTV in the locked source.
SOURCE_URL = "https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/req/abcorr.html"
SOURCE_VERSION = ("2.10.03", "2.10.3.2")


def aberration_spatial_correction(
    position: Sequence[float], velocity: Sequence[float], beta: Sequence[float]
) -> Tuple[float, ...]:
    """Replace swi_aberr_light's backward spatial difference by its Jacobian.

    Observer beta is held fixed. Subtract the inspected source approximation,
    not the whole native speed (which also contains observer and frame terms).
    The finite difference is rotation equivariant in real arithmetic; binary64
    cancellation leaves a small frame-dependent remainder. This does not
    replace the observer-acceleration derivative or certify total motion.
    """
    _, analytic = aberration_position_jvp(position, velocity, beta)

    def native_position(values: Sequence[float]) -> Tuple[float, ...]:
        # Explicit source order, independent of Python sum() version changes.
        # Compiled contraction/rounding can still differ from this replay.
        radius = math.sqrt(
            values[0] * values[0] + values[1] * values[1] + values[2] * values[2]
        )
        b = math.sqrt(1 - (beta[0] * beta[0] + beta[1] * beta[1] + beta[2] * beta[2]))
        g = (values[0] * beta[0] + values[1] * beta[1] + values[2] * beta[2]) / radius
        h = 1 + g / (1 + b)
        return tuple((b * x + h * radius * be) / (1 + g) for x, be in zip(values, beta))

    step = NATIVE_ABERRATION_STEP_DAYS
    previous = tuple(x - step * v for x, v in zip(position, velocity))
    if math.hypot(*previous) <= 0:
        raise EphemerisSourceError("coordinate_values_unavailable")
    apparent = native_position(position)
    previous_apparent = native_position(previous)
    change = tuple(
        j - (v + ((a - x) - (pa - px)) / step)
        for j, v, a, x, pa, px in zip(
            analytic, velocity, apparent, position, previous_apparent, previous
        )
    )
    if not all(math.isfinite(x) for x in change):
        raise EphemerisSourceError("coordinate_values_unavailable")
    return change


def lunar_light_time_correction(
    julian_day_tt: float,
    displayed_coordinates: Sequence[float],
    model: str,
    *,
    source_trace: Optional[PhysicalEphemerisTrace] = None,
) -> Tuple[Optional[float], Dict[str, Any]]:
    """Return a longitude-rate correction and explicit applicability metadata.

    Only the locked/source-inspected native version and physical JPL/Swiss
    backends are covered. Moshier has a different lunar light-time algorithm
    and no supported barycentric state API; its raw rate is retained.
    This transaction restores the managed pipeline's Lahiri sidereal mode.
    """
    swe = runtime.swe
    native_version = str(getattr(swe, "version", "unavailable"))
    binding_version = binding_distribution_version(swe, version)
    metadata: Dict[str, Any] = {
        "method_id": METHOD_ID,
        "native_version": native_version,
        "binding_version": binding_version,
        "ephemeris_model": model,
        "epoch_jd_tt": julian_day_tt,
        "source_url": SOURCE_URL,
        "source_function": "pyswisseph2.10.3.2/libswe/sweph.c:app_pos_etc_moon",
        "scope": "Light-time and spatial terms are retained separately. An eligible observer/source remainder differentiates the declared continuous source model in the fixed reception frame; positions are unchanged. Complete moving-frame derivatives, native binary identity, physical TT-clock mapping, station time and observational accuracy remain unqualified.",
    }
    if model not in {"swieph", "jpl"}:
        return None, {
            **metadata,
            "status": "not_applied",
            "reason": "unsupported_physical_model",
        }
    if (native_version, binding_version) != SOURCE_VERSION or swe is None:
        return None, {
            **metadata,
            "status": "not_applied",
            "reason": "unverified_native_version",
        }
    if not math.isfinite(julian_day_tt):
        raise EphemerisSourceError("coordinate_values_unavailable")
    trace = source_trace if source_trace is not None else PhysicalEphemerisTrace()
    factors = []
    contexts = {}
    returned_flags: Dict[str, int] = {}
    # Keep reception-frame auxiliary states in the already checked apparent
    # light-path window. Resetting each geometric sample can select the newer
    # reception-only file and sever the retarded dependency at a file start.
    with (
        runtime.preserve_ephemeris_path(),
        preserve_native_dependency_context(
            julian_day_tt, julian_day_tt, model, native=ephemeris_runtime.swe
        ),
    ):
        selected = configured_ephemeris_path()
        base = (
            swe.FLG_SWIEPH
            | swe.FLG_SPEED
            | swe.FLG_XYZ
            | swe.FLG_TRUEPOS
            | swe.FLG_SIDEREAL
        )

        def state(
            epoch: float,
            body: int,
            *,
            barycentric: bool,
            factor: str,
            kind: str = "geometric",
        ) -> Tuple[float, ...]:
            flags = base | (swe.FLG_BARYCTR if barycentric else 0)
            if kind != "geometric":
                flags &= ~swe.FLG_TRUEPOS
            if kind == "preaberration":
                flags |= swe.FLG_NOABERR
            if kind not in {"geometric", "preaberration", "apparent"}:
                raise ValueError("Unknown lunar Cartesian state kind")
            values, returned = runtime.ephemeris_call("calc", epoch, body, flags)
            assert_physical_configuration(selected)
            required = swe.FLG_SPEED | swe.FLG_XYZ | swe.FLG_SIDEREAL | swe.FLG_NONUT
            if kind == "geometric":
                required |= swe.FLG_TRUEPOS
            if kind == "preaberration":
                required |= swe.FLG_NOABERR
            forbidden = (
                swe.FLG_EQUATORIAL
                | swe.FLG_J2000
                | swe.FLG_ICRS
                | swe.FLG_RADIANS
                | swe.FLG_HELCTR
                | swe.FLG_TOPOCTR
            )
            if kind != "geometric":
                forbidden |= swe.FLG_TRUEPOS
            if kind == "apparent":
                forbidden |= swe.FLG_NOABERR
            if (
                returned < 0
                or returned & required != required
                or returned & forbidden
                or bool(returned & swe.FLG_BARYCTR) != barycentric
            ):
                raise EphemerisSourceError("coordinate_contract_changed")
            if runtime.ephemeris_model_from_retflag(returned) != model:
                raise EphemerisSourceError("coordinate_model_changed")
            if len(values) != 6 or not all(math.isfinite(v) for v in values):
                raise EphemerisSourceError("coordinate_values_unavailable")
            contexts[factor] = trace.observe(factor, model, record_factor=False)
            returned_flags[factor] = int(returned)
            factors.append(factor)
            return tuple(float(v) for v in values)

        def observer_state(
            epoch: float,
            body: int,
            *,
            barycentric: bool,
            factor: str,
            kind: str = "geometric",
        ) -> Tuple[Tuple[float, ...], int]:
            values = state(
                epoch, body, barycentric=barycentric, factor=factor, kind=kind
            )
            return values, returned_flags[factor]

        try:
            runtime.ephemeris_call(
                "set_sid_mode", swe.SIDM_USER | swe.SIDBIT_ECL_T0, julian_day_tt, 0.0
            )
            geometric = state(
                julian_day_tt,
                swe.MOON,
                barycentric=False,
                factor="Moon_motion_geometric",
            )
            radius = math.hypot(*geometric[:3])
            if radius <= 0:
                raise EphemerisSourceError("coordinate_values_unavailable")
            light_time = radius / LIGHT_SPEED_AU_PER_DAY
            light_time_rate = (
                dot(geometric[:3], geometric[3:]) / radius / LIGHT_SPEED_AU_PER_DAY
            )
            earth = state(
                julian_day_tt,
                swe.EARTH,
                barycentric=True,
                factor="Moon_motion_observer_barycentric",
            )
            with preserve_native_dependency_context(
                julian_day_tt,
                julian_day_tt - light_time,
                model,
                native=ephemeris_runtime.swe,
            ):
                moon = state(
                    julian_day_tt - light_time,
                    swe.MOON,
                    barycentric=True,
                    factor="Moon_motion_retarded_barycentric",
                )
            position = tuple(a - b for a, b in zip(moon[:3], earth[:3]))
            delta = tuple(-v * light_time_rate for v in moon[3:])
            beta = tuple(v / LIGHT_SPEED_AU_PER_DAY for v in earth[3:])
            apparent, change = aberration_position_jvp(position, delta, beta)
            relative_velocity = tuple(a - b for a, b in zip(moon[3:], earth[3:]))
            # Match the source's scalar conversion for the approximation being
            # removed; retain the existing light-time chain's arithmetic above.
            native_beta = tuple(
                v / 24.0 / 3600.0 / 299792458.0 * 149597870700.0 for v in earth[3:]
            )
            spatial_change = aberration_spatial_correction(
                position, relative_velocity, native_beta
            )
            computed_latitude = math.degrees(
                math.atan2(apparent[2], math.hypot(*apparent[:2]))
            )
            latitude_residual = abs(computed_latitude - float(displayed_coordinates[1]))
            radius_residual = abs(
                math.hypot(*apparent) - float(displayed_coordinates[2])
            )
            # Internal frame/source coherence, not observational tolerances.
            if latitude_residual > 1e-8 or radius_residual > 1e-12:
                raise EphemerisSourceError("lunar_motion_position_mismatch")
            correction = longitude_rate_change(apparent, change)
            spatial_correction = longitude_rate_change(apparent, spatial_change)
            # Late import keeps the pure Jacobians available to the sampler
            # without a module-initialization cycle.
            from fatebridge.core.astro.lunar_observer import lunar_observer_remainder

            observer_remainder, observer_policy = lunar_observer_remainder(
                julian_day_tt,
                model,
                observer_state,
                (earth, returned_flags["Moon_motion_observer_barycentric"]),
                light_time_rate,
                correction,
                spatial_correction,
            )
        finally:
            runtime.ephemeris_call("set_sid_mode", swe.SIDM_LAHIRI, 0.0, 0.0)
        assert_physical_configuration(selected)
        if source_trace is None:
            trace.finish()
    return correction, {
        **metadata,
        "status": "applied",
        "frame_method": "native_fixed_mean_ecliptic_at_observation_tt",
        "longitude_origin_invariance": "tropical_true_equinox_and_traditional_lahiri",
        "light_time_days": light_time,
        "light_time_derivative": light_time_rate,
        "longitude_speed_correction": correction,
        "spatial_aberration": {
            "method_id": "lunar_spatial_aberration_jacobian_replacement_v1",
            "status": "applied",
            "source_function": "pyswisseph2.10.3.2/libswe/sweph.c:swi_aberr_light",
            "native_backward_step_days": NATIVE_ABERRATION_STEP_DAYS,
            "longitude_speed_correction": spatial_correction,
            "observer_beta_held_fixed": True,
            "positions_unchanged": True,
            "native_binary_arithmetic_identity_certified": False,
            "scope": "Spatial Jacobian minus the inspected backward-difference approximation in the fixed reception ecliptic. Compiled native arithmetic and binary64 frame-dependent cancellation remain unqualified; no observer-acceleration replacement or complete apparent-rate certification.",
        },
        "fixed_frame_source_derivative": observer_policy,
        "latitude_reproduction_error_degrees": latitude_residual,
        "radius_reproduction_error_au": radius_residual,
        "source_factors": factors,
        "source_contexts": contexts,
    }
