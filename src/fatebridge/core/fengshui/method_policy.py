"""Method order and boundaries, independent of available chart data.

Priority controls explanation order. It never manufactures a reference date,
historical house period, compass sector, or a favourable result.
"""

from collections.abc import Mapping
from typing import Any

from fatebridge.core.fengshui.method_details import (
    method_reference_provenance,
    reference_data,
)
from fatebridge.core.fengshui.models import AssessRequest, EnvironmentFeature, Method


def _input_scopes(request: AssessRequest) -> dict[Method, list[dict[str, Any]]]:
    """Describe which required facts were supplied."""
    current_locations = [
        placement.object_id
        for placement in request.placements
        if placement.location_direction is not None
    ]
    candidate_locations = [
        candidate.candidate_id
        for candidate in request.layout_alternatives
        if candidate.placement is not None
        and candidate.placement.location_direction is not None
    ]
    chart_scope = {
        "scope": "shared_chart_reference",
        "current_location_object_ids": current_locations,
        "candidate_location_ids": candidate_locations,
        "location_scope": "independently_declared_locations_not_derived_from_chart",
    }
    annual_missing = (
        ["annual_stars.query_at_or_effective_year"]
        if request.effective_year is None and request.query_at is None
        else []
    )
    natal = request.xuankong
    natal_house = (natal.house if natal is not None else None) or request.house
    natal_missing = []
    if (
        natal_house is None
        or natal_house.facing_degrees is None
        or natal_house.north_reference != "magnetic"
    ):
        natal_missing.append("xuankong_natal.house.facing_degrees_magnetic")
    if natal is None or natal.period is None:
        natal_missing.append("xuankong_natal.period")

    features = request.features

    def feature_missing(records: list[EnvironmentFeature], empty: str) -> list[str]:
        return (
            [empty]
            if not records
            else [
                f"features.{record.object_id}.single_confirmed_classification"
                for record in records
                if record.classification not in {"sand", "water"}
            ]
        )

    feature_scopes = [
        {
            "scope": "current_environment",
            "object_ids": [feature.object_id for feature in features],
            "missing_inputs": feature_missing(
                features, "confirmed_environment_features"
            ),
        }
    ]
    current_feature_ids = {feature.object_id for feature in features}
    for candidate in request.layout_alternatives:
        fresh = candidate.features
        if not fresh and candidate.object_id not in current_feature_ids:
            continue
        feature_scopes.append(
            {
                "scope": "candidate_environment",
                "candidate_id": candidate.candidate_id,
                "object_ids": [feature.object_id for feature in fresh],
                "missing_inputs": feature_missing(
                    fresh, f"layout_alternatives.{candidate.candidate_id}.features"
                ),
            }
        )
    house = natal_house
    personal_missing = []
    if house is None or (
        house.sitting_trigram is None and house.facing_degrees is None
    ):
        personal_missing.append("house.sitting_trigram_or_confirmed_facing")
    occupants = request.occupants
    if not occupants:
        personal_missing.append("occupants")
    for occupant in occupants:
        prefix = f"occupants.{occupant.subject_id}"
        if (
            occupant.birth_date is None
            and occupant.birth_at is None
            and occupant.effective_birth_year is None
        ):
            personal_missing.append(
                f"{prefix}.birth_date_or_birth_at_or_effective_birth_year"
            )
        if occupant.gender_convention is None:
            personal_missing.append(f"{prefix}.gender_convention")
    scopes: dict[Method, list[dict[str, Any]]] = {
        "annual_stars": [{**chart_scope, "missing_inputs": annual_missing}],
        "xuankong_natal": [{**chart_scope, "missing_inputs": natal_missing}],
        "jinsuo": feature_scopes,
        "bazhai": [
            {
                "scope": "shared_house_and_independent_person_minggua",
                "subject_ids": [occupant.subject_id for occupant in occupants],
                "current_location_object_ids": current_locations,
                "candidate_location_ids": candidate_locations,
                "missing_inputs": personal_missing,
            }
        ],
    }
    monthly = request.monthly
    monthly_time_present = (
        request.query_at is not None
        if monthly is None
        else monthly.query_at is not None
        or (
            monthly.effective_solar_year is not None
            and monthly.solar_month_number is not None
        )
    )
    scopes["monthly_stars"] = [
        {
            **chart_scope,
            "missing_inputs": (
                []
                if monthly_time_present
                else [
                    "monthly_stars.query_at_or_confirmed_effective_solar_year_and_solar_month"
                ]
            ),
        }
    ]
    for records in scopes.values():
        for record in records:
            record["input_presence_status"] = (
                "missing_inputs"
                if record["missing_inputs"]
                else "required_inputs_present_not_computed"
            )
    return scopes


