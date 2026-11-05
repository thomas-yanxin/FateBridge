"""Composition only: preserve method, person, observation and time scopes."""

from itertools import combinations
from typing import Any, Dict, List

from pydantic import JsonValue, TypeAdapter

from fatebridge.core.fengshui.annual import annual_stars
from fatebridge.core.fengshui.bazhai import bazhai, minggua
from fatebridge.core.fengshui.directions import bearing_context, provenance, rule_data
from fatebridge.core.fengshui.geomagnetic import (
    geomagnetic_provenance,
    geomagnetic_reference,
)
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
from fatebridge.core.fengshui.monthly import monthly_provenance, monthly_stars
from fatebridge.core.fengshui.mutual_geometry import validate_author_geometries
from fatebridge.core.fengshui.natal_interpretation import (
    analyze_natal_interpretation,
    interpretation_provenance,
)
from fatebridge.core.fengshui.planning import evaluate_alternatives
from fatebridge.core.fengshui.snapshot import sections
from fatebridge.core.fengshui.spatial_delivery import merge_measured_layout
from fatebridge.core.fengshui.spatial_layout import prepare_spatial_request
from fatebridge.core.fengshui.surface import summarize_analysis_progress
from fatebridge.core.fengshui.xuankong import natal_provenance, xuankong_natal
from fatebridge.services.snapshot_builders import (
    build_snapshot_export,
    render_snapshot_lines,
)


def _layer(result: Dict[str, Any], ruleset_id: str) -> Dict[str, Any]:
    return {**result, "ruleset": provenance(ruleset_id)}


