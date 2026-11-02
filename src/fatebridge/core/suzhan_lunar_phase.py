"""Modern instantaneous Moon-Sun longitude reference, separate from T1299.

This consumes the already guarded, same-epoch geocentric apparent tropical
coordinates. It neither calls an ephemeris nor assigns a sunrise calendar day.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.native_coordinates import COORDINATE_FLAGS
from fatebridge.utils.errors import EphemerisSourceError

METHOD = "modern_geocentric_apparent_elongation_tithi12_v1"
DEFINITIONS = [
    {
        "id": "imd_positional_astronomy_panchang_explanation",
        "url": "https://packolkata.imd.gov.in/panchang/en/explanation",
        "role": "Modern tithi spans successive 12 degree Moon-Sun longitude differences; instantaneous segmentation only here.",
    },
    {
        "id": "usno_primary_phase_definition_archived_by_ntsb",
        "url": "https://data.ntsb.gov/Docket/Document/docBLOB?FileExtension=.PDF&FileName=Data+from+U.S.+Naval+Observatory-Master.PDF&ID=40170653",
        "locator": "PDF page 4, USNO primary-phase definition",
        "role": "Apparent ecliptic Moon minus Sun longitude 0, 90, 180, 270 degrees defines the four primary phases.",
    },
]


def _finite(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EphemerisSourceError("coordinate_values_unavailable")
    try:
        result = float(value)
    except OverflowError as error:
        raise EphemerisSourceError("coordinate_values_unavailable") from error
    if not math.isfinite(result):
        raise EphemerisSourceError("coordinate_values_unavailable")
    return result


def lunar_phase_reference(raw: dict[str, Any]) -> dict[str, Any]:
    """Use captured longitudes, not rounded chart degrees or equatorial RA.

    Binary input ratios decide half-open intervals before float conversion.
    Precision here describes arithmetic, not uncertainty of the ephemeris.
    """
    native = runtime.swe
    if native is None:
        raise ImportError("现代月日黄经差需要Swiss Ephemeris坐标来源。")
    coordinate_mask = 0
    for name in COORDINATE_FLAGS:
        coordinate_mask |= getattr(native, name)
    source_mask = native.FLG_SWIEPH | native.FLG_MOSEPH | native.FLG_JPLEPH
    longitudes = {}
    sources = {}
    try:
        tt = _finite(raw["julian_day_tt"])
        ut1 = _finite(raw["julian_day_ut1"])
        for body in ("Sun", "Moon"):
            value = _finite(raw["states"][body]["longitude"])
            if not 0 <= value < 360:
                raise EphemerisSourceError("coordinate_values_unavailable")
            receipt = raw["ephemeris_provenance"]["by_body"][body]
            flags = receipt["ecliptic_return_flags"]
            if (
                isinstance(flags, bool)
                or not isinstance(flags, int)
                or flags < 0
                or flags & coordinate_mask
            ):
                raise EphemerisSourceError("coordinate_contract_changed")
            bits = flags & source_mask
            if bits not in (native.FLG_SWIEPH, native.FLG_MOSEPH, native.FLG_JPLEPH):
                raise EphemerisSourceError("coordinate_model_changed")
            model = runtime.ephemeris_model_from_retflag(flags)
            if receipt["ecliptic_model"] != model:
                raise EphemerisSourceError("coordinate_model_changed")
            longitudes[body] = value
            sources[body] = {
                "ecliptic_model": model,
                "ecliptic_return_flags": flags,
            }
    except (KeyError, TypeError) as error:
        raise EphemerisSourceError("coordinate_values_unavailable") from error

    angle = (Fraction(longitudes["Moon"]) - Fraction(longitudes["Sun"])) % 360
    segment = int(angle // 12)
    lower, upper = segment * 12, (segment + 1) * 12
    # Float export must not contradict the exact half-open segment near an
    # endpoint (including a small negative difference rounded up to 360).
    display = max(float(lower), min(float(angle), math.nextafter(upper, -math.inf)))
    distance = min(angle - lower, upper - angle)
    return {
        "method_id": METHOD,
        "coordinate_frame": "geocentric_apparent_tropical_ecliptic_equinox_of_date",
        "coordinate_unit": "modern_degree_360",
        "julian_day_tt": tt,
        "julian_day_ut1": ut1,
        "source_longitudes": longitudes,
        "ephemeris_provenance": sources,
        "elongation_degrees": display,
        "elongation_exact_binary_ratio": {
            # Decimal strings preserve integers beyond JavaScript's 53 bits
            # on REST/MCP JSON transports. Exactness concerns binary inputs,
            # not uncertainty of the physical coordinates.
            "numerator": str(angle.numerator),
            "denominator": str(angle.denominator),
        },
        "display_adjusted_for_half_open_interval": display != float(angle),
        "modern_tithi": {
            "index": segment + 1,
            "half": "waxing" if segment < 15 else "waning",
            "half_zh": "白" if segment < 15 else "黑",
            "half_tithi_index": segment % 15 + 1,
            "lower_degrees_inclusive": lower,
            "upper_degrees_exclusive": upper,
            "distance_to_nearest_boundary_degrees": float(distance),
            "interval_convention": "[12*(index-1),12*index); exact 180 starts modern waning 1",
        },
        "definitions": [dict(row) for row in DEFINITIONS],
        "calendar_day_assigned": False,
        "sunrise_day_or_tithi_end_times_computed": False,
        "lunar_star_conjunction_computed": False,
        "ancient_ritual_condition_evaluated": False,
        "historical_day_boundary_or_half_established": False,
        "leap_short_month_priority_established": False,
        "ephemeris_accuracy_certified": False,
        "scope": "同次TT的现代月日视黄经差与12度角距分段；不是T1299历日日号、日出历日或T1796仪轨定日的认证，不改变日界、主宿或闰小月候选。二进制算术边界不代表物理时刻精度或现实预测效力。",
    }
