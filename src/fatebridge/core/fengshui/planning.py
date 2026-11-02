"""Compare independently observed proposals using the same existing rules.

This is an engineering feasibility policy, not another Feng Shui lineage.
There are no invented scores, prescription rules, or inferred floorplan facts.
"""

from typing import Any, Dict, List

from .actions import permission_state
from .bazhai import bazhai
from .jinsuo import jinsuo
from .layout import analyze_layout
from .models import AssessRequest, JinsuoRequest


def evaluate_alternatives(req: AssessRequest, layers: Dict[str, Any]) -> Dict[str, Any]:
    constraints = {c.object_id: c for c in req.layout_constraints}
    current_placements = {p.object_id: p for p in req.placements}
    current_forms = {o.object_id: o for o in req.form_observations}
    findings: List[Dict[str, Any]] = []
    for candidate in req.layout_alternatives:
        # Never transfer old entrance/backing observations after a move or turn.
        proposal_features = [
            feature
            for feature in req.features
            if feature.object_id != candidate.object_id
        ] + list(candidate.features)
        proposed = req.model_copy(
            update={
                # A proposal keeps the request's chosen rule scope even when
                # removing a target feature makes automatic input selection
                # differ. Preserve None only on the original public request.
                "methods": req.selected_methods,
                "placements": [candidate.placement] if candidate.placement else [],
                "form_observations": (
                    [candidate.form_observation] if candidate.form_observation else []
                ),
                "surface_layouts": [],
                "surface_constraints": [],
                "layout_alternatives": [],
                "layout_constraints": list(req.layout_constraints),
                "element_adjustments": [],
                "annual_remedy_ruleset_id": None,
                "environmental_context": candidate.environmental_context,
                "features": proposal_features,
            }
        )
        if (
            proposed.environmental_context is not None
            and proposed.workstation_review
            and proposed.workstation_review.evaluation_period is None
            and req.workstation_review
            and req.workstation_review.evaluation_period is not None
        ):
            # The explicitly chosen evaluation period is a query parameter,
            # independent of the geometry that must be observed again.
            proposed.environmental_context = proposed.environmental_context.model_copy(
                update={
                    "workstation_review": proposed.workstation_review.model_copy(
                        update={
                            "evaluation_period": req.workstation_review.evaluation_period
                        }
                    )
                }
            )
        candidate_layers = dict(layers)
        if "bazhai" in layers:
            candidate_layers["bazhai"] = {
                **bazhai(proposed),
                "ruleset": layers["bazhai"]["ruleset"],
            }
        if "jinsuo" in layers:
            candidate_layers["jinsuo"] = {
                **jinsuo(
                    JinsuoRequest(
                        features=proposal_features, ruleset_id=req.jinsuo_ruleset_id
                    )
                ),
                "ruleset": layers["jinsuo"]["ruleset"],
            }
        layout = analyze_layout(proposed, candidate_layers)
        if req.environmental_context is not None:
            static_floors = {
                object_id: floor
                for floor in req.environmental_context.floors
                for object_id in floor.object_ids
                if object_id != candidate.object_id
            }
            for entry in layout["environment_adjustments"]:
                floor = static_floors.get(entry["object_id"])
                if floor is not None:
                    entry.update(
                        floor_id=floor.floor_id,
                        floor_level=(
                            1 if floor.space_kind == "courtyard" else floor.level
                        ),
                        location_reference="independently_confirmed_floor_center_shared_orientation",
                        chart_scope="declared_house_and_annual_layers_no_automatic_floor_period",
                    )
        missing = list(layout["missing_inputs"])
        # Any moved end requires a new observation of the same relationship.
        if req.workstation_review:
            fresh_review = proposed.workstation_review
            for activity in req.workstation_review.activities:
                if activity.object_id == candidate.object_id and not any(
                    a.object_id == activity.object_id
                    for a in (fresh_review.activities if fresh_review else [])
                ):
                    missing.append(
                        f"layout_alternatives.{candidate.candidate_id}.environmental_context.workstation_review.activities.{activity.object_id}"
                    )
            for relation in req.workstation_review.entry_barriers:
                identity = (relation.entrance_id, relation.desk_id, relation.barrier_id)
                if candidate.object_id in identity and not any(
                    (r.entrance_id, r.desk_id, r.barrier_id) == identity
                    for r in (fresh_review.entry_barriers if fresh_review else [])
                ):
                    missing.append(
                        f"layout_alternatives.{candidate.candidate_id}.environmental_context.workstation_review.entry_barriers.{relation.relation_id}"
                    )
        if (
            "jinsuo" in layers
            and not candidate.features
            and any(
                feature.object_id == candidate.object_id for feature in req.features
            )
        ):
            missing.append(f"layout_alternatives.{candidate.candidate_id}.features")
        if req.environmental_context is not None:
            context = req.environmental_context
            fresh = candidate.environmental_context
            branch = (
                f"layout_alternatives.{candidate.candidate_id}.environmental_context"
            )
            old_floors = {
                f.floor_id
                for f in context.floors
                if candidate.object_id in f.object_ids
            }
            old_observations = [
                o for o in context.observations if o.object_id == candidate.object_id
            ]
            old_relations = [
                relation
                for relation in context.interior_relations
                if candidate.object_id
                in (relation.source_object_id, relation.target_object_id)
            ]
            old_materials = [
                fact
                for fact in context.material_facts
                if fact.object_id == candidate.object_id
            ]
            if fresh is None:
                if old_floors or old_observations or old_relations or old_materials:
                    missing.append(branch)
            else:
                fresh_relations = {
                    (r.kind, r.source_object_id, r.target_object_id)
                    for r in fresh.interior_relations
                }
                for relation in old_relations:
                    if (
                        relation.kind,
                        relation.source_object_id,
                        relation.target_object_id,
                    ) not in fresh_relations:
                        missing.append(
                            f"{branch}.interior_relations.{relation.relation_id}"
                        )
                for fact in old_materials:
                    if fact.application:
                        new_app = next(
                            (
                                f.application
                                for f in fresh.material_facts
                                if f.object_id == fact.object_id and f.application
                            ),
                            None,
                        )
                        for field in type(fact.application).model_fields:
                            if getattr(fact.application, field) is not None and (
                                new_app is None or getattr(new_app, field) is None
                            ):
                                missing.append(
                                    f"{branch}.material_facts.{fact.fact_id}.application.{field}"
                                )
                    for attribute in (
                        "material",
                        "shape",
                        "colour",
                        "element_use",
                        "plant_alive",
                    ):
                        if getattr(fact, attribute) is not None and not any(
                            f.object_id == candidate.object_id
                            and getattr(f, attribute) is not None
                            for f in fresh.material_facts
                        ):
                            missing.append(
                                f"{branch}.material_facts.{fact.fact_id}.{attribute}"
                            )
                if old_floors and not any(
                    candidate.object_id in f.object_ids for f in fresh.floors
                ):
                    missing.append(f"{branch}.floors")
                for observation in old_observations:
                    if not any(
                        o.object_id == candidate.object_id
                        and o.category == observation.category
                        and o.feature == observation.feature
                        for o in fresh.observations
                    ):
                        missing.append(
                            f"{branch}.observations.{observation.category}.{observation.feature}"
                        )
                old_influences = {
                    i.influence_id
                    for i in context.floor_influences
                    if i.source_floor_id in old_floors
                    or set(i.shared_floor_ids) & old_floors
                }
                for influence_id in old_influences - {
                    i.influence_id for i in fresh.floor_influences
                }:
                    missing.append(f"{branch}.floor_influences.{influence_id}")
        if candidate.object_id in current_forms and candidate.form_observation is None:
            missing.append(
                f"layout_alternatives.{candidate.candidate_id}.form_observation"
            )
        elif candidate.object_id in current_forms:
            before_form = current_forms[candidate.object_id]
            for field in (
                "entrance_visible",
                "entrance_direct_line",
                "solid_backing",
                "passage_direct_line",
                "exposed_beam_over_user",
                "sharp_corner_points_at_user",
                "window_position",
            ):
                if (
                    getattr(before_form, field) is not None
                    and getattr(candidate.form_observation, field) is None
                ):
                    missing.append(
                        f"layout_alternatives.{candidate.candidate_id}.form_observation.{field}"
                    )
        if (
            candidate.object_id in current_placements
            and candidate.placement is None
            and any(m in layers for m in ("bazhai", "annual_stars", "xuankong_natal"))
        ):
            missing.append(f"layout_alternatives.{candidate.candidate_id}.placement")
        elif (
            candidate.object_id in current_placements
            and candidate.placement is not None
        ):
            for aspect in ("location", "facing"):
                field = f"{aspect}_direction"
                if (
                    getattr(current_placements[candidate.object_id], field) is not None
                    and getattr(candidate.placement, field) is None
                ):
                    missing.append(
                        f"layout_alternatives.{candidate.candidate_id}.placement.{field}"
                    )
        constraint = constraints.get(candidate.object_id)
        permission = permission_state(constraint, [list(candidate.changes)])
        workstation_actions = [
            action
            for action in layout.get("workstation_analysis", {}).get(
                "action_options", []
            )
            if action["object_id"] == candidate.object_id
        ]
        blocked = (
            permission == "blocked"
            or candidate.physically_feasible is False
            or any(action["status"] == "blocked" for action in workstation_actions)
        )
        execution_pending = [
            item
            for action in workstation_actions
            for item in action["pending_confirmations"]
        ]
        partial = bool(missing) or layout["status"] != "complete"
        status = (
            "blocked"
            if blocked
            else (
                "candidate_only"
                if partial
                else (
                    "ready"
                    if permission == "allowed"
                    and candidate.physically_feasible is True
                    and not execution_pending
                    else "conditional_option"
                )
            )
        )
        pending = []
        if not blocked:
            pending.extend(execution_pending)
            for field, reason in [
                ("layout_constraints", "confirm_action_permissions"),
                (
                    f"layout_alternatives.{candidate.candidate_id}.physically_feasible",
                    "confirm_proposal_space_clearance_and_operation",
                ),
            ]:
                if (field == "layout_constraints" and permission == "unknown") or (
                    field != "layout_constraints"
                    and candidate.physically_feasible is None
                ):
                    pending.append(
                        {
                            "path": field,
                            "reason": reason,
                            "object_id": candidate.object_id,
                            "action_id": candidate.candidate_id,
                            "required_for": "optional_action",
                        }
                    )
            pending.extend(
                {
                    "path": p,
                    "reason": "confirm_independent_proposal_observation",
                    "object_id": candidate.object_id,
                    "action_id": candidate.candidate_id,
                    "required_for": "optional_action",
                }
                for p in dict.fromkeys(missing)
            )
        comparisons = []
        for finding in layout["placement_findings"]:
            if finding["method"] == "bazhai":
                comparisons.append(
                    {
                        key: finding[key]
                        for key in (
                            "method",
                            "subject_id",
                            "subject_kind",
                            "gender_convention",
                            "aspect",
                            "matches_convention",
                            "candidate_only",
                            "rule_id",
                            "source_ids",
                        )
                    }
                    | {
                        key: finding[key]
                        for key in ("house_candidate_id", "house_sitting_trigram")
                        if key in finding
                    }
                )
            elif finding["method"] in {
                "annual_stars",
                "monthly_stars",
                "xuankong_natal",
            }:
                comparisons.append(
                    {
                        **finding,
                        "comparison_scope": "computed_star_reference_not_combination_fortune_judgment",
                    }
                )
        for form in layout["form_analysis"]["findings"]:
            comparisons.extend(
                {"method": "indoor_forms", **check} for check in form["checks"]
            )
        for branch in (
            "interior_analysis",
            "material_analysis",
            "workstation_analysis",
        ):
            comparisons.extend(
                {
                    **finding,
                    "method": (
                        "indoor_authored_relations"
                        if branch == "interior_analysis"
                        else (
                            "workstation_authored_review"
                            if branch == "workstation_analysis"
                            else "material_and_shape_reference"
                        )
                    ),
                    "comparison_scope": (
                        "independent_relation_predicate_not_compass_or_effect_prediction"
                        if branch == "interior_analysis"
                        else (
                            "authored_activity_or_entry_relationship_not_placement_fortune"
                            if branch == "workstation_analysis"
                            else "source_scoped_representation_eligibility_not_placement_fortune"
                        )
                    ),
                }
                for finding in layout.get(branch, {}).get("findings", [])
            )
        for environment in layout["environment_adjustments"]:
            environment["feature_observation_scope"] = (
                "independent_candidate_confirmation"
                if environment["object_id"] == candidate.object_id
                else "unchanged_environment_feature"
            )
            comparisons.append({"method": "jinsuo", **environment})
        findings.append(
            {
                "candidate_id": candidate.candidate_id,
                "object_id": candidate.object_id,
                "changes": candidate.changes,
                "evidence": candidate.evidence,
                "status": status,
                "optional": True,
                "permission_status": permission,
                "physically_feasible": candidate.physically_feasible,
                "calculation_status": "partial" if partial else "complete",
                "layer_statuses": {
                    name: {
                        "status": layer["status"],
                        "missing_inputs": layer["missing_inputs"],
                    }
                    for name, layer in candidate_layers.items()
                },
                "missing_inputs": list(dict.fromkeys(missing)),
                "pending_confirmations": pending,
                "rule_comparisons": comparisons,
                "placement_findings": layout["placement_findings"],
                "form_analysis": layout["form_analysis"],
                "environment_adjustments": layout["environment_adjustments"],
                **{
                    name: layout[name]
                    for name in (
                        "interior_analysis",
                        "material_analysis",
                        "workstation_analysis",
                    )
                    if name in layout
                },
                "old_target_feature_reused": False,
                **(
                    {"environmental_context": layout["environmental_context"]}
                    if "environmental_context" in layout
                    else {}
                ),
                **(
                    {"natal_interpretation": layout["natal_interpretation"]}
                    if "natal_interpretation" in layout
                    else {}
                ),
                "supplemental_rulesets": layout["supplemental_rulesets"],
                "decision_scope": "executable_proposal_not_universal_recommendation_or_effect_guarantee",
                "old_form_observations_reused": False,
                **(
                    {"old_environmental_context_reused": False}
                    if req.environmental_context is not None
                    or candidate.environmental_context is not None
                    else {}
                ),
            }
        )
    return {
        "policy_id": "layout_feasibility_v1",
        "findings": findings,
        "ready_candidate_ids": [
            f["candidate_id"] for f in findings if f["status"] == "ready"
        ],
        "selection_policy": "compare_rules_individually_no_weighted_score_or_automatic_winner",
        "limitations": [
            "ready只确认所选计算与动作门槛已满足，不代表候选符合所有流派或具有现实效力。",
            "候选仅来自明确提交的方案，不自动生成户型、推断可用空间或继承搬转前的形态。",
            (
                "年盘保持独立；玄空只列有限五行与当令外局条件，不合成总分或自动排名。"
                if layers.get("xuankong_natal", {}).get("interpretation") is not None
                else "年盘与玄空只列落宫关系，没有来源支持的组合判断或外局条件时不自动排名。"
            ),
        ],
    }
