"""Diurnal/nocturnal noble selection: fixed branch convention or sunrise/sunset."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

import swisseph as swe

from fatebridge.core.ephemeris_runtime import ephemeris_call, native_ephemeris_errors
from fatebridge.utils.civil_time import utc_calendar
from fatebridge.utils.data import EARTHLY_BRANCHES
from fatebridge.utils.errors import EphemerisSourceError

DAY_BRANCHES = "卯辰巳午未申"
DiurnalMode = Literal["clock", "sunrise_sunset"]


def _latest_solar_event(
    jd_ut: float, flag: int, lon: float, lat: float
) -> float | None:
    """Return the most recent sunrise/sunset JD(UT) <= jd_ut within 24h."""
    geopos = (lon, lat, 0.0)
    for ephe_flag in (swe.FLG_SWIEPH, swe.FLG_MOSEPH):
        try:
            rc, tret = ephemeris_call(
                "rise_trans", jd_ut - 1.0, swe.SUN, flag, geopos, 0.0, 0.0, ephe_flag
            )
            if rc != 0:
                return None
            t1 = float(tret[0])
            if t1 > jd_ut:
                return None
            if t1 < jd_ut - 0.5:
                rc2, tret2 = ephemeris_call(
                    "rise_trans", t1 + 1e-4, swe.SUN, flag, geopos, 0.0, 0.0, ephe_flag
                )
                if rc2 == 0 and float(tret2[0]) <= jd_ut:
                    return float(tret2[0])
            return t1
        except EphemerisSourceError:
            raise
        except native_ephemeris_errors(swe):
            continue
    return None


def _sunrise_sunset_diurnal(
    instant: datetime, latitude: float, longitude: float
) -> tuple[bool, float, float] | None:
    utc = utc_calendar(instant)
    y, m, d = utc.date_parts
    hh, mm, ss, us = utc.time_parts
    jd_ut = swe.julday(y, m, d, hh + mm / 60.0 + (ss + us / 1_000_000.0) / 3600.0)
    rise_jd = _latest_solar_event(
        jd_ut, swe.CALC_RISE | swe.BIT_DISC_CENTER, longitude, latitude
    )
    set_jd = _latest_solar_event(
        jd_ut, swe.CALC_SET | swe.BIT_DISC_CENTER, longitude, latitude
    )
    if rise_jd is None or set_jd is None:
        return None
    return (rise_jd > set_jd), rise_jd, set_jd


def resolve_diurnal(
    hour_branch: str,
    explicit: bool | None = None,
    *,
    diurnal_mode: DiurnalMode = "clock",
    instant: datetime | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict[str, Any]:
    if hour_branch not in EARTHLY_BRANCHES:
        raise ValueError("昼夜选择需要有效占时时支")
    if explicit is not None and type(explicit) is not bool:
        raise ValueError("is_diurnal 必须是布尔选择或省略")
    if diurnal_mode not in ("clock", "sunrise_sunset"):
        raise ValueError("diurnal_mode 仅支持 clock 或 sunrise_sunset")

    astronomical = False
    rise_jd: float | None = None
    set_jd: float | None = None
    if explicit is not None:
        selected = explicit
        source = "explicit_parameter"
        basis = f"显式选择{'昼贵' if selected else '夜贵'}（is_diurnal={'true' if selected else 'false'}），占时时支{hour_branch}。"
    elif diurnal_mode == "sunrise_sunset":
        if instant is None or latitude is None or longitude is None:
            raise ValueError(
                "diurnal_mode='sunrise_sunset' 需要提供瞬间时刻、纬度(latitude)与经度(longitude)"
            )
        astro = _sunrise_sunset_diurnal(instant, float(latitude), float(longitude))
        if astro is not None:
            selected, rise_jd, set_jd = astro
            astronomical = True
            source = "sunrise_sunset_ephemeris"
            basis = f"按经纬度({longitude:.2f},{latitude:.2f})日出日落界定：{'昼贵' if selected else '夜贵'}。"
        else:
            selected = hour_branch in DAY_BRANCHES
            source = "hour_branch_convention_fallback"
            basis = f"极昼/极夜无法求得日出日落，回退按时支{hour_branch}取{'昼贵' if selected else '夜贵'}。"
    else:
        selected = hour_branch in DAY_BRANCHES
        source = "hour_branch_convention"
        basis = f"按占时时支{hour_branch}（卯至申昼、酉至寅夜）选择{'昼贵' if selected else '夜贵'}。"

    result: dict[str, Any] = {
        "method_id": "ren_diurnal_selection_provenance_v1",
        "diurnal_mode": diurnal_mode,
        "hour_branch": hour_branch,
        "explicit_choice": explicit,
        "is_diurnal": selected,
        "selection_source": source,
        "fixed_day_branches": list(DAY_BRANCHES),
        "astronomical_boundary_computed": astronomical,
        "basis": basis,
    }
    if astronomical:
        result["sunrise_jd_ut"] = rise_jd
        result["sunset_jd_ut"] = set_jd
    return result
