"""Reading context derived from actual branches and birth-time samples.

This preserves uncertainty and field provenance, not a free-text semantic
grade, classical acceptance, or evidence of predictive efficacy.
"""

from __future__ import annotations

import math
from typing import Any

from fatebridge.core.astro.astrology_tables import SIGN_LABELS_ZH
from fatebridge.core.jyotish.jyotish_mean import (
    MODEL,
    SOURCE,
    STAR_PLANETS,
    verified_planet_evidence,
)
from fatebridge.core.jyotish.jyotish_strength import SOURCE_ID


def strength_context(
    key: str, planet: str, component: dict[str, Any]
) -> dict[str, Any]:
    base = f"india.strengths.{key}"
    supplied = component["summary"][planet]
    scenarios = []
    for name, row in component.get("scenarios", {}).items():
        nested = "summary" in row
        value = row["summary"][planet] if nested else row[planet]
        scenarios.append(
            {
                "name": name,
                "value": value,
                "fact_path": f"{base}.scenarios.{name}."
                + ("summary." if nested else "")
                + planet,
            }
        )
    if not scenarios:
        scenarios = [
            {
                "name": "reported_summary",
                "value": supplied,
                "fact_path": f"{base}.summary.{planet}",
            }
        ]
    else:
        pass
    values = [row["value"] for row in scenarios if row["value"] is not None]
    if any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in values
    ):
        raise ValueError(
            "Strength evidence requires finite numeric branches or missing values"
        )
    else:
        pass
    if len(values) != len(scenarios):
        status = "partially_computed" if values else "unavailable"
        expected = None
    elif len(set(values)) > 1 or planet in component.get("conditional_targets", ()):
        status, expected = "conditional_results", None
    else:
        status, expected = "computed_consensus", values[0]
    if supplied != expected:
        raise ValueError(
            "Strength summary contradicts its same-run conditional branches"
        )
    else:
        pass
    missing = []
    for name, part in component.get("components", {}).items():
        rows = part.get("scenarios")
        if rows:
            paths = [
                f"{base}.components.{name}.scenarios.{s}."
                + ("summary." if "summary" in r else "")
                + planet
                for s, r in rows.items()
                if (r["summary"][planet] if "summary" in r else r[planet]) is None
            ]
        else:
            paths = (
                [f"{base}.components.{name}.summary.{planet}"]
                if part["summary"][planet] is None
                else []
            )
        if paths:
            missing.append({"component": name, "missing_value_paths": paths})
        else:
            pass
    context_paths = [
        f"{base}.{name}"
        for name in (
            "nature_context",
            "model_context",
            "solar_context",
            "source_witness",
            "source_reading_conflicts",
            "alternative_source_witnesses",
        )
        if name in component
        and not (
            key == "cheshta_bala"
            and planet in {"Sun", "Moon"}
            and name == "model_context"
        )
    ]
    constraints = []
    for name, fields in {
        "model_context": (
            "selected",
            "status",
            "validated_window_tt",
            "julian_day_tt",
            "source_id",
            "frame",
        ),
        "nature_context": ("moon_options", "mercury_options", "mercury_status"),
        "source_witness": (
            "status",
            "complete_single_original_accepted",
        ),
        "solar_context": (
            "status",
            "sunrise_day_status",
            "active_arc_status",
            "hora_status",
        ),
    }.items():
        if (
            key == "cheshta_bala"
            and planet in {"Sun", "Moon"}
            and name == "model_context"
        ):
            continue
        else:
            pass
        for field in fields:
            if field in component.get(name, {}):
                constraints.append(
                    {
                        "fact_path": f"{base}.{name}.{field}",
                        "value": component[name][field],
                    }
                )
            else:
                pass
    return {
        "planet": planet,
        "value_status": status,
        "scenario_count": len(scenarios),
        "computed_scenario_count": len(values),
        "scenarios": scenarios,
        "missing_evidence": missing,
        "context_paths": context_paths,
        "constraints": constraints,
        "component_status": component.get("status"),
        "scope": "This ruler and this component only; global component gaps do not automatically invalidate another ruler. Branch and sample counts are not probabilities, and consensus is not source adjudication or complete Shadbala.",
    }


