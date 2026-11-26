"""Source-scoped material use checks, kept separate from geometric taboos."""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, cast

from fatebridge.core.fengshui.material_application import analyze_application
from fatebridge.core.fengshui.material_inputs import MaterialShapeFact
from fatebridge.core.fengshui.workstation_sources import disagreement, provenance


@lru_cache(maxsize=1)
def _bundle() -> dict[str, Any]:
    path = Path(__file__).parents[2] / "data/fengshui/material-representations-v1.json"
    return cast(Dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def material_reference() -> dict[str, Any]:
    data = deepcopy(_bundle())
    return {
        "status": "reference_only",
        "scope": "source_scoped_representations_not_placement_prescriptions",
        "ruleset": {
            **data["ruleset"],
            "sources": [
                dict(source_id=key, **value) for key, value in data["sources"].items()
            ],
        },
        "shapes": data["shapes"],
        "materials": data["materials"],
        "colours": data["colours"],
        "limitations": data["limitations"],
    }


def analyze_material_facts(
    facts: Iterable[MaterialShapeFact], targets: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    data = _bundle()
    reference = material_reference()
    findings = []
    missing = []
    counts = dict(supported=0, confirmed_unsupported=0, unknown=0)
    trace: list[dict[str, Any]] = []
    extra_rules = {}
    for fact in facts:
        path = f"environmental_context.material_facts.{fact.fact_id}"
        pending = []
        if fact.observation_basis == "image_observed":
            pending.append(f"{path}.observation_basis")
        for field in ("material", "shape", "colour"):
            if getattr(fact, field) == "unknown":
                pending.append(f"{path}.{field}")
        shape = data["shapes"].get(fact.shape)
        material = data["materials"].get(fact.material)
        colour = data["colours"].get(fact.colour)
        target = (
            {
                "wood_remedy": "木",
                "fire_remedy": "火",
                "earth_remedy": "土",
                "metal_remedy": "金",
                "water_remedy": "水",
            }[fact.element_use]
            if fact.element_use is not None
            else None
        )
        material_status = "not_requested"
        colour_status = "not_requested"
        finding = "reference_only_no_general_taboo"
        if target is not None:
            if fact.material is None and fact.colour is None:
                pending.append(f"{path}.material_or_colour")
            if (
                fact.material == "living_plant"
                and target == "木"
                and fact.plant_alive is None
            ):
                pending.append(f"{path}.plant_alive")
            if fact.material is None:
                material_status = "not_provided"
            elif fact.material == "unknown":
                material_status = "needs_confirmation"
            elif (
                fact.material == "living_plant"
                and target == "木"
                and fact.plant_alive is None
            ):
                material_status = "needs_confirmation"
            elif fact.material == "processed_wood" and target == "木":
                material_status = "excluded_by_selected_author"
            elif fact.material == "living_plant" and fact.plant_alive is False:
                material_status = "does_not_match_living_representation"
            elif material is not None:
                material_status = (
                    "conditional_material_match"
                    if material["element"] == target
                    else "not_registered_for_requested_element"
                )
            else:
                material_status = "no_registered_material_representation"
            colour_status = (
                "not_provided"
                if fact.colour is None
                else (
                    "needs_confirmation"
                    if fact.colour == "unknown"
                    else (
                        "colour_substitute_match"
                        if colour == target
                        else "no_matching_colour_substitute"
                    )
                )
            )
            finding = (
                "conditional_material_representation"
                if material_status == "conditional_material_match"
                else (
                    "colour_substitute_only"
                    if colour_status == "colour_substitute_match"
                    else (
                        "not_determined_from_supplied_attributes"
                        if material_status in {"not_provided", "needs_confirmation"}
                        else "not_eligible_as_registered_representation"
                    )
                )
            )
        unknown = bool(pending)
        if unknown:
            counts["unknown"] += 1
        elif target is not None:
            counts["supported"] += 1
        rule_id = (
            "sourced_material_representation_v1.afsi_use_eligibility"
            if target is not None
            else "sourced_material_representation_v1.attribute_reference"
        )
        sources = ["M_AFSI"] + (["M_FSI"] if shape is not None else [])
        finding_record = {
            **fact.model_dump(),
            "finding": "needs_confirmation" if unknown else finding,
            "status": "candidate_only" if unknown else "reviewed",
            "candidate_only": unknown,
            "reference_finding": finding,
            "requested_element": target,
            "requested_element_basis": "explicit_representation_question_not_natal_or_environmental_need",
            "material_reference": deepcopy(material),
            "shape_reference": (
                {
                    **shape,
                    "source_ids": ["M_FSI"],
                    "scope": "shape_symbol_only_not_geometry_or_afsi_remedy",
                }
                if shape
                else None
            ),
            "colour_reference": colour,
            "material_eligibility": material_status,
            "colour_eligibility": colour_status,
            "shape_used_as_afsi_remedy": False,
            "placement_suitability": "not_assessed",
            "action_status": "no_action_needed",
            "action_required": False,
            "rule_id": rule_id,
            "source_ids": sources,
            "scope": "representation_eligibility_only_not_global_taboo_or_placement",
            "missing_inputs": pending,
            "coverage_reason": (
                "facts_need_confirmation"
                if unknown
                else (
                    "attribute_reference_only"
                    if target is None
                    else (
                        "excluded_by_selected_author"
                        if material_status == "excluded_by_selected_author"
                        else (
                            "preliminary_representation_match"
                            if finding
                            in {
                                "conditional_material_representation",
                                "colour_substitute_only",
                            }
                            else (
                                "does_not_match_requested_element"
                                if material_status
                                == "not_registered_for_requested_element"
                                else "no_registered_application_rule"
                            )
                        )
                    )
                )
            ),
        }
        if target is not None:
            finding_record["method_disagreements"] = [disagreement("objects")]
            extra_rules["workstation_source_boundaries_v1"] = provenance(
                "workstation_source_boundaries_v1"
            )
        if fact.application is not None:
            application = analyze_application(fact, targets or [], material_status)
            finding_record["application_analysis"] = {
                k: v for k, v in application.items() if k != "provenance"
            }
            finding_record["method_disagreements"].extend(
                application["source_disagreements"]
            )
            extra_rules[fact.application.ruleset_id] = application["provenance"]
            missing.extend(application["missing_inputs"])
            trace.append(
                dict(
                    rule_id=application["rule_id"],
                    source_ids=application["source_ids"],
                    fact_id=fact.fact_id,
                    status=application["status"],
                )
            )
            trace.extend(
                dict(
                    rule_id=c["rule_id"],
                    source_ids=c["source_ids"],
                    fact_id=fact.fact_id,
                )
                for c in application["application_conditions"]
            )
        findings.append(finding_record)
        missing.extend(pending)
        trace.append(dict(rule_id=rule_id, source_ids=sources, fact_id=fact.fact_id))
    return {
        "status": "partial" if missing else "complete",
        "findings": findings,
        "rulesets": ([reference["ruleset"]] if findings else [])
        + list(extra_rules.values()),
        "rule_trace": trace,
        "missing_inputs": list(dict.fromkeys(missing)),
        "rule_coverage_counts": counts,
        "reference_only_count": sum(f["requested_element"] is None for f in findings),
        "action_options": [],
        "limitations": reference["limitations"],
    }
