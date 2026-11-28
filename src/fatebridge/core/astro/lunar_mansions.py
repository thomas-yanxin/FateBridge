"""Shared 28-mansion (今度/古度) frames and 7-luminary ephemeris positions."""

from __future__ import annotations

import json
import math
from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from fatebridge.core.astro import runtime
from fatebridge.core.astro.angle_definitions import (
    geographic_pole_angle_definition,
    is_ascendant_resolved,
)
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.native_coordinates import (
    require_altitude,
    require_spherical_coordinates,
)
from fatebridge.core.astro.native_motion import require_longitude_speed
from fatebridge.core.astro.profiles import (
    _resolve_core_chart_house_system,
    _resolve_core_chart_zodiacal_mode,
)
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.fixed_star_paths import fixed_star_catalogue
from fatebridge.utils.errors import EphemerisSourceError

DATA = Path(__file__).resolve().parents[2] / "data" / "guolao"

MANSIONS = tuple("角亢氐房心尾箕斗牛女虚危室壁奎娄胃昴毕觜参井鬼柳星张翼轸")
MANSION_LORDS: dict[str, str] = dict(
    zip((name + "宿" for name in MANSIONS), list("木金土日月火水") * 4)
)
SEVEN_LUMINARIES_ZH: dict[str, str] = {
    "Sun": "日",
    "Moon": "月",
    "Mercury": "水",
    "Venus": "金",
    "Mars": "火",
    "Jupiter": "木",
    "Saturn": "土",
}

MansionFrame = Literal[
    "modern_equatorial",
    "modern_ecliptic",
    "shoushi_ecliptic",
    "shoushi_equatorial",
]


@dataclass(frozen=True)
class HistoricalMansions:
    source_id: str
    circle_du: Fraction
    widths_du: tuple[Fraction, ...]
    coordinate_frame: str = "unspecified"

    def __post_init__(self) -> None:
        object.__setattr__(self, "widths_du", tuple(self.widths_du))
        if sum(self.widths_du) != self.circle_du or len(self.widths_du) != 28:
            raise ValueError("历史宿表须包含28个闭合宿宽")

    def locate(self, angle_from_jiao_du: Fraction) -> tuple[str, Fraction, Fraction]:
        starts = [sum(self.widths_du[:i], Fraction()) for i in range(28)]
        angle = angle_from_jiao_du % self.circle_du
        index = bisect_right(starts, angle) - 1
        return MANSIONS[index], angle - starts[index], self.widths_du[index]


SHOUSHI_1281 = HistoricalMansions(
    source_id="yuanshi_054_shoushi_1281",
    coordinate_frame="source_ecliptic",
    circle_du=Fraction("365.2575"),
    widths_du=tuple(
        map(
            Fraction,
            (
                "12.87",
                "9.56",
                "16.40",
                "5.48",
                "6.27",
                "17.95",
                "9.59",
                "23.47",
                "6.90",
                "11.12",
                "9.0075",
                "15.95",
                "18.32",
                "9.34",
                "17.87",
                "12.36",
                "15.81",
                "11.08",
                "16.50",
                "0.05",
                "10.28",
                "31.03",
                "2.11",
                "13",
                "6.31",
                "17.79",
                "20.09",
                "18.75",
            ),
        )
    ),
)

SHOUSHI_EQUATORIAL_1281 = HistoricalMansions(
    source_id="yuanshi_054_nlc166_equatorial_mansions",
    coordinate_frame="source_equatorial",
    circle_du=Fraction("365.2575"),
    widths_du=tuple(
        map(
            Fraction,
            (
                "12.10",
                "9.20",
                "16.30",
                "5.60",
                "6.50",
                "19.10",
                "10.40",
                "25.20",
                "7.20",
                "11.35",
                "8.9575",
                "15.40",
                "17.10",
                "8.60",
                "16.60",
                "11.80",
                "15.60",
                "11.30",
                "17.40",
                "0.05",
                "11.10",
                "33.30",
                "2.20",
                "13.30",
                "6.30",
                "17.25",
                "18.75",
                "17.30",
            ),
        )
    ),
)


@lru_cache(maxsize=1)
def _cached_sources_and_stars() -> tuple[dict[str, Any], bytes]:
    sources = json.loads((DATA / "sources.json").read_text(encoding="utf-8"))
    catalogue_bytes = (DATA / "sefstars.txt").read_bytes()
    return sources, catalogue_bytes


