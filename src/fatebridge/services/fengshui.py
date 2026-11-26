"""Composition only: preserve method, person, observation and time scopes."""

from itertools import combinations
from typing import Any

from pydantic import JsonValue, TypeAdapter

from fatebridge.core.fengshui.annual import annual_stars
from fatebridge.core.fengshui.bazhai import bazhai, minggua
from fatebridge.core.fengshui.directions import bearing_context, provenance, rule_data
from fatebridge.core.fengshui.geomagnetic import geomagnetic_reference
from fatebridge.core.fengshui.host_guest import validate as validate_host_guest
from fatebridge.core.fengshui.jinsuo import jinsuo
from fatebridge.core.fengshui.layout import analyze_layout
from fatebridge.core.fengshui.method_details import method_details
from fatebridge.core.fengshui.method_policy import method_policy
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
from fatebridge.core.fengshui.monthly import monthly_stars
from fatebridge.core.fengshui.mutual_geometry import validate_author_geometries
from fatebridge.core.fengshui.natal_interpretation import analyze_natal_interpretation
from fatebridge.core.fengshui.planning import evaluate_alternatives
from fatebridge.core.fengshui.spatial_delivery import merge_measured_layout
from fatebridge.core.fengshui.spatial_layout import prepare_spatial_request
from fatebridge.core.fengshui.surface import summarize_analysis_progress
from fatebridge.core.fengshui.xuankong import natal_provenance, xuankong_natal
from fatebridge.services.fengshui_composition import compose_fengshui_result


def _layer(result: dict[str, Any], ruleset_id: str) -> dict[str, Any]:
    return {**result, "ruleset": provenance(ruleset_id)}


def calculate_directions(request: DirectionsRequest) -> dict[str, Any]:
    bearing = None
    if request.bearing_degrees is not None:
        assert request.north_reference is not None
        bearing = bearing_context(request.bearing_degrees, request.north_reference)
    result = {
        "status": "complete",
        "directions": rule_data("directions"),
        "missing_inputs": [],
        "bearing": bearing,
        "division_scope": "confirmed_angular_sectors_no_automatic_geometry",
    }
    if request.geomagnetic_reference is not None:
        result["geomagnetic_reference"] = geomagnetic_reference(
            request.geomagnetic_reference,
            request.bearing_degrees,
            request.north_reference,
        )
    return compose_fengshui_result(
        {"directions": _layer(result, request.ruleset_id)}, []
    )


def calculate_minggua(request: MingguaRequest) -> dict[str, Any]:
    return compose_fengshui_result(
        {"minggua": _layer(minggua(request), request.ruleset_id)}, []
    )


def calculate_bazhai(request: BazhaiRequest) -> dict[str, Any]:
    layer = _layer(bazhai(request), request.ruleset_id)
    return compose_fengshui_result({"bazhai": layer}, _differences({"bazhai": layer}))


def calculate_jinsuo(request: JinsuoRequest) -> dict[str, Any]:
    return compose_fengshui_result(
        {"jinsuo": _layer(jinsuo(request), request.ruleset_id)}, []
    )


def calculate_annual_stars(request: AnnualRequest) -> dict[str, Any]:
    return compose_fengshui_result(
        {"annual_stars": _layer(annual_stars(request), request.ruleset_id)}, []
    )


def calculate_monthly_stars(request: MonthlyRequest) -> dict[str, Any]:
    return compose_fengshui_result({"monthly_stars": monthly_stars(request)}, [])


def _natal_layer(
    request: XuankongRequest, placements: list[Placement] | None = None
) -> dict[str, Any]:
    layer = {**xuankong_natal(request), "ruleset": natal_provenance()}
    if request.interpretation is not None:
        layer["interpretation"] = analyze_natal_interpretation(
            request.interpretation, layer, placements or []
        )
        validate_author_geometries(
            layer["interpretation"],
            layer,
            current=request.interpretation.current_period_number,
            expected_selected=request.interpretation.timeliness_ruleset_id is not None,
        )
        validate_host_guest(
            layer["interpretation"],
            layer,
            expected_selected=request.interpretation.host_guest_ruleset_id is not None,
        )
    return layer


