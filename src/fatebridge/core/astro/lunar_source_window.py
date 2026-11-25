"""Give the lunar reception light path one overlapping Swiss file context.

The inspected sweph() keeps an open file while its epoch remains in range.
At a file boundary a cold observation can use one compressed fit for Earth(t)
and another for Earth(t-tau). Prime the physical retarded state, then recompute
the observation in a context covering BOTH epochs. No residual selects a file.
"""

from __future__ import annotations

import math
from importlib.metadata import version
from pathlib import Path
from typing import Any, Dict, Sequence

from fatebridge.core import ephemeris_runtime
from fatebridge.core.astro import runtime
from fatebridge.core.astro.aberration_math import LIGHT_SPEED_AU_PER_DAY
from fatebridge.core.astro.lunar_motion import SOURCE_VERSION
from fatebridge.core.astro.native_identity import binding_distribution_version
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    assert_physical_configuration,
)
from fatebridge.core.compressed_ephemeris import POLICY_ID as OWNED_CONTEXT_POLICY
from fatebridge.core.compressed_ephemeris import (
    coordinate_context_evidence,
    preserve_native_dependency_context,
)
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.utils.errors import EphemerisSourceError

METHOD_ID = "fatebridge_lunar_light_path_source_window_v2"


def selected_windows(julian_day_tt: float, retarded_tt: float) -> list[Dict[str, Any]]:
    """Observed file intervals, not a proof of every internal native read."""
    windows = []
    for slot in (0, 1):
        filename, start, end, edition = runtime.swe.get_current_file_data(slot)
        if (
            not filename
            or not all(math.isfinite(v) for v in (start, end))
            or not start <= retarded_tt <= julian_day_tt <= end
        ):
            raise EphemerisSourceError("lunar_source_window_incoherent")
        windows.append(
            {
                "slot": slot,
                "filename": Path(filename).name,
                "start_jd_tt": start,
                "end_jd_tt": end,
                "de_number": edition,
            }
        )
    return windows


def prime_lunar_source_window(
    julian_day_tt: float, model: str, trace: PhysicalEphemerisTrace
) -> Dict[str, Any]:
    swe = runtime.swe
    native = str(getattr(swe, "version", "unavailable"))
    binding = binding_distribution_version(swe, version)
    policy: Dict[str, Any] = {
        "method_id": METHOD_ID,
        "epoch_jd_tt": julian_day_tt,
        "ephemeris_model": model,
        "native_version": native,
        "binding_version": binding,
        "source_url": "https://www.astro.com/swisseph/swephprg.htm",
        "source_function": "pyswisseph2.10.3.2/libswe/sweph.c:sweplan,sweph,app_pos_etc_moon",
        "scope": "Retarded-state priming followed by a required apparent recomputation. Selected file intervals must cover the whole reception light path; not an atomic native read-set or accuracy certification.",
    }
    if model != "swieph":
        return {**policy, "status": "not_applied", "reason": "not_compressed_swiss"}
    if swe is None or (native, binding) != SOURCE_VERSION:
        return {
            **policy,
            "status": "not_applied",
            "reason": "unverified_native_version",
        }
    if not callable(getattr(swe, "get_current_file_data", None)):
        return {
            **policy,
            "status": "not_applied",
            "reason": "file_window_interface_unavailable",
        }
    if not math.isfinite(julian_day_tt):
        raise EphemerisSourceError("coordinate_values_unavailable")
    owned = coordinate_context_evidence()
    light_path = owned.get("lunar_light_path") if owned is not None else None
    if (
        owned is not None
        and owned.get("policy_id") == OWNED_CONTEXT_POLICY
        and owned.get("private_native_cache_reset") is True
        and owned.get("body_id") == swe.MOON
        and owned.get("physical_jd_tt") == julian_day_tt
        and light_path is not None
        and light_path.get("status") in {"already_covered", "reselected_common_window"}
    ):
        # The private layer already established the physical light path.
        # A new geometric call would reset it back to a reception-only fit.
        windows = selected_windows(julian_day_tt, light_path["retarded_jd_tt"])
        if (
            windows != owned["selected_windows"]
            or windows != light_path["selected_windows"]
        ):
            raise EphemerisSourceError("lunar_source_window_incoherent")
        return {
            **policy,
            "status": "primed",
            "light_time_days": light_path["light_time_days"],
            "retarded_jd_tt": light_path["retarded_jd_tt"],
            "selected_windows": windows,
            "source_contexts": {
                "Moon_owned_reception_light_path": trace.observe(
                    "Moon_owned_reception_light_path", model, record_factor=False
                )
            },
            "source_function": "compressed_ephemeris._lunar_light_path; sweph.c:app_pos_etc_moon",
            "scope": "Reuse the checked owned-native geocentric reception light path, then require apparent recomputation. Source context is observed after owned preselection; auxiliary native states are in that coordinate receipt. No independent re-priming, atomic native read-set or accuracy certification.",
        }
    selected = configured_ephemeris_path()
    base = (
        swe.FLG_SWIEPH
        | swe.FLG_SPEED
        | swe.FLG_XYZ
        | swe.FLG_EQUATORIAL
        | swe.FLG_J2000
        | swe.FLG_ICRS
        | swe.FLG_TRUEPOS
    )
    contexts = {}

    def state(epoch: float, barycentric: bool, factor: str) -> Any:
        flags = base | (swe.FLG_BARYCTR if barycentric else 0)
        values, returned = runtime.ephemeris_call("calc", epoch, swe.MOON, flags)
        assert_physical_configuration(selected)
        required = flags & ~swe.FLG_SWIEPH
        forbidden = (
            swe.FLG_SIDEREAL | swe.FLG_RADIANS | swe.FLG_HELCTR | swe.FLG_TOPOCTR
        )
        if (
            returned < 0
            or returned & required != required
            or returned & forbidden
            or bool(returned & swe.FLG_BARYCTR) != barycentric
        ):
            raise EphemerisSourceError("coordinate_contract_changed")
        if runtime.ephemeris_model_from_retflag(returned) != model:
            raise EphemerisSourceError("model_changed")
        if len(values) != 6 or not all(math.isfinite(v) for v in values):
            raise EphemerisSourceError("coordinate_values_unavailable")
        contexts[factor] = trace.observe(factor, model, record_factor=False)
        return tuple(float(v) for v in values)

    geometric = state(julian_day_tt, False, "Moon_light_path_geometric")
    radius = math.hypot(*geometric[:3])
    if radius <= 0:
        raise EphemerisSourceError("coordinate_values_unavailable")
    delay = radius / LIGHT_SPEED_AU_PER_DAY
    retarded = julian_day_tt - delay
    with preserve_native_dependency_context(
        julian_day_tt, retarded, model, native=ephemeris_runtime.swe
    ):
        state(retarded, True, "Moon_light_path_retarded_barycentric")
    return {
        **policy,
        "status": "primed",
        "light_time_days": delay,
        "retarded_jd_tt": retarded,
        "selected_windows": selected_windows(julian_day_tt, retarded),
        "source_contexts": contexts,
    }