def mansion_at(
    coordinate: float | Fraction,
    boundaries: list[dict[str, Any]],
    *,
    frame: MansionFrame = "modern_equatorial",
) -> dict[str, Any]:
    """Locate a coordinate inside 28 mansions under 今度 (360°) or 古度 (365.2575度)."""
    if not math.isfinite(coordinate):
        raise ValueError("宿界坐标须有限")
    if frame in ("shoushi_ecliptic", "shoushi_equatorial"):
        jiao_edge = next((b for b in boundaries if b["su28"] == "角宿"), boundaries[0])
        key = "right_ascension" if frame == "shoushi_equatorial" else "longitude"
        origin = Fraction(jiao_edge.get(key, jiao_edge["right_ascension"]))
        table = (
            SHOUSHI_EQUATORIAL_1281 if frame == "shoushi_equatorial" else SHOUSHI_1281
        )
        offset_deg = (Fraction(coordinate) - origin) % 360
        du = offset_deg * table.circle_du / 360
        su_name, deg_in_du, width_du = table.locate(du)
        su28 = su_name + "宿"
        return {
            "su28": su28,
            "degree_lord": MANSION_LORDS[su28],
            "coordinate": float(Fraction(coordinate) % 360),
            "degree_in_mansion": float(deg_in_du),
            "mansion_width": float(width_du),
            "boundary_distance": float(min(deg_in_du, width_du - deg_in_du)),
            "determinative_star": jiao_edge["star"],
            "coordinate_unit": "shoushi_du_365_2575",
            "placement_basis": table.source_id,
        }

    coord_key = "right_ascension" if frame == "modern_equatorial" else "longitude"
    ordered = sorted(boundaries, key=lambda b: b[coord_key])
    values = [b[coord_key] for b in ordered]
    if len(ordered) != 28 or len(set(values)) != 28:
        raise ValueError("宿界须为28个不同的有限坐标")
    starts = [Fraction(v) for v in values]
    exact = Fraction(coordinate) % 360
    index = (bisect_right(starts, exact) - 1) % 28
    edge, end = ordered[index], ordered[(index + 1) % 28]
    width = float((Fraction(end[coord_key]) - Fraction(edge[coord_key])) % 360)
    offset = min(
        float((exact - Fraction(edge[coord_key])) % 360), math.nextafter(width, 0.0)
    )
    return {
        "su28": edge["su28"],
        "degree_lord": MANSION_LORDS[edge["su28"]],
        coord_key: min(float(exact), math.nextafter(360.0, 0.0)),
        "degree_in_mansion": offset,
        "mansion_width": width,
        "boundary_distance": float(
            min(
                (exact - Fraction(edge[coord_key])) % 360,
                (Fraction(end[coord_key]) - exact) % 360,
            )
        ),
        "determinative_star": edge["star"],
        "coordinate_unit": "modern_degree_360",
        "placement_basis": (
            "modern_equatorial_research_anchors_v1"
            if frame == "modern_equatorial"
            else "modern_ecliptic_research_anchors_v1"
        ),
    }


