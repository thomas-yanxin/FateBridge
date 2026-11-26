"""Shared house layouts and cusp geometry for natal and relationship charts."""

from __future__ import annotations

import math
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.angle_definitions import (
    native_ecliptic_horizon_angle_definition,
)
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.ephemeris import _swisseph_angles, fast_swe_call
from fatebridge.core.astro.geometry import (
    _angles,
    _ayanamsha,
    normalize_angle,
)
from fatebridge.core.astro.house_axes import canonical_house_geometry
from fatebridge.core.astro.parts import _build_houses
from fatebridge.core.astro.zodiac import native_lahiri_houses
from fatebridge.utils.errors import EphemerisSourceError


def _unique_midpoint(a: float, b: float) -> float:
    diff = ((b - a) + 180.0) % 360.0 - 180.0
    return normalize_angle(a + diff / 2.0)


def _house_cusp_values_from_payload(chart_payload: dict[str, Any]) -> list[float]:
    return [
        float(item["cusp_longitude"])
        for item in chart_payload.get("houses", [])
        if "cusp_longitude" in item
    ]


def _midpoint_house_cusps(
    left_cusps: list[float],
    right_cusps: list[float],
) -> list[float]:
    if len(left_cusps) != 12 or len(right_cusps) != 12:
        return []
    return [
        _unique_midpoint(left_cusps[index], right_cusps[index]) for index in range(12)
    ]


def _porphyry_cusps(ascendant: float, midheaven: float) -> list[float]:
    """Trisect each quadrant between Ascendant, IC, Descendant, MC."""
    ic = normalize_angle(midheaven + 180.0)
    dsc = normalize_angle(ascendant + 180.0)
    mc = normalize_angle(midheaven)
    asc = normalize_angle(ascendant)
    q1 = (ic - asc) % 360.0
    q2 = (dsc - ic) % 360.0
    q3 = (mc - dsc) % 360.0
    q4 = (asc - mc) % 360.0
    return [
        asc,
        normalize_angle(asc + q1 / 3.0),
        normalize_angle(asc + 2.0 * q1 / 3.0),
        ic,
        normalize_angle(ic + q2 / 3.0),
        normalize_angle(ic + 2.0 * q2 / 3.0),
        dsc,
        normalize_angle(dsc + q3 / 3.0),
        normalize_angle(dsc + 2.0 * q3 / 3.0),
        mc,
        normalize_angle(mc + q4 / 3.0),
        normalize_angle(mc + 2.0 * q4 / 3.0),
    ]


