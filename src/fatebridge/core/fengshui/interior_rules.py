"""Limited modern authored interior rules, with explicit factual/action gates."""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Sequence, cast

from fatebridge.core.fengshui.interior_inputs import InteriorRelation
from fatebridge.core.fengshui.models import LayoutConstraint
from fatebridge.core.fengshui.workstation_sources import disagreement, provenance


@lru_cache(maxsize=1)
def _bundle() -> dict[str, Any]:
    path = (
        Path(__file__).parents[2] / "data" / "fengshui" / "interior-relations-v1.json"
    )
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def interior_relation_provenance() -> dict[str, Any]:
    data = _bundle()
    result = deepcopy(data["ruleset"])
    result["bundle_version"] = data["bundle_version"]
    result["sources"] = [
        {"source_id": source_id, **deepcopy(data["sources"][source_id])}
        for source_id in result["source_ids"]
    ]
    return cast(dict[str, Any], result)


def _action(
    relation: InteriorRelation,
    rule: dict[str, Any],
    specification: dict[str, Any],
    constraints: dict[str, LayoutConstraint],
) -> dict[str, Any]:
    object_id = (
        relation.source_object_id
        if specification["endpoint"] == "source"
        else relation.target_object_id
    )
    operation = specification["operation"]
    permission_field = {"location": "can_relocate", "facing": "can_rotate"}[operation]
    constraint = constraints.get(object_id)
    permission = (
        None
        if constraint is None
        else (
            constraint.can_relocate
            if operation == "location"
            else constraint.can_rotate
        )
    )
    blocked = permission is False
    pending = []
    if not blocked:
        if permission is not True:
            pending.append(f"layout_constraints.{object_id}.{permission_field}")
        pending.extend(
            [
                "independently_confirmed_candidate_relation_geometry",
                "independently_confirmed_candidate_physical_feasibility",
            ]
        )
    return {
        "action_id": f"interior:{relation.relation_id}:{object_id}:{operation}",
        "relation_id": relation.relation_id,
        "source_object_id": relation.source_object_id,
        "target_object_id": relation.target_object_id,
        "object_id": object_id,
        "operation": operation,
        "status": "blocked" if blocked else "conditional_option",
        "permission_field": permission_field,
        "permission_confirmed": permission,
        "physical_feasibility": "not_independently_confirmed",
        "pending_confirmations": pending,
        "reason": (
            "object_operation_not_permitted"
            if blocked
            else "candidate_requires_fresh_geometry_and_feasibility"
        ),
        "description": specification["description"],
        "action_basis": specification["action_basis"],
        "method": "indoor_authored_relations",
        "rule_id": rule["rule_id"],
        "rule_version": _bundle()["ruleset"]["version"],
        "ruleset_id": "interior_authored_relations_v1",
        "source_ids": list(rule["source_ids"]),
    }


