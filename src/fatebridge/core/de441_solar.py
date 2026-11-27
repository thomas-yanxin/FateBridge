"""Bundled DE441 Sun, using the shared receiver, light cone and date frame.

This replaces the lower-fidelity calendar fallback without changing native
file-backed positions. No reference crossings or fitted offsets are used.
"""

from __future__ import annotations

import math

from fatebridge.core.astro.analytic_observer import (
    ABERRATION_METHOD,
    LIGHT_TIME_METHOD,
    AnalyticObserver,
)
from fatebridge.core.astro.de441_source import source_details
from fatebridge.core.astro.reference_frames import (
    NATIVE_TROPICAL_MODEL,
    mean_j2000_apparent_ecliptic,
)

MODEL_ID = "fatebridge_de441_solar_v1"
PROVIDER = "jpl_de441"
CACHE_IDENTITY = (MODEL_ID, NATIVE_TROPICAL_MODEL)


def solar_longitude(jd_tt: float) -> float:
    """Geocentric apparent native-frame longitude at the given TT point."""
    if not math.isfinite(jd_tt):
        raise ValueError("Solar TT Julian day must be finite")
    position = AnalyticObserver().apparent_position("Sun", jd_tt - 2451545.0)
    x, y, _ = mean_j2000_apparent_ecliptic(position, jd_tt)
    return math.degrees(math.atan2(y, x)) % 360.0


def model_details() -> dict[str, object]:
    return {
        **source_details(),
        "model_id": MODEL_ID,
        "frame_model": NATIVE_TROPICAL_MODEL,
        "time_argument": "TT reception; full geocentric ERFA Fairhead TDB for source states",
        "light_time_method": LIGHT_TIME_METHOD,
        "observer_aberration_method": ABERRATION_METHOD,
        "receiver_and_target_source": "same DE441 EMB/geocentric Moon/EMRAT Earth and barycentric Sun",
        "position_frame": "geocentric apparent Vondrak2011 scalar-obliquity true ecliptic of date; full-Simon 77-term nutation and IAU2006 ICRS bias",
        "native_moshier_relabelled": False,
        "reference_values_used_at_runtime": False,
        "accuracy_certified": False,
        "scope": "Named bounded DE441 representation and shared optical reduction, not stock Swiss Moshier or a runtime load of the original JPL file. Finite comparisons do not certify all epochs or civil UTC.",
    }
