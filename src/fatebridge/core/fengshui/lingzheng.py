"""Fixed period directions and flying-star requirements are different objects."""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, cast

from .directions import rule_data
from .lingzheng_inputs import FixedLingzhengRequest, LingzhengObservation


@lru_cache(maxsize=1)
def _data() -> Dict[str, Any]:
    p = Path(__file__).parents[2] / "data/fengshui/fixed-lingzheng-v1.json"
    return cast(Dict[str, Any], json.loads(p.read_text(encoding="utf-8")))


def lingzheng_provenance() -> Dict[str, Any]:
    data = _data()
    return {
        **deepcopy(data["ruleset"]),
        "sources": [
            dict(source_id=k, **deepcopy(v)) for k, v in data["sources"].items()
        ],
    }


def _condition(
    role: str, observation: Optional[LingzhengObservation], ambiguous: bool
) -> Dict[str, Any]:
    requirements = (
        ["high_solid_terrain_present"]
        if role == "zheng"
        else (
            ["low_lying_terrain_present", "river_water_present"]
            if role == "ling"
            else []
        )
    )
    facts = {
        key: getattr(observation, key) if observation else None for key in requirements
    }
    match = (
        False
        if False in facts.values()
        else None if not facts or None in facts.values() else True
    )
    image = (
        observation is not None and observation.observation_basis == "image_observed"
    )
    candidate = bool(requirements) and (ambiguous or image)
    return {
        "rule_id": "shen_fixed_lingzheng_v1.selected_form_presence",
        "source_ids": ["SFL3"],
        "status": (
            "rule_not_covered_not_inauspicious"
            if not requirements
            else (
                "candidate_only"
                if candidate
                else (
                    "needs_confirmation"
                    if match is None
                    else (
                        "selected_presence_matched"
                        if match
                        else "selected_presence_not_matched"
                    )
                )
            )
        ),
        "requirements": requirements,
        "observed": facts,
        "raw_condition_match": match,
        "condition_match": None if candidate else match,
        "candidate_only": candidate,
        "evidence": observation.model_dump(mode="json") if observation else None,
        "scope": "specified_presence_only_not_complete_quality_site_or_action_verdict",
    }


