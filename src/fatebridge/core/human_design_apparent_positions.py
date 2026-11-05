"""Capture existing native position calls without evaluating another ephemeris.

The private identity map binds nominal sides to the actual batch used to build
them. Serialized observations remain receipt evidence, not native attestation.
"""

from __future__ import annotations

import json
import math
from contextvars import ContextVar
from functools import wraps
from typing import Any, Callable

from fatebridge.core.human_design_interval_geometry import METHOD as ARITHMETIC_METHOD
from fatebridge.core.human_design_interval_geometry import ProjectionRoundingUnresolved
from fatebridge.core.human_design_solar_projection import (
    ASTRONOMICAL_UNIT_M,
    AU_SOURCE,
    DEFLECTION_SOURCE,
    NOMINAL_SOLAR_RADIUS_M,
    RADIUS_SOURCE,
    nominal_solar_projection,
)

METHOD = "human_design_apparent_position_context_v1"
PHYSICAL_BODIES = (
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
)
SCOPE = "仅同次positions_at_tt物理天体完整或中断批次已返回的原生坐标、旗标及其名义投影；覆盖本命、区间样本、根端点和整盘对照实际批次，中断前缀不补齐。仅太阳求根、仅交点对照或周期搜索的单体调用不在此计数。观察次数不是独立样本，不认证连续区间、原生执行真实性、物理精度、真实遮掩或可见性。"


def ruleset() -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": METHOD,
        "version": "1.1.0",
        "author": "FateBridge implementation of Swiss documentation and IAU nominal units",
        "source_kind": "astronomical_software_convention_and_nominal_conversion_constants",
        "sources": {
            "swiss_deflection": DEFLECTION_SOURCE,
            "nominal_radius": RADIUS_SOURCE,
            "au": AU_SOURCE,
        },
        "scope": SCOPE,
    }
    result["sources"].update(
        {
            "trigonometric_series": "https://dlmf.nist.gov/4.19",
            "inverse_trigonometric_series": "https://dlmf.nist.gov/4.24",
            "range_reduction": "https://dlmf.nist.gov/4.45",
        }
    )
    result["arithmetic_method"] = ARITHMETIC_METHOD
    return result