def _relative_house_layout(
    birth_info: AstroBirthInfo,
    *,
    house_system_info: dict[str, Any],
    zodiacal_info: dict[str, Any],
    high_latitude_fallback: str = "error",
) -> dict[str, Any]:
    times = birth_info.time_scales
    julian_day = times.ut1
    if zodiacal_info["sidereal"] and runtime.swe is not None:
        code = house_system_info.get("swisseph_code")
        if code is None:
            code = {"whole_sign": b"W", "equal": b"E"}[house_system_info["key"]]
        try:
            return native_lahiri_houses(
                julian_day_ut1=times.ut1,
                julian_day_tt=times.tt,
                latitude=birth_info.latitude,
                longitude=birth_info.longitude,
                house_code=code,
            )
        except EphemerisSourceError:
            raise
        except Exception as error:
            if high_latitude_fallback in {"porphyry", "whole_sign"}:
                fallback_code = b"W" if high_latitude_fallback == "whole_sign" else b"O"
                try:
                    fallback_layout = native_lahiri_houses(
                        julian_day_ut1=times.ut1,
                        julian_day_tt=times.tt,
                        latitude=birth_info.latitude,
                        longitude=birth_info.longitude,
                        house_code=fallback_code,
                    )
                    fallback_layout["fallback_house_system"] = high_latitude_fallback
                    return fallback_layout
                except Exception:
                    pass
            runtime._log_swe_runtime_failure("houses_ex(sidereal)", error)
            raise ValueError(
                f"原生Lahiri {house_system_info['key']}宫头计算失败，不能冒用热带宫头"
            ) from error
    ayanamsha = (
        _ayanamsha(times.jd_ut1, julian_day_tt=times.tt)
        if zodiacal_info["sidereal"]
        else None
    )

    if runtime.swe is None or house_system_info["key"] in {"whole_sign", "equal"}:
        native_angles = _swisseph_angles(
            julian_day,
            birth_info.longitude,
            birth_info.latitude,
            julian_day_tt=times.tt,
        )
        angle_state = native_angles or _angles(
            julian_day,
            birth_info.longitude,
            birth_info.latitude,
            julian_day_tt=times.tt,
        )
        ascendant = angle_state["ascendant"]
        midheaven = angle_state["midheaven"]
        if ayanamsha is not None:
            ascendant = normalize_angle(ascendant - ayanamsha)
            midheaven = normalize_angle(midheaven - ayanamsha)
        house_cusps = [
            item["cusp_longitude"]
            for item in _build_houses(
                ascendant,
                house_system_info["key"],
                midheaven=midheaven,
                round_coordinates=False,
            )
        ]
        convention = angle_state.get("house_axis_convention")
        if convention is not None:
            convention["house_code"] = (
                "W" if house_system_info["key"] == "whole_sign" else "E"
            )
            precision = convention.get("eastern_direction_precision")
            if precision is not None:
                precision["house_cusp_scope"] = (
                    "consumer_whole_sign_or_equal_rebuilt_from_checked_ASC"
                )
                precision["delivered_cusps"] = house_cusps
                precision["coordinate_frame"] = "tropical"
                if precision["ascendant_action"] != "native_coordinate_retained":
                    precision["corrected_cusps"] = list(range(1, 13))
                    convention["native_cusps_and_projection_retained"] = False
                    convention["note_zh"] += " 宫头已从复核后的ASC重新建立。"
        return {
            "ascendant": ascendant,
            "midheaven": midheaven,
            "house_cusps": house_cusps,
            "ayanamsha": ayanamsha,
            "ayanamsha_includes_nutation": ayanamsha is not None,
            "angle_method": "swisseph" if native_angles else "approximate_angles",
            **({"house_axis_convention": convention} if convention else {}),
            **(
                {"angle_definition": angle_state["angle_definition"]}
                if "angle_definition" in angle_state
                else {}
            ),
        }

    fallback_used: str | None = None
    try:
        with runtime.preserve_ephemeris_path():
            cusps, ascmc = runtime.ephemeris_call(
                "houses_ex",
                julian_day,
                birth_info.latitude,
                birth_info.longitude,
                house_system_info["swisseph_code"],
                _julian_day_tt=times.tt,
            )
            if (
                high_latitude_fallback in {"porphyry", "whole_sign"}
                and abs(birth_info.latitude) > 66.5
                and house_system_info["key"]
                in {"placidus", "koch", "alcabitus", "topocentric", "polich_page"}
            ):
                raise RuntimeError("high_latitude_quadrant_degeneracy")
            cusps, ascmc, house_axis_convention = canonical_house_geometry(
                julian_day_ut1=julian_day,
                julian_day_tt=times.tt,
                latitude=birth_info.latitude,
                longitude=birth_info.longitude,
                house_code=house_system_info["swisseph_code"],
                native_angles=ascmc,
                native_cusps=cusps,
            )
            definition = native_ecliptic_horizon_angle_definition(
                julian_day_ut1=julian_day,
                julian_day_tt=times.tt,
                latitude=birth_info.latitude,
                longitude=birth_info.longitude,
                armc=float(ascmc[2]),
            )
    except EphemerisSourceError:
        raise
    except Exception as error:
        if high_latitude_fallback in {"porphyry", "whole_sign"}:
            native_angles = _swisseph_angles(
                julian_day,
                birth_info.longitude,
                birth_info.latitude,
                julian_day_tt=times.tt,
            ) or _angles(
                julian_day,
                birth_info.longitude,
                birth_info.latitude,
                julian_day_tt=times.tt,
            )
            ascendant = float(native_angles["ascendant"])
            midheaven = float(native_angles["midheaven"])
            if ayanamsha is not None:
                ascendant = normalize_angle(ascendant - ayanamsha)
                midheaven = normalize_angle(midheaven - ayanamsha)
            if high_latitude_fallback == "porphyry" and abs(birth_info.latitude) < 90.0:
                house_cusps = _porphyry_cusps(ascendant, midheaven)
                fallback_used = "porphyry"
            else:
                house_cusps = [
                    item["cusp_longitude"]
                    for item in _build_houses(
                        ascendant, "whole_sign", round_coordinates=False
                    )
                ]
                fallback_used = "whole_sign"
            return {
                "ascendant": ascendant,
                "midheaven": midheaven,
                "house_cusps": house_cusps,
                "ayanamsha": ayanamsha,
                "angle_method": "swisseph",
                "fallback_house_system": fallback_used,
                **(
                    {"angle_definition": native_angles["angle_definition"]}
                    if "angle_definition" in native_angles
                    else {}
                ),
            }
        runtime._log_swe_runtime_failure("houses_ex", error)
        raise ValueError(
            f"当前输入无法计算 {house_system_info['key']} 的原生宫头"
            f"（{type(error).__name__}）；象限宫制无离线等价，已停止计算。"
        ) from error
    ascendant = float(ascmc[0])
    midheaven = float(ascmc[1])
    house_cusps = [float(item) for item in cusps[:12]]

    if ayanamsha is not None:
        ascendant = normalize_angle(ascendant - ayanamsha)
        midheaven = normalize_angle(midheaven - ayanamsha)
        house_cusps = [normalize_angle(item - ayanamsha) for item in house_cusps]

    return {
        "ascendant": ascendant,
        "midheaven": midheaven,
        "house_cusps": house_cusps,
        "ayanamsha": ayanamsha,
        "angle_method": "swisseph",
        **(
            {"house_axis_convention": house_axis_convention}
            if house_axis_convention
            else {}
        ),
        **({"angle_definition": definition} if definition is not None else {}),
    }
