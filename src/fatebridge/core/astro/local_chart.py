"""Astronomical local chart builders and house/object adapters."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from fatebridge.core.astro.birth import AstroBirthInfo, build_astro_birth_info
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.astro.geometry import (
    _sign_name,
    angle_fraction,
    longitude_float,
)
from fatebridge.core.astro.house_geometry import HouseGeometry, HouseRecord
from fatebridge.utils.civil_clock import parse_local_datetime
from fatebridge.utils.civil_time import normalize_date_text, normalize_time_text
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE, resolve_coordinates

ZODIAC_SIGN_CN = {
    "Aries": "白羊座",
    "Taurus": "金牛座",
    "Gemini": "双子座",
    "Cancer": "巨蟹座",
    "Leo": "狮子座",
    "Virgo": "处女座",
    "Libra": "天秤座",
    "Scorpio": "天蝎座",
    "Sagittarius": "射手座",
    "Capricorn": "摩羯座",
    "Aquarius": "水瓶座",
    "Pisces": "双鱼座",
}

OUTER_PLANETS = {"Uranus", "Neptune", "Pluto"}


def build_local_astro_birth_info(
    *,
    date_text: str,
    time_text: str,
    timezone_name: str | None,
    lat: Any = None,
    lon: Any = None,
    gps_lat: float | None = None,
    gps_lon: float | None = None,
) -> tuple[AstroBirthInfo, float, float]:
    moment = parse_local_datetime(date_text, time_text, timezone_name)
    latitude, longitude = resolve_coordinates(
        lat=lat,
        lon=lon,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
    )
    birth_info = build_astro_birth_info(
        birth_year=moment.year,
        birth_month=moment.month,
        birth_day=moment.day,
        birth_hour=moment.hour,
        birth_minute=moment.minute,
        birth_second=moment.second,
        birth_microsecond=moment.microsecond,
        birth_timezone=timezone_name or DEFAULT_BIRTH_TIMEZONE,
        birth_longitude=longitude,
        birth_latitude=latitude,
    )
    return birth_info, latitude, longitude


def build_local_house_ring(
    house1_longitude: float,
    *,
    reverse: bool = False,
) -> list[HouseRecord]:
    return HouseGeometry.equal(house1_longitude, reverse=reverse).records(
        ZODIAC_SIGN_CN
    )


def _adapt_chart_houses(core_payload: dict[str, Any]) -> list[HouseRecord]:
    return [
        {
            "id": f"House{item['house']}",
            "lon": item["cusp_longitude"],
            "sign": item["sign"],
            "sign_zh": item["sign_zh"],
        }
        for item in core_payload["houses"]
    ]


def _build_houses(
    core_payload: dict[str, Any],
    *,
    house_start_mode: int = 1,
    shape_mode: int = 0,
    preserve_core_cusps: bool = False,
) -> tuple[list[HouseRecord], HouseGeometry | None]:
    base_houses = _adapt_chart_houses(core_payload)
    reverse = bool(shape_mode % 2)
    anchor: int | Fraction
    if house_start_mode == 2:
        ascendant = core_payload["angles"]["ascendant"]["longitude"]
        if ascendant is None:
            return [], None
        anchor = (angle_fraction(ascendant) // 30) * 30
    elif not base_houses:
        return [], None
    elif preserve_core_cusps:
        if reverse:
            base_houses = [base_houses[0], *reversed(base_houses[1:])]
        geometry = HouseGeometry(
            tuple(angle_fraction(house["lon"]) for house in base_houses),
            reverse=reverse,
            projected=(core_payload.get("chart_profile") or {}).get(
                "house_position_projection"
            )
            is not None,
        )
        houses = geometry.records(ZODIAC_SIGN_CN)
        for house, source in zip(houses, base_houses):
            house["sign_zh"] = source["sign_zh"]
        return houses, geometry
    else:
        anchor = angle_fraction(base_houses[0]["lon"])
    geometry = HouseGeometry.equal(anchor, reverse=reverse)
    return geometry.records(ZODIAC_SIGN_CN), geometry


def _build_point_object(
    *,
    point_id: str,
    longitude: float | Fraction,
    geometry: HouseGeometry | None,
    projected_phase: Fraction | None = None,
    house_longitude: Fraction | None = None,
) -> dict[str, Any]:
    phase = angle_fraction(longitude) % 360
    delivered = longitude_float(phase)
    sign = _sign_name(delivered)
    house_phase = phase if house_longitude is None else house_longitude
    payload = {
        "id": point_id,
        "house": (
            f"House{geometry.house(house_phase, projected_phase=projected_phase)}"
            if geometry is not None
            else None
        ),
        "sign": sign,
        "signlon": longitude_float(phase % 30),
        "lon": delivered,
    }
    if projected_phase is not None:
        payload["ecliptic_house_phase_degrees_ratio"] = str(projected_phase)
    return payload


def _adapt_chart_objects(
    core_payload: dict[str, Any],
    *,
    tradition: bool,
    geometry: HouseGeometry | None,
    preserve_core_houses: bool = False,
    fortune_house_longitude: Fraction | None = None,
) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    projected = geometry is not None and geometry.projected
    context_points = {
        item["id"]: item
        for item in (core_payload.get("context_geometry") or {}).get("objects", [])
    }
    for item in core_payload["planets"]:
        point_id = item["id"]
        if tradition and point_id in OUTER_PLANETS:
            continue
        source_longitude = float(item["longitude"])
        phase_text = (
            context_points[point_id]["ecliptic_house_phase_degrees_ratio"]
            if projected
            else None
        )
        projected_phase = Fraction(phase_text) if phase_text is not None else None
        # An unchanged native layout retains the core classification. A changed
        # layout uses original coordinates or the core's working projection.
        house_id: str | None
        if geometry is None:
            house_id = None
        elif preserve_core_houses:
            house_id = f"House{item['house']}"
        else:
            house_id = f"House{geometry.house(source_longitude, projected_phase=projected_phase)}"
        payload: dict[str, Any] = {
            "id": point_id,
            "house": house_id,
            "sign": item.get("sign"),
            "signlon": float(item["degree_in_sign"]),
            "lon": source_longitude,
        }
        if projected_phase is not None:
            payload["ecliptic_house_phase_degrees_ratio"] = str(projected_phase)
        objects.append(payload)

    north_node = next((item for item in objects if item["id"] == "North Node"), None)
    if north_node is not None:
        source_node = next(
            item["longitude"]
            for item in core_payload["planets"]
            if item["id"] == "North Node"
        )
        south_node_longitude = (angle_fraction(source_node) + 180) % 360
        phase_text = (
            context_points["South Node"]["ecliptic_house_phase_degrees_ratio"]
            if projected
            else None
        )
        objects.append(
            _build_point_object(
                point_id="South Node",
                longitude=south_node_longitude,
                geometry=geometry,
                projected_phase=(
                    Fraction(phase_text) if phase_text is not None else None
                ),
            )
        )

    # Reuse the canonical lot, computed from the true ASC and solar horizon.
    # First cusp != ASC for whole-sign/equal-MC/Vehlow; a Sun in H1 can be day.
    fortune = ((core_payload.get("classical") or {}).get("lots") or {}).get("fortune")
    if fortune is not None:
        phase_text = (
            context_points["Pars Fortuna"]["ecliptic_house_phase_degrees_ratio"]
            if projected
            else None
        )
        objects.append(
            _build_point_object(
                point_id="Pars Fortuna",
                longitude=float(fortune["longitude"]),
                house_longitude=None if projected else fortune_house_longitude,
                geometry=geometry,
                projected_phase=(
                    Fraction(phase_text) if phase_text is not None else None
                ),
            )
        )

    return objects


def build_local_chart_response(
    *,
    date_text: str,
    time_text: str,
    timezone_name: str | None,
    lat: Any = None,
    lon: Any = None,
    gps_lat: float | None = None,
    gps_lon: float | None = None,
    tradition: bool = False,
    chart_variant: str = "chart",
    house_start_mode: int = 1,
    shape_mode: int = 0,
    hsys: int | None = None,
    zodiacal: int | None = None,
    extra_params: dict[str, Any] | None = None,
    allow_extended_hsys: bool = False,
    include_calculation_metadata: bool = False,
    preserve_context_geometry: bool = False,
    context_fortune_method: str = "sect_reversing",
) -> dict[str, Any]:
    birth_info, latitude, longitude = build_local_astro_birth_info(
        date_text=date_text,
        time_text=time_text,
        timezone_name=timezone_name,
        lat=lat,
        lon=lon,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
    )
    lot_longitudes: dict[str, Fraction] = {}
    resolved_hsys = None
    if chart_variant == "chart" and (hsys is not None or zodiacal is not None):
        resolved_hsys = 8 if hsys is None else int(hsys)
        resolved_zodiacal = 0 if zodiacal is None else int(zodiacal)
        if not allow_extended_hsys and resolved_hsys not in {0, 8}:
            raise ValueError("本地盘当前仅支持 hsys=0(整宫制) 或 hsys=8(等宫制)。")
        core_payload = build_core_chart_payload(
            birth_info,
            chart_variant,
            hsys=resolved_hsys,
            zodiacal=resolved_zodiacal,
            include_context_geometry=preserve_context_geometry
            or chart_variant == "chart",
            include_physical_source=preserve_context_geometry,
            context_fortune_method=context_fortune_method,
            lot_longitudes=lot_longitudes,
            include_planetary_hours=False,
        )
    else:
        is_guolao_variant = chart_variant == "guolao_chart"
        core_payload = build_core_chart_payload(
            birth_info,
            chart_variant,
            include_context_geometry=preserve_context_geometry
            or chart_variant == "chart",
            include_physical_source=preserve_context_geometry,
            context_fortune_method=context_fortune_method,
            lot_longitudes=lot_longitudes,
            include_planetary_hours=False,
            include_classical=not is_guolao_variant,
            include_fixed_stars=not is_guolao_variant,
            include_aspects=not is_guolao_variant,
        )
    houses, house_geometry = _build_houses(
        core_payload,
        house_start_mode=house_start_mode,
        shape_mode=shape_mode,
        preserve_core_cusps=allow_extended_hsys,
    )
    objects = _adapt_chart_objects(
        core_payload,
        tradition=tradition,
        geometry=house_geometry,
        fortune_house_longitude=lot_longitudes.get("fortune"),
        preserve_core_houses=allow_extended_hsys
        and house_start_mode != 2
        and not shape_mode % 2,
    )
    geometry = (
        core_payload.get("context_geometry") if preserve_context_geometry else None
    )
    if geometry is not None:
        if house_start_mode == 2 or shape_mode % 2:
            raise ValueError(
                "Unrounded context geometry requires the original house layout"
            )
        houses = geometry["houses"]
        objects = [
            item
            for item in geometry["objects"]
            if not tradition or item["id"] not in OUTER_PLANETS
        ]
    params = {
        "date": normalize_date_text(date_text),
        "time": normalize_time_text(time_text),
        "zone": timezone_name or DEFAULT_BIRTH_TIMEZONE,
        "lat": lat,
        "lon": lon,
        "gpsLat": gps_lat,
        "gpsLon": gps_lon,
        "birthLatitude": round(latitude, 4),
        "birthLongitude": round(longitude, 4),
        "tradition": tradition,
        "chartVariant": chart_variant,
        "houseSystemResolved": core_payload["chart_profile"]["house_system"],
        "zodiacMode": core_payload["chart_profile"].get("zodiac"),
        "enginePrecision": core_payload["chart_profile"].get("engine_precision"),
        "engineBackend": core_payload["chart_profile"].get("engine_backend"),
    }
    if house_geometry is not None:
        params.update(
            {
                "houseStartModeApplied": house_start_mode,
                "houseOrientation": (
                    (
                        "reverse_native_projection"
                        if house_geometry.reverse
                        else "native_nonprograde_cusps"
                    )
                    if house_geometry.projected
                    else ("reverse" if house_geometry.reverse else "forward")
                ),
                "coordinatePolicy": "unrounded_source_and_exact_house_intermediates",
                "houseAssignmentBasis": (
                    "original_working_projection_phase"
                    if house_geometry.projected
                    else "original_working_cusp_intervals"
                ),
                "houseGeometryModel": (
                    "native_projection_phase"
                    if house_geometry.projected
                    else (
                        "native_cusp_partition"
                        if allow_extended_hsys and house_start_mode != 2
                        else (
                            "whole_sign_from_original_ascendant"
                            if house_start_mode == 2
                            else "equal_from_original_first_cusp"
                        )
                    )
                ),
            }
        )
    else:
        params.update(
            {
                "houseStartModeApplied": None,
                "houseOrientation": None,
                "coordinatePolicy": "unrounded_source_and_exact_house_intermediates",
                "houseAssignmentBasis": "not_assigned_source_house_geometry_unavailable",
                "houseGeometryModel": "unavailable_selected_reference",
                "houseGeometryStatus": "unavailable_selected_reference",
                "houseGeometryNote": "所选参考宫位几何不可用；宫头与落宫留空，可用星体数据已保留。",
            }
        )
    if resolved_hsys is not None:
        params["hsys"] = resolved_hsys
        params["zodiacal"] = (core_payload.get("chart_profile") or {}).get("zodiacal")
        params["zodiacLabelZh"] = (core_payload.get("chart_profile") or {}).get(
            "zodiac_label_zh"
        )
    ayanamsha = (core_payload.get("chart_profile") or {}).get("ayanamsha")
    if ayanamsha:
        params["ayanamsha"] = ayanamsha
    if extra_params:
        params.update(extra_params)
    angle_definition = core_payload["chart_profile"].get("angle_definition")
    if angle_definition is not None:
        params["angleDefinition"] = angle_definition
    if house_geometry is not None and house_geometry.projected:
        projection = core_payload["context_geometry"]["house_position_projection"]
        params["housePositionMethod"] = projection["method"]
        params["housePositionProjection"] = projection
    if include_calculation_metadata:
        params["chart_profile"] = dict(core_payload.get("chart_profile") or {})
        params["calculationTimeLocal"] = birth_info.local_datetime.isoformat()
        params["calculationTimeUtc"] = birth_info.utc_isoformat
        if house_geometry is not None:
            params["houseAssignmentBasis"] = "core_geometry_before_display_rounding"
        params["auxiliaryPointSources"] = {
            "Pars Fortuna": "core.classical.lots.fortune"
        }
        if geometry is not None:
            params["birthLatitude"] = latitude
            params["birthLongitude"] = longitude
            params["coordinatePolicy"] = geometry["coordinate_policy"]
            params["intervalConvention"] = geometry["interval_convention"]
            params["auxiliaryPointSources"] = geometry["auxiliary_point_sources"]
            params["fortuneDefinition"] = geometry["fortune_definition"]
            if "motion_policy" in geometry:
                params["motionPolicy"] = geometry["motion_policy"]
            if "ephemeris_reference_points" in geometry:
                params["ephemerisReferencePoints"] = geometry[
                    "ephemeris_reference_points"
                ]
            params["housePositionMethod"] = "ecliptic_longitude_cusp_intervals"
            if "house_position_projection" in geometry:
                projection = geometry["house_position_projection"]
                params["housePositionMethod"] = projection["method"]
                params["housePositionProjection"] = projection
                params["houseOrientation"] = "native_nonprograde_cusps"
            params["lunarNodeModel"] = "mean_node_and_its_opposite"
    response: dict[str, object] = {
        "params": params,
        "chart": {
            "ok": True,
            "houses": houses,
            "objects": objects,
            "angles": (
                geometry["angles"]
                if geometry is not None
                else {
                    "ascendant": core_payload["angles"]["ascendant"]["longitude"],
                    "midheaven": core_payload["angles"]["midheaven"]["longitude"],
                }
            ),
        },
    }
    return response
