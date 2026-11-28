"""WMM2025 (2025-2030) and IGRF-14 (1900-2030) geomagnetic reference evaluation."""

from __future__ import annotations

import math
from datetime import date, datetime
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import JsonValue, TypeAdapter
from typing_extensions import TypedDict

from fatebridge.core.fengshui.directions import bearing_context
from fatebridge.core.fengshui.models import GeomagneticReference
from fatebridge.core.geomagnetic_field import (
    IGRF14_IMPLEMENTATION_ID,
    IMPLEMENTATION_ID,
    IgrfCoefficient,
    WmmCoefficient,
    igrf14_field,
    wmm2025_field,
)


class _WmmData(TypedDict):
    ruleset: dict[str, JsonValue]
    model_header: list[JsonValue]
    degree: int
    coefficients: list[WmmCoefficient]


class _IgrfData(TypedDict):
    ruleset: dict[str, JsonValue]
    model_header: list[JsonValue]
    degree: int
    coefficients: list[IgrfCoefficient]


@lru_cache(maxsize=1)
def _wmm_bundle() -> tuple[
    list[JsonValue],
    tuple[WmmCoefficient, ...],
]:
    path = Path(__file__).parents[2] / "data/fengshui/geomagnetic-wmm2025-v1.json"
    data = TypeAdapter(_WmmData).validate_json(path.read_bytes())
    return data["model_header"], tuple(data["coefficients"])


@lru_cache(maxsize=1)
def _igrf_bundle() -> tuple[
    list[JsonValue],
    tuple[IgrfCoefficient, ...],
]:
    path = Path(__file__).parents[2] / "data/fengshui/geomagnetic-igrf14-v1.json"
    data = TypeAdapter(_IgrfData).validate_json(path.read_bytes())
    return data["model_header"], tuple(data["coefficients"])


def _select_model(model_id: str, year: float) -> Literal["wmm2025_v1", "igrf14_v1"]:
    if model_id == "wmm2025_v1":
        return "wmm2025_v1"
    if model_id == "igrf14_v1":
        return "igrf14_v1"
    return "wmm2025_v1" if 2025.0 <= year < 2030.0 else "igrf14_v1"


def field_zone(horizontal_nt: float) -> str:
    return (
        "blackout"
        if horizontal_nt < 2000
        else "caution" if horizontal_nt < 6000 else "normal"
    )


def geomagnetic_reference(
    req: GeomagneticReference,
    bearing_degrees: float | None = None,
    north_reference: Literal["magnetic", "true"] | None = None,
) -> dict[str, object]:
    year = req.year_value()
    chosen = _select_model(req.model_id, year)
    if chosen == "wmm2025_v1":
        header, coeffs = _wmm_bundle()
        value = wmm2025_field(
            req.latitude, req.longitude, req.height_km_wgs84, year, coeffs
        )
        model_info: dict[str, JsonValue] = {
            "model_id": "wmm2025_v1",
            "name": header[1],
            "epoch": header[0],
            "degree": 12,
            "implementation": IMPLEMENTATION_ID,
            "arithmetic": "IEEE-754 binary64",
            "supported_decimal_year": {
                "from_inclusive": 2025.0,
                "until_exclusive": 2030.0,
            },
        }
    else:
        header, coeffs_igrf = _igrf_bundle()
        value = igrf14_field(
            req.latitude, req.longitude, req.height_km_wgs84, year, coeffs_igrf
        )
        model_info = {
            "model_id": "igrf14_v1",
            "name": header[2],
            "release": header[3],
            "degree": 13,
            "implementation": IGRF14_IMPLEMENTATION_ID,
            "arithmetic": "IEEE-754 binary64",
            "supported_decimal_year": {
                "from_inclusive": 1900.0,
                "until_inclusive": 2030.0,
            },
        }

    field: dict[str, JsonValue] = {
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
    conversion: dict[str, object] = {
        "status": "unavailable" if unavailable else "not_requested",
        "unavailable_reason": unavailable,
        "candidate": None,
        "formula": "true=magnetic+east_positive_D (mod360)",
        "original_input_retained": True,
        "automatically_applied_to_house": False,
    }
    if bearing_degrees is not None and unavailable is None:
        if north_reference not in ("magnetic", "true"):
            raise ValueError("换算方位必须明确原始north_reference")
        target = "magnetic" if north_reference == "true" else "true"
        angle = (
            Fraction(bearing_degrees)
            + (-Fraction(value.d) if target == "magnetic" else Fraction(value.d))
        ) % 360
        conversion.update(
            status="model_candidate",
            input=bearing_context(bearing_degrees, north_reference),
            candidate=bearing_context(angle, target),
            angle_exact={
                "numerator": str(angle.numerator),
                "denominator": str(angle.denominator),
            },
        )
    return {
        "calculation_status": "complete",
        "selected_model_id": chosen,
        "input": {
            **req.model_dump(mode="json"),
            "effective_decimal_year": year,
        },
        "model": model_info,
        "field": field,
        "heading_context": {
            "zone": zone,
            "geographic_pole": pole,
            "declination_usable_as_heading_reference": unavailable is None,
        },
        "uncertainty": {
            "interpretation": "one_sigma_at_earth_surface_not_hard_bound",
            "declination_degrees": (
                math.hypot(0.26, 5417 / value.h) if value.h > 0 else None
            ),
        },
        "conversion": conversion,
    }
