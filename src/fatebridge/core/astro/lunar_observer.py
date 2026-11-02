"""Observer acceleration and the declared fixed-frame lunar source derivative.

The source pre-aberration state avoids reconstructing a hidden emission epoch.
This is not a complete moving-frame or observational accuracy certificate.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

from fatebridge.core import ephemeris_runtime
from fatebridge.core.astro import runtime
from fatebridge.core.astro.aberration_math import (
    LIGHT_SPEED_AU_PER_DAY,
    aberration_beta_jvp,
    aberration_position_jvp,
    longitude_rate_change,
)
from fatebridge.core.astro.motion_source_window import observed_windows
from fatebridge.core.compressed_ephemeris import preserve_native_observer_sample_context
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.jpl_ephemeris import configured_jpl_file, jpl_header
from fatebridge.utils.errors import EphemerisSourceError

METHOD_ID = "lunar_fixed_frame_source_derivative_with_observer_acceleration_v1"
FIXED_FRAME_ID = "native_fixed_reception_mean_ecliptic_v1"
STEPS_DAYS = (1 / 1024, 1 / 512)
STENCILS = {
    "central": ((-3, -2, -1, 1, 2, 3), (-1, 9, -45, 45, -9, 1)),
    "backward": ((0, -1, -2, -3, -4, -5, -6), (147, -360, 450, -400, 225, -72, 10)),
    "forward": ((0, 1, 2, 3, 4, 5, 6), (-147, 360, -450, 400, -225, 72, -10)),
}
ACCELERATION_LINE = 1e-10
OBSERVER_RATE_LINE = 1e-6
POSITION_LINE_ARCSEC = 1e-7
NativeState = Tuple[Tuple[float, ...], int]
Sampler = Callable[..., NativeState]


def acceleration_from_velocities(
    velocities: Sequence[Sequence[float]], step: float, direction: str
) -> Tuple[float, ...]:
    """Sixth-order derivative; coefficients independently derived rationally."""
    if direction not in STENCILS or not math.isfinite(step) or step <= 0:
        raise EphemerisSourceError("coordinate_motion_unavailable")
    offsets, weights = STENCILS[direction]
    if len(velocities) != len(offsets) or any(
        len(v) != 3 or not all(math.isfinite(x) for x in v) for v in velocities
    ):
        raise EphemerisSourceError("coordinate_values_unavailable")
    result = tuple(
        math.fsum(w * v[i] for w, v in zip(weights, velocities)) / (60 * step)
        for i in range(3)
    )
    if not all(math.isfinite(x) for x in result):
        raise EphemerisSourceError("coordinate_motion_unavailable")
    return result


def select_source_stencil(epoch: float, lower: float, upper: float) -> Optional[str]:
    """Source-only priority; rates/residuals cannot affect this choice."""
    if (
        not all(math.isfinite(x) for x in (epoch, lower, upper))
        or not lower <= epoch <= upper
    ):
        return None
    for direction, (offsets, _) in STENCILS.items():
        eligible = True
        for step in STEPS_DAYS:
            for offset in offsets:
                if offset == 0:
                    continue  # Reuse the already checked center value.
                delta = offset * step
                at = epoch + delta
                pad = 64 * math.ulp(at)
                if at - epoch != delta or not lower + pad < at < upper - pad:
                    eligible = False
        if eligible:
            return direction
    return None


def fixed_frame_source_remainder(
    preaberration: Sequence[float],
    native_apparent: Sequence[float],
    observer_velocity: Sequence[float],
    beta: Sequence[float],
    beta_derivative: Sequence[float],
    light_time_derivative: float,
    prior_light: float,
    prior_spatial: float,
) -> Tuple[float, Dict[str, Any]]:
    """Differentiate the full source formula; subtract already exposed terms.

    Geometry and velocity use the same native argument-day unit. A physical
    TT/TDB conversion or moving reference frame is not supplied here.
    """
    if (
        len(preaberration) != 6
        or len(native_apparent) != 6
        or len(observer_velocity) != 3
        or not all(
            math.isfinite(x)
            for x in (
                *preaberration,
                *native_apparent,
                *observer_velocity,
                light_time_derivative,
                prior_light,
                prior_spatial,
            )
        )
    ):
        raise EphemerisSourceError("coordinate_values_unavailable")
    derivative = tuple(
        vr - (vr + ve) * light_time_derivative
        for vr, ve in zip(preaberration[3:], observer_velocity)
    )
    apparent, position_jvp = aberration_position_jvp(
        preaberration[:3], derivative, beta
    )
    _, observer_jvp = aberration_beta_jvp(preaberration[:3], beta, beta_derivative)
    full_velocity = tuple(a + b for a, b in zip(position_jvp, observer_jvp))
    full_rate = longitude_rate_change(apparent, full_velocity)
    native_rate = longitude_rate_change(native_apparent[:3], native_apparent[3:])
    remainder = full_rate - native_rate - prior_light - prior_spatial
    radius, native_radius = math.hypot(*apparent), math.hypot(*native_apparent[:3])
    if native_radius <= 0:
        raise EphemerisSourceError("coordinate_values_unavailable")
    unit = tuple(x / radius for x in apparent)
    native_unit = tuple(x / native_radius for x in native_apparent[:3])
    cross = (
        unit[1] * native_unit[2] - unit[2] * native_unit[1],
        unit[2] * native_unit[0] - unit[0] * native_unit[2],
        unit[0] * native_unit[1] - unit[1] * native_unit[0],
    )
    error = (
        math.degrees(
            math.atan2(
                math.hypot(*cross), math.fsum(a * b for a, b in zip(unit, native_unit))
            )
        )
        * 3600
    )
    return remainder, {
        "full_fixed_frame_apparent_position_au": list(apparent),
        "full_fixed_frame_velocity_au_per_native_argument_day": list(full_velocity),
        "full_fixed_frame_longitude_speed_degrees_per_day": full_rate,
        "native_fixed_frame_longitude_speed_degrees_per_day": native_rate,
        "observer_beta_jvp_longitude_speed_degrees_per_day": longitude_rate_change(
            apparent, observer_jvp
        ),
        "source_position_reproduction_arcsec": error,
        "source_radius_reproduction_error_au": abs(radius - native_radius),
        "longitude_speed_correction": remainder,
    }


def _native_context(model: str) -> Any:
    if model == "swieph":
        return observed_windows()
    return (tuple(runtime.swe.get_current_file_data(0)),)


def lunar_observer_remainder(
    epoch: float,
    model: str,
    sample: Sampler,
    earth_center: NativeState,
    light_time_derivative: float,
    prior_light: float,
    prior_spatial: float,
) -> Tuple[Optional[float], Dict[str, Any]]:
    """Checked transaction; caller owns the lock and fixes SIDBIT_ECL_T0.

    The frame epoch must remain the reception epoch throughout all samples.
    """
    metadata: Dict[str, Any] = {
        "method_id": METHOD_ID,
        "epoch_jd_tt": epoch,
        "ephemeris_model": model,
        "fixed_frame_id": FIXED_FRAME_ID,
        "fixed_frame_epoch_jd_tt": epoch,
        "input_frame_held_fixed": True,
        "input_velocity_time_variable": "native_numeric_argument_day",
        "acceleration_steps_days": list(STEPS_DAYS),
        "acceleration_agreement_line_au_per_day2": ACCELERATION_LINE,
        "observer_agreement_line_arcsec_per_day": OBSERVER_RATE_LINE,
        "position_reproduction_line_arcsec": POSITION_LINE_ARCSEC,
        "source_function": "pyswisseph2.10.3.2/libswe/sweph.c:app_pos_etc_moon,swi_aberr_light",
        "preaberration_source": "Native geocentric Moon with light time and NOABERR, in the fixed reception ecliptic",
        "scope": "Declared continuous native-argument source derivative in a fixed reception frame. The remainder includes observer acceleration and differences from previously exposed spatial/light terms. Source checks are endpoint checks, not an atomic read-set. Complete moving-frame derivatives, binary identity, physical TT-clock mapping, observational accuracy and prediction remain unqualified.",
        "positions_unchanged": True,
        "complete_moving_frame_derivative_certified": False,
        "native_binary_arithmetic_identity_certified": False,
    }
    context = _native_context(model)
    if context is None:
        return None, {
            **metadata,
            "status": "not_applied",
            "reason": "observer_source_window_unavailable",
        }
    if model == "swieph":
        lower, upper = max(w[1] for w in context), min(w[2] for w in context)
        window = {
            "argument_scale": "native_Swiss_TT_argument",
            "start": lower,
            "end": upper,
        }
    else:
        header = jpl_header(Path(context[0][0]))
        lower, upper = header["start_julian_day_tdb"], header["end_julian_day_tdb"]
        window = {
            "argument_scale": "raw_JPL_native_numeric_argument_no_TT_conversion",
            "start": lower,
            "end": upper,
        }
    direction = (
        "analytic_jpl_source"
        if model == "jpl"
        else select_source_stencil(epoch, lower, upper)
    )
    metadata.update(source_window=window, selected_stencil=direction)
    if direction is None:
        return None, {
            **metadata,
            "status": "not_applied",
            "reason": "no_exact_source_window_stencil",
            "sample_count": 0,
        }
    configuration = (configured_ephemeris_path(), configured_jpl_file())
    if model == "jpl":
        metadata.update(
            acceleration_steps_days=[],
            observer_acceleration_method_id="de441_analytic_source_kinematics_v1",
            stencil_offsets=[],
            stencil_integer_weights=[],
            stencil_divisor=None,
        )
    else:
        metadata.update(
            stencil_offsets=list(STENCILS[direction][0]),
            stencil_integer_weights=list(STENCILS[direction][1]),
            stencil_divisor=60,
        )
    initial: Dict[str, NativeState] = {"earth": earth_center}
    cache = {epoch: earth_center[0][3:]}

    def check_context() -> None:
        if _native_context(model) != context:
            raise EphemerisSourceError("observer_source_window_incoherent")
        if (configured_ephemeris_path(), configured_jpl_file()) != configuration:
            raise EphemerisSourceError("physical_configuration_changed")

    try:
        initial["pre"] = sample(
            epoch,
            runtime.swe.MOON,
            barycentric=False,
            kind="preaberration",
            factor="Moon_motion_source_preaberration",
        )
        initial["app"] = sample(
            epoch,
            runtime.swe.MOON,
            barycentric=False,
            kind="apparent",
            factor="Moon_motion_source_apparent_fixed",
        )
        if any(math.hypot(*initial[key][0][:3]) <= 0 for key in ("pre", "app")):
            raise EphemerisSourceError("coordinate_values_unavailable")
        check_context()
        estimates = []
        if model == "jpl":
            from fatebridge.core.astro.jpl_kinematics import (
                checked_fixed_acceleration,
                source_kinematics,
            )

            raw, source_policy = source_kinematics(Path(context[0][0]), epoch, "Earth")
            acceleration, rotation_policy = checked_fixed_acceleration(
                raw, earth_center[0]
            )
            estimates.append(acceleration)
            metadata.update(
                analytic_observer_source=source_policy,
                fixed_observer_rotation=rotation_policy,
                observer_center_fixed_frame_state=list(earth_center[0]),
                observer_derivative_agreement_status="not_applicable_analytic_source",
            )
        else:
            offsets, _ = STENCILS[direction]
            for step in STEPS_DAYS:
                velocities = []
                for offset in offsets:
                    at = epoch + offset * step
                    if at not in cache:
                        with preserve_native_observer_sample_context(
                            epoch, at, model, native=ephemeris_runtime.swe
                        ):
                            values, _ = sample(
                                at,
                                runtime.swe.EARTH,
                                barycentric=True,
                                factor=f"Moon_motion_observer_sample_{(at - epoch).hex()}",
                            )
                        check_context()
                        cache[at] = values[3:]
                    velocities.append(cache[at])
                estimates.append(
                    acceleration_from_velocities(velocities, step, direction)
                )
    finally:
        for key, body, kind, barycentric in (
            ("pre", runtime.swe.MOON, "preaberration", False),
            ("app", runtime.swe.MOON, "apparent", False),
            ("earth", runtime.swe.EARTH, "geometric", True),
        ):
            if key not in initial:
                continue
            restored = sample(
                epoch,
                body,
                barycentric=barycentric,
                kind=kind,
                factor=f"Moon_motion_observer_restored_{key}",
            )
            if restored != initial[key]:
                raise EphemerisSourceError("lunar_motion_center_not_reproduced")
        check_context()
    metadata.update(
        sample_count=len(cache) - 1,
        acceleration_estimates_au_per_day2=[list(v) for v in estimates],
        acceleration_samples=[
            {
                "epoch_jd_tt": at,
                "velocity_au_per_native_argument_day": list(cache[at]),
                "is_center": at == epoch,
            }
            for at in sorted(cache)
        ],
        acceleration_difference_au_per_day2=(
            math.dist(*estimates) if len(estimates) == 2 else None
        ),
        center_native_states_reproduced_exactly=True,
        center_file_context_reproduced_exactly=True,
    )
    earth_velocity = earth_center[0][3:]
    beta = tuple(
        v / 24.0 / 3600.0 / 299792458.0 * 149597870700.0 for v in earth_velocity
    )
    beta_rates = [tuple(a / LIGHT_SPEED_AU_PER_DAY for a in v) for v in estimates]
    pre, app = initial["pre"][0], initial["app"][0]
    jvps = [aberration_beta_jvp(pre[:3], beta, v)[1] for v in beta_rates]
    angular_disagreement = (
        math.dist(*jvps) / math.hypot(*app[:3]) * (180 / math.pi * 3600)
        if len(jvps) == 2
        else None
    )
    metadata["observer_derivative_disagreement_arcsec_per_day"] = angular_disagreement
    if model != "jpl" and (
        math.dist(*estimates) > ACCELERATION_LINE
        or angular_disagreement is None
        or angular_disagreement > OBSERVER_RATE_LINE
    ):
        return None, {
            **metadata,
            "status": "not_applied",
            "reason": "observer_acceleration_not_converged",
        }
    remainder, details = fixed_frame_source_remainder(
        pre,
        app,
        earth_velocity,
        beta,
        beta_rates[0],
        light_time_derivative,
        prior_light,
        prior_spatial,
    )
    if (
        details["source_position_reproduction_arcsec"] > POSITION_LINE_ARCSEC
        or details["source_radius_reproduction_error_au"] > 1e-12
    ):
        raise EphemerisSourceError("lunar_motion_position_mismatch")
    return remainder, {
        **metadata,
        **details,
        "selected_step_days": STEPS_DAYS[0] if model != "jpl" else None,
        "status": "applied",
    }
