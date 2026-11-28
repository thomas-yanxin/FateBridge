"""Feng Shui services: clean multi-layer structural calculation and composition."""

from __future__ import annotations

from itertools import combinations
from typing import Any

from fatebridge.core.fengshui.assess import analyze_layout
from fatebridge.core.fengshui.bazhai import bazhai, minggua
from fatebridge.core.fengshui.directions import bearing_context, raw_rule_data
from fatebridge.core.fengshui.geomagnetic import geomagnetic_reference
from fatebridge.core.fengshui.jinsuo import jinsuo
from fatebridge.core.fengshui.models import (
    AnnualRequest,
    AssessRequest,
    BazhaiRequest,
    DirectionsRequest,
    JinsuoRequest,
    MingguaRequest,
    MonthlyRequest,
    Placement,
    XuankongRequest,
)
from fatebridge.core.fengshui.xuankong import (
    XuankongNatalResult,
    analyze_natal_interpretation,
    xuankong_natal,
)
from fatebridge.core.fengshui.zibai import (
    annual_stars,
    build_palace_overlay,
    monthly_stars,
)


def compose_fengshui_result(
    layers: dict[str, Any],
    conflicts: list[dict[str, Any]],
    layout: dict[str, Any] | None = None,
    palace_overlay: dict[str, Any] | None = None,
) -> dict[str, Any]:
    missing = [m for layer in layers.values() for m in layer["missing_inputs"]]
    status = "partial" if missing else "complete"
    summary = "；".join(f"{name}: {layer['status']}" for name, layer in layers.items())
    natal_selected = "xuankong_natal" in layers

    coverage: dict[str, Any] = {
        "implemented_layers": list(layers),
        "missing_inputs": missing,
        "unavailable_layers": [
            n
            for n in raw_rule_data("unavailable_layers")
            if n not in {"xuankong_natal", "monthly_stars"}
        ],
        "not_requested_layers": [
            n
            for n in (
                "bazhai",
                "jinsuo",
                "annual_stars",
                "monthly_stars",
                "xuankong_natal",
            )
            if n not in layers
        ],
    }

    result: dict[str, Any] = {
        "analysis_type": "家居风水分层计算" if natal_selected else "家居风水基础计算",
        "engine": (
            "fatebridge-fengshui-natal-v1"
            if natal_selected
            else "fatebridge-fengshui-foundation-v1"
        ),
        "status": status,
        "layers": layers,
        "coverage": coverage,
        "conflicts": conflicts,
        "summary": summary,
    }
    if palace_overlay is not None:
        result["palace_overlay"] = palace_overlay
    if layout is not None:
        result["layout_analysis"] = layout
        coverage["requested_analysis_status"] = (
            "partial"
            if status == "partial" or layout["status"] == "partial"
            else "complete"
        )
        result["summary"] = (
            f"{summary}；layout: {layout['status']}"
            if layers
            else f"layout: {layout['status']}"
        )

    interpretation = layers.get("xuankong_natal", {}).get("interpretation")
    if interpretation is not None:
        coverage["natal_interpretation_status"] = interpretation["status"]
        coverage["requested_analysis_status"] = (
            "partial"
            if interpretation["status"] == "partial"
            or coverage.get("requested_analysis_status", status) == "partial"
            else "complete"
        )

    city_gate = layers.get("xuankong_natal", {}).get("city_gate_analysis")
    if city_gate is not None:
        result["summary"] += f"；city_gate: {city_gate['status']}"
        coverage["city_gate_status"] = city_gate["status"]
        coverage["requested_analysis_status"] = (
            "partial"
            if city_gate["status"] == "partial"
            or coverage.get("requested_analysis_status", status) == "partial"
            else "complete"
        )

    return result


def calculate_directions(request: DirectionsRequest) -> dict[str, Any]:
    bearing = None
    if request.bearing_degrees is not None:
        assert request.north_reference is not None
        bearing = bearing_context(request.bearing_degrees, request.north_reference)
    result: dict[str, Any] = {
        "status": "complete",
        "directions": raw_rule_data("directions"),
        "missing_inputs": [],
        "bearing": bearing,
    }
    if request.geomagnetic_reference is not None:
        result["geomagnetic_reference"] = geomagnetic_reference(
            request.geomagnetic_reference,
            request.bearing_degrees,
            request.north_reference,
        )
    return compose_fengshui_result({"directions": result}, [])