def method_policy(
    request: AssessRequest,
    *,
    explicit_methods: bool | None = None,
    layer_results: Mapping[str, Any] | None = None,
    candidate_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Describe the policy without treating unrequested layers as failures.

    explicit_methods may be supplied by the service before Pydantic
    normalizes methods. A normalized model alone cannot recover that fact.
    layer_results supplies the already calculated current layers. Missing
    layers are never calculated here to answer an availability question.
    Candidate layer statuses remain independent of those current results.
    """
    selected = request.selected_methods
    policy = reference_data("policy")
    local = request.scene in {"workstation", "shared_rental"}
    locations = [
        placement.object_id
        for placement in request.placements
        if placement.location_direction is not None
    ]
    selected_families = []
    layer_families = {
        "xuankong_natal": "nine_palace_flying_stars",
        "annual_stars": "nine_palace_flying_stars",
        "monthly_stars": "nine_palace_flying_stars",
        "jinsuo": "jinsuo",
        "bazhai": "bazhai",
    }
    for method in selected:
        family = layer_families[method]
        if family not in selected_families:
            selected_families.append(family)
    input_scopes = _input_scopes(request)
    candidate_ids = [
        candidate.candidate_id for candidate in request.layout_alternatives
    ]
    candidate_records = {c["candidate_id"]: c for c in candidate_results or []}
    availability: dict[str, dict[str, Any]] = {}
    for method, scopes in input_scopes.items():
        actual = (layer_results or {}).get(method) if method in selected else None
        actual_status = actual.get("status") if actual is not None else None
        missing = list(actual.get("missing_inputs", [])) if actual is not None else []
        candidate_calculations: list[dict[str, Any]] = []
        for candidate_id in candidate_ids:
            candidate_layer = (
                candidate_records.get(candidate_id, {})
                .get("layer_statuses", {})
                .get(method)
                if method in selected
                else None
            )
            candidate_status = (
                candidate_layer.get("status") if candidate_layer is not None else None
            )
            candidate_calculations.append(
                {
                    "scope": "candidate_calculation",
                    "candidate_id": candidate_id,
                    "availability": (
                        "computed_complete"
                        if candidate_status == "complete"
                        else (
                            "computed_partial"
                            if candidate_layer is not None
                            else "not_computed"
                        )
                    ),
                    "calculation_status": candidate_status,
                    "calculation_missing_inputs": (
                        list(candidate_layer.get("missing_inputs", []))
                        if candidate_layer is not None
                        else []
                    ),
                }
            )
        availability[method] = {
            "engine_layer": method,
            "selected": method in selected,
            "availability": (
                "computed_complete"
                if actual_status == "complete"
                else ("computed_partial" if actual is not None else "not_computed")
            ),
            "calculation_status": actual_status,
            "calculation_missing_inputs": missing,
            "input_scopes": scopes,
            "input_presence_sufficient": any(not s["missing_inputs"] for s in scopes),
            "input_presence_scope": "required_field_presence_only_not_resolved_chart_or_physical_binding",
            "candidate_calculations": candidate_calculations,
        }
    priorities = policy["local_method_priority"]
    for priority in priorities:
        selected_layers = [m for m in selected if m in priority["engine_layers"]]
        layer_availability = [availability[m] for m in priority["engine_layers"]]
        inputs_present = [
            row["engine_layer"]
            for row in layer_availability
            if row["input_presence_sufficient"]
        ]
        priority.update(
            selected_engine_layers=selected_layers,
            selection_status=(
                "selected" if selected_layers else "reference_only_not_selected"
            ),
            judgment_scope=(
                "selected_layer_facts_only"
                if selected_layers
                else "no_calculation_or_physical_judgment"
            ),
            not_selected_reason=(
                None
                if selected_layers
                else (
                    "explicitly_excluded"
                    if explicit_methods is True
                    else (
                        "selection_origin_not_recorded"
                        if explicit_methods is None
                        else (
                            "automatic_scope_not_requested"
                            if priority["method"] == "bazhai"
                            and not request.placements
                            and request.scene != "home"
                            else "automatic_missing_inputs"
                        )
                    )
                )
            ),
            available_engine_layers=[
                row["engine_layer"]
                for row in layer_availability
                if row["availability"] == "computed_complete"
            ],
            available_engine_layers_scope="current_calculation_only",
            available_candidate_engine_layers={
                candidate_id: [
                    row["engine_layer"]
                    for row in layer_availability
                    if any(
                        record["candidate_id"] == candidate_id
                        and record["availability"] == "computed_complete"
                        for record in row["candidate_calculations"]
                    )
                ]
                for candidate_id in candidate_ids
            },
            input_ready_engine_layers=inputs_present,
            input_readiness_scope="required_field_presence_only_not_resolved_or_confirmed_chart",
            layer_availability=layer_availability,
            input_alternatives_policy="one_supported_layer_can_satisfy_family_not_all_alternatives_required",
        )
    preferred = priorities[:2] if local else []
    priority_missing = []
    evidence_pending = False
    for priority in preferred:
        if explicit_methods is True and not priority["selected_engine_layers"]:
            continue
        if explicit_methods is None and not priority["selected_engine_layers"]:
            evidence_pending = True
            continue
        if priority["available_engine_layers"]:
            continue
        if (
            layer_results is None
            and priority["selected_engine_layers"]
            and priority["input_ready_engine_layers"]
        ):
            evidence_pending = True
        else:
            priority_missing.append(priority["method"])
    priority_status = (
        "not_requested"
        if not local or (explicit_methods is True and not selected)
        else (
            "partial"
            if priority_missing
            else "not_assessed" if evidence_pending else "complete"
        )
    )
    candidate_reviews = []
    for candidate_id in candidate_ids:
        missing_methods = []
        pending_evidence = candidate_results is None and any(
            explicit_methods is not True or priority["selected_engine_layers"]
            for priority in preferred
        )
        for priority in preferred:
            if explicit_methods is True and not priority["selected_engine_layers"]:
                continue
            if candidate_results is None:
                continue
            if priority["available_candidate_engine_layers"][candidate_id]:
                continue
            calculations = [
                record
                for row in priority["layer_availability"]
                if row["selected"]
                for record in row["candidate_calculations"]
                if record["candidate_id"] == candidate_id
            ]
            if not priority["selected_engine_layers"] or any(
                record["availability"] == "computed_partial" for record in calculations
            ):
                missing_methods.append(priority["method"])
            else:
                pending_evidence = True
        status = (
            "not_requested"
            if not local or (explicit_methods is True and not selected)
            else (
                "partial"
                if missing_methods
                else "not_assessed" if pending_evidence else "complete"
            )
        )
        candidate_reviews.append(
            {
                "candidate_id": candidate_id,
                "priority_review_status": status,
                "priority_missing_methods": missing_methods,
                "priority_missing_inputs": [
                    f"method_policy.candidates.{candidate_id}.{method}.supported_layer_inputs_or_resolution"
                    for method in missing_methods
                ],
            }
        )
    priority_missing_inputs = [
        f"method_policy.{method}.supported_layer_inputs_or_resolution"
        for method in priority_missing
    ]
    return {
        "policy_id": "expert_fengshui_methods_v1",
        "version": "1.0.0",
        "source_ids": ["EXPERT_20261015"],
        "selection_mode": (
            "explicit_methods"
            if explicit_methods is True
            else (
                "input_driven_default"
                if explicit_methods is False
                else "explicit_or_normalized_selection"
            )
        ),
        "priority_scope": "local_space" if local else "main_method_reference",
        "method_priority": priorities,
        "selected_method_order": selected,
        "selected_family_order": selected_families,
        "priority_meaning": "review_order_not_compensation_or_combined_score",
        "priority_review_status": priority_status,
        "priority_review_scope": "local_preferred_method_availability_separate_from_selected_calculation_completeness",
        "priority_review_status_values": [
            "not_requested",
            "not_assessed",
            "partial",
            "complete",
        ],
        "priority_missing_methods": priority_missing,
        "priority_missing_inputs": priority_missing_inputs,
        "priority_missing_inputs_required_for": "optional_preferred_method_review_not_automatic_followup_requirement",
        "priority_review_by_scope": {
            "current": {
                "priority_review_status": priority_status,
                "priority_missing_methods": priority_missing,
                "priority_missing_inputs": priority_missing_inputs,
            },
            "candidates": candidate_reviews,
        },
        "domains": policy["domains"],
        "direction_policy": policy["direction_policy"],
        "chart_input_policy": policy["chart_input_policy"],
        "fact_availability": {
            "provided_location_object_ids": locations,
            "location_claim_scope": "supplied_placements_subject_to_context_orientation_gate",
            "annual_reference_supplied": request.effective_year is not None
            or request.query_at is not None,
            "natal_inputs_supplied": request.xuankong is not None,
            "jinsuo_features_supplied": bool(request.features),
            "occupants_supplied": bool(request.occupants),
        },
        "supplemental_rules": {
            "indoor_forms": "explicit_authored_observations_only",
            "desktop_btb": "explicit_surface_ruleset_only_not_a_main_method",
        },
        "ruleset": method_reference_provenance(),
    }