def calculate_xuankong_natal(request: XuankongRequest) -> dict[str, Any]:
    return compose_fengshui_result(
        {"xuankong_natal": _natal_layer(request)},
        [],
        include_calculation_reading=bool(
            request.interpretation
            and request.interpretation.include_calculation_reading
        ),
    )


def _differences(layers: dict[str, Any]) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    bazhai_layer = layers.get("bazhai", {})
    charts = []
    if bazhai_layer.get("house"):
        house = bazhai_layer["house"]
        charts.append((house["object_id"], "house", house["sectors"]))
    for occupant in bazhai_layer.get("occupants", []):
        # Unknown birth convention produces alternatives, never a confirmed
        # conflict between imaginary residents.
        if occupant["status"] == "complete":
            charts.append(
                (
                    occupant["subject_id"],
                    "occupant",
                    occupant["candidates"][0]["sectors"],
                )
            )
    for a, b in combinations(charts, 2):
        for direction in rule_data("directions"):
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
                                "subject_kind": c[1],
                                "star": c[2][direction]["star"],
                            }
                            for c in (a, b)
                        ],
                        "resolution": "keep_each_subject_result_no_household_override",
                        "rule_id": "bazhai_sitting_v1.dayounian_xor",
                        "source_ids": ["S3"],
                    }
                )
    if (
        all(name in layers for name in ("bazhai", "jinsuo", "annual_stars"))
        and bazhai_layer.get("house")
        and layers["annual_stars"].get("palaces")
    ):
        for direction in rule_data("directions"):
            differences.append(
                {
                    "kind": "distinct_scope_overlay",
                    "direction": direction,
                    "bazhai_house_star": bazhai_layer["house"]["sectors"][direction][
                        "star"
                    ],
                    "jinsuo_preference": layers["jinsuo"]["preferences"][direction][
                        "preferred_classification"
                    ],
                    "annual_star_number": layers["annual_stars"]["palaces"][direction][
                        "annual_star_number"
                    ],
                    "resolution": "different_conditions_and_time_scopes_no_combined_score",
                    "rule_ids": [
                        "bazhai_sitting_v1.dayounian_xor",
                        "jinsuo_basic_fixed_v1.palace_preference",
                        "annual_zibai_lichun_v1.forward_flight",
                    ],
                    "source_ids": ["S3", "S4", "S5"],
                }
            )
    return differences


