"""Material identity is not dosage, target need, placement or efficacy."""

from typing import Any

from fatebridge.core.fengshui.workstation_sources import disagreement, provenance


def analyze_application(
    fact: Any, targets: list[dict[str, Any]], eligibility: str
) -> dict[str, Any]:
    app = fact.application
    eligible = eligibility == "conditional_material_match"
    keys = {
        "water": ("water_clean", "water_moving", "proportionate_to_space"),
        "metal": ("metal_exposed", "proportionate_to_space"),
        "living_plant": ("plant_healthy", "proportionate_to_space"),
        "stone": ("proportionate_to_space",),
        "ceramic": ("proportionate_to_space",),
    }.get(fact.material, ())
    checks = []
    pending = []
    path = f"environmental_context.material_facts.{fact.fact_id}.application"
    for key in keys if eligible else ():
        condition = getattr(app, key)
        status = (
            "needs_confirmation"
            if condition is None or condition.value is None
            else (
                "candidate_only"
                if condition.observation_basis == "image_observed"
                else (
                    "matches_condition"
                    if condition.value
                    else "does_not_match_condition"
                )
            )
        )
        checks.append(
            dict(
                criterion=key,
                status=status,
                fact=condition.model_dump(mode="json") if condition else None,
                rule_id="afsi_application_conditions_v1." + key,
                source_ids=(
                    ["A2", "A3"]
                    if key in {"water_clean", "water_moving", "plant_healthy"}
                    else ["A2"]
                ),
            )
        )
        if status in {"needs_confirmation", "candidate_only"}:
            pending.append(path + "." + key)
    binding: dict[str, Any] = dict(
        status="not_requested", location_confirmed=False, effect="not_established"
    )
    if app.target_request_id is not None:
        matched = [p for p in targets if p["request_id"] == app.target_request_id]
        required = fact.element_use.removesuffix("_remedy")
        element = {
            "wood": "木",
            "water": "水",
            "earth": "土",
            "metal": "金",
            "fire": "火",
        }[required]
        binding.update(request_id=app.target_request_id, computed_targets=matched)
        binding["status"] = (
            "needs_computed_target"
            if not matched
            or any(p["status"] == "needs_computed_target" for p in matched)
            else (
                "not_indicated_by_selected_target"
                if any("introduced_element" not in p for p in matched)
                else (
                    "element_mismatch"
                    if any(p["introduced_element"] != element for p in matched)
                    else (
                        "candidate_only"
                        if any(p["status"] == "candidate_only" for p in matched)
                        else "bound_to_computed_target"
                    )
                )
            )
        )
        if binding["status"] in {"needs_computed_target", "candidate_only"}:
            pending.append(path + ".target_request_id.computed_target")
    failed = any(c["status"] == "does_not_match_condition" for c in checks)
    # A known failed condition already answers applicability; do not demand the
    # rest of the observations merely to finish a checklist.
    if failed or not eligible:
        pending = []
    return dict(
        ruleset_id=app.ruleset_id,
        rule_id="afsi_application_conditions_v1.application",
        source_ids=["A2", "A3"],
        status=(
            "needs_material_confirmation"
            if eligibility in {"needs_confirmation", "not_provided"}
            else (
                "not_applicable"
                if not eligible
                else (
                    "candidate_only"
                    if fact.observation_basis == "image_observed"
                    else (
                        "conditions_not_met"
                        if failed
                        else "needs_confirmation" if pending else "conditions_reviewed"
                    )
                )
            )
        ),
        eligibility_scope="preliminary_material_match_only",
        application_conditions=checks,
        target_binding=binding,
        missing_inputs=pending,
        source_disagreements=(
            [disagreement("metal_storage")] if fact.material == "metal" else []
        ),
        unassessed_dimensions=[
            "quantitative_dosage_or_sufficiency",
            "actual_target_location",
            "placement_favourability",
            "effectiveness",
        ],
        placement_suitability="not_assessed",
        action_status="not_evaluated",
        inference_policy="qualitative_conditions_do_not_certify_sufficiency_or_ready",
        provenance=provenance(app.ruleset_id),
    )