def analyze_fixed_lingzheng(
    config: FixedLingzhengRequest, current: Optional[int], natal: Dict[str, Any]
) -> Dict[str, Any]:
    """Use the explicit evaluation period; never rewrite a chart or select a half."""
    if current is not None and (
        type(current) is not int or current not in range(1, 10)
    ):
        raise ValueError("评价运必须为1至9的整数")
    if config.five_period_half is not None and current != 5:
        raise ValueError("五运分段仅适用于明确评价五运")
    directions = rule_data("directions")
    by_number = {p["palace_number"]: d for d, p in directions.items()}
    observations = {o.direction: o for o in config.observations}
    charts = natal.get("candidates", [])
    if not charts and natal.get("chart"):
        charts = [natal["chart"]]
    variants = []
    missing = []
    if not charts:
        missing.append("interpretation.fixed_lingzheng.computed_natal_for_comparison")
    if current is None:
        missing.append("interpretation.current_period_number")
    elif current == 5:
        halves = (
            [config.five_period_half]
            if config.five_period_half
            else ["first_decade", "second_decade"]
        )
        if config.five_period_half is None:
            missing.append("interpretation.fixed_lingzheng.five_period_half")
        for half in halves:
            variants.append(
                {
                    "five_period_half": half,
                    **deepcopy(_data()["five_period_hosting"][half]),
                }
            )
    else:
        variants.append(
            {
                "five_period_half": None,
                "zheng_direction": by_number[current],
                "ling_direction": by_number[10 - current],
                "ling_number": 10 - current,
            }
        )
    ambiguous = len(variants) > 1
    results = []
    trace = []
    for variant in variants:
        fixed_id = (
            f"fixed_period_{current}_{variant['five_period_half'] or 'whole_period'}"
        )
        palaces = {}
        for direction in directions:
            role = (
                "zheng"
                if direction == variant["zheng_direction"]
                else (
                    "ling" if direction == variant["ling_direction"] else "not_selected"
                )
            )
            condition = _condition(role, observations.get(direction), ambiguous)
            if condition["status"] in {"needs_confirmation", "candidate_only"}:
                prefix = f"interpretation.fixed_lingzheng.observations.{direction}"
                missing.extend(
                    f"{prefix}.{key}"
                    for key, value in condition["observed"].items()
                    if value is None
                )
                if (
                    observations.get(direction)
                    and observations[direction].observation_basis == "image_observed"
                ):
                    missing.append(f"{prefix}.user_or_measurement_confirmation")
            comparisons = []
            for chart in charts:
                p = chart["palaces"][direction]
                current_roles = [
                    r
                    for r in ("mountain", "facing")
                    if p[f"{r}_star_number"] == current
                ]
                same = (
                    "mountain"
                    if role == "zheng"
                    else "facing" if role == "ling" else None
                )
                comparisons.append(
                    {
                        "candidate_id": chart["candidate_id"],
                        "candidate_only": ambiguous or len(charts) > 1,
                        "natal_period_number": chart["period_number"],
                        "mountain_star_number": p["mountain_star_number"],
                        "facing_star_number": p["facing_star_number"],
                        "matching_current_star_roles": [
                            r for r in current_roles if r == same
                        ],
                        "different_current_star_roles": [
                            r for r in current_roles if same is not None and r != same
                        ],
                        "scope": "broad_requirement_alignment_only_not_equal_criteria_or_site_verdict",
                    }
                )
            palaces[direction] = {
                "fixed_palace_number": directions[direction]["palace_number"],
                "role": role,
                "form_assessment": condition,
                "flying_star_comparisons": comparisons,
            }
            if role != "not_selected":
                trace.append(
                    {
                        "candidate_id": fixed_id,
                        "direction": direction,
                        "fixed_role": role,
                        **deepcopy(condition),
                    }
                )
                trace.extend(
                    {
                        "rule_id": "shen_fixed_lingzheng_v1.fixed_vs_flying",
                        "source_ids": ["SFL3"],
                        "fixed_candidate_id": fixed_id,
                        "direction": direction,
                        "fixed_role": role,
                        "reference_period_number": current,
                        **deepcopy(comparison),
                    }
                    for comparison in comparisons
                )
        item = {
            "candidate_id": fixed_id,
            "candidate_only": ambiguous,
            "reference_period_number": current,
            **variant,
            "zheng_number": current,
            "zheng_native_palace": "C" if current == 5 else variant["zheng_direction"],
            "five_hosting_scope": (
                "fixed_ground_only_not_natal_seed_borrowing"
                if current == 5
                else "not_applicable"
            ),
            "palaces": palaces,
        }
        results.append(item)
        trace.append(
            {
                "rule_id": "shen_fixed_lingzheng_v1.period_and_hosting",
                "source_ids": ["SFL1", "SFL3"],
                "candidate_id": item["candidate_id"],
                "evidence": {
                    "explicit_current_period_number": current,
                    "five_period_half": variant["five_period_half"],
                    "half_evidence": config.half_evidence,
                },
                "zheng_direction": variant["zheng_direction"],
                "ling_direction": variant["ling_direction"],
            }
        )
    return {
        "status": "partial" if missing else "complete",
        "calculation_status": "complete" if current is not None else "partial",
        "selection_status": (
            "requires_five_period_half"
            if ambiguous
            else "resolved" if current is not None else "needs_current_period"
        ),
        "ruleset": lingzheng_provenance(),
        "reference_period_number": current,
        "flying_star_comparison_status": (
            "partial"
            if not charts
            else "candidate_only" if len(charts) > 1 else "complete"
        ),
        "reference_frame": "fixed_houtian_house_centred_magnetic_palaces_not_natal_or_annual_plate",
        "candidates": results,
        "missing_inputs": list(dict.fromkeys(missing)),
        "rule_trace": trace,
        "overall_auspiciousness": "not_produced",
    }
