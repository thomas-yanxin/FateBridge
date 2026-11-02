"""Remove whole-turn aliasing in the inspected traditional Lahiri rate.

Managed callers set SIDM_LAHIRI while holding the native runtime lock. This
only removes the integer branch of swi_get_ayanamsa_with_speed's subtraction;
the remaining native one-sided derivative is deliberately not certified.
"""

from __future__ import annotations

import math
from importlib.metadata import version
from typing import Any, Dict, Optional, Tuple

from fatebridge.core.astro import runtime
from fatebridge.core.astro.lunar_motion import SOURCE_URL, SOURCE_VERSION
from fatebridge.core.astro.native_identity import binding_distribution_version
from fatebridge.core.ephemeris_runtime import (
    configured_ephemeris_path,
    configured_jpl_file,
    lock_ephemeris_configuration,
)
from fatebridge.utils.errors import EphemerisSourceError

METHOD_ID = "traditional_lahiri_native_origin_whole_turn_removal_v1"
NATIVE_INTERVAL_DAYS = 0.001


def circular_origin_correction(
    current: float, previous: float
) -> Tuple[float, int, float, float]:
    """Replace only the integer winding of two normalized degree values."""
    if not all(math.isfinite(v) and 0 <= v < 360 for v in (current, previous)):
        raise EphemerisSourceError("coordinate_values_unavailable")
    difference = current - previous
    principal = math.remainder(difference, 360.0)
    if abs(principal) == 180:
        raise EphemerisSourceError("coordinate_motion_unavailable")
    turns = round((difference - principal) / 360.0)
    if abs(turns) > 1 or difference - principal != turns * 360.0:
        raise EphemerisSourceError("coordinate_motion_unavailable")
    correction = turns * 360.0 / NATIVE_INTERVAL_DAYS
    return correction, turns, difference, principal


def traditional_lahiri_origin_wrap(
    julian_day_tt: float, context: Dict[str, Any]
) -> Optional[float]:
    """Inspect the managed traditional origin, retaining its unwrapped inputs."""
    swe = runtime.swe
    native_version = str(getattr(swe, "version", "unavailable"))
    binding_version = binding_distribution_version(swe, version)
    policy: Dict[str, Any] = {
        "method_id": METHOD_ID,
        "epoch_jd_tt": julian_day_tt,
        "native_version": native_version,
        "binding_version": binding_version,
        "source_url": SOURCE_URL,
        "source_function": "pyswisseph2.10.3.2/libswe/sweph.c:swi_get_ayanamsa_with_speed",
        "sidereal_mode": "managed_traditional_lahiri",
        "native_divisor_days": NATIVE_INTERVAL_DAYS,
        "positions_unchanged": True,
        "complete_origin_derivative_certified": False,
        "physical_TT_clock_mapping_certified": False,
        "scope": "Integer branch repair only. The native 0.001-day backward derivative and its nominal divisor are retained; no complete frame derivative, station-time, observational or predictive accuracy certificate. Origin values are source-defined precession quantities, not physical ephemeris observations.",
    }
    if swe is None or (native_version, binding_version) != SOURCE_VERSION:
        context["traditional_sidereal_origin_wrap"] = {
            **policy,
            "status": "not_applied",
            "reason": "unverified_native_version",
        }
        return None
    if not math.isfinite(julian_day_tt):
        raise EphemerisSourceError("coordinate_values_unavailable")
    previous_epoch = julian_day_tt - NATIVE_INTERVAL_DAYS
    if not math.isfinite(previous_epoch) or previous_epoch == julian_day_tt:
        raise EphemerisSourceError("coordinate_motion_unavailable")
    requested_flags = swe.FLG_SWIEPH | swe.FLG_NONUT

    def read(epoch: float) -> Tuple[int, float]:
        value = runtime.ephemeris_call("get_ayanamsa_ex", epoch, requested_flags)
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise EphemerisSourceError("coordinate_values_unavailable")
        flags, angle = value
        if flags != requested_flags:
            raise EphemerisSourceError("coordinate_contract_changed")
        try:
            angle = float(angle)
        except (TypeError, ValueError) as error:
            raise EphemerisSourceError("coordinate_values_unavailable") from error
        if not math.isfinite(angle) or not 0 <= angle < 360:
            raise EphemerisSourceError("coordinate_values_unavailable")
        return int(flags), angle

    # Lock without a path-restoration call: preserve_ephemeris_path resets
    # native file caches on exit, severing an already qualified Moon center.
    with lock_ephemeris_configuration():
        selected_path = configured_ephemeris_path()
        selected_jpl = configured_jpl_file()
        requested_flags = (
            swe.FLG_JPLEPH if selected_jpl is not None else swe.FLG_SWIEPH
        ) | swe.FLG_NONUT
        # Match the source call order and divisor, rather than replacing its
        # continuous derivative with an independently chosen stencil.
        previous_flags, previous = read(previous_epoch)
        current_flags, current = read(julian_day_tt)
        restored = read(julian_day_tt)
        if restored != (current_flags, current):
            raise EphemerisSourceError("sidereal_origin_not_reproduced")
        if (
            configured_ephemeris_path() != selected_path
            or configured_jpl_file() != selected_jpl
        ):
            raise EphemerisSourceError("physical_configuration_changed")
    correction, turns, difference, principal = circular_origin_correction(
        current, previous
    )
    context["traditional_sidereal_origin_wrap"] = {
        **policy,
        "status": "applied" if turns else "not_needed",
        "previous_epoch_jd_tt": previous_epoch,
        "actual_binary64_interval_days": julian_day_tt - previous_epoch,
        "previous_origin_degrees": previous,
        "current_origin_degrees": current,
        "previous_returned_flags": previous_flags,
        "current_returned_flags": current_flags,
        "requested_origin_flags": requested_flags,
        "raw_difference_degrees": difference,
        "principal_difference_degrees": principal,
        "whole_turns_removed": turns,
        "longitude_speed_correction": correction,
        "center_origin_reproduced_exactly": True,
    }
    return correction
