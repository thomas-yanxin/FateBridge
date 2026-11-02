"""Shared house layouts and cusp geometry for natal and relationship charts."""

from __future__ import annotations

from typing import Any, Dict, List

from fatebridge.core.astro import runtime
from fatebridge.core.astro.angle_definitions import (
    native_ecliptic_horizon_angle_definition,
)
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.ephemeris import _swisseph_angles
from fatebridge.core.astro.geometry import (
    _angles,
    _ayanamsha,
    normalize_angle,
)
from fatebridge.core.astro.house_axes import canonical_house_geometry
from fatebridge.core.astro.parts import _build_houses
from fatebridge.core.astro.relationship_geometry import unique_midpoint
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.astro.zodiac import native_lahiri_houses
from fatebridge.utils.errors import EphemerisSourceError


def _house_cusp_values_from_payload(chart_payload: Dict[str, Any]) -> List[float]:
    return [
        float(item["cusp_longitude"])
        for item in chart_payload.get("houses", [])
        if "cusp_longitude" in item
    ]


def _midpoint_house_cusps(
    left_cusps: List[float],
    right_cusps: List[float],
) -> List[float]:
    if len(left_cusps) != 12 or len(right_cusps) != 12:
        return []
    return [
        unique_midpoint(left_cusps[index], right_cusps[index]) for index in range(12)
    ]


def _relative_house_layout(
    birth_info: AstroBirthInfo,
    *,
    house_system_info: Dict[str, Any],
    zodiacal_info: Dict[str, Any],
) -> Dict[str, Any]:
    times = ephemeris_time(birth_info.physical_datetime)
    julian_day = times.jd_ut1
    if zodiacal_info["sidereal"] and runtime.swe is not None:
        code = house_system_info.get("swisseph_code")
        if code is None:
            code = {"whole_sign": b"W", "equal": b"E"}[house_system_info["key"]]
        try:
            return native_lahiri_houses(
                julian_day_ut1=times.jd_ut1,
                julian_day_tt=times.jd_tt,
                latitude=birth_info.latitude,
                longitude=birth_info.longitude,
                house_code=code,
            )
        except EphemerisSourceError:
            raise
        except Exception as error:
            runtime._log_swe_runtime_failure("houses_ex(sidereal)", error)
            raise ValueError(
                f"原生Lahiri {house_system_info['key']}宫头计算失败，不能冒用热带宫头"
            ) from error
    ayanamsha = _ayanamsha(julian_day) if zodiacal_info["sidereal"] else None

    if runtime.swe is None or house_system_info["key"] in {"whole_sign", "equal"}:
        native_angles = _swisseph_angles(
            julian_day,
            birth_info.longitude,
            birth_info.latitude,
        )
        angle_state = native_angles or _angles(
            julian_day, birth_info.longitude, birth_info.latitude
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
            "angle_method": "swisseph" if native_angles else "approximate_angles",
            **({"house_axis_convention": convention} if convention else {}),
            **(
                {"angle_definition": angle_state["angle_definition"]}
                if "angle_definition" in angle_state
                else {}
            ),
        }

    try:
        with runtime.preserve_ephemeris_path():
            cusps, ascmc = runtime.ephemeris_call(
                "houses_ex",
                julian_day,
                birth_info.latitude,
                birth_info.longitude,
                house_system_info["swisseph_code"],
            )
            cusps, ascmc, house_axis_convention = canonical_house_geometry(
                julian_day_ut1=julian_day,
                latitude=birth_info.latitude,
                longitude=birth_info.longitude,
                house_code=house_system_info["swisseph_code"],
                native_angles=ascmc,
                native_cusps=cusps,
            )
            definition = native_ecliptic_horizon_angle_definition(
                julian_day_ut1=julian_day,
                latitude=birth_info.latitude,
                armc=float(ascmc[2]),
            )
    except EphemerisSourceError:
        raise
    except Exception as error:
        # Quadrant house systems have no honest offline equivalent: degrading to
        # _build_houses would anchor the cusps on the ascendant while keeping the
        # requested label, faking an approximation. Fail loud instead — mirrors
        # the offline-mode raise in _resolve_offline_house_system.
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