def cheshta_ruler_provenance(
    planet: str, component: dict[str, Any], kala: dict[str, Any]
) -> dict[str, Any]:
    """Attribute this ruler to the inputs actually used, not a global option.

    Santhanam27.18 reuses Ayana/Paksha for the luminaries; the optional modern
    means apply only to the other five stars and only in their admitted window.
    This verifies same-run dependencies, not independent textual acceptance.
    """
    base = "india.strengths"
    if component["source_id"] != SOURCE_ID:
        raise ValueError("Cheshta source receipt contradicts its declared source")
    else:
        pass
    inputs = [
        {"fact_path": f"{base}.cheshta_bala.source_id", "value": component["source_id"]}
    ]
    supporting = {}
    if planet in {"Sun", "Moon"}:
        rule, section = "jyotish.luminary_cheshta.v1", "27.18, printed284"
        origin = "ayana_bala" if planet == "Sun" else "paksha_bala"
        part = kala["components"][origin]
        if planet == "Sun":
            source_value = part["summary"][planet]
            inputs.append(
                {
                    "fact_path": f"{base}.kala_bala.components.{origin}.summary.{planet}",
                    "value": source_value,
                }
            )
            inputs.append(
                {
                    "fact_path": f"{base}.kala_bala.components.{origin}.rule",
                    "value": part["rule"],
                }
            )
            expected = {name: source_value for name in component["scenarios"]}
        else:
            expected = {
                name: part["scenarios"][name][planet] for name in component["scenarios"]
            }
            inputs.extend(
                {
                    "fact_path": f"{base}.kala_bala.components.{origin}.scenarios.{name}.{planet}",
                    "value": value,
                }
                for name, value in expected.items()
            )
            inputs.append(
                {
                    "fact_path": f"{base}.kala_bala.components.{origin}.moon_readings",
                    "value": part["moon_readings"],
                }
            )
        state = "reused_luminary_component"
        mean_applied = False
    elif planet in STAR_PLANETS:
        model = component["model_context"]
        origin = "five_star_angular_formula"
        section = "27.24-25, printed285; mean model separately declared"
        inputs.extend(
            {
                "fact_path": f"{base}.cheshta_bala.model_context.{name}",
                "value": model[name],
            }
            for name in ("selected", "status")
        )
        mean_applied = model["status"] == "computed_declared_secular_model"
        if mean_applied:
            if model["selected"] != MODEL or model["source_id"] != SOURCE["id"]:
                raise ValueError(
                    "Cheshta model provenance contradicts its computed status"
                )
            else:
                pass
            evidence = verified_planet_evidence(model, planet)
            expected = {
                name: evidence["arc"]["value"] for name in component["scenarios"]
            }
            inputs.extend(
                {
                    "fact_path": f"{base}.cheshta_bala.model_context.{name}.{planet}",
                    "value": model[name][planet],
                }
                for name in ("planet_evidence", "true_position_provenance")
            )
            rule = "jyotish.cheshta_simon1994.v1"
            supporting = {"supporting_source_id": SOURCE["id"]}
            state = evidence["arc"]["status"]
        else:
            rule = "jyotish.cheshta_arc.v1"
            origin = "unavailable_five_star_mean_model"
            state = model["status"]
            if (state, model["selected"]) not in {
                ("mean_model_unadjudicated", "unadjudicated"),
                ("outside_validated_model_window", MODEL),
            }:
                raise ValueError("Unrecognized uncomputed Cheshta model state")
            else:
                pass
            expected = dict.fromkeys(component["scenarios"])
    else:
        raise ValueError("Cheshta provenance covers seven physical rulers only")
    if not expected or any(
        component["scenarios"][name][planet] != value
        for name, value in expected.items()
    ):
        raise ValueError("Cheshta ruler value contradicts its same-run upstream inputs")
    else:
        pass
    return {
        "rule_id": rule,
        "source_section": section,
        **supporting,
        "method_context": {
            "reading_rule_id": "jyotish.cheshta_ruler_provenance.v1",
            "value_origin": origin,
            "calculation_status": state,
            "five_star_mean_model_applied": mean_applied,
            "input_claims": inputs,
            "scope": "This natal ruler only; same-run dependency agreement is not independent model/textual acceptance or predictive evidence.",
        },
    }


def birth_reading_basis(
    charts: dict[str, Any], nakshatras: dict[str, Any], sensitivity: dict[str, Any]
) -> dict[str, Any]:
    nominal_sign = charts["D1"]["ascendant"]["sign"]
    asc = sensitivity.get("alternatives", {}).get("D1", {}).get("Ascendant", [])
    signs = sorted({nominal_sign, *(r["sign"] for r in asc)})
    moon_options = sensitivity.get("nakshatra_alternatives", {}).get("Moon")
    if not moon_options:
        moon_options = [
            {k: nakshatras["Moon"][k] for k in ("index", "name", "lord", "pada")}
        ]
    else:
        pass
    return {
        "reference": "nominal_birth_instant",
        "options_basis": (
            "nominal_only"
            if sensitivity["status"] == "not_assessed"
            else "sampled_grid"
        ),
        "uncertainty_minutes": sensitivity["uncertainty_minutes"],
        "uncertainty_status": sensitivity["status"],
        "ascendant_sign_options": [
            {"sign": s, "sign_zh": SIGN_LABELS_ZH[s]} for s in signs
        ],
        "moon_nakshatra_options": [
            {k: r[k] for k in ("index", "name", "lord", "pada")} for r in moon_options
        ],
        "scope": "Nominal chart plus actually sampled alternatives; omitted uncertainty is not exact time. Options stable on the grid are not proof of interval-wide stability or birth-time rectification.",
    }