def finish_lunar_source_window(
    policy: Dict[str, Any], initial: Sequence[float], refreshed: Sequence[float]
) -> None:
    if policy["status"] != "primed":
        return
    after = selected_windows(policy["epoch_jd_tt"], policy["retarded_jd_tt"])
    if after != policy["selected_windows"]:
        raise EphemerisSourceError("lunar_source_window_incoherent")
    policy["selected_windows_after_recomputation"] = after
    policy["initial_spherical_coordinates"] = list(initial[:3])
    policy["coherent_spherical_coordinates"] = list(refreshed[:3])
    policy["initial_native_state"] = list(initial)
    policy["coherent_native_state"] = list(refreshed)
    policy["status"] = "recomputed_in_common_window"


def coherent_lunar_native_state(
    operation: str,
    epoch: float,
    flags: int,
    julian_day_tt: float,
    model: str,
    trace: PhysicalEphemerisTrace,
    *,
    initial: Any = None,
    initial_flags: Any = None,
) -> tuple[Any, int, Dict[str, Any]]:
    """The same physical source window for every requested apparent frame.

    Call under the managed runtime lock. A surrounding third-party path
    restoration may clear caches; each invocation establishes its own window.
    """
    swe = runtime.swe
    if initial is None:
        initial, initial_flags = runtime.ephemeris_call(
            operation, epoch, swe.MOON, flags
        )
    if initial_flags is None:
        raise EphemerisSourceError("coordinate_contract_changed")
    if runtime.ephemeris_model_from_retflag(initial_flags) != model:
        raise EphemerisSourceError("model_changed")
    policy = prime_lunar_source_window(julian_day_tt, model, trace)
    coordinates, returned = initial, initial_flags
    if policy["status"] == "primed":
        coordinates, returned = runtime.ephemeris_call(
            operation, epoch, swe.MOON, flags
        )
        if runtime.ephemeris_model_from_retflag(returned) != model:
            raise EphemerisSourceError("model_changed")
        if len(coordinates) != 6 or not all(math.isfinite(v) for v in coordinates):
            raise EphemerisSourceError("coordinate_values_unavailable")
        finish_lunar_source_window(policy, initial, coordinates)
        if flags & swe.FLG_XYZ:
            policy.pop("initial_spherical_coordinates", None)
            policy.pop("coherent_spherical_coordinates", None)
    policy["requested_coordinate_flags"] = flags
    policy["coordinate_kind"] = "cartesian" if flags & swe.FLG_XYZ else "spherical"
    return coordinates, returned, policy