def geometry(bodies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sun = bodies[0]["native_coordinates"][:3]
    rows = []
    for row in bodies[1:]:
        try:
            projection = nominal_solar_projection(sun, row["native_coordinates"][:3])
            rows.append(
                {
                    "body": row["body"],
                    "status": "supplied_coordinates_evaluated",
                    **projection,
                }
            )
        except ProjectionRoundingUnresolved:
            rows.append(
                {
                    "body": row["body"],
                    "status": "arithmetic_rounding_unresolved",
                    "arithmetic_method": ARITHMETIC_METHOD,
                    "arithmetic_precision_budget_bits": 8192,
                    "physical_accuracy_certified": False,
                }
            )
        except ValueError:
            # Supplementary latitude/distance must never be guessed when only
            # the original longitude/speed calculation could be completed.
            rows.append(
                {
                    "body": row["body"],
                    "status": "supplementary_coordinates_unavailable",
                    "physical_accuracy_certified": False,
                }
            )
    return rows


def build_context(
    batches: list[dict[str, Any]],
    nominal: dict[str, str],
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "method_id": METHOD,
        "coordinate_order": [
            "longitude_degrees",
            "latitude_degrees",
            "distance_au",
            "longitude_speed_degrees_per_day",
        ],
        "nominal_solar_radius_m": NOMINAL_SOLAR_RADIUS_M,
        "astronomical_unit_m": ASTRONOMICAL_UNIT_M,
        "radius_is_nominal_conversion_constant": True,
        "solar_deflection_policy": "Swiss_default_apparent_with_documented_transparent_solar_mass_continuation",
        "policy_basis": "validated_return_flags_exclude_NOGDEFL_TRUEPOS_NOABERR_J2000_NONUT_and_topocentric_bits",
        "nominal_side_batch_ids": dict(nominal),
        "batches": [{**b, "solar_projection": geometry(b["bodies"])} for b in batches],
        "unique_batch_count": len(batches),
        "observed_batch_count": sum(b["observed_count"] for b in batches),
        "observed_physical_position_count": sum(
            len(b["bodies"]) * b["observed_count"] for b in batches
        ),
        "complete_physical_batch_count": sum(len(b["bodies"]) == 10 for b in batches),
        "partial_physical_batch_count": sum(len(b["bodies"]) < 10 for b in batches),
        "excluded_factors": [
            "Earth_derived_opposition",
            "NorthNode_mathematical_point",
            "SouthNode_derived_opposition",
        ],
        "native_execution_authenticated": False,
        "physical_accuracy_certified": False,
        "physical_occultation_certified": False,
        "visibility_certified": False,
        "original_human_design_software_convention_certified": False,
        "ruleset": ruleset(),
        "scope": SCOPE,
    }
    context["arithmetic_method"] = ARITHMETIC_METHOD
    context["arithmetic_policy"] = (
        "Outward-rounded integer intervals with analytic series-tail bounds; adapt until both endpoints round to one binary64 value and prove the unchanged1e-12radian classification. Positive zero is canonical; no platform transcendental fallback."
    )
    from fatebridge.core.human_design_provenance import position_flag_model

    for batch in batches:
        for body in batch["bodies"]:
            position_flag_model(body["return_flags"])
    context["coordinate_context"] = {
        "schema_version": "1.0.0",
        "observer_origin": "earth_geocenter",
        "position_kind": "apparent",
        "spatial_frame": "tropical_true_ecliptic_and_equinox_of_date",
        "distance_origin": "earth_geocenter",
        "distance_unit": "astronomical_unit",
        "angular_separation_vertex": "earth_geocenter",
        "angular_separation_rays": ["Sun", "target"],
        "heliocentric_coordinates": False,
        "basis": "Same native batches; declared SPEED plus one backend only; HELCTR/BARYCTR/TOPOCTR and other coordinate-changing flags excluded.",
    }
    return context


def context_reading(context: dict[str, Any]) -> dict[str, Any]:
    lookup = {b["id"]: b for b in context["batches"]}
    descriptions = []
    for side in ("personality", "design"):
        batch = lookup[context["nominal_side_batch_ids"][side]]
        inside = [
            r["body"]
            for r in batch["solar_projection"]
            if r.get("inside_nominal_solar_disk_projection") is True
        ]
        unknown = [
            r["body"]
            for r in batch["solar_projection"]
            if r.get("inside_nominal_solar_disk_projection") is None
        ]
        descriptions.append(
            f"{side}名义盘中投影落在名义太阳圆盘内的天体为{'、'.join(inside) or '无'}，数值边界或补充坐标未定项为{'、'.join(unknown) or '无'}"
        )
        if "arithmetic_method" in context:
            unresolved = [
                r["body"]
                for r in batch["solar_projection"]
                if r["status"] == "arithmetic_rounding_unresolved"
            ]
            descriptions[
                -1
            ] += f"，未在精度预算内确定舍入的项为{'、'.join(unresolved) or '无'}"
    reading: dict[str, Any] = {
        "text": "；".join(descriptions)
        + "。此处使用同批返回的黄经、黄纬和距离，并另列目标是否比太阳更远，前景与背景不能混同。IAU名义太阳半径是单位换算常数，投影不证明真实遮掩或可见性。当前旗标采用Swiss默认视位置；其文档说明太阳内部的光偏折使用透明太阳质量分布延拓，太阳附近的不同算法可能改变Color/Tone/Base。这里保留实际所选算法的激活值，不据投影改选较容易通过的后端，也未证明原始人类图软件采用此约定。",
        "time_scope": "本段只解释两侧名义盘；其余实际全体位置批次见apparent_position_context.batches。未评估周期搜索的单体调用或连续区间。",
        "basis": [
            {"path": "apparent_position_context." + key, "value": context[key]}
            for key in (
                "nominal_side_batch_ids",
                "solar_deflection_policy",
                "nominal_solar_radius_m",
                "radius_is_nominal_conversion_constant",
                "physical_occultation_certified",
                "original_human_design_software_convention_certified",
            )
        ]
        + [
            {
                "path": f"apparent_position_context.batches.{i}.{key}",
                "value": batch[key],
            }
            for i, batch in enumerate(context["batches"])
            if batch["id"] in context["nominal_side_batch_ids"].values()
            for key in ("jd_tt", "bodies", "solar_projection")
        ],
        "source_urls": list(context["ruleset"]["sources"].values()),
    }
    if "arithmetic_method" in context:
        reading[
            "text"
        ] += "本次数值投影采用向外舍入的整数区间：只在区间两端舍入到同一binary64值且证明原1e-12弧度分类后返回，未调用平台三角函数；这保证所给坐标的运算重放，不提高原生星历的物理准确度。"
        reading["basis"].extend(
            {"path": "apparent_position_context." + key, "value": context[key]}
            for key in ("arithmetic_method", "arithmetic_policy")
        )
    if "coordinate_context" in context:
        reading["text"] = coordinate_frame_reading() + reading["text"]
        reading["basis"].append(
            {
                "path": "apparent_position_context.coordinate_context",
                "value": context["coordinate_context"],
            }
        )
    return reading


def coordinate_frame_reading() -> str:
    return "同批视位置以地球地心为观测原点，采用当日真黄道／真春分点；距离从地心起算，单位AU。太阳角距是地心处太阳视线与目标视线的夹角，不是以太阳为原点的日心角距，也不是天体相对太阳的距离。"


def add_apparent_evidence(value: dict[str, Any], context: dict[str, Any]) -> None:
    value["apparent_position_context"] = context
    value["rulesets"].append(context["ruleset"])
    value["rule_trace"].append(
        {
            "rule_id": METHOD,
            "ruleset_id": METHOD,
            "inputs": {
                "native_batches_path": "apparent_position_context.batches",
                "nominal_side_batch_ids": context["nominal_side_batch_ids"],
            },
            "result": {
                "unique_batch_count": context["unique_batch_count"],
                "observed_physical_position_count": context[
                    "observed_physical_position_count"
                ],
                "physical_accuracy_certified": False,
            },
            "source_url": DEFLECTION_SOURCE,
        }
    )
    value["interpretation"]["apparent_position_context"] = context_reading(context)
    if "coordinate_context" in context:
        value["interpretation"]["coordinate_frame_meaning"] = coordinate_frame_reading()
    value["interpretation"]["basis"].append("apparent_position_context")


class PositionTrace:
    def __init__(self) -> None:
        self.batches: list[dict[str, Any]] = []
        self.indices: dict[str, int] = {}
        self.positions: dict[int, tuple[Any, str]] = {}
        self.charts: dict[int, tuple[Any, dict[str, str]]] = {}

    def record(
        self,
        positions: dict[str, Any],
        tt: float,
        mode: str,
        backend: str,
        role: str,
        bodies: list[dict[str, Any]],
    ) -> None:
        batch = {
            "jd_tt": tt,
            "node_mode": mode,
            "requested_backend": backend,
            "source_role": role,
            "bodies": bodies,
        }
        key = json.dumps(batch, sort_keys=True, allow_nan=False)
        index = self.indices.get(key)
        if index is None:
            index = len(self.batches)
            self.indices[key] = index
            self.batches.append({"id": f"batch_{index}", **batch, "observed_count": 0})
        self.batches[index]["observed_count"] += 1
        self.positions[id(positions)] = positions, self.batches[index]["id"]


_ACTIVE: ContextVar[PositionTrace | None] = ContextVar(
    "human_design_apparent_position_trace", default=None
)


def record_position_batch(
    positions: dict[str, Any],
    tt: float,
    mode: str,
    backend: str,
    role: str,
    bodies: list[dict[str, Any]],
) -> None:
    trace = _ACTIVE.get()
    if trace is not None:
        trace.record(positions, tt, mode, backend, role, bodies)


def observed_coordinates(coords: Any) -> list[float | str]:
    # Nonfinite supplementary coordinates have explicit JSON-safe labels.
    # They are unavailable for geometry, never silently replaced with zero.
    return [float(x) if math.isfinite(float(x)) else str(float(x)) for x in coords[:4]]


def position_batch_id(positions: dict[str, Any]) -> str | None:
    trace = _ACTIVE.get()
    return trace.positions[id(positions)][1] if trace is not None else None


def register_chart(activations: dict[str, Any], refs: dict[str, str]) -> None:
    trace = _ACTIVE.get()
    if trace is not None:
        trace.charts[id(activations)] = activations, refs


def guard_apparent_positions(
    function: Callable[..., dict[str, Any]],
) -> Callable[..., dict[str, Any]]:
    @wraps(function)
    def guarded(*args: Any, **kwargs: Any) -> dict[str, Any]:
        trace = PositionTrace()
        token = _ACTIVE.set(trace)
        try:
            result = function(*args, **kwargs)
            refs = trace.charts[id(result["activations"])][1]
            add_apparent_evidence(result, build_context(trace.batches, refs))
            return result
        finally:
            _ACTIVE.reset(token)

    return guarded
