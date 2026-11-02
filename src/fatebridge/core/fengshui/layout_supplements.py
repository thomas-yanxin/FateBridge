"""Authored indoor forms and conditional element prescriptions, never scores."""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, cast

from fatebridge.core.hexagram_relations import ELEMENT_CONTROLS, ELEMENT_GENERATES

from .bazhai import placement_polarity
from .models import AssessRequest
from .surface import evaluate_surfaces, surface_provenance
from .workstation_sources import disagreement, provenance


@lru_cache(maxsize=1)
def _bundle() -> Dict[str, Any]:
    path = (
        Path(__file__).parents[2] / "data" / "fengshui" / "layout-supplements-v1.json"
    )
    return cast(Dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def supplement_provenance(key: str) -> Dict[str, Any]:
    data = _bundle()
    rule = {"ruleset_id": key, **deepcopy(data["rulesets"][key])}
    rule["sources"] = [
        dict(source_id=s, **deepcopy(data["sources"][s])) for s in rule["source_ids"]
    ]
    rule["bundle_version"] = data["bundle_version"]
    return rule


def evaluate_forms(req: AssessRequest) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    missing: List[str] = []
    for obs in req.form_observations:
        rear = obs.entrance_position in {"back", "back_left", "back_right"}
        checks = []
        for rule in _bundle()["form_rules"]:
            if obs.purpose not in rule["purposes"]:
                continue
            key = rule["criterion"]
            value = getattr(obs, key)
            if rule.get("optional") and value is None:
                continue
            matches = None if value is None else value == rule["expected"]
            if value is None:
                missing.append(f"form_observations.{obs.object_id}.{key}")
            checks.append(
                {
                    "criterion": key,
                    "observed": value,
                    "expected": rule["expected"],
                    "finding": (
                        "undetermined"
                        if matches is None
                        else "matches_rule" if matches else "opposes_rule"
                    ),
                    "candidate_only": obs.observation_basis == "image_observed",
                    "adjustment": rule["adjustment"] if matches is False else None,
                    "rule_id": rule["rule_id"],
                    "source_ids": list(rule["source_ids"]),
                }
            )
            if key == "sharp_corner_points_at_user":
                checks[-1]["method_disagreements"] = [disagreement("corners")]
        if obs.observation_basis == "image_observed":
            missing.append(
                f"form_observations.{obs.object_id}.user_or_measurement_confirmation"
            )
        if obs.purpose == "desk" and obs.window_position is not None:
            side = obs.window_position in {"left", "right"}
            checks.append(
                {
                    "criterion": "window_to_side",
                    "observed": obs.window_position,
                    "expected": "left_or_right",
                    "finding": (
                        "matches_rule"
                        if side
                        else (
                            "opposes_rule"
                            if obs.window_position == "front"
                            else "undetermined"
                        )
                    ),
                    "candidate_only": obs.observation_basis == "image_observed",
                    "adjustment": (
                        None if side else "核对是否直接面对窗及调整可行性，保留入口视野"
                    ),
                    "rule_id": "indoor_command_authored_v1.window_to_side",
                    "source_ids": ["F3"],
                }
            )
            if not side and obs.window_position != "front":
                missing.append(
                    f"form_observations.{obs.object_id}.window_side_or_direct_front_relation"
                )
        unknown = any(c["finding"] == "undetermined" for c in checks)
        finding = (
            "needs_confirmation"
            if unknown or obs.observation_basis == "image_observed"
            else (
                "adjust_position_or_layout"
                if any(c["finding"] == "opposes_rule" for c in checks)
                else "matches_selected_form_rules"
            )
        )
        mirrors = []
        if obs.entrance_visible is False:
            action_id = f"mirror:{obs.object_id}"
            pending = [
                {
                    "path": f"form_observations.{obs.object_id}.view_via_mirror",
                    "reason": "confirm_mirror_entrance_view",
                    "object_id": obs.object_id,
                    "action_id": action_id,
                    "required_for": "optional_action",
                },
                {
                    "path": f"layout_analysis.form_analysis.{obs.object_id}.object_options",
                    "reason": "verify_position_adjustment_unavailable",
                    "object_id": obs.object_id,
                    "action_id": action_id,
                    "required_for": "optional_action",
                },
            ]
            if obs.entrance_direct_line is not False:
                pending.append(
                    {
                        "path": f"form_observations.{obs.object_id}.entrance_direct_line",
                        "reason": "verify_avoid_entrance_direct_line",
                        "object_id": obs.object_id,
                        "action_id": action_id,
                        "required_for": "optional_action",
                    }
                )
            mirrors.append(
                {
                    "object": "镜面",
                    "action_id": action_id,
                    "optional": True,
                    "pending_confirmations": pending,
                    "status": (
                        "candidate_only"
                        if obs.observation_basis == "image_observed"
                        else "conditional_option"
                    ),
                    "conditions": [
                        "无法以位置/朝向调整补足入口视野",
                        "实际确认镜面能看见入口",
                        "仍需避开入口直线",
                    ],
                    "scope": "entrance_view_only_not_universal_sha_cure",
                    "rule_id": "indoor_command_authored_v1.mirror_view",
                    "source_ids": ["F1"],
                }
            )
        findings.append(
            {
                **obs.model_dump(mode="json"),
                "finding": finding,
                "checks": checks,
                "derived_geometry": {
                    "reference": "user_of_this_object_not_house_centre",
                    "entrance_in_rear_half_plane": (
                        rear if obs.entrance_position is not None else None
                    ),
                    "entrance_direct_line": obs.entrance_direct_line,
                    "relative_position_does_not_establish_direct_line": True,
                    "backing_distance_m": obs.backing_distance_m,
                    "distance_verdict": "no_sourced_numerical_threshold",
                },
                "object_options": mirrors,
                "application_scope": "selected_modern_authored_form_rules_not_all_classical_forms",
            }
        )
    return {
        "status": (
            "not_requested"
            if not req.form_observations
            else "partial" if missing else "complete"
        ),
        "findings": findings,
        "missing_inputs": missing,
        "distance_policy": "record_measurements_without_inventing_lucky_distance_cutoffs",
    }


def _effect(introduced: str, target: str) -> str:
    if introduced == target:
        return "same_element"
    if ELEMENT_GENERATES[introduced] == target:
        return "generates_target"
    if ELEMENT_GENERATES[target] == introduced:
        return "drains_target"
    if ELEMENT_CONTROLS[introduced] == target:
        return "controls_target"
    return "controlled_by_target"


def _cross_scope_effects(
    introduced: str, object_id: str, profiles: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    return [
        {
            "method": p["method"],
            "subject_id": p.get("subject_id"),
            "subject_kind": p.get("subject_kind"),
            "gender_convention": p.get("gender_convention"),
            "aspect": p["aspect"],
            "direction": p["direction"],
            "star_role": p.get("star_role"),
            "candidate_id": p.get("candidate_id"),
            "candidate_only": p.get("candidate_only", False),
            "target_element": p["star_element"],
            "relationship": _effect(introduced, p["star_element"]),
            "scope": "relationship_only_no_merged_good_bad_verdict",
        }
        for p in profiles
        if p["object_id"] == object_id
    ]


def evaluate_element_targets(
    req: AssessRequest, profiles: List[Dict[str, Any]]
) -> Dict[str, Any]:
    plans: List[Dict[str, Any]] = []
    missing: List[str] = []
    complete = True
    for request in req.element_adjustments:
        targets = [
            p
            for p in profiles
            if p["object_id"] == request.object_id
            and p["method"] == request.target_method
            and (
                request.subject_id is None or p.get("subject_id") == request.subject_id
            )
            and (request.aspect is None or p["aspect"] == request.aspect)
            and (request.star_role is None or p.get("star_role") == request.star_role)
        ]
        if not targets:
            complete = False
            missing.append(f"element_adjustments.{request.request_id}.computed_target")
            plans.append(
                {
                    "request_id": request.request_id,
                    "object_id": request.object_id,
                    "status": "needs_computed_target",
                    "reason": "所选层/位置/作用域尚无可绑定的计算事实，不能生成物件候选",
                }
            )
        for target in targets:
            identity = {
                k: target[k]
                for k in (
                    "method",
                    "subject_id",
                    "subject_kind",
                    "gender_convention",
                    "aspect",
                    "direction",
                    "star_role",
                    "candidate_id",
                    "candidate_only",
                )
                if k in target
            }
            plan = {
                "request_id": request.request_id,
                "object_id": request.object_id,
                "goal": request.goal,
                "goal_evidence": request.evidence,
                "target_scope": identity,
                "target_element": target["star_element"],
                "rule_id": "afsi_element_balance_v1.selected_goal",
                "source_ids": ["E1"],
                "needed": "not_inferred_from_personal_trigram",
            }
            if target["purpose"] == "stove" and target["aspect"] == "location":
                complete = False
                plans.append(
                    {
                        **plan,
                        "status": "unsupported_application",
                        "reason": "灶座凶方属特殊用途，本版本未有以物件调节灶座星的来源，不能按普通凶星削弱",
                    }
                )
                continue
            if target["method"] == "bazhai":
                expected = placement_polarity(target["purpose"], target["aspect"])
                matches = target["star"]["polarity"] == expected
                if (request.goal == "drain" and matches) or (
                    request.goal == "support" and not matches
                ):
                    plans.append(
                        {
                            **plan,
                            "status": "not_indicated_by_current_rule",
                            "reason": "所选目标与当前用途判定不一致，不据此要求新增物件",
                        }
                    )
                    continue
            introduced = (
                target["draining_element"]
                if request.goal == "drain"
                else target["generating_element"]
            )
            candidate = bool(target.get("candidate_only"))
            if candidate:
                complete = False
                missing.append(
                    f"element_adjustments.{request.request_id}.unambiguous_target_chart"
                )
            plans.append(
                {
                    **plan,
                    "status": "candidate_only" if candidate else "conditional_options",
                    "introduced_element": introduced,
                    "relationship": _effect(introduced, target["star_element"]),
                    "representations": deepcopy(
                        _bundle()["representations"][introduced]
                    ),
                    "representation_precedence": "actual_element_before_colour_substitute",
                    "cross_scope_effects": _cross_scope_effects(
                        introduced, request.object_id, profiles
                    ),
                    "application_scope": "selected_afsi_element_goal_not_cancelled_orientation_or_verified_fortune_effect",
                    "purchase_required": False,
                    "quantity_or_weight": None,
                }
            )
    return {
        "status": (
            "not_requested"
            if not req.element_adjustments
            else "complete" if complete else "partial"
        ),
        "findings": plans,
        "missing_inputs": missing,
    }


def evaluate_annual_remedies(
    req: AssessRequest, layers: Dict[str, Any], profiles: List[Dict[str, Any]]
) -> Dict[str, Any]:
    if req.annual_remedy_ruleset_id is None:
        return {"status": "not_requested", "findings": [], "missing_inputs": []}
    annual = layers.get("annual_stars", {})
    year = annual.get("effective_year")
    policy = _bundle()["annual_remedies"]
    if year is None:
        return {
            "status": "partial",
            "findings": [],
            "missing_inputs": ["annual_stars.query_at_or_effective_year"],
        }
    if year != policy["effective_year"]:
        return {
            "status": "unsupported_year",
            "effective_year": year,
            "supported_effective_year": policy["effective_year"],
            "findings": [],
            "missing_inputs": [],
            "reason": "已登记作者规则只覆盖2026年；不把该年度物件规则外推到其他年份",
        }
    findings: List[Dict[str, Any]] = []
    missing: List[str] = []
    if not req.placements:
        missing.append("annual_remedies.placements")
    for placement in req.placements:
        if placement.location_direction is None:
            missing.append(f"placements.{placement.object_id}.location_direction")
            findings.append(
                {
                    "object_id": placement.object_id,
                    "status": "needs_location",
                    "reason": "年盘调节依对象所在宫位，面朝方向不能代替位置",
                }
            )
            continue
        palace = annual["palaces"][placement.location_direction]
        matches = [
            r
            for r in policy["entries"]
            if r["direction"] == placement.location_direction
            and r["annual_star_number"] == palace["annual_star_number"]
        ]
        if not matches:
            findings.append(
                {
                    "object_id": placement.object_id,
                    "direction": placement.location_direction,
                    "status": "no_registered_prescription",
                    "annual_star_number": palace["annual_star_number"],
                }
            )
        for rule in matches:
            element = rule["introduced_element"]
            findings.append(
                {
                    **deepcopy(rule),
                    "object_id": placement.object_id,
                    "status": "conditional_author_rule",
                    "effective_year": year,
                    "time_context": annual["time_context"],
                    "target_element": palace["annual_star"]["element"],
                    "relationship": _effect(element, palace["annual_star"]["element"]),
                    "representations": deepcopy(_bundle()["representations"][element]),
                    "cross_scope_effects": _cross_scope_effects(
                        element, placement.object_id, profiles
                    ),
                    "application_scope": "selected_2026_annual_author_policy_not_whole_house_or_personal_cure",
                    "purchase_required": False,
                    "quantity_or_weight": None,
                }
            )
    return {
        "status": "partial" if missing else "complete",
        "findings": findings,
        "missing_inputs": missing,
        "effective_year": year,
    }


def analyze_supplements(
    req: AssessRequest, layers: Dict[str, Any], profiles: List[Dict[str, Any]]
) -> Dict[str, Any]:
    forms = evaluate_forms(req)
    targets = evaluate_element_targets(req, profiles)
    annual = evaluate_annual_remedies(req, layers, profiles)
    keys: List[str] = []
    if req.form_observations:
        keys.append(req.form_ruleset_id)
    if req.element_adjustments:
        keys.append(req.element_ruleset_id)
    if req.annual_remedy_ruleset_id is not None:
        keys.append(req.annual_remedy_ruleset_id)
    statuses = {
        "forms": forms["status"],
        "element_adjustments": targets["status"],
        "annual_remedies": annual["status"],
    }
    surface = evaluate_surfaces(req) if req.surface_layouts else None
    extra = {}
    if surface is not None:
        statuses["surfaces"] = surface["status"]
        extra["surface_analysis"] = surface
    corner_review = any(
        c["criterion"] == "sharp_corner_points_at_user"
        for f in forms["findings"]
        for c in f["checks"]
    )
    return {
        "form_analysis": forms,
        "element_remedies": targets["findings"],
        "annual_remedies": annual,
        "supplemental_rulesets": [supplement_provenance(key) for key in keys]
        + ([surface_provenance()] if surface is not None else [])
        + ([provenance("workstation_source_boundaries_v1")] if corner_review else []),
        "supplement_statuses": statuses,
        "missing_inputs": list(
            dict.fromkeys(
                forms["missing_inputs"]
                + targets["missing_inputs"]
                + annual["missing_inputs"]
                + (surface["missing_inputs"] if surface is not None else [])
            )
        ),
        "incomplete_requested_supplements": any(
            s not in {"not_requested", "complete"} for s in statuses.values()
        ),
        "method_disagreements": ([disagreement("corners")] if corner_review else [])
        + (
            deepcopy(_bundle()["method_disagreements"])
            if req.element_adjustments or req.annual_remedy_ruleset_id is not None
            else []
        ),
        **extra,
    }
