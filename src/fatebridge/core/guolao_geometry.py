"""Optional astronomical reference geometry, independent of Guolao palaces.

Unavailable requested cusps must not discard valid geocentric bodies. Equal
houses may be called solely to recover ASC/MC; those cusps are never used as
substitutes for the requested system. Exact geographic poles have no unique
rising point, so no angles or houses are assigned there.
"""

from __future__ import annotations

import math
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.geometry import is_prograde_house_partition
from fatebridge.core.astro.zodiac import native_lahiri_houses


def reference_geometry(
    *,
    jd_ut1: float,
    jd_tt: float,
    latitude: float,
    longitude: float,
    house_info: dict[str, Any],
    sidereal: bool,
) -> dict[str, Any]:
    """Caller holds the shared Swiss lock. No fallback house partition."""
    swe = runtime.swe
    if swe is None:
        raise ValueError("果老天文参考计算需要Swiss Ephemeris")
    ayanamsha = 0.0
    if sidereal:
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        flag, ayanamsha = runtime.ephemeris_call(
            "get_ayanamsa_ex", jd_tt, swe.FLG_SWIEPH
        )
        if flag < 0 or not math.isfinite(ayanamsha):
            raise ValueError("Lahiri偏移计算失败，不能误标所选黄道")
    code = house_info.get("swisseph_code", b"W")
    available = {
        "status": "unavailable",
        "angles_status": "unavailable",
        "houses_status": "unavailable",
        "requested_house_system": house_info["key"],
        "requested_house_code": code.decode("ascii"),
        "coordinate_frame": (
            "selected_lahiri_sidereal_zodiac" if sidereal else "tropical_zodiac"
        ),
        "angle_method": None,
        "house_method": None,
        "reason": None,
        "substituted_house_system": False,
    }
    layout: dict[str, Any] = {
        "ascendant": None,
        "midheaven": None,
        "tropical_ascendant": None,
        "tropical_midheaven": None,
        "house_cusps": [],
        "method": None,
        "ayanamsha": ayanamsha,
        "availability": available,
    }
    if abs(latitude) == 90:
        available["reason"] = "geographic_pole_no_unique_rising_point"
        return layout

    def calculate(selected_code: bytes) -> dict[str, Any]:
        cusps, angles = runtime.ephemeris_call(
            "houses_ex", jd_ut1, latitude, longitude, selected_code
        )
        tropical_asc, tropical_mc = float(angles[0]) % 360, float(angles[1]) % 360
        result = {
            "ascendant": tropical_asc,
            "midheaven": tropical_mc,
            "tropical_ascendant": tropical_asc,
            "tropical_midheaven": tropical_mc,
            "house_cusps": list(cusps),
            "method": "swisseph_houses_ex_tropical",
        }
        if sidereal:
            native = native_lahiri_houses(
                julian_day_ut1=jd_ut1,
                julian_day_tt=jd_tt,
                latitude=latitude,
                longitude=longitude,
                house_code=selected_code,
            )
            result.update(
                ascendant=native["ascendant"],
                midheaven=native["midheaven"],
                house_cusps=native["house_cusps"],
                method=native["sidereal_house_method"],
            )
        return result

    try:
        candidate = calculate(code)
    except swe.Error:
        available["reason"] = "requested_house_unavailable_from_swisseph"
        try:
            candidate = calculate(b"E")
        except swe.Error:
            return layout
        candidate["house_cusps"] = []
        candidate["method"] = None
        available["angle_method"] = "swisseph_ascmc_equal_call_cusps_discarded"
    if not all(
        math.isfinite(candidate[key])
        for key in [
            "ascendant",
            "midheaven",
            "tropical_ascendant",
            "tropical_midheaven",
        ]
    ):
        available["reason"] = "invalid_reference_angles"
        return layout
    available["angles_status"] = "available"
    if available["angle_method"] is None:
        available["angle_method"] = "swisseph_ascmc"
    cusps = candidate["house_cusps"]
    if cusps:
        if (
            len(cusps) != 12
            or not all(math.isfinite(v) for v in cusps)
            or not is_prograde_house_partition(cusps)
        ):
            candidate["house_cusps"] = []
            candidate["method"] = None
            available["reason"] = "requested_cusps_not_a_valid_ecliptic_partition"
        else:
            available["houses_status"] = "available"
            available["house_method"] = candidate["method"]
    available["status"] = (
        "available" if available["houses_status"] == "available" else "partial"
    )
    layout.update(candidate)
    return layout
