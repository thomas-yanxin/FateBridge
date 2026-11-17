"""Frozen WMM2025 reference; original directional facts remain unchanged."""

import math
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import JsonValue, TypeAdapter
from typing_extensions import TypedDict

from fatebridge.core.geomagnetic_field import (
    IMPLEMENTATION_ID,
    WmmCoefficient,
    wmm2025_field,
)

from .directions import bearing_context
from .geomagnetic_inputs import GeomagneticReference


class _GeomagneticRuleset(TypedDict):
    ruleset_id: str
    version: str
    method: str
    source_ids: list[str]
    scope: str
    conventions: list[str]


class _GeomagneticOrigin(TypedDict):
    coefficient_sha256: str


class _GeomagneticData(TypedDict):
    ruleset: _GeomagneticRuleset
    sources: dict[str, dict[str, JsonValue]]
    model_header: tuple[float, str, str]
    degree: Literal[12]
    coefficients: tuple[WmmCoefficient, ...]
    origin: _GeomagneticOrigin


class GeomagneticResult(TypedDict):
    calculation_status: Literal["complete"]
    ruleset: dict[str, JsonValue]
    input: dict[str, JsonValue]
    model: dict[str, JsonValue]
    field: dict[str, float]
    heading_context: dict[str, JsonValue]
    uncertainty: dict[str, JsonValue]
    conversion: dict[str, JsonValue]
    limitations: list[str]


@lru_cache(maxsize=1)
def _bundle() -> _GeomagneticData:
    path = Path(__file__).parents[2] / "data/fengshui/geomagnetic-wmm2025-v1.json"
    return TypeAdapter(_GeomagneticData).validate_json(path.read_bytes())


def geomagnetic_provenance() -> dict[str, JsonValue]:
    data = _bundle()
    return {
        "ruleset_id": data["ruleset"]["ruleset_id"],
        "version": data["ruleset"]["version"],
        "method": data["ruleset"]["method"],
        "source_ids": list(data["ruleset"]["source_ids"]),
        "scope": data["ruleset"]["scope"],
        "conventions": list(data["ruleset"]["conventions"]),
        "sources": [
            dict(source_id=k, **deepcopy(data["sources"][k]))
            for k in data["ruleset"]["source_ids"]
        ],
    }


def field_zone(horizontal_nt: float) -> str:
    return (
        "blackout"
        if horizontal_nt < 2000
        else "caution" if horizontal_nt < 6000 else "normal"
    )


def geomagnetic_reference(
    req: GeomagneticReference,
    bearing_degrees: Optional[float] = None,
    north_reference: Optional[Literal["magnetic", "true"]] = None,
) -> GeomagneticResult:
    data = _bundle()
    value = wmm2025_field(
        req.latitude,
        req.longitude,
        req.height_km_wgs84,
        req.year_value(),
        data["coefficients"],
    )
    field = {
        "declination_degrees_east": value.d,
        "inclination_degrees_down": value.i,
        "north_component_nt": value.x,
        "east_component_nt": value.y,
        "down_component_nt": value.z,
        "horizontal_intensity_nt": value.h,
        "total_intensity_nt": value.f,
    }
    zone = field_zone(value.h)
    pole = abs(req.latitude) == 90
    unavailable = (
        "geographic_pole"
        if pole
        else "magnetic_blackout" if zone == "blackout" else None
    )
    conversion: dict[str, JsonValue] = {
        "status": "unavailable" if unavailable else "not_requested",
        "unavailable_reason": unavailable,
        "candidate": None,
        "formula": "true=magnetic+east_positive_D (mod360)",
        "original_input_retained": True,
        "automatically_applied_to_house": False,
        "scope": "model_candidate_not_confirmed_site_heading",
    }
    if bearing_degrees is not None and unavailable is None:
        if north_reference not in ("magnetic", "true"):
            raise ValueError("换算方位必须明确原始north_reference")
        target = "magnetic" if north_reference == "true" else "true"
        angle = bearing_degrees + (-value.d if target == "magnetic" else value.d)
        conversion.update(
            status="model_candidate",
            input=bearing_context(bearing_degrees, north_reference),
            candidate=bearing_context(angle, target),
        )
    return {
        "calculation_status": "complete",
        # Full source records live once in the public envelope's rulesets.
        # Keep this branch's identity without duplicating large source blocks,
        # so a strict evidence projection fits the default response budget.
        "ruleset": {
            "ruleset_id": data["ruleset"]["ruleset_id"],
            "version": data["ruleset"]["version"],
            "method": data["ruleset"]["method"],
            "source_ids": list(data["ruleset"]["source_ids"]),
        },
        "input": {
            **req.model_dump(mode="json"),
            "effective_decimal_year": req.year_value(),
            "date_convention": (
                "explicit_decimal_year"
                if req.model_date is None
                else "UTC_start_of_reference_date"
            ),
            "coordinate_reference": "WGS84_geodetic_latitude_longitude_ellipsoid_height",
        },
        "model": {
            "name": data["model_header"][1],
            "epoch": data["model_header"][0],
            "coefficient_header_release": data["model_header"][2],
            "degree": data["degree"],
            "implementation": IMPLEMENTATION_ID,
            "implementation_identity": {
                "ellipsoid": "WGS84",
                "geodetic_conversion": "WGS84 exact inverse flattening",
                "semimajor_axis_metres": 6378137.0,
                "inverse_flattening": "298.257223563",
                "degree": 12,
                "arithmetic_decimal_digits": 50,
            },
            "coefficient_sha256": data["origin"]["coefficient_sha256"],
            "supported_decimal_year": {
                "from_inclusive": 2025.0,
                "until_exclusive": 2030.0,
            },
            "numerical_reference_precision": "WGS84 source arithmetic at 1e-7nT/1e-9deg on fixed reference cohorts; not physical accuracy",
        },
        "field": field,
        "heading_context": {
            "zone": zone,
            "geographic_pole": pole,
            "declination_usable_as_heading_reference": unavailable is None,
            "site_measurement_confirmed": False,
            "space_weather_checked": False,
        },
        "uncertainty": {
            "interpretation": "one_sigma_at_earth_surface_not_hard_bound",
            "declination_degrees": (
                math.hypot(0.26, 5417 / value.h) if value.h > 0 else None
            ),
            "x_nt": 137,
            "y_nt": 89,
            "z_nt": 141,
            "h_nt": 133,
            "f_nt": 138,
            "inclination_degrees": 0.20,
            "total_site_measurement_error_known": False,
            "converted_to_bearing_uncertainty_interval": False,
            "source_ids": ["GM2"],
        },
        "conversion": conversion,
        "limitations": [
            "模型估计地球主磁场；室内钢筋、电器和局部磁扰未实测，不能据此确认磁北朝向。",
            "一倍标准差是地表统计模型误差，不是保证误差范围、现场总误差或候选概率；不生成玄空角度区间。",
            "黑障区H<2000nT及地理极点不提供方位换算；2000≤H<6000nT为慎用区。",
            "未查询实时磁暴；模型不能替代现场方向复测，严重磁暴期间不应据此确认方向。",
            "原始方位和宅盘不变；换算值仅为待复测候选。本模型验证不构成风水现实预测验证。",
        ],
    }