def analyze_interior_relations(
    relations: Sequence[InteriorRelation], constraints: Iterable[LayoutConstraint]
) -> dict[str, Any]:
    """Review only supplied relations; no direction or relocation is invented.

    Action prerequisites are separate from factual assessment completeness.
    Permission is insufficient for readiness; this module cannot establish a
    fresh candidate position's geometry or physical feasibility.
    """
    data = _bundle()
    result: dict[str, Any] = {
        "status": "complete" if relations else "not_requested",
        "findings": [],
        "rulesets": [interior_relation_provenance()] if relations else [],
        "rule_trace": [],
        "missing_inputs": [],
        "rule_coverage_counts": {
            "supported": 0,
            "confirmed_unsupported": 0,
            "unknown": 0,
        },
        "rule_coverage_status": "covered" if relations else "not_requested",
        "action_options": [],
        "limitations": deepcopy(data["limitations"]) if relations else [],
    }
    constraint_map = {item.object_id: item for item in constraints}
    for relation in relations:
        rule = deepcopy(data["rules"][relation.kind])
        if relation.kind == "sharp_corner_points_at_desk":
            rule.setdefault("method_disagreements", []).append(disagreement("corners"))
            if not any(
                r["ruleset_id"] == "workstation_source_boundaries_v1"
                for r in result["rulesets"]
            ):
                result["rulesets"].append(
                    provenance("workstation_source_boundaries_v1")
                )
        present = relation.present
        basis = relation.observation_basis
        relation_id = relation.relation_id
        missing: list[str] = []
        if basis == "image_observed":
            status = "candidate_only"
            missing.append(
                f"environmental_context.interior_relations.{relation_id}.confirmation"
            )
        elif present is None:
            status = "needs_confirmation"
            missing.append(
                f"environmental_context.interior_relations.{relation_id}.present"
            )
        else:
            status = "authored_caution" if present else "not_present"
        confirmed = status in {"authored_caution", "not_present"}
        result["rule_coverage_counts"]["supported" if confirmed else "unknown"] += 1
        actions = (
            [
                _action(relation, rule, specification, constraint_map)
                for specification in rule["actions"]
            ]
            if status == "authored_caution"
            or (status == "candidate_only" and present is True)
            else []
        )
        finding = {
            "relation_id": relation_id,
            "kind": relation.kind,
            "source_object_id": relation.source_object_id,
            "target_object_id": relation.target_object_id,
            "present": present,
            "observation_basis": basis,
            "evidence": relation.evidence,
            "status": status,
            "method": "indoor_authored_relations",
            "scope": "authored_non_compass_interior_relation_only",
            "ruleset_id": "interior_authored_relations_v1",
            "rule_id": rule["rule_id"],
            "rule_version": data["ruleset"]["version"],
            "source_ids": rule["source_ids"],
            "predicate": rule["predicate"],
            "exceptions": rule["exceptions"],
            "interpretation": (
                rule["interpretation"] if status == "authored_caution" else None
            ),
            # Preserve the candidate state while allowing a useful explanation
            # of a visibly suggested relation. Unknown/absent relations never
            # receive a positive caution, even conditionally.
            "conditional_interpretation": (
                {
                    "condition": "若现场确认该关系成立",
                    "interpretation": rule["interpretation"],
                    "suggestions": [
                        {
                            "description": action["description"],
                            "action_basis": action["action_basis"],
                            "condition": "若允许相应调整且新位置可容纳、不妨碍通行和使用",
                        }
                        for action in actions
                        if action["status"] != "blocked"
                    ],
                    "source_ids": list(rule["source_ids"]),
                    "rule_id": rule["rule_id"],
                }
                if status == "candidate_only" and present is True
                else None
            ),
            "method_disagreements": rule.get("method_disagreements", []),
            "action_options": [],
            "missing_inputs": missing,
            "action_status": "not_applicable",
        }
        if status == "authored_caution":
            finding["action_options"] = actions
            finding["action_status"] = (
                "no_registered_nonstructural_action"
                if not actions
                else (
                    "blocked"
                    if all(action["status"] == "blocked" for action in actions)
                    else "conditional_option"
                )
            )
            result["action_options"].extend(deepcopy(actions))
        result["findings"].append(finding)
        result["missing_inputs"].extend(missing)
        result["rule_trace"].append(
            {
                "rule_id": rule["rule_id"],
                "rule_version": data["ruleset"]["version"],
                "ruleset_id": "interior_authored_relations_v1",
                "method": "indoor_authored_relations",
                "source_ids": list(rule["source_ids"]),
                "relation_id": relation_id,
                "source_object_id": relation.source_object_id,
                "target_object_id": relation.target_object_id,
                "status": status,
                "predicate_confirmed": confirmed,
                "predicate_present": present if confirmed else None,
            }
        )
    if result["missing_inputs"]:
        result["status"] = "partial"
        result["rule_coverage_status"] = "needs_confirmation"
    return result