def _compose(
    layers: Dict[str, Any],
    conflicts: List[Dict[str, Any]],
    layout: Dict[str, Any] | None = None,
    scene_scope: Dict[str, Any] | None = None,
    method_selection: Dict[str, Any] | None = None,
    method_reference: Dict[str, Any] | None = None,
    include_calculation_reading: bool = False,
) -> Dict[str, Any]:
    missing = [m for layer in layers.values() for m in layer["missing_inputs"]]
    status = "partial" if missing else "complete"
    summary = "；".join(f"{name}: {layer['status']}" for name, layer in layers.items())
    natal_selected = "xuankong_natal" in layers
    result: Dict[str, Any] = {
        "analysis_type": "家居风水分层计算" if natal_selected else "家居风水基础计算",
        "engine": (
            "fatebridge-fengshui-natal-v1"
            if natal_selected
            else "fatebridge-fengshui-foundation-v1"
        ),
        "status": status,
        "layers": layers,
        "rulesets": [layer["ruleset"] for layer in layers.values()],
        "coverage": {
            "implemented_layers": list(layers),
            "missing_inputs": missing,
            "unavailable_layers": [
                n
                for n in rule_data("unavailable_layers")
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
        },
        "conflicts": conflicts,
        "rule_trace": [
            {
                "method": name,
                "ruleset_id": layer["ruleset"]["ruleset_id"],
                "version": layer["ruleset"]["version"],
                "source_ids": layer["ruleset"]["source_ids"],
                "scope": layer["ruleset"]["scope"],
            }
            for name, layer in layers.items()
        ],
        "summary": summary,
    }
    if layout is not None:
        result["layout_analysis"] = layout
        measured = layout.get("workstation_layout_analysis")
        if measured is not None:
            result["coverage"]["unavailable_layers"] = [
                name
                for name in result["coverage"]["unavailable_layers"]
                if name != "automatic_floorplan_geometry"
            ] + ["automatic_image_floorplan_extraction"]
            result["coverage"]["measured_workstation"] = {
                "status": measured["status"],
                "scope": measured["scope"],
                "candidate_only": measured["geometry"]["candidate_only"],
                "search_enumeration_complete": measured.get("search", {}).get(
                    "enumeration_complete"
                ),
            }
        # Top-level status retains the raw-chart contract. Requested layout
        # readiness is separate and must survive a coverage-only projection.
        result["coverage"].update(
            analysis_progress=layout["analysis_progress"],
            layout_status=layout["status"],
            layout_missing_inputs=layout["missing_inputs"],
            requested_analysis_status=(
                "partial"
                if status == "partial" or layout["status"] == "partial"
                else "complete"
            ),
        )
        result["summary"] = (
            f"{summary}；layout: {layout['status']}"
            if layers
            else f"layout: {layout['status']}"
        )
        extra_rules = layout["supplemental_rulesets"]
        if extra_rules:
            result["rulesets"].extend(extra_rules)
            result["coverage"]["supplemental_rulesets"] = [
                r["ruleset_id"] for r in extra_rules
            ]
            result["rule_trace"].extend(
                {
                    "method": r["method"],
                    "ruleset_id": r["ruleset_id"],
                    "version": r["version"],
                    "source_ids": r["source_ids"],
                    "scope": r["scope"],
                }
                for r in extra_rules
            )
        if not layers:
            result["status"] = layout["status"]
            result["summary"] = f"layout: {layout['status']}"
            result["coverage"]["missing_inputs"] = layout["missing_inputs"]
        for branch in (
            "interior_analysis",
            "material_analysis",
            "workstation_analysis",
            "workstation_layout_analysis",
        ):
            result["rule_trace"].extend(layout.get(branch, {}).get("rule_trace", []))
    source_comparison = layers.get("xuankong_natal", {}).get("source_comparison")
    if source_comparison is not None:
        record = source_comparison["ruleset"]
        result["rulesets"].append(record)
        result["coverage"]["natal_source_comparison"] = source_comparison["summary"]
        result["rule_trace"].append(
            {
                key: record[key]
                for key in ("method", "ruleset_id", "version", "source_ids", "scope")
            }
        )
    interpretation = layers.get("xuankong_natal", {}).get("interpretation")
    if interpretation is not None:
        provenance_record = interpretation_provenance()
        result["rulesets"].append(provenance_record)
        if interpretation.get("timeliness_ruleset") is not None:
            record = interpretation["timeliness_ruleset"]
            result["rulesets"].append(record)
            result["rule_trace"].append(
                {
                    key: record[key]
                    for key in (
                        "method",
                        "ruleset_id",
                        "version",
                        "source_ids",
                        "scope",
                    )
                }
            )
        if interpretation.get("host_guest_analysis") is not None:
            host_guest = interpretation["host_guest_analysis"]
            result["rulesets"].append(host_guest["ruleset"])
            result["coverage"]["natal_host_guest"] = {
                "status": host_guest["status"],
                "candidate_count": len(host_guest["candidates"]),
                "relation_count": 8 * len(host_guest["candidates"]),
                "scope": host_guest["scope"],
                "whole_book_conformity_established": False,
            }
        if interpretation.get("fixed_lingzheng_analysis") is not None:
            record = interpretation["fixed_lingzheng_analysis"]["ruleset"]
            result["rulesets"].append(record)
            result["rule_trace"].extend(
                interpretation["fixed_lingzheng_analysis"]["rule_trace"]
            )
        result["rule_trace"].append(
            {
                key: provenance_record[key]
                for key in ("method", "ruleset_id", "version", "source_ids", "scope")
            }
        )
        result["coverage"].update(
            natal_interpretation_status=interpretation["status"],
            natal_interpretation_missing_inputs=interpretation["missing_inputs"],
            requested_analysis_status=(
                "partial"
                if interpretation["status"] == "partial"
                or result["coverage"].get("requested_analysis_status", status)
                == "partial"
                else "complete"
            ),
        )
    city_gate = layers.get("xuankong_natal", {}).get("city_gate_analysis")
    if city_gate is not None:
        result["summary"] += f"；city_gate: {city_gate['status']}（独立参考运）"
        record = city_gate["ruleset"]
        result["rulesets"].append(record)
        result["rule_trace"].append(
            {
                key: record[key]
                for key in ("method", "ruleset_id", "version", "source_ids", "scope")
            }
        )
        result["coverage"].update(
            city_gate_status=city_gate["status"],
            city_gate_calculation_status=city_gate["calculation_status"],
            city_gate_missing_inputs=city_gate["missing_inputs"],
            requested_analysis_status=(
                "partial"
                if city_gate["status"] == "partial"
                or result["coverage"].get("requested_analysis_status", status)
                == "partial"
                else "complete"
            ),
        )
    geomagnetic = layers.get("directions", {}).get("geomagnetic_reference")
    if geomagnetic is not None:
        record = geomagnetic_provenance()
        result["rulesets"].append(record)
        result["rule_trace"].append(
            {
                key: record[key]
                for key in ("method", "ruleset_id", "version", "source_ids", "scope")
            }
        )
    if scene_scope is not None:
        result["coverage"]["scene_scope"] = scene_scope
    if method_selection is not None and method_reference is not None:
        result["method_policy"] = method_selection
        result["method_details"] = method_reference
        result["coverage"]["method_priority_review"] = {
            key: method_selection[key]
            for key in (
                "priority_review_status",
                "priority_missing_methods",
                "priority_missing_inputs",
            )
        }
        reference = method_reference["ruleset"]
        result["rulesets"].append(reference)
        result["rule_trace"].append(
            {
                key: reference[key]
                for key in ("method", "ruleset_id", "version", "source_ids", "scope")
            }
        )
    context = (layout or {}).get("environmental_context")
    if context is not None:
        result["coverage"].update(
            environmental_context_status=context["status"],
            environmental_context_missing_inputs=context["missing_inputs"],
        )
    snapshot_sections = sections(result)
    result["snapshot_text"] = render_snapshot_lines(snapshot_sections)
    result["snapshot_export"] = build_snapshot_export(
        technique="fengshui",
        snapshot_text=result["snapshot_text"],
        selected_sections=[title for title, _ in snapshot_sections],
    )
    if include_calculation_reading:
        from fatebridge.core.fengshui.reading import build_natal_reading

        result["calculation_reading"] = build_natal_reading(result)
    return result


def calculate_directions(**kwargs: Any) -> Dict[str, Any]:
    req = DirectionsRequest.model_validate(kwargs)
    bearing = None
    if req.bearing_degrees is not None:
        assert req.north_reference is not None
        bearing = bearing_context(req.bearing_degrees, req.north_reference)
    result = {
        "status": "complete",
        "directions": rule_data("directions"),
        "missing_inputs": [],
        "bearing": bearing,
        "division_scope": "confirmed_angular_sectors_no_automatic_geometry",
    }
    if req.geomagnetic_reference is not None:
        result["geomagnetic_reference"] = geomagnetic_reference(
            req.geomagnetic_reference, req.bearing_degrees, req.north_reference
        )
    return _compose({"directions": _layer(result, req.ruleset_id)}, [])


def calculate_minggua(**kwargs: Any) -> Dict[str, Any]:
    req = MingguaRequest.model_validate(kwargs)
    return _compose({"minggua": _layer(minggua(req), req.ruleset_id)}, [])


def calculate_bazhai(**kwargs: Any) -> Dict[str, Any]:
    req = BazhaiRequest.model_validate(kwargs)
    layer = _layer(bazhai(req), req.ruleset_id)
    return _compose({"bazhai": layer}, _differences({"bazhai": layer}))


def calculate_jinsuo(**kwargs: Any) -> Dict[str, Any]:
    req = JinsuoRequest.model_validate(kwargs)
    return _compose({"jinsuo": _layer(jinsuo(req), req.ruleset_id)}, [])


def calculate_annual_stars(**kwargs: Any) -> Dict[str, Any]:
    req = AnnualRequest.model_validate(kwargs)
    return _compose({"annual_stars": _layer(annual_stars(req), req.ruleset_id)}, [])


def _monthly_layer(req: MonthlyRequest) -> Dict[str, Any]:
    from fatebridge.core.fengshui.monthly_integrity import validate_monthly_layer

    result = {**monthly_stars(req), "ruleset": monthly_provenance()}
    validate_monthly_layer(result, req)
    return result


def calculate_monthly_stars(**kwargs: Any) -> Dict[str, Any]:
    req = MonthlyRequest.model_validate(kwargs)
    return _compose({"monthly_stars": _monthly_layer(req)}, [])


def _natal_layer(
    req: XuankongRequest, placements: List[Placement] | None = None
) -> Dict[str, Any]:
    layer = {**xuankong_natal(req), "ruleset": natal_provenance()}
    if req.interpretation is not None:
        layer["interpretation"] = analyze_natal_interpretation(
            req.interpretation, layer, placements or []
        )
        validate_author_geometries(
            layer["interpretation"],
            layer,
            current=req.interpretation.current_period_number,
            require_current_version=req.interpretation.timeliness_ruleset_id
            is not None,
        )
        validate_host_guest(
            layer["interpretation"],
            layer,
            expected_selected=req.interpretation.host_guest_ruleset_id is not None,
        )
    return layer


def calculate_xuankong_natal(**kwargs: Any) -> Dict[str, Any]:
    req = XuankongRequest.model_validate(kwargs)
    return _compose(
        {"xuankong_natal": _natal_layer(req)},
        [],
        include_calculation_reading=bool(
            req.interpretation and req.interpretation.include_calculation_reading
        ),
    )


def _differences(layers: Dict[str, Any]) -> List[Dict[str, Any]]:
    differences: List[Dict[str, Any]] = []
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


def assess(**kwargs: Any) -> Dict[str, Any]:
    req = AssessRequest.model_validate(kwargs)
    original = req
    geometry = None
    if req.workstation_layout is not None:
        req, geometry = prepare_spatial_request(req, req.workstation_layout.scene)
    layers = {}
    if "bazhai" in req.selected_methods:
        layers["bazhai"] = _layer(bazhai(req), req.ruleset_id)
    if "jinsuo" in req.selected_methods:
        layers["jinsuo"] = _layer(
            jinsuo(
                JinsuoRequest(features=req.features, ruleset_id=req.jinsuo_ruleset_id)
            ),
            req.jinsuo_ruleset_id,
        )
    if "annual_stars" in req.selected_methods:
        layers["annual_stars"] = _layer(
            annual_stars(
                AnnualRequest(
                    effective_year=req.effective_year,
                    query_at=req.query_at,
                    timezone_name=req.timezone_name,
                    ruleset_id=req.annual_ruleset_id,
                )
            ),
            req.annual_ruleset_id,
        )
    if "xuankong_natal" in req.selected_methods:
        natal = req.xuankong or XuankongRequest()
        natal = XuankongRequest.model_validate(
            {**natal.model_dump(), "house": natal.house or req.house}
        )
        layers["xuankong_natal"] = _natal_layer(natal, req.placements)
    if "monthly_stars" in req.selected_methods:
        monthly = req.monthly or MonthlyRequest(
            query_at=req.query_at, timezone_name=req.timezone_name
        )
        layers["monthly_stars"] = _monthly_layer(monthly)
    layers = {name: layers[name] for name in req.selected_methods}
    layout = (
        analyze_layout(req, layers)
        if req.analyze_layout
        # A scene also labels method-reference queries. It does not by itself
        # request a site assessment or create missing physical observations.
        or (req.scene and (req.selected_methods or req.placements or req.features))
        or req.layout_constraints
        or req.layout_alternatives
        or req.form_observations
        or req.environmental_context is not None
        or req.surface_layouts
        or req.element_adjustments
        or req.annual_remedy_ruleset_id is not None
        or req.workstation_layout is not None
        else None
    )
    if layout is not None and geometry is not None:
        layout = merge_measured_layout(
            original,
            req,
            geometry,
            TypeAdapter(dict[str, JsonValue]).validate_python(layers),
            TypeAdapter(dict[str, JsonValue]).validate_python(layout),
        )
    if layout is not None and req.layout_alternatives:
        alternatives = evaluate_alternatives(req, layers)
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
    if req.scene is not None:
        scene_scope = {
            "scene": req.scene,
            "selected_methods": req.selected_methods,
            "selection_policy": "explicit_methods_override_input_driven_default",
            "scope": "supplied_objects_and_selected_rules_not_whole_property_certification",
            "indoor_forms": (
                "selected_modern_authored_rules"
                if req.form_observations
                else "not_provided"
            ),
            "geometry": (
                "measured_planar_scene_with_explicit_chart_binding"
                if req.workstation_layout
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
            "effectiveness": "not_established_by_software_validation",
        }
    policy_selected = req.scene is not None or req.environmental_context is not None
    return _compose(
        layers,
        _differences(layers),
        layout,
        scene_scope,
        (
            method_policy(
                req,
                explicit_methods=kwargs.get("methods") is not None,
                layer_results=layers,
                candidate_results=(layout or {})
                .get("alternatives_analysis", {})
                .get("findings", []),
            )
            if policy_selected
            else None
        ),
        method_details(req.selected_methods) if policy_selected else None,
        include_calculation_reading=bool(
            req.xuankong
            and req.xuankong.interpretation
            and req.xuankong.interpretation.include_calculation_reading
        ),
    )
