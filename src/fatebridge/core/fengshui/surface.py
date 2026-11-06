"""Sourced surface options and a separate feasibility filter; no case scoring."""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

from .surface_inputs import SurfaceItem

if TYPE_CHECKING:
    from .models import AssessRequest


@lru_cache(maxsize=1)
def _data() -> Dict[str, Any]:
    path = Path(__file__).parents[2] / "data/fengshui/desktop-bagua-v1.json"
    return cast(Dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def surface_provenance() -> Dict[str, Any]:
    data = _data()
    rule = cast(Dict[str, Any], deepcopy(data["ruleset"]))
    rule["sources"] = [
        {"source_id": key, **deepcopy(data["sources"][key])}
        for key in rule["source_ids"]
    ]
    rule["bundle_version"] = data["bundle_version"]
    return rule


def summarize_analysis_progress(
    missing: List[str],
    counts: Dict[str, int],
    actions: List[Dict[str, Any]],
    pending: List[Dict[str, Any]],
    *,
    count_unit: str,
    limited: bool = False,
    conditional_basis_count: int = 0,
    reference_basis_count: int = 0,
) -> Dict[str, Any]:
    """Separate review completeness from whether a candidate can be executed.

    Counts describe supplied items/checks and candidate actions, never the number
    of traditional rules. Optional and blocked actions do not prevent finishing
    the review of known facts; their status remains visible separately.
    """
    action_counts = dict(ready=0, conditional=0, candidate=0, blocked=0)
    status_keys = {
        "ready": "ready",
        "conditional_option": "conditional",
        "candidate_only": "candidate",
        "blocked": "blocked",
    }
    for action in actions:
        key = status_keys.get(action.get("status", ""))
        if key:
            action_counts[key] += 1
    readiness = set()
    if action_counts["ready"]:
        readiness.add("ready")
    if action_counts["conditional"] or action_counts["candidate"]:
        readiness.add("needs_confirmation")
    if action_counts["blocked"]:
        readiness.add("blocked")
    calculation_complete = not missing and not counts["unknown"]
    # A partial calculation can still support an explanation. Unknown values
    # alone are not a conditional basis: callers count actual observed facts.
    interpretation_status = (
        "available"
        if counts["supported"] or reference_basis_count
        else (
            "conditional"
            if conditional_basis_count
            else (
                "scope_only"
                if counts["confirmed_unsupported"]
                or (limited and not missing and not counts["unknown"])
                else "insufficient_evidence"
            )
        )
    )
    unique_pending = list(
        {json.dumps(p, sort_keys=True, ensure_ascii=False): p for p in pending}.values()
    )
    conclusion_paths = list(
        dict.fromkeys(
            p["path"] for p in unique_pending if p["required_for"] == "assessment"
        )
    )
    return {
        "interpretation_status": interpretation_status,
        "follow_up": {
            # Reference existing confirmation records, rather than duplicate
            # their full payload in the default response budget.
            "conclusion_candidates": conclusion_paths,
            "execution_only": list(
                dict.fromkeys(
                    p["path"]
                    for p in unique_pending
                    if p["required_for"] != "assessment"
                    and p["path"] not in conclusion_paths
                )
            ),
            "selection_policy": "ask_only_if_changes_requested_conclusion",
            "unsupported_policy": "explain_limit_without_requesting_more_input",
        },
        "calculation_status": "complete" if calculation_complete else "partial",
        "rule_coverage_status": (
            "needs_confirmation"
            if missing or counts["unknown"]
            else "limited" if limited else "reviewed"
        ),
        "assessment_complete": calculation_complete,
        "rule_coverage_count_unit": count_unit,
        "rule_coverage_counts": counts,
        "action_readiness": (
            (
                "no_action_needed"
                if calculation_complete and not limited
                else "not_evaluated"
            )
            if not readiness
            else next(iter(readiness)) if len(readiness) == 1 else "mixed"
        ),
        "action_count_unit": "candidate_actions",
        "action_counts": action_counts,
        "optional_action_count": sum(
            bool(a.get("optional")) for a in actions if a.get("status") in status_keys
        ),
        "pending_confirmations": unique_pending,
    }


def evaluate_surfaces(req: "AssessRequest") -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    missing: List[str] = []
    constraints = {c.object_id: c for c in req.surface_constraints}
    uncovered: List[str] = []
    counts = dict(supported=0, confirmed_unsupported=0, unknown=0)
    all_actions: List[Dict[str, Any]] = []
    pending: List[Dict[str, Any]] = []
    for surface in req.surface_layouts:
        constraint = constraints.get(surface.object_id)
        options: List[Dict[str, Any]] = []
        item_findings: List[Dict[str, Any]] = []
        selected = [e for e in _data()["entries"] if surface.goal in e["goals"]]
        if surface.observation_basis == "image_observed":
            missing.append(
                f"surface_layouts.{surface.object_id}.confirmed_boundary_and_anchor"
            )
            pending.append(
                {
                    "path": f"surface_layouts.{surface.object_id}.observation_basis",
                    "reason": "confirm_surface_boundary_and_anchor",
                    "object_id": surface.object_id,
                    "required_for": "assessment",
                }
            )
        for observed_item in surface.items:
            matches = [
                e
                for e in selected
                if observed_item.representation in e["representations"]
            ]
            unconfirmed = (
                observed_item.representation == "unknown"
                or observed_item.observation_basis == "image_observed"
            )
            coverage_status = (
                "needs_confirmation"
                if unconfirmed
                else "reviewed_supported" if matches else "reviewed_unsupported"
            )
            counts[
                (
                    "unknown"
                    if unconfirmed
                    else "supported" if matches else "confirmed_unsupported"
                )
            ] += 1
            if unconfirmed:
                pending.append(
                    {
                        "path": f"surface_layouts.{surface.object_id}.items.{observed_item.object_id}.representation",
                        "reason": "confirm_item_representation",
                        "object_id": surface.object_id,
                        "item_id": observed_item.object_id,
                        "required_for": "assessment",
                    }
                )
            item_findings.append(
                {
                    "object_id": observed_item.object_id,
                    "label": observed_item.label,
                    "observed_zone": observed_item.zone,
                    "zone_observation_basis": observed_item.zone_observation_basis,
                    "representation": observed_item.representation,
                    "observation_basis": observed_item.observation_basis,
                    "evidence": observed_item.evidence,
                    "status": (
                        "sourced_option_available"
                        if matches
                        else "no_independent_placement_rule"
                    ),
                    "rule_coverage_status": coverage_status,
                    "rule_ids": [e["rule_id"] for e in matches],
                    "inference_policy": "name_does_not_establish_element_or_lucky_side",
                }
            )
            if not matches:
                uncovered.append(observed_item.object_id)
            elif observed_item.observation_basis == "image_observed":
                missing.append(
                    f"surface_layouts.{surface.object_id}.items.{observed_item.object_id}.confirmed_representation"
                )
        for entry in selected:
            items = [
                i for i in surface.items if i.representation in entry["representations"]
            ]
            # No matching object is an explicit optional representation, not an
            # instruction to purchase or to reclassify an unrelated possession.
            candidates: List[Optional[SurfaceItem]] = list(items) if items else [None]
            for item in candidates:
                retain = (
                    item is not None
                    and item.zone == entry["zone"]
                    and item.zone_observation_basis != "image_observed"
                )
                blocks = []
                if constraint:
                    if entry["zone"] in constraint.unavailable_zones:
                        blocks.append("target_zone_unavailable")
                    if item is None and constraint.can_add_items is False:
                        blocks.append("additions_forbidden")
                    if item is not None and not retain:
                        if constraint.can_move_items is False:
                            blocks.append("moving_items_forbidden")
                        if item.object_id in constraint.locked_item_ids:
                            blocks.append("item_locked")
                candidate = surface.observation_basis == "image_observed" or (
                    item is not None and item.observation_basis == "image_observed"
                )
                permission = constraint is not None and (
                    retain
                    or (
                        constraint.can_add_items
                        if item is None
                        else constraint.can_move_items
                    )
                    is True
                )
                feasible = (
                    constraint is not None
                    and entry["zone"] in constraint.feasible_zones
                )
                status = (
                    "blocked"
                    if blocks
                    else (
                        "candidate_only"
                        if candidate
                        else (
                            "ready" if permission and feasible else "conditional_option"
                        )
                    )
                )
                action_id = f"surface-{len(all_actions) + len(options)}"
                action_pending: List[Dict[str, Any]] = []

                def need(path: str, reason: str) -> None:
                    action_pending.append(
                        {
                            "path": path,
                            "reason": reason,
                            "object_id": surface.object_id,
                            **({"item_id": item.object_id} if item else {}),
                            "action_id": action_id,
                            "required_for": "action" if item else "optional_action",
                        }
                    )

                if status != "blocked":
                    if surface.observation_basis == "image_observed":
                        need(
                            f"surface_layouts.{surface.object_id}.observation_basis",
                            "confirm_surface_boundary_and_anchor",
                        )
                    if item is not None and item.observation_basis == "image_observed":
                        need(
                            f"surface_layouts.{surface.object_id}.items.{item.object_id}.representation",
                            "confirm_item_representation",
                        )
                    if not permission and not retain:
                        need(
                            f"surface_constraints.{surface.object_id}."
                            + ("can_add_items" if item is None else "can_move_items"),
                            "confirm_action_permission",
                        )
                    if not feasible:
                        need(
                            f"surface_constraints.{surface.object_id}.feasible_zones",
                            "confirm_target_zone_feasibility",
                        )
                pending.extend(action_pending)
                options.append(
                    {
                        "surface_id": surface.object_id,
                        "action_id": action_id,
                        "optional": item is None,
                        "pending_confirmations": action_pending,
                        "item_id": item.object_id if item else None,
                        "action": (
                            "retain_item"
                            if retain
                            else "place_item" if item else "consider_representation"
                        ),
                        "status": status,
                        "from_zone": item.zone if item else None,
                        "from_zone_basis": (
                            item.zone_observation_basis if item else None
                        ),
                        "to_zone": entry["zone"],
                        "to_zone_label": entry["zone_label"],
                        "representations": list(entry["representations"]),
                        "rule_id": entry["rule_id"],
                        "source_ids": list(entry["source_ids"]),
                        "traditional_reason": entry["reason"],
                        "conditions": list(entry["conditions"]),
                        "constraint_reasons": blocks,
                        "constraint_evidence": (
                            constraint.evidence if constraint else None
                        ),
                        "scope": "authored_seated_desktop_symbolism_not_compass_or_fortune_effect",
                        "changes_compass_result": False,
                    }
                )
        all_actions.extend(options)
        findings.append(
            {
                "object_id": surface.object_id,
                "goal": surface.goal,
                "reference_frame": surface.anchor,
                "division": "three_equal_rows_and_columns_of_confirmed_rectangular_surface",
                "rule_id": "desktop_bagua_btb_v1.seated_grid",
                "source_ids": ["D1", "D3"],
                "boundary_basis": surface.observation_basis,
                "boundary_evidence": surface.evidence,
                "item_findings": item_findings,
                "action_options": options,
            }
        )
    return {
        "status": "partial" if missing or uncovered else "complete",
        "findings": findings,
        "missing_inputs": missing,
        "uncovered_item_ids": uncovered,
        "analysis_progress": summarize_analysis_progress(
            missing,
            counts,
            all_actions,
            pending,
            count_unit="surface_items",
            conditional_basis_count=sum(
                item["rule_coverage_status"] == "needs_confirmation"
                and bool(item["rule_ids"])
                for finding in findings
                for item in finding["item_findings"]
            ),
        ),
        "coverage_scope": "selected_goal_and_explicit_representations_not_every_object",
        "method_separation": "desktop_zones_never_substitute_for_house_palaces_or_minggua",
    }
