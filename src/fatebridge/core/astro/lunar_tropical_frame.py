"""Analytic tropical frame motion applied to a checked fixed-frame Moon state.

The inspected display position is Rz(dpsi) E(eps) P x. Differentiate that
composition, keeping source and date-frame terms separate. Native scalar
precession increments and a backward nutation difference are not its complete
derivative. This supplies a mathematical frame derivative, not physical clock
equivalence, a derivative of binary rounding, or an observational certificate.
"""

from __future__ import annotations

import math
from importlib.metadata import version
from typing import Any, Dict, Optional, Sequence, Tuple

from fatebridge.core.astro import reference_frames, runtime
from fatebridge.core.astro.native_identity import binding_distribution_version
from fatebridge.core.astro.nutation import COEFFICIENT_SHA256, SOURCE_URL, nutation
from fatebridge.utils.errors import EphemerisSourceError

METHOD_ID = "fatebridge_lunar_analytic_tropical_frame_v1"
MODEL_POSITION_LINE_ARCSEC = 1e-7
_DEG = 180.0 / math.pi


def complete_lunar_tropical_rate(
    epoch: float,
    coordinates: Sequence[float],
    model: str,
    fixed: Optional[Dict[str, Any]],
    legacy_rate: float,
) -> Tuple[Optional[float], Dict[str, Any]]:
    policy: Dict[str, Any] = {
        "method_id": METHOD_ID,
        "epoch_jd_tt": epoch,
        "ephemeris_model": model,
        "frame_model": "native_Vondrak_scalar_obliquity_plus_77term_full_Simon_nutation",
        "frame_coefficient_sha256": reference_frames.COEFFICIENT_SHA256,
        "nutation_coefficient_sha256": COEFFICIENT_SHA256,
        "source_url": SOURCE_URL,
        "positions_unchanged": True,
        "physical_TT_equivalence_certified": False,
        "native_binary_function_derivative_certified": False,
        "scope": "Analytic date-frame derivative added to the checked fixed-reception source velocity; native numerical argument retained. Source accuracy and physical TT/TDB conversion require separate evidence.",
    }

    def unavailable(reason: str) -> Tuple[None, Dict[str, Any]]:
        return None, {**policy, "status": "not_applied", "reason": reason}

    if runtime.swe is None or (
        str(runtime.swe.version),
        binding_distribution_version(runtime.swe, version),
    ) != ("2.10.03", "2.10.3.2"):
        return unavailable("unverified_native_version")
    if model not in {"swieph", "jpl"}:
        return unavailable("unverified_source_model")
    if not math.isfinite(epoch) or not 1721425.5 <= epoch <= 5373485.5:
        return unavailable("outside_frame_model_domain")
    if epoch == 2451545.0:
        return unavailable("isolated_native_J2000_precession_identity_shortcut")
    if (
        fixed is None
        or fixed.get("status") != "applied"
        or fixed.get("fixed_frame_id") != "native_fixed_reception_mean_ecliptic_v1"
        or fixed.get("fixed_frame_epoch_jd_tt") != epoch
        or fixed.get("ephemeris_model") != model
        or fixed.get("center_native_states_reproduced_exactly") is not True
        or fixed.get("center_file_context_reproduced_exactly") is not True
    ):
        return unavailable("checked_fixed_reception_source_state_unavailable")
    p = fixed["full_fixed_frame_apparent_position_au"]
    v = fixed["full_fixed_frame_velocity_au_per_native_argument_day"]
    if (
        len(p) != 3
        or len(v) != 3
        or not all(math.isfinite(x) for x in (*p, *v, legacy_rate))
    ):
        raise EphemerisSourceError("coordinate_motion_unavailable")
    rho2 = math.fsum(x * x for x in p[:2])
    if rho2 <= 0:
        raise EphemerisSourceError("coordinate_motion_unavailable")
    psi, deps, psi_d, _ = nutation(epoch)
    mean_epsilon = reference_frames.pair(epoch, "pepol", "peper")[0][1] * _DEG
    with runtime.preserve_ephemeris_path():
        native, flags = runtime.ephemeris_call(
            "calc", epoch, runtime.swe.ECL_NUT, runtime.swe.FLG_SWIEPH
        )
    if flags < 0 or len(native) < 4 or not all(math.isfinite(x) for x in native[:4]):
        raise EphemerisSourceError("coordinate_values_unavailable")
    model_errors = [
        abs(a - b) * 3600 for a, b in zip((mean_epsilon, psi, deps), native[1:4])
    ]
    lon = (math.atan2(p[1], p[0]) * _DEG + psi) % 360
    lat = math.atan2(p[2], math.sqrt(rho2)) * _DEG
    position_errors = [
        abs(math.remainder(lon - float(coordinates[0]), 360)) * 3600,
        abs(lat - float(coordinates[1])) * 3600,
    ]
    policy.update(
        native_model_component_errors_arcsec=model_errors,
        display_position_reproduction_errors_arcsec=position_errors,
        model_reproduction_line_arcsec=MODEL_POSITION_LINE_ARCSEC,
    )
    if max(model_errors + position_errors) > MODEL_POSITION_LINE_ARCSEC:
        return unavailable("declared_native_frame_not_reproduced")
    mean, derivative = reference_frames.mean_ecliptic_frame(epoch)
    moving = reference_frames.mv(
        reference_frames.mm(derivative, reference_frames.transpose(mean)), p
    )
    source_rate = (p[0] * v[1] - p[1] * v[0]) / rho2 * _DEG
    frame_rate = (p[0] * moving[1] - p[1] * moving[0]) / rho2 * _DEG
    complete = math.fsum((source_rate, frame_rate, psi_d))
    if not math.isfinite(complete):
        raise EphemerisSourceError("coordinate_motion_unavailable")
    return complete, {
        **policy,
        "status": "applied",
        "legacy_display_rate_degrees_per_native_argument_day": legacy_rate,
        "fixed_reception_source_rate_degrees_per_native_argument_day": source_rate,
        "mean_frame_rate_degrees_per_native_argument_day": frame_rate,
        "nutation_longitude_rate_degrees_per_native_argument_day": psi_d,
        "complete_display_rate_degrees_per_native_argument_day": complete,
        "additional_correction_degrees_per_native_argument_day": complete - legacy_rate,
    }
