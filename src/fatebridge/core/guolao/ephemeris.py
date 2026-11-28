"""Cached Swiss Ephemeris positions, 28-mansion frames (今度/古度), and fast LiChun lookup."""

from __future__ import annotations

from datetime import datetime
from fractions import Fraction
from functools import lru_cache
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.lunar_mansions import (
    DATA,
    MansionFrame,
    _cached_sources_and_stars,
    mansion_at,
    reference_geometry,
    seven_luminary_mansion_positions,
)
from fatebridge.core.astro.native_coordinates import require_spherical_coordinates
from fatebridge.core.astro.native_motion import require_longitude_speed
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path, solcross_tt
from fatebridge.core.guolao.moira import (
    PURPLE_CLOUDS_MODEL_ID,
    PURPLE_CLOUDS_RATE_DEG_PER_DAY,
    purple_clouds_longitude,
)

__all__ = [
    "DATA",
    "MansionFrame",
    "_cached_sources_and_stars",
    "_lichun_jd_tt",
    "fast_lichun_year",
    "mansion_at",
    "positions",
    "reference_geometry",
]


@lru_cache(maxsize=128)
def _lichun_jd_tt(year: int) -> float:
    """Fast Sun = 315° LiChun instant via C swe.solcross (<0.1 ms)."""
    if runtime.swe is None:
        raise RuntimeError("Swiss Ephemeris is required for fast LiChun calculation")
    jan1_tt = runtime.swe.julday(year, 1, 1, 0.0, runtime.swe.GREG_CAL)
    jd_tt, _ = solcross_tt(315.0, jan1_tt, runtime.swe.FLG_SWIEPH)
    return jd_tt


def fast_lichun_year(local_dt: datetime, jd_tt: float) -> int:
    """Determine the LiChun-anchored year in <0.1 ms without full 24-term almanac scan."""
    year = local_dt.year
    if runtime.swe is not None:
        lichun_tt = _lichun_jd_tt(year)
        return year if jd_tt >= lichun_tt else year - 1
    from fatebridge.core.almanac import get_bazi_year

    return get_bazi_year(local_dt, "UTC")


def positions(
    birth: AstroBirthInfo,
    *,
    hsys: int | str | None = None,
    zodiacal: int | str | None = None,
    observer_geometry: bool = True,
    correct_motion: bool = False,
    mansion_frame: MansionFrame = "modern_equatorial",
) -> dict[str, Any]:
    """Compute Guolao 7 luminaries, 4 extras (罗计孛炁), and 28-mansion boundaries (<3 ms)."""
    base = seven_luminary_mansion_positions(
        birth,
        hsys=hsys,
        zodiacal=zodiacal,
        observer_geometry=observer_geometry,
        correct_motion=correct_motion,
        mansion_frame=mansion_frame,
        chart_variant="guolao_chart",
    )
    swe = runtime.swe
    if swe is None:
        raise ValueError("果老研究盘需要 Swiss Ephemeris")
    times = birth.time_scales
    if times.tt is None:
        raise ValueError("果老研究盘需要可用的 TT/UT1 转换")
    jd_tt = times.tt.as_float()
    ut = times.ut1
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    extra: dict[str, Any] = {}
    with runtime.preserve_ephemeris_path():
        swe.set_ephe_path(configured_ephemeris_path() or "")
        for name, body in [("罗", swe.MEAN_NODE), ("孛", swe.MEAN_APOG)]:
            coords, flag = runtime.ephemeris_call("calc", jd_tt, body, flags)
            lon, lat, _ = require_spherical_coordinates(coords, flag, native=swe)
            speed = require_longitude_speed(coords, flag, swe.FLG_SPEED)
            eq, eq_flag = runtime.ephemeris_call(
                "calc", jd_tt, body, flags | swe.FLG_EQUATORIAL
            )
            ra, _, _ = require_spherical_coordinates(
                eq, eq_flag, native=swe, equatorial=True
            )
            extra[name] = {
                "longitude": lon % 360.0,
                "latitude": lat,
                "right_ascension": ra % 360.0,
                "longitude_speed": float(speed),
                "retrograde": float(speed) < 0,
                "model": "mean_lunar_node" if name == "罗" else "mean_lunar_apogee",
            }
        extra["计"] = {
            **extra["罗"],
            "longitude": float((Fraction(extra["罗"]["longitude"]) + 180) % 360)
            % 360.0,
            "right_ascension": float(
                (Fraction(extra["罗"]["right_ascension"]) + 180) % 360
            )
            % 360.0,
            "latitude": -extra["罗"]["latitude"],
            "model": "opposite_mean_lunar_node",
            "derived_from": "罗",
            "derivation_source_longitude": extra["罗"]["longitude"],
            "derivation_source_right_ascension": extra["罗"]["right_ascension"],
        }
        purple = purple_clouds_longitude(ut.as_float())
        purple_ra, _, _ = swe.cotrans((purple, 0, 1), -base["obliquity"])
        extra["炁"] = {
            "longitude": purple,
            "latitude": 0.0,
            "right_ascension": purple_ra % 360.0,
            "longitude_speed": PURPLE_CLOUDS_RATE_DEG_PER_DAY,
            "retrograde": False,
            "model": PURPLE_CLOUDS_MODEL_ID,
        }
    return {**base, "extra": extra}
