"""Frozen WMM2025 reference; original directional facts remain unchanged."""

import hashlib
import json
import math
from copy import deepcopy
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path
from typing import Any, Dict, Literal, Optional, cast

from .directions import bearing_context
from .geomagnetic_inputs import GeomagneticReference


@lru_cache(maxsize=1)
def _bundle() -> Dict[str, Any]:
    return cast(
        Dict[str, Any],
        json.loads(
            (
                Path(__file__).parents[2] / "data/fengshui/geomagnetic-wmm2025-v1.json"
            ).read_text(encoding="utf-8")
        ),
    )


def geomagnetic_provenance() -> Dict[str, Any]:
    data = _bundle()
    return {
        **deepcopy(data["ruleset"]),
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


def _implementation() -> tuple[Any, Dict[str, Any]]:
    """Check the pinned wheel's source identity, not loaded-memory integrity.

    Import only on this optional branch. A missing or incompatible deployment
    is a dependency fault (ImportError), never a rejection of the user's input.
    Do not cache this check: each returned identity describes the files read
    for this calculation, while the deployment receipt is process-scoped.
    """
    import pygeomag  # type: ignore[import-untyped]
    from pygeomag import geomag  # type: ignore[import-untyped]

    reference = _bundle()["implementation_reference"]
    installed = version(reference["distribution"])
    if (
        installed != reference["version"]
        or getattr(pygeomag, "__version__", None) != installed
    ):
        raise ImportError("WMM2025 requires the validated pygeomag distribution")
    observed = {}
    try:
        for name, module in (
            ("pygeomag/__init__.py", pygeomag),
            ("pygeomag/geomag.py", geomag),
        ):
            observed[name] = hashlib.sha256(
                Path(module.__file__).read_bytes()
            ).hexdigest()
    except (OSError, TypeError) as exc:
        raise ImportError("Cannot verify the validated pygeomag source files") from exc
    if observed != reference["source_files"] or pygeomag.GeoMag is not geomag.GeoMag:
        raise ImportError("WMM2025 pygeomag source differs from the validated wheel")
    return geomag.GeoMag, {
        "distribution_version": installed,
        "source_sha256": observed["pygeomag/geomag.py"],
        "validated_wheel_match": True,
        "scope": "source_files_not_loaded_memory",
    }


def geomagnetic_reference(
    req: GeomagneticReference,
    bearing_degrees: Optional[float] = None,
    north_reference: Optional[Literal["magnetic", "true"]] = None,
) -> Dict[str, Any]:
    data = _bundle()
    GeoMag, implementation = _implementation()
    # GeoMag maintains internal work arrays. A fresh instance per request avoids
    # sharing mutable calculation state between concurrent REST/MCP calls.
    model = GeoMag(
        coefficients_data=(tuple(data["model_header"]), data["coefficients"])
    )
    value = model.calculate(
        glat=req.latitude,
        glon=req.longitude,
        alt=req.height_km_wgs84,
        time=req.year_value(),
        allow_date_outside_lifespan=False,
        raise_in_warning_zone=False,
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
    conversion: Dict[str, Any] = {
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
            key: deepcopy(data["ruleset"][key])
            for key in ("ruleset_id", "version", "method", "source_ids")
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
            "implementation": "pygeomag==" + implementation["distribution_version"],
            "implementation_identity": {
                key: value
                for key, value in implementation.items()
                if key != "distribution_version"
            },
            "coefficient_sha256": data["origin"]["coefficient_sha256"],
            "supported_decimal_year": {
                "from_inclusive": 2025.0,
                "until_exclusive": 2030.0,
            },
            "numerical_reference_precision": "12 vectors at 0.1nT/0.01deg; not six-decimal nT",
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
