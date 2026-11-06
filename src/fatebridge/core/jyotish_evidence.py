"""Reading context derived from actual branches and birth-time samples.

This preserves uncertainty and field provenance, not a free-text semantic
grade, classical acceptance, or evidence of predictive efficacy.
"""

from __future__ import annotations

import math
from typing import Any

from fatebridge.core.astrology_tables import SIGN_LABELS_ZH
from fatebridge.core.jyotish_mean import (
    MODEL,
    SOURCE,
    STAR_PLANETS,
    verified_planet_evidence,
)
from fatebridge.core.jyotish_strength import SOURCE_ID


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
    values = [row["value"] for row in scenarios if row["value"] is not None]
    if any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in values
    ):
        raise ValueError(
            "Strength evidence requires finite numeric branches or missing values"
        )
    if len(values) != len(scenarios):
        status = "partially_computed" if values else "unavailable"
        expected = None
    elif len(set(values)) > 1:
        status, expected = "conditional_results", None
    else:
        status, expected = "computed_consensus", values[0]
    if supplied != expected:
        raise ValueError(
            "Strength summary contradicts its same-run conditional branches"
        )
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
        for field in fields:
            if field in component.get(name, {}):
                constraints.append(
                    {
                        "fact_path": f"{base}.{name}.{field}",
                        "value": component[name][field],
                    }
                )
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
            description = "本宫主为太阳，运动力直接取本次Ayana分量，依据Santhanam27.18；五星平均模型的选择或适用窗口不参与该值。"
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
            description = "本宫主为月亮，运动力直接取本次同一性质分支的Paksha分量，依据Santhanam27.18；月亮性质读法仍保留条件，五星平均模型不参与该值。"
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
            description = (
                "本五星宫主的对径中点仍有两个候选，但角度公式的两分支精确同值，故仅交付共同强度；未裁定中点，也不是Raman1900表的校勘结果。"
                if state == "opposed_midpoint_not_adjudicated"
                and evidence["arc"]["value"] is not None
                else "本五星宫主采用本次已计算的Simon1994平均黄经、同框架J2000几何真位置与Santhanam27.24-25角度步骤；对径中点未裁定时保留缺失。这不是Raman1900表的校勘结果。"
            )
        else:
            rule = "jyotish.cheshta_arc.v1"
            origin = "unavailable_five_star_mean_model"
            state = model["status"]
            if (
                state == "mean_model_unadjudicated"
                and model["selected"] == "unadjudicated"
            ):
                description = "本五星宫主的平均位置模型尚未裁定，本项未计算；角度公式不能自行提供平均位置，不能用顺逆行标签或零值补齐。"
            elif (
                state == "outside_validated_model_window" and model["selected"] == MODEL
            ):
                description = "虽选择Simon1994模型，出生TT已超出本项目声明的1900–2050适用窗口，本五星宫主的平均／几何运动分量未计算；不能写成已采用该模型取得数值。"
            else:
                raise ValueError("Unrecognized uncomputed Cheshta model state")
            expected = dict.fromkeys(component["scenarios"])
    else:
        raise ValueError("Cheshta provenance covers seven physical rulers only")
    if not expected or any(
        component["scenarios"][name][planet] != value
        for name, value in expected.items()
    ):
        raise ValueError("Cheshta ruler value contradicts its same-run upstream inputs")
    return {
        "rule_id": rule,
        "source_section": section,
        **supporting,
        "description": description,
        "method_context": {
            "reading_rule_id": "jyotish.cheshta_ruler_provenance.v1",
            "value_origin": origin,
            "calculation_status": state,
            "five_star_mean_model_applied": mean_applied,
            "input_claims": inputs,
            "scope": "This natal ruler only; same-run dependency agreement is not independent model/textual acceptance or predictive evidence.",
        },
    }


def strength_text(context: dict[str, Any]) -> str:
    status = context["value_status"]
    computed, total = context["computed_scenario_count"], context["scenario_count"]
    if status == "computed_consensus":
        value = context["scenarios"][0]["value"]
        return f"该宫主本项在本次已计算分支中一致为{value:.6g} Virupa。"
    if status == "conditional_results":
        values = sorted({r["value"] for r in context["scenarios"]})
        text = "、".join(f"{v:.6g}" for v in values)
        return f"该宫主本项{total}个条件分支均已计算，取值为{text} Virupa；摘要null表示条件未裁定，不能当作零或缺项。"
    if status == "partially_computed":
        return f"该宫主本项仅{computed}/{total}个条件分支取得数值，其余缺项保留；不能只挑已计算或较高分支作结论。"
    return "该宫主本项所有已列分支均未提供可用数值，不能补成零；先核对同run的模型／性质及缺项上下文，不一概当成用户资料不足。"


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


def natal_prose(india: dict[str, Any]) -> dict[str, str]:
    basis = india["reading_basis"]
    asc = india["charts"]["D1"]["ascendant"]["sign_zh"]
    moon = india["nakshatras"]["Moon"]
    moon_point = next(p for p in india["charts"]["D1"]["planets"] if p["id"] == "Moon")
    identity = f"名义生时的D1上升{asc}；按印占整宫制读取宫主与九曜。"
    if len(basis["ascendant_sign_options"]) > 1:
        identity += (
            "给定生时范围的抽样上升候选为"
            + "、".join(r["sign_zh"] for r in basis["ascendant_sign_options"])
            + "。"
        )
    emotional = f"名义生时月亮在{moon_point['sign_zh']}，月宿{moon['name']}，第{moon['pada']}足。"
    if len(basis["moon_nakshatra_options"]) > 1:
        emotional += (
            "给定生时范围的抽样候选为"
            + "、".join(
                f"{r['name']}第{r['pada']}足（宿主{r['lord']}）"
                for r in basis["moon_nakshatra_options"]
            )
            + "，不能只选名义值解释。"
        )
    if basis["uncertainty_status"] == "not_assessed":
        note = "未提供生时误差范围，尚未评估稳定性。"
    else:
        note = "候选来自给定时间范围的抽样，不是概率分配或区间内无边界的保证。"
    return {
        "core_identity": identity,
        "emotional_style": emotional,
        "uncertainty_note": note,
    }