def calculate_fengshui_assessment(request: AssessRequest) -> dict[str, Any]:
    original = request
    geometry = None
    if request.workstation_layout is not None:
        request, geometry = prepare_spatial_request(
            request, request.workstation_layout.scene
        )
    layers = {}
    if "bazhai" in request.selected_methods:
        layers["bazhai"] = _layer(bazhai(request), request.ruleset_id)
    if "jinsuo" in request.selected_methods:
        layers["jinsuo"] = _layer(
            jinsuo(
                JinsuoRequest(
                    features=request.features, ruleset_id=request.jinsuo_ruleset_id
                )
            ),
            request.jinsuo_ruleset_id,
        )
    if "annual_stars" in request.selected_methods:
        layers["annual_stars"] = _layer(
            annual_stars(
                AnnualRequest(
                    effective_year=request.effective_year,
                    query_at=request.query_at,
                    timezone_name=request.timezone_name,
                    ruleset_id=request.annual_ruleset_id,
                )
            ),
            request.annual_ruleset_id,
        )
    if "xuankong_natal" in request.selected_methods:
        if request.xuankong is None:
            natal = XuankongRequest(house=request.house)
        elif request.xuankong.house is None and request.house is not None:
            # note (house): Inheriting a house applies Xuankong's magnetic-bearing constraints.
            natal = XuankongRequest(
                house=request.house,
                period=request.xuankong.period,
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
    layout = (
        analyze_layout(request, layers)
        if request.analyze_layout
        # A scene also labels method-reference queries. It does not by itself
        # request a site assessment or create missing physical observations.
        or (
            request.scene
            and (request.selected_methods or request.placements or request.features)
        )
        or request.layout_constraints
        or request.layout_alternatives
        or request.form_observations
        or request.environmental_context is not None
        or request.surface_layouts
        or request.element_adjustments
        or request.annual_remedy_ruleset_id is not None
        or request.workstation_layout is not None
        else None
    )
    if layout is not None and geometry is not None:
        layout = merge_measured_layout(
            original,
            request,
            geometry,
            TypeAdapter(dict[str, JsonValue]).validate_python(layers),
            TypeAdapter(dict[str, JsonValue]).validate_python(layout),
        )
    if layout is not None and request.layout_alternatives:
        alternatives = evaluate_alternatives(request, layers)
        layout["alternatives_analysis"] = alternatives
        registered = {r["ruleset_id"] for r in layout["supplemental_rulesets"]}
        for proposal in alternatives["findings"]:
            for ruleset in proposal["supplemental_rulesets"]:
                if ruleset["ruleset_id"] not in registered:
                    layout["supplemental_rulesets"].append(ruleset)
                    registered.add(ruleset["ruleset_id"])
        previous = layout["analysis_progress"]
        states = {
            "ready": "ready",
            "conditional": "conditional_option",
            "candidate": "candidate_only",
            "blocked": "blocked",
        }
        existing_actions = [
            {"status": states[key], "optional": False}
            for key, count in previous["action_counts"].items()
            for _ in range(count)
        ]
        progress = summarize_analysis_progress(
            layout["missing_inputs"],
            previous["rule_coverage_counts"],
            [*existing_actions, *alternatives["findings"]],
            [
                *previous["pending_confirmations"],
                *(
                    p
                    for f in alternatives["findings"]
                    for p in f["pending_confirmations"]
                ),
            ],
            count_unit=previous["rule_coverage_count_unit"],
            limited=previous["rule_coverage_status"] == "limited",
        )
        # Optional proposals cannot reopen or close the review of current facts.
        for key in (
            "calculation_status",
            "rule_coverage_status",
            "assessment_complete",
            "interpretation_status",
        ):
            progress[key] = previous[key]
        progress["optional_action_count"] = previous["optional_action_count"] + len(
            alternatives["findings"]
        )
        layout["analysis_progress"] = progress
    scene_scope = None
    if request.scene is not None:
        scene_scope = {
            "scene": request.scene,
            "selected_methods": request.selected_methods,
            "selection_policy": "explicit_methods_override_input_driven_default",
            "scope": "supplied_objects_and_selected_rules_not_whole_property_certification",
            "indoor_forms": (
                "selected_modern_authored_rules"
                if request.form_observations
                else "not_provided"
            ),
            "geometry": (
                "measured_planar_scene_with_explicit_chart_binding"
                if request.workstation_layout
                else "user_confirmed_house_sectors_no_automatic_floorplan_geometry"
            ),
            "natal_interpretation": (
                "conditioned_element_pairs_current_star_external_forms_and_bed_door_roles"
                if layers.get("xuankong_natal", {}).get("interpretation") is not None
                else (
                    "three_star_roles_without_complete_combination_or_external_form_judgment"
                    if "xuankong_natal" in layers
                    else "not_selected"
                )
            ),
            "unsupported_methods": [
                "yangzhai_sanyao_structural_rules",
                "sanhe_water_formulas",
                "xuankong_dagua",
                "complete_classical_landforms",
            ],
        }
    policy_selected = (
        request.scene is not None or request.environmental_context is not None
    )
    return compose_fengshui_result(
        layers,
        _differences(layers),
        layout,
        scene_scope,
        (
            method_policy(
                request,
                explicit_methods=request.methods is not None,
                layer_results=layers,
                candidate_results=(layout or {})
                .get("alternatives_analysis", {})
                .get("findings", []),
            )
            if policy_selected
            else None
        ),
        method_details(request.selected_methods) if policy_selected else None,
        include_calculation_reading=bool(
            request.xuankong
            and request.xuankong.interpretation
            and request.xuankong.interpretation.include_calculation_reading
        ),
    )
