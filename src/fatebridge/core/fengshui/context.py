"""Source-scoped environmental context; no natal-chart mixing or omens."""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, cast

from .context_inputs import EnvironmentalContext


@lru_cache(maxsize=1)
def _bundle() -> Dict[str, Any]:
    path = Path(__file__).parents[2] / "data" / "fengshui" / "expert-policy-v1.json"
    return cast(Dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def expert_context_provenance() -> Dict[str, Any]:
    data = _bundle()
    result = deepcopy(data["ruleset"])
    result["sources"] = [
        {"source_id": source_id, **deepcopy(data["sources"][source_id])}
        for source_id in result["source_ids"]
    ]
    result["bundle_version"] = data["bundle_version"]
    return cast(Dict[str, Any], result)


def _rule(key: str) -> Dict[str, Any]:
    return cast(Dict[str, Any], deepcopy(_bundle()["rules"][key]))


def _association_scope(methods: Iterable[str], household_scope: str) -> Dict[str, Any]:
    applicable = ["annual_stars", "monthly_stars", "xuankong_natal", "jinsuo"]
    selected = [method for method in methods if method in applicable]
    return {
        "scope": "environmental_palace_symbolic_index_not_bazhai_minggua",
        "household_scope": household_scope,
        "applicable_methods": applicable,
        "selected_applicable_methods": selected,
        "application_status": (
            "symbolic_index_for_selected_environmental_methods"
            if selected and household_scope == "environmental_binding"
            else "symbolic_reference_only"
        ),
    }


def _association(
    palace: str, kind: str, ready: bool, methods: Iterable[str], household_scope: str
) -> Dict[str, Any]:
    data = _bundle()
    opposite = data["opposite_palaces"][palace]
    return {
        **_association_scope(methods, household_scope),
        "association_kind": kind,
        "primary_palace": palace,
        "primary_direction": data["palace_directions"][palace] if ready else None,
        "opposite_palace": opposite,
        "opposite_direction": data["palace_directions"][opposite] if ready else None,
        "primary_priority": "primary",
        "opposite_priority": "secondary",
        "physical_sector_binding": "confirmed" if ready else "not_confirmed",
        "finding": "symbolic_attention_index_only",
    }


def analyze_environmental_context(
    context: Optional[EnvironmentalContext],
    selected_methods: Iterable[str],
    *,
    non_directional_scope: bool = False,
) -> Dict[str, Any]:
    """Review confirmed context without recalculating or grading any chart.

    ``confirmed_suitable`` is an explicit supplied assessment with evidence,
    never an engine-derived verdict. A local concern is not assigned to a user
    of another suitable floor only under the complete, confirmed conditions.
    """
    methods = list(selected_methods)
    result: Dict[str, Any] = {
        "status": "not_requested" if context is None else "complete",
        "ruleset": expert_context_provenance(),
        "separation_policy": {
            "environmental_chart_inputs": "objective_environment_only",
            "bazi_ziwei_favourable_elements": "excluded",
            "other_people_natal_attributes": "excluded",
            "bazhai_personal_matching": "independent_minggua_layer",
            "selected_environmental_methods": [
                method
                for method in methods
                if method
                in {"annual_stars", "monthly_stars", "xuankong_natal", "jinsuo"}
            ],
            **_rule("separation"),
        },
        "orientation_review": None,
        "household_correspondences": [],
        "floor_review": {"floors": [], "influences": []},
        "environment_findings": [],
        "missing_inputs": [],
        "rule_coverage_counts": {
            "supported": 0,
            "confirmed_unsupported": 0,
            "unknown": 0,
        },
        "rule_coverage_status": "not_requested" if context is None else "covered",
        "rule_trace": [_rule("separation")],
        "limitations": deepcopy(_bundle()["limitations"]),
    }
    if context is None:
        return result

    supported = 0
    unsupported = 0
    missing: List[str] = []
    trace_keys = ["separation"]
    orientation = context.orientation
    ready = orientation is not None and orientation.ready_for_sectors()
    needs_sector_binding = bool(
        context.floors
        or (
            context.household_members
            and context.household_scope == "environmental_binding"
        )
        or (
            context.orientation is not None
            and not context.household_members
            and not context.observations
            and not context.interior_relations
            and not context.material_facts
            and not non_directional_scope
        )
    )
    orientation_missing = []
    if needs_sector_binding:
        for name in (
            "direction_confirmed",
            "floorplan_alignment_confirmed",
            "center_confirmed",
        ):
            if orientation is None or not getattr(orientation, name):
                orientation_missing.append(f"environmental_context.orientation.{name}")
        missing.extend(orientation_missing)
    result["orientation_review"] = {
        "status": "confirmed" if ready else "not_confirmed",
        "north_reference": (
            orientation.north_reference if orientation is not None else None
        ),
        "physical_sector_binding_allowed": ready,
        "unknown_direction_policy": "confirmed_non_directional_facts_only",
        "missing_inputs": orientation_missing,
        **_rule("orientation"),
    }
    trace_keys.append("orientation")
    if orientation is not None and ready:
        supported += 1

    resident_members = [m for m in context.household_members if m.co_resident]
    members = {m.subject_id: m for m in context.household_members}
    oldest_generation = min((m.generation for m in resident_members), default=None)
    household_binding_ready = (
        ready and context.household_scope == "environmental_binding"
    )
    for member in context.household_members:
        associations = []
        withheld_roles = []
        roles = list(member.family_roles)
        rank_basis = "confirmed_own_household_rank"
        if member.follow_spouse_rank:
            assert member.spouse_subject_id is not None
            roles = [r for r in roles if r == "parent"] + [
                r
                for r in members[member.spouse_subject_id].family_roles
                if r != "parent"
            ]
            rank_basis = "explicitly_following_spouse_rank"
        if member.co_resident:
            for role in roles:
                if role == "parent":
                    if not context.household_composition_confirmed:
                        withheld_roles.append(
                            {
                                "role": role,
                                "reason": "household_composition_unconfirmed",
                            }
                        )
                        missing.append(
                            "environmental_context.household_composition_confirmed"
                        )
                        continue
                    if member.generation != oldest_generation:
                        withheld_roles.append(
                            {
                                "role": role,
                                "reason": "senior_co_resident_generation_takes_parent_palace",
                            }
                        )
                        continue
                palace = _bundle()["role_palaces"][member.gender_role][role]
                associations.append(
                    {
                        **_association(
                            palace,
                            "family_role",
                            household_binding_ready,
                            methods,
                            context.household_scope,
                        ),
                        "family_role": role,
                        "rank_basis": (
                            "confirmed_generation" if role == "parent" else rank_basis
                        ),
                        **_rule("family"),
                    }
                )
                supported += 1
            if member.zodiac is not None:
                palace = _bundle()["zodiac_palaces"][member.zodiac]
                associations.append(
                    {
                        **_association(
                            palace,
                            "confirmed_zodiac",
                            household_binding_ready,
                            methods,
                            context.household_scope,
                        ),
                        "zodiac": member.zodiac,
                        "boundary_scope": "eight_sector_symbolic_index_not_exact_24_mountain",
                        "mapping_basis": "combined_classical_branch_and_museum_zodiac_tables",
                        **_rule("zodiac"),
                    }
                )
                supported += 1
                trace_keys.append("zodiac")
            if (
                not roles
                and member.zodiac is None
                and not any(
                    member.subject_id in floor.subject_ids for floor in context.floors
                )
            ):
                missing.append(
                    f"environmental_context.household_members.{member.subject_id}.family_roles"
                )
        result["household_correspondences"].append(
            {
                **_association_scope(methods, context.household_scope),
                "subject_id": member.subject_id,
                "generation": member.generation,
                "co_resident": member.co_resident,
                "status": (
                    "symbolic_indices_available"
                    if associations
                    else "no_active_confirmed_role"
                ),
                "associations": associations,
                "withheld_roles": withheld_roles,
                "decision_making_power_used": False,
                "evidence": member.evidence,
                "effects_inferred": False,
            }
        )
    if context.household_members:
        trace_keys.extend(["family", "opposite"])

    floors = {floor.floor_id: floor for floor in context.floors}
    for floor in context.floors:
        frame_ready = ready and floor.ready_for_sectors()
        if floor.uses_shared_orientation is None:
            missing.append(
                f"environmental_context.floors.{floor.floor_id}.uses_shared_orientation"
            )
        elif floor.uses_shared_orientation is False:
            unsupported += 1
        for name in ("center_confirmed", "floorplan_alignment_confirmed"):
            if getattr(floor, name) is not True:
                missing.append(f"environmental_context.floors.{floor.floor_id}.{name}")
        result["floor_review"]["floors"].append(
            {
                "floor_id": floor.floor_id,
                "level": floor.level,
                "space_kind": floor.space_kind,
                "analysis_level": 1 if floor.space_kind == "courtyard" else floor.level,
                "direction_frame": (
                    "shared_confirmed" if frame_ready else "not_confirmed"
                ),
                "center_confirmed": floor.center_confirmed,
                "floorplan_alignment_confirmed": floor.floorplan_alignment_confirmed,
                "uses_shared_orientation": floor.uses_shared_orientation,
                "subject_ids": list(floor.subject_ids),
                "usage_confirmed": floor.usage_confirmed,
                "usage_evidence": floor.usage_evidence,
                "object_ids": list(floor.object_ids),
                "suitability": floor.suitability,
                "suitability_evidence": floor.suitability_evidence,
                "suitability_source": "explicit_input_not_engine_calculation",
                "courtyard_review_scope": (
                    ["layout", "planting", "object_shape"]
                    if floor.space_kind == "courtyard"
                    else []
                ),
                **_rule("floors"),
            }
        )
        supported += 1

    subject_ids = list(
        dict.fromkeys(
            [m.subject_id for m in resident_members]
            + [subject for floor in context.floors for subject in floor.subject_ids]
        )
    )
    for influence in context.floor_influences:
        source = floors[influence.source_floor_id]
        assignments = []
        shared_ids = set(influence.shared_floor_ids) | {source.floor_id}
        shared_levels = {floors[floor_id].level for floor_id in shared_ids}
        local_spaces = [
            floor for floor in context.floors if floor.level == source.level
        ]
        shared_spaces = [
            floor for floor in context.floors if floor.level in shared_levels
        ]
        if influence.extent == "unknown":
            missing.append(
                f"environmental_context.floor_influences.{influence.influence_id}.extent"
            )
        for subject_id in subject_ids:
            used = [f for f in context.floors if subject_id in f.subject_ids]
            if influence.extent == "shared_confirmed":
                if any(f.level in shared_levels for f in used):
                    status = "shared_review_required"
                elif all(f.usage_confirmed for f in shared_spaces):
                    status = "outside_declared_shared_scope"
                else:
                    status = "usage_confirmation_required"
                    missing.extend(
                        f"environmental_context.floors.{floor.floor_id}.usage_confirmed"
                        for floor in shared_spaces
                        if not floor.usage_confirmed
                    )
            elif influence.extent == "unknown":
                status = "scope_confirmation_required"
            elif any(f.level == source.level for f in used):
                status = "local_exposure_review_required"
            elif not used:
                status = "usage_confirmation_required"
                missing.append(
                    f"environmental_context.household_members.{subject_id}.floor_usage"
                )
            elif all(f.suitability == "confirmed_suitable" for f in used):
                if all(f.usage_confirmed for f in local_spaces):
                    status = "local_exposure_not_assigned_to_other_floor"
                else:
                    status = "usage_confirmation_required"
                    missing.extend(
                        f"environmental_context.floors.{floor.floor_id}.usage_confirmed"
                        for floor in local_spaces
                        if not floor.usage_confirmed
                    )
            else:
                status = "other_floor_suitability_not_confirmed"
                for floor in used:
                    if floor.suitability == "not_assessed":
                        missing.append(
                            f"environmental_context.floors.{floor.floor_id}.suitability"
                        )
            assignments.append(
                {
                    "subject_id": subject_id,
                    "used_floor_ids": [f.floor_id for f in used],
                    "status": status,
                    "effects_inferred": False,
                }
            )
        result["floor_review"]["influences"].append(
            {
                "influence_id": influence.influence_id,
                "source_floor_id": influence.source_floor_id,
                "extent": influence.extent,
                "shared_floor_ids": list(influence.shared_floor_ids),
                "subject_scope": assignments,
                "shared_factors_cancelled": False,
                "evidence": influence.evidence,
                **_rule("floors"),
            }
        )
        supported += 1
    result["floor_review"]["overall_review"] = (
        "shared_review_required" if context.floors else "not_requested"
    )
    if context.floors:
        trace_keys.append("floors")

    for observation in context.observations:
        modern = observation.category == "modern_design"
        rule_key = "modern" if modern else "uncovered_form"
        result["environment_findings"].append(
            {
                "observation_id": observation.observation_id,
                "object_id": observation.object_id,
                "floor_id": observation.floor_id,
                "category": observation.category,
                "feature": observation.feature,
                "present": observation.present,
                "finding": (
                    (
                        "low_priority_reminder"
                        if observation.present
                        else "feature_not_present"
                    )
                    if modern
                    else "confirmed_fact_without_specific_taboo_rule"
                ),
                "priority": "low" if modern else "unranked_without_rule",
                "recommendation": (
                    "轻度提示，结合现代使用需要抓大放小；不据此要求拆改"
                    if modern and observation.present
                    else None
                ),
                "direction_inferred": False,
                "action_required": False,
                "evidence": observation.evidence,
                **_rule(rule_key),
            }
        )
        trace_keys.append(rule_key)
        if modern:
            supported += 1
        else:
            unsupported += 1

    result["missing_inputs"] = list(dict.fromkeys(missing))
    result["status"] = "partial" if missing else "complete"
    result["rule_coverage_counts"] = {
        "supported": supported,
        "confirmed_unsupported": unsupported,
        "unknown": len(result["missing_inputs"]),
    }
    result["rule_coverage_status"] = (
        "needs_confirmation" if missing else "limited" if unsupported else "covered"
    )
    result["rule_trace"] = [_rule(key) for key in dict.fromkeys(trace_keys)]
    return result