def reference_geometry(
    *,
    jd_ut1: UT1Instant | float,
    tt: TTInstant,
    latitude: float,
    longitude: float,
    house_info: dict[str, Any],
    sidereal: bool,
) -> dict[str, Any]:
    """Compute reference ascendant, midheaven, and house cusps with clean pole/polar handling."""
    swe = runtime.swe
    assert swe is not None
    hcode = house_info.get("swisseph_code") or (
        b"W" if house_info["key"] == "whole_sign" else b"E"
    )
    hcode_str = hcode.decode() if isinstance(hcode, bytes) else str(hcode)

    pole_def = geographic_pole_angle_definition(latitude)
    if abs(latitude) >= 90.0 or (
        pole_def is not None and not is_ascendant_resolved(pole_def)
    ):
        return {
            "tropical_ascendant": None,
            "tropical_midheaven": None,
            "ascendant": None,
            "midheaven": None,
            "house_cusps": [],
            "ayanamsha": 0.0,
            "method": "geographic_pole",
            "availability": {
                "status": "unavailable",
                "angles_status": "unavailable",
                "houses_status": "unavailable",
                "requested_house_system": house_info["key"],
                "requested_house_code": hcode_str,
                "reason": "geographic_pole_no_unique_rising_point",
                "substituted_house_system": False,
            },
        }

    ayanamsha = 0.0
    if sidereal:
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        flag, ayanamsha = runtime.ephemeris_call(
            "get_ayanamsa_ex", tt.as_float(), swe.FLG_SWIEPH
        )
        if flag < 0 or not math.isfinite(ayanamsha):
            raise EphemerisSourceError("ayanamsha_unavailable")

    ut1_val = jd_ut1.as_float() if isinstance(jd_ut1, UT1Instant) else float(jd_ut1)
    cusps_out: list[float] = []
    house_method: str | None = f"swisseph_{house_info['key']}"
    reason: str | None = None
    sid_flags = swe.FLG_SIDEREAL if sidereal else 0

    try:
        trop_cusps, trop_ascmc = runtime.ephemeris_call(
            "houses_ex", ut1_val, latitude, longitude, hcode, 0, _julian_day_tt=tt
        )
        trop_asc = float(trop_ascmc[0])
        trop_mc = float(trop_ascmc[1])
        if sidereal:
            cusps_raw, sid_ascmc = runtime.ephemeris_call(
                "houses_ex",
                ut1_val,
                latitude,
                longitude,
                hcode,
                sid_flags,
                _julian_day_tt=tt,
            )
            asc = float(sid_ascmc[0])
            mc = float(sid_ascmc[1])
            cusps_cand = [float(c) for c in cusps_raw[:12]]
        else:
            asc, mc = trop_asc, trop_mc
            cusps_cand = [float(c) for c in trop_cusps[:12]]

        if house_info["key"] == "whole_sign":
            asc_sign = int((asc % 360.0) // 30)
            cusps_out = [float(((asc_sign + i) % 12) * 30) for i in range(12)]
        elif house_info["key"] == "equal":
            cusps_out = [float((asc + 30.0 * i) % 360.0) for i in range(12)]
        else:
            if len(cusps_cand) == 12 and len({round(c, 8) for c in cusps_cand}) == 12:
                cusps_out = cusps_cand
            else:
                reason = "requested_cusps_not_a_valid_ecliptic_partition"
                house_method = None
    except swe.Error as err:
        reason = f"swisseph_houses_unavailable:{err}"
        house_method = None
        _, trop_ascmc = runtime.ephemeris_call(
            "houses_ex", ut1_val, latitude, longitude, b"W", 0, _julian_day_tt=tt
        )
        trop_asc = float(trop_ascmc[0])
        trop_mc = float(trop_ascmc[1])
        asc = (trop_asc - ayanamsha) % 360.0 if sidereal else trop_asc
        mc = (trop_mc - ayanamsha) % 360.0 if sidereal else trop_mc

    valid = len(cusps_out) == 12
    if not valid and reason is None:
        reason = "requested_cusps_not_a_valid_ecliptic_partition"
        house_method = None

    return {
        "tropical_ascendant": trop_asc,
        "tropical_midheaven": trop_mc,
        "ascendant": asc,
        "midheaven": mc,
        "house_cusps": cusps_out,
        "ayanamsha": ayanamsha,
        "method": (
            "swisseph_houses_ex_sidereal_lahiri"
            if sidereal
            else "swisseph_houses_ex_tropical"
        ),
        "availability": {
            "status": "available" if valid else "partial",
            "angles_status": "available",
            "houses_status": "available" if valid else "unavailable",
            "requested_house_system": house_info["key"],
            "requested_house_code": hcode_str,
            "house_method": house_method,
            "reason": reason,
            "substituted_house_system": False,
        },
    }


def seven_luminary_mansion_positions(
    birth: AstroBirthInfo,
    *,
    hsys: int | str | None = None,
    zodiacal: int | str | None = None,
    observer_geometry: bool = True,
    correct_motion: bool = False,
    mansion_frame: MansionFrame = "modern_equatorial",
    chart_variant: str = "guolao_chart",
) -> dict[str, Any]:
    """Compute the 7 luminaries, optional observer house geometry, and 28-mansion boundaries."""
    del correct_motion
    if runtime.swe is None:
        raise ValueError("果老研究盘需要 Swiss Ephemeris")
    swe = runtime.swe
    hi = _resolve_core_chart_house_system(hsys, chart_variant=chart_variant)
    zi = _resolve_core_chart_zodiacal_mode(zodiacal, chart_variant=chart_variant)
    sources, catalogue_bytes = _cached_sources_and_stars()
    states: dict[str, Any] = {}
    body_provenance: dict[str, Any] = {}
    models: set[str] = set()
    with runtime.preserve_ephemeris_path():
        swe.set_ephe_path(configured_ephemeris_path() or "")
        times = birth.time_scales
        if times.tt is None:
            raise ValueError("果老研究盘需要可用的 TT/UT1 转换")
        tt, ut = times.tt, times.ut1
        jd_tt = tt.as_float()
        flags = swe.FLG_SWIEPH | swe.FLG_SPEED
        for name in SEVEN_LUMINARIES_ZH:
            body_id = getattr(swe, name.upper())
            ecliptic, flag = runtime.ephemeris_call("calc", jd_tt, body_id, flags)
            lon, lat, _ = require_spherical_coordinates(ecliptic, flag, native=swe)
            speed = require_longitude_speed(ecliptic, flag, swe.FLG_SPEED)
            model = runtime.ephemeris_model_from_retflag(flag)
            equatorial, eq_flag = runtime.ephemeris_call(
                "calc", jd_tt, body_id, flags | swe.FLG_EQUATORIAL
            )
            ra, dec, _ = require_spherical_coordinates(
                equatorial, eq_flag, native=swe, equatorial=True
            )
            models.add(model)
            body_provenance[name] = {
                "ecliptic_model": model,
                "ecliptic_return_flags": int(flag),
                "equatorial_model": runtime.ephemeris_model_from_retflag(eq_flag),
                "equatorial_return_flags": int(eq_flag),
            }
            states[name] = {
                "longitude": lon % 360.0,
                "latitude": lat,
                "longitude_speed": float(speed),
                "retrograde": float(speed) < 0,
                "right_ascension": ra % 360.0,
                "declination": dec,
            }
        obliquity, ob_flag = runtime.ephemeris_call("calc", jd_tt, swe.ECL_NUT)
        if ob_flag < 0 or len(obliquity) < 4:
            raise EphemerisSourceError("coordinate_values_unavailable")

        asc = mc = asc_ra = altitude = None
        cusps: list[float] = []
        ayanamsha = 0.0
        zodiac_layout: dict[str, Any] = {
            "ascendant": None,
            "midheaven": None,
            "house_cusps": [],
            "method": "swisseph_houses_ex_tropical",
            "availability": {"status": "not_requested"},
        }
        if observer_geometry:
            _, altitude, _ = runtime.ephemeris_call(
                "azalt",
                ut,
                swe.EQU2HOR,
                (birth.longitude, birth.latitude, 0),
                0,
                0,
                (states["Sun"]["right_ascension"], states["Sun"]["declination"], 1),
                _julian_day_tt=tt,
            )
            require_altitude(altitude)
            zodiac_layout = reference_geometry(
                jd_ut1=ut,
                tt=tt,
                latitude=birth.latitude,
                longitude=birth.longitude,
                house_info=hi,
                sidereal=zi["sidereal"],
            )
            ayanamsha = zodiac_layout["ayanamsha"]
            asc = zodiac_layout["tropical_ascendant"]
            mc = zodiac_layout["tropical_midheaven"]
            cusps = zodiac_layout["house_cusps"]
            if asc is not None:
                asc_ra, _, _ = swe.cotrans((asc, 0, 1), -obliquity[0])
        elif zi["sidereal"]:
            swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
            flag, ayanamsha = runtime.ephemeris_call(
                "get_ayanamsa_ex", jd_tt, swe.FLG_SWIEPH
            )
            if flag < 0 or not math.isfinite(ayanamsha):
                raise EphemerisSourceError("ayanamsha_unavailable")

        with fixed_star_catalogue(swe, catalogue_bytes):
            boundaries: list[dict[str, Any]] = []
            need_ecliptic = mansion_frame in ("modern_ecliptic", "shoushi_ecliptic")
            for index, star in enumerate(sources["stars"]):
                star_key = f"FBJ{index:02}"
                coord, _, flag = runtime.ephemeris_call(
                    "fixstar2", star_key, jd_tt, swe.FLG_SWIEPH | swe.FLG_EQUATORIAL
                )
                ra, _, _ = require_spherical_coordinates(
                    coord, flag, native=swe, equatorial=True
                )
                entry: dict[str, Any] = {
                    "su28": star["mansion"],
                    "star": star["star"],
                    "right_ascension": ra % 360.0,
                }
                if need_ecliptic:
                    ec_coord, _, ec_flag = runtime.ephemeris_call(
                        "fixstar2", star_key, jd_tt, swe.FLG_SWIEPH
                    )
                    ec_lon, _, _ = require_spherical_coordinates(
                        ec_coord, ec_flag, native=swe
                    )
                    entry["longitude"] = ec_lon % 360.0
                boundaries.append(entry)

    return {
        "states": states,
        "boundaries": boundaries,
        "obliquity": float(obliquity[0]),
        "ascendant": asc,
        "ascendant_ra": asc_ra,
        "midheaven": mc,
        "cusps": cusps,
        "zodiac_house_layout": zodiac_layout,
        "ayanamsha": ayanamsha,
        "house_info": hi,
        "zodiac_info": zi,
        "julian_day_tt": jd_tt,
        "julian_day_ut1": ut.as_float(),
        "time_conversion": times.method,
        "future_leap_seconds_assumed_unchanged": times.future_leap_seconds_assumed_unchanged,
        "solar_altitude": altitude,
        "models": sorted(models),
        "ephemeris_provenance": {"by_body": body_provenance},
    }
