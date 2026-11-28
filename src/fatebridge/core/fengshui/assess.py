"""Clean multi-layer layout assessment: placements, 4-layer palace overlay, and elements."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fatebridge.core.fengshui.bazhai import placement_application
from fatebridge.core.fengshui.directions import AnnualStarInfo, raw_rule_data
from fatebridge.core.fengshui.models import AssessRequest
from fatebridge.core.hexagram_relations import ELEMENT_CONTROLS, ELEMENT_GENERATES


def element_relationships(element: str) -> dict[str, str]:
    return {
        "same_element": element,
        "generating_element": next(
            k for k, v in ELEMENT_GENERATES.items() if v == element
        ),
        "draining_element": ELEMENT_GENERATES[element],
        "controlling_element": next(
            k for k, v in ELEMENT_CONTROLS.items() if v == element
        ),
        "controlled_element": ELEMENT_CONTROLS[element],
    }


def analyze_layout(req: AssessRequest, layers: dict[str, Any]) -> dict[str, Any]:
    """Apply calculated chart layers to supplied placements and features (no prescriptions)."""
    missing: list[str] = []
    findings: list[dict[str, Any]] = []
    options: list[dict[str, Any]] = []
    elements: list[dict[str, Any]] = []

    bazhai_layer = layers.get("bazhai", {})
    annual_layer = layers.get("annual_stars", {})
    monthly_layer = layers.get("monthly_stars", {})
    natal_layer = layers.get("xuankong_natal", {})
    annual_table = raw_rule_data("annual_stars")
    directions_list = list(raw_rule_data("directions"))

    charts: list[tuple[str, str, str | None, bool, dict[str, Any], dict[str, Any]]] = []
    if bazhai_layer.get("house_candidates"):
        for cand in bazhai_layer["house_candidates"]:
            charts.append(
                (
                    cand["object_id"],
                    "house",
                    None,
                    cand["candidate_only"],
                    cand["sectors"],
                    {"house_candidate_id": cand["candidate_id"]},
                )
            )
    elif bazhai_layer.get("house"):
        h = bazhai_layer["house"]
        charts.append((h["object_id"], "house", None, False, h["sectors"], {}))
    for person in bazhai_layer.get("occupants", []):
        for cand in person["candidates"]:
            charts.append(
                (
                    person["subject_id"],
                    "occupant",
                    cand["gender"],
                    person["status"] != "complete",
                    cand["sectors"],
                    {},
                )
            )

    def add_element(
        entry: dict[str, Any], star: AnnualStarInfo | Mapping[str, Any]
    ) -> None:
        elements.append(
            {
                "object_id": entry["object_id"],
                "method": entry["method"],
                "direction": entry["direction"],
                "star_element": star["element"],
                **element_relationships(star["element"]),
            }
        )

    for placement in req.placements:
        common = {
            "object_id": placement.object_id,
            "purpose": placement.purpose,
        }
        location = placement.location_direction
        if location is None and any(
            m in layers
            for m in ("bazhai", "annual_stars", "monthly_stars", "xuankong_natal")
        ):
            missing.append(f"placements.{placement.object_id}.location_direction")

        for aspect, direction in (
            ("location", location),
            ("facing", placement.facing_direction),
        ):
            if direction is None or "bazhai" not in layers:
                continue
            scope_options = []
            confirmed_sets = []
            for subject, kind, convention, cand_only, chart, cand_ctx in charts:
                if kind == "occupant" and not placement.applies_to_occupant(subject):
                    continue
                matching = [
                    d
                    for d, p in chart.items()
                    if placement_application(p, placement.purpose, aspect)[
                        "matches_convention"
                    ]
                ]
                app = placement_application(chart[direction], placement.purpose, aspect)
                entry = {
                    **common,
                    "method": "bazhai",
                    "subject_id": subject,
                    "subject_kind": kind,
                    "gender": convention,
                    **cand_ctx,
                    "candidate_only": cand_only,
                    "aspect": aspect,
                    "direction": direction,
                    **app,
                }
                findings.append(entry)
                add_element(entry, chart[direction]["star"])
                scope_options.append(
                    {
                        "subject_id": subject,
                        "subject_kind": kind,
                        "gender": convention,
                        "candidate_only": cand_only,
                        "matches_convention": app["matches_convention"],
                        "matching_directions": matching,
                    }
                )
                if not cand_only:
                    confirmed_sets.append(set(matching))
            intersection = (
                set.intersection(*confirmed_sets) if confirmed_sets else set()
            )
            options.append(
                {
                    **common,
                    "aspect": aspect,
                    "current_direction": direction,
                    "agreed_matching_directions": [
                        d for d in directions_list if d in intersection
                    ],
                    "scopes": scope_options,
                }
            )

        if location is None:
            continue
        if "annual_stars" in layers:
            if annual_layer.get("palaces"):
                palace = annual_layer["palaces"][location]
                entry = {
                    **common,
                    "method": "annual_stars",
                    "aspect": "location",
                    "direction": location,
                    "effective_year": annual_layer["effective_year"],
                    "annual_star_number": palace["annual_star_number"],
                    "annual_star": palace["annual_star"],
                }
                findings.append(entry)
                add_element(entry, palace["annual_star"])
            else:
                missing.extend(annual_layer["missing_inputs"])
        if "monthly_stars" in layers:
            if monthly_layer.get("palaces"):
                palace = monthly_layer["palaces"][location]
                findings.append(
                    {
                        **common,
                        "method": "monthly_stars",
                        "aspect": "location",
                        "direction": location,
                        "monthly_star_number": palace["monthly_star_number"],
                        "monthly_star": palace["monthly_star"],
                    }
                )
            else:
                missing.extend(monthly_layer["missing_inputs"])
        if "xuankong_natal" in layers:
            natal_charts = (
                [natal_layer["chart"]]
                if natal_layer.get("chart") is not None
                else natal_layer.get("candidates", [])
            )
            if not natal_charts:
                missing.extend(natal_layer["missing_inputs"])
            for cand in natal_charts:
                palace = cand["palaces"][location]
                entry = {
                    **common,
                    "method": "xuankong_natal",
                    "aspect": "location",
                    "direction": location,
                    "candidate_id": cand["candidate_id"],
                    "candidate_only": natal_layer["status"] != "complete",
                    "period_number": cand["period_number"],
                    "palace": palace,
                }
                findings.append(entry)
                for role in ("period", "mountain", "facing"):
                    num = palace[f"{role}_star_number"]
                    add_element({**entry, "star_role": role}, annual_table[str(num)])

    environment = [
        {
            **f,
            "target_classification": (
                f["preferred_classification"]
                if f["finding"] != "undetermined"
                else None
            ),
        }
        for f in layers.get("jinsuo", {}).get("feature_findings", [])
    ]
    for layer in layers.values():
        missing.extend(layer["missing_inputs"])

    return {
        "status": "partial" if missing else "complete",
        "calculation_scope": "selected_methods_on_supplied_objects",
        "placement_findings": findings,
        "adjustment_options": options,
        "environment_adjustments": environment,
        "element_relationships": elements,
        "missing_inputs": list(dict.fromkeys(missing)),
    }