def calculate_minggua(request: MingguaRequest) -> dict[str, Any]:
    return compose_fengshui_result({"minggua": minggua(request)}, [])


def calculate_bazhai(request: BazhaiRequest) -> dict[str, Any]:
    layer = bazhai(request)
    return compose_fengshui_result({"bazhai": layer}, _differences({"bazhai": layer}))


def calculate_jinsuo(request: JinsuoRequest) -> dict[str, Any]:
    return compose_fengshui_result({"jinsuo": jinsuo(request)}, [])


def calculate_annual_stars(request: AnnualRequest) -> dict[str, Any]:
    return compose_fengshui_result({"annual_stars": annual_stars(request)}, [])


def calculate_monthly_stars(request: MonthlyRequest) -> dict[str, Any]:
    return compose_fengshui_result({"monthly_stars": monthly_stars(request)}, [])


def _natal_layer(
    request: XuankongRequest, placements: list[Placement] | None = None
) -> XuankongNatalResult:
    layer = xuankong_natal(request)
    if request.interpretation is not None:
        layer["interpretation"] = analyze_natal_interpretation(
            request.interpretation, layer, placements or []
        )
    return layer


def calculate_xuankong_natal(request: XuankongRequest) -> dict[str, Any]:
    return compose_fengshui_result({"xuankong_natal": _natal_layer(request)}, [])


def _differences(layers: dict[str, Any]) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    bazhai_layer = layers.get("bazhai", {})
    charts = []
    if bazhai_layer.get("house"):
        house = bazhai_layer["house"]
        charts.append((house["object_id"], "house", house["sectors"]))
    for occupant in bazhai_layer.get("occupants", []):
        if occupant["status"] == "complete":
            charts.append(
                (
                    occupant["subject_id"],
                    "occupant",
                    occupant["candidates"][0]["sectors"],
                )
            )
    directions = raw_rule_data("directions")
    for a, b in combinations(charts, 2):
        for direction in directions:
            first, second = a[2][direction]["star"], b[2][direction]["star"]
            if first["polarity"] != second["polarity"]:
                differences.append(
                    {
                        "kind": (
                            "personal_direction_difference"
                            if a[1] == b[1] == "occupant"
                            else "house_person_scope_difference"
                        ),
                        "direction": direction,
                        "entries": [
                            {
                                "subject_id": c[0],
                                "star": c[2][direction]["star"]["name"],
                                "polarity": c[2][direction]["star"]["polarity"],
                            }
                            for c in (a, b)
                        ],
                    }
                )
    return differences


def calculate_fengshui_assessment(request: AssessRequest) -> dict[str, Any]:
    layers: dict[str, Any] = {}
    if "bazhai" in request.selected_methods:
        layers["bazhai"] = bazhai(request)
    if "jinsuo" in request.selected_methods:
        layers["jinsuo"] = jinsuo(
            JinsuoRequest(
                features=request.features, ruleset_id=request.jinsuo_ruleset_id
            )
        )
    if "annual_stars" in request.selected_methods:
        layers["annual_stars"] = annual_stars(
            AnnualRequest(
                effective_year=request.effective_year,
                query_at=(
                    None if request.effective_year is not None else request.query_at
                ),
                timezone_name=request.timezone_name,
                ruleset_id=request.annual_ruleset_id,
            )
        )
    if "xuankong_natal" in request.selected_methods:
        if request.xuankong is None:
            natal = XuankongRequest(house=request.house)
        elif request.xuankong.house is None and request.house is not None:
            natal = XuankongRequest(
                house=request.house,
                period=request.xuankong.period,
                current_period_number=request.xuankong.current_period_number,
                ruleset_id=request.xuankong.ruleset_id,
                interpretation=request.xuankong.interpretation,
                city_gate=request.xuankong.city_gate,
            )
        else:
            natal = request.xuankong
        layers["xuankong_natal"] = _natal_layer(natal, request.placements)
    if "monthly_stars" in request.selected_methods:
        monthly = request.monthly or MonthlyRequest(
            query_at=request.query_at, timezone_name=request.timezone_name
        )
        layers["monthly_stars"] = monthly_stars(monthly)

    layers = {name: layers[name] for name in request.selected_methods}
    layout = analyze_layout(request, layers) if request.analyze_layout else None
    palace_overlay = build_palace_overlay(layers)
    return compose_fengshui_result(
        layers, _differences(layers), layout=layout, palace_overlay=palace_overlay
    )
