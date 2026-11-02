"""Compose bounded line references from a previously verified complete chart.

Private composition is not a verifier. Public callers enter through the service
which first checks the entire original calculation, without native replay.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fatebridge.core.human_design_mechanics import CHANNELS

METHOD = "human_design_nominal_activation_line_reference_packet_v1"
EMPHASIS = {
    "exaltation": ["exaltation"],
    "detriment": ["detriment"],
    "juxtaposition": ["exaltation", "detriment"],
    "unfixed": [],
    "not_applicable_no_planet_polarity": [],
}
POLES = {"exaltation": "上升", "detriment": "下降"}


def _condition(source: dict, chart: dict, fixing: dict) -> dict:
    """Only a named clause is qualified; absence does not imply its converse."""
    result: dict[str, Any] = {
        "source_condition": deepcopy(source),
        "predicate_model": "declared_natal_complete_channel_model_v1",
        "calculation_condition_satisfied": None,
        "evaluation_status": "unsupported_condition_rule",
        "channel_witnesses": [],
        "gate_activation_witnesses": [],
        "fixing_emphasizes_clause_polarity": source["polarity"]
        in EMPHASIS[fixing["fixing_state"]],
        "scope_is_named_clause_only": True,
        "source_condition_semantics_independently_accepted": False,
        "converse_inferred": False,
        "outcome_guaranteed": False,
    }
    relation = source["source_condition"]
    requested = relation.get("channel_gates") if isinstance(relation, dict) else None
    if (
        not isinstance(relation, dict)
        or set(relation) != {"relation", "channel_gates"}
        or relation["relation"] != "permanent_channel_connection"
        or not isinstance(requested, list)
        or len(requested) != 2
        or any(type(g) is not int for g in requested)
        or sorted(requested) not in [sorted((a, b)) for a, b, _ in CHANNELS]
    ):
        return result
    endpoints = set(requested)
    witnesses = [
        {"path": f"bodygraph.channels.{i}", "value": deepcopy(c)}
        for i, c in enumerate(chart["bodygraph"]["channels"])
        if set(c["gates"]) == endpoints
    ]
    gates = [
        {
            "path": f"activations.{side}.{i}",
            "body": a["body"],
            "gate": a["gate"],
            "line": a["line"],
        }
        for side in ("personality", "design")
        for i, a in enumerate(chart["activations"][side])
        if a["gate"] in endpoints
    ]
    complete = {r["gate"] for r in gates} == endpoints
    if bool(witnesses) != complete:
        raise ValueError("Channel and same-run activation witnesses disagree")
    result.update(
        calculation_condition_satisfied=complete,
        evaluation_status="evaluated_natal_graph_predicate",
        channel_witnesses=witnesses,
        gate_activation_witnesses=gates,
    )
    return result


def _compose(
    chart: dict,
    references: dict[str, dict],
    *,
    source_available_poles_only: bool = False,
) -> dict:
    fixings = chart["depth_evidence"]["line_fixings"]
    if len(fixings) != 26 or any(
        len(chart["activations"][s]) != 13 for s in ("personality", "design")
    ):
        raise ValueError("Complete26-activation inventory required")
    rows = []
    for i, fixing in enumerate(fixings):
        key = f"{fixing['gate']}.{fixing['line']}"
        reference = references[key]["reference_details"]["record"]
        if key != reference["key"] or fixing["fixing_state"] not in EMPHASIS:
            raise ValueError("Wrong line reference or unknown fixing state")
        meaning = reference["editorial_paraphrase"]
        conditions = reference.get("source_conditions")
        bound = (
            None
            if conditions is None
            else [_condition(c, chart, fixing) for c in conditions]
        )
        text = fixing["reading"]
        if meaning is None:
            text += "本门本线的具体爻义尚未整理，保留未知，不用角色线主题补齐。"
        else:
            if source_available_poles_only:
                available = [
                    p for p in POLES if reference["source_polarity_planets"][p]
                ]
                if any((meaning[p] is None) != (p not in available) for p in POLES):
                    raise ValueError(
                        "Source pole and editorial text inventory disagree"
                    )
                text += "局部待复核转述：" + "".join(
                    POLES[p] + "为" + meaning[p] for p in available
                )
            else:
                text += f"局部待复核转述：上升为{meaning['exaltation']}下降为{meaning['detriment']}"
            emphasized = (
                "、".join(POLES[p] for p in EMPHASIS[fixing["fixing_state"]])
                or "无已触发侧重"
            )
            if source_available_poles_only and len(available) != 2:
                text += f"本次固定侧重：{emphasized}；未列极性不补造，亦不等于能力或结果评分。"
            else:
                text += f"本次固定侧重：{emphasized}；侧重不排除另一极性，亦不等于能力或结果评分。"
        for condition in bound or []:
            role = condition["source_condition"]["polarity"]
            text += (
                f"原文{POLES[role]}段限定句："
                + condition["source_condition"]["local_clause_paraphrase_zh"]
            )
            text += "条件判定不改变实际固定状态，也不排除另一极性。"
            truth = condition["calculation_condition_satisfied"]
            if truth is None:
                text += "本条件规则尚未支持，适用性保留未知。"
            elif truth:
                text += "当前所选名义盘的完整通道口径下观察到该结构条件；它与固定侧重分开记录，不保证现实回报。"
            else:
                text += "当前所选名义盘未观察到该完整通道，不能据该限定句断言回报，也不反推没有回报。"
        for note in reference["source_reading_notes"]:
            text += note
        rows.append(
            {
                "activation_path": fixing["calculation_path"],
                "fixing_path": f"depth_evidence.line_fixings.{i}",
                "side": fixing["side"],
                "body": fixing["body"],
                "gate": fixing["gate"],
                "line": fixing["line"],
                "reference_key": key,
                "actual_fixing_state": fixing["fixing_state"],
                "emphasized_polarities": list(EMPHASIS[fixing["fixing_state"]]),
                "fixing_planets": deepcopy(fixing["fixing_planets"]),
                "source_polarity_planets": deepcopy(
                    reference["source_polarity_planets"]
                ),
                "meaning_status": reference["meaning_status"],
                "editorial_paraphrase": deepcopy(meaning),
                "source_reading_notes": deepcopy(reference["source_reading_notes"]),
                "condition_review_status": reference.get(
                    "condition_review_status", "not_assessed"
                ),
                "bound_source_conditions": bound,
                "complete_line_meaning_accepted": False,
                "reading": text,
            }
        )
        if source_available_poles_only:
            rows[-1].update(
                source_available_polarities=[
                    p for p in POLES if reference["source_polarity_planets"][p]
                ],
                source_polarity_wording_policy="enumerated_source_poles_no_invented_opposite_v1",
            )
    expected_paths = [
        f"activations.{s}.{i}" for s in ("personality", "design") for i in range(13)
    ]
    if [r["activation_path"] for r in rows] != expected_paths:
        raise ValueError("Original activation traversal changed or a row was omitted")
    curated = sum(r["editorial_paraphrase"] is not None for r in rows)
    return {
        "activation_scope": "selected_nominal_personality_and_design",
        "rows": rows,
        "source_references": deepcopy(references),
        "coverage": {
            "required_activations": 26,
            "included_activations": len(rows),
            "activations_with_pending_local_paraphrase": curated,
            "activations_without_curated_meaning": len(rows) - curated,
            "independently_accepted_full_line_meanings": 0,
            "source_conditions_exhaustively_reviewed": False,
        },
        "whole_chart_context": {
            "type": chart["bodygraph"]["type"],
            "subtype": chart["bodygraph"]["subtype"],
            "authority": chart["bodygraph"]["authority"],
            "definition": deepcopy(chart["bodygraph"]["definition"]),
            "profile": chart["profile"],
            "incarnation_cross": deepcopy(chart["incarnation_cross"]),
            "time_sensitivity_summary": deepcopy(
                chart.get("time_sensitivity", {}).get("summary")
            ),
            "node_mode": chart["calculation_policy"]["node_mode"],
            "context_paths_in_original_result": [
                key
                for key in (
                    "bodygraph",
                    "source_consistency",
                    "historical_polarity_context",
                    "time_sensitivity",
                    "calculation_policy",
                )
                if key in chart
            ],
            "context_fields_not_in_original_result": [
                key
                for key in (
                    "bodygraph",
                    "source_consistency",
                    "historical_polarity_context",
                    "time_sensitivity",
                    "calculation_policy",
                )
                if key not in chart
            ],
        },
        "other_context_line_meanings": {
            "alternative_node_or_backend_charts": "not_assembled",
            "birth_time_interval_samples": "not_assembled",
            "cycle_contacts": "not_assembled",
        },
        "scope": "所选名义人格／设计盘的完整26激活清单与局部转述，不是其他口径、区间样本或周期的完整线义。门线、固定与通道条件只绑定该名义TT，不断言在生时范围内始终成立；其他上下文和原核验原样保留。不把未整理或条件未穷尽误报为完整爻义；限定句不扩成整条爻义或现实保证。",
    }
