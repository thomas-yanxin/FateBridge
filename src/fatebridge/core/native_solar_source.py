"""Explicit Swiss Sun file contexts without changing the physical epoch."""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path
from typing import Any, Callable

from fatebridge.core.ephemeris_runtime import lock_ephemeris_configuration
from fatebridge.utils.errors import EphemerisSourceError

POLICY_ID = (
    "same_epoch_moshier_preflight_then_requested_swiss_before_fixed_source_bisection_v1"
)
SWISS_SOLAR_CONTEXT_TT_INTERVAL = (
    date(1799, 1, 1).toordinal() + 1721424.5,
    date(2202, 1, 1).toordinal() + 1721424.5,
)


def swiss_solar_context_required(jd_tt: float) -> bool:
    """Return whether jd_tt lies inside the Swiss source-pinning interval."""
    start, end = SWISS_SOLAR_CONTEXT_TT_INTERVAL
    return start <= jd_tt < end


def native_solar_file_context(
    native: Any,
) -> tuple[tuple[str, float, float, int], ...] | None:
    """Lightweight Swiss file-slot context without per-call Path.stat()."""
    getter = getattr(native, "get_current_file_data", None)
    if not callable(getter):
        return None
    windows: list[tuple[str, float, float, int]] = []
    for slot in (0, 1):
        filename, start, end, edition = getter(slot)
        if (
            not filename
            or not all(math.isfinite(x) for x in (start, end))
            or start >= end
        ):
            return None
        windows.append((Path(filename).name, float(start), float(end), int(edition)))
    return tuple(windows)


def prime_swiss_solar_context(
    jd_tt: float,
    *,
    native: Any,
    invoke: Callable[..., Any],
    capture_context: bool = True,
) -> tuple[Any, tuple[tuple[str, float, float, int], ...] | None]:
    """Select the requested Swiss source at this same TT point via public APIs."""
    if not swiss_solar_context_required(jd_tt):
        raise EphemerisSourceError("solar_native_context_unavailable")
    with lock_ephemeris_configuration():
        _, flags = invoke("calc", jd_tt, native.SUN, native.FLG_MOSEPH)
        if flags != native.FLG_MOSEPH:
            raise EphemerisSourceError("coordinate_contract_changed")
        result = invoke("calc", jd_tt, native.SUN, native.FLG_SWIEPH)
        context = (
            native_solar_file_context(native)
            if capture_context and result[1] == native.FLG_SWIEPH
            else None
        )
        return result, context
