"""Consolidated Sukuyo equatorial 28-mansion projection and Moon-Sun elongation phase."""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.lunar_mansions import (
    mansion_at,
    seven_luminary_mansion_positions,
)
from fatebridge.core.astro.native_coordinates import COORDINATE_FLAGS
from fatebridge.utils.errors import EphemerisSourceError

METHOD = "modern_equatorial_research_anchors_v1"
LUNAR_PHASE_METHOD = "modern_geocentric_apparent_elongation_tithi12_v1"


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
    """Compute instantaneous Moon-Sun elongation and 12-degree tithi segment."""
    native = runtime.swe
    if native is None:
        raise ModuleNotFoundError("现代月日黄经差需要Swiss Ephemeris坐标来源。")
    coordinate_mask = 0
    for name in COORDINATE_FLAGS:
        coordinate_mask |= getattr(native, name)
    source_mask = native.FLG_SWIEPH | native.FLG_MOSEPH | native.FLG_JPLEPH
    longitudes: dict[str, float] = {}
    sources: dict[str, dict[str, Any]] = {}
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
            sources[body] = {"ecliptic_model": model, "ecliptic_return_flags": flags}
    except (KeyError, TypeError) as error:
        raise EphemerisSourceError("coordinate_values_unavailable") from error

    angle = (Fraction(longitudes["Moon"]) - Fraction(longitudes["Sun"])) % 360
    segment = int(angle // 12)
    lower, upper = segment * 12, (segment + 1) * 12
    display = max(float(lower), min(float(angle), math.nextafter(upper, -math.inf)))
    distance = min(angle - lower, upper - angle)
    return {
        "method_id": LUNAR_PHASE_METHOD,
        "coordinate_frame": "geocentric_apparent_tropical_ecliptic_equinox_of_date",
        "coordinate_unit": "modern_degree_360",
        "julian_day_tt": tt,
        "julian_day_ut1": ut1,
        "source_longitudes": longitudes,
        "ephemeris_provenance": sources,
        "elongation_degrees": display,
        "modern_tithi": {
            "index": segment + 1,
            "half": "waxing" if segment < 15 else "waning",
            "half_zh": "白" if segment < 15 else "黑",
            "half_tithi_index": segment % 15 + 1,
            "lower_degrees_inclusive": lower,
            "upper_degrees_exclusive": upper,
            "distance_to_nearest_boundary_degrees": float(distance),
        },
        "calendar_day_assigned": False,
    }


def build_equatorial_mansions(birth: AstroBirthInfo) -> dict[str, Any]:
    """Compute geocentric 28 equatorial mansion positions for the 7 luminaries."""
    if runtime.swe is None:
        raise ModuleNotFoundError(
            "天文不等宽宿度需要Swiss Ephemeris；不静默降级为等分示意。"
        )
    raw = seven_luminary_mansion_positions(
        birth,
        hsys=0,
        zodiacal=0,
        observer_geometry=False,
        correct_motion=False,
    )
    bodies = [
        {
            "id": name,
            "longitude": state["longitude"],
            "latitude": state["latitude"],
            "right_ascension": state["right_ascension"],
            "declination": state["declination"],
            "mansion": mansion_at(state["right_ascension"], raw["boundaries"]),
        }
        for name, state in raw["states"].items()
    ]
    return {
        "method_id": METHOD,
        "coordinate_frame": "geocentric_apparent_true_equator_equinox_of_date",
        "coordinate_unit": "modern_degree_360",
        "utc_datetime": birth.utc_isoformat,
        "julian_day_tt": raw["julian_day_tt"],
        "julian_day_ut1": raw["julian_day_ut1"],
        "ephemeris_models": raw["models"],
        "lunar_phase_reference": lunar_phase_reference(raw),
        "bodies": bodies,
        "boundaries": raw["boundaries"],
        "classical_boundary_acceptance": False,
    }


def apply_equatorial_mansions(chart: dict[str, Any], astronomy: dict[str, Any]) -> None:
    by_name = {body["id"]: body for body in astronomy["bodies"]}
    for point in chart["objects"]:
        point.pop("su28", None)
        point.pop("su28_degree", None)
        if point["id"] not in by_name:
            point["su28_unavailable_reason"] = "outside_seven_physical_luminaries_scope"
            continue
        body = by_name[point["id"]]
        mansion = body["mansion"]
        point.update(
            su28=mansion["su28"].removesuffix("宿"),
            su28_method=METHOD,
            su28_degree=mansion["degree_in_mansion"],
            su28_width=mansion["mansion_width"],
            right_ascension=body["right_ascension"],
            declination=body["declination"],
            su28_boundary_distance=mansion["boundary_distance"],
        )
