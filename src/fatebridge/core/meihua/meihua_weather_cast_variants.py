"""Evaluate each retained cast, never merge candidates into a weather verdict."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def _rule_signature(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row[key]
        for key in (
            "status",
            "time_scope",
            "effective_status",
            "controlled_tags",
            "conditional_tags",
            "effective_tags",
            "qualification_reasons",
        )
    }


def augment_weather_cast_variants(
    result: dict[str, Any],
    cast: dict[str, Any],
    context: dict[str, Any] | None,
    evaluate: Callable[..., dict[str, Any]],
) -> None:
    variants, details = [], []
    signatures: list[dict[str, dict[str, Any]]] = []
    control_signatures = []
    for index, candidate in enumerate(cast.get("counting_variants", [])):
        prefix = f"meihua.counting_variants.{index}"
        # Use this candidate's actual changed/mutual structures and moving line.
        # It has no alternatives attached: evaluation cannot recurse or redraw.
        weather = evaluate(
            {**candidate, "seed": {"moving_line": candidate["moving_line"]}},
            context,
            fact_prefix=prefix,
        )["weather"]
        identity = {
            key: candidate[key]
            for key in (
                "line_sum_basis",
                "selected",
                "moving_line",
                "base_code",
                "changed_code",
                "mutual_code",
            )
        }
        identity["fact_prefix"] = prefix
        variants.append(
            {
                **identity,
                **{
                    key: weather[key]
                    for key in (
                        "trigram_counts",
                        "selected_readings",
                        "matched_rule_ids",
                        "pending_rule_ids",
                        "conflicts",
                        "time_scope_comparison",
                        "single_forecast",
                        "symbolic_attributions",
                    )
                },
                "control_statuses": [
                    {key: row[key] for key in ("rule_id", "status", "affected_targets")}
                    for row in weather["controls"]
                ],
            }
        )
        details.append(
            {
                **identity,
                **{
                    key: weather[key]
                    for key in (
                        "trigram_slots",
                        "frequency_views",
                        "rule_trace",
                        "controls",
                    )
                },
            }
        )
        signatures.append(
            {r["rule_id"]: _rule_signature(r) for r in weather["rule_trace"]}
        )
        control_signatures.append(
            {
                r["rule_id"]: {key: r[key] for key in ("status", "affected_targets")}
                for r in weather["controls"]
            }
        )
    changed_rules = [
        rule_id
        for rule_id in (signatures[0] if signatures else {})
        if any(rows[rule_id] != signatures[0][rule_id] for rows in signatures[1:])
    ]
    changed_controls = [
        rule_id
        for rule_id in (control_signatures[0] if control_signatures else {})
        if any(
            rows[rule_id] != control_signatures[0][rule_id]
            for rows in control_signatures[1:]
        )
    ]
    status = (
        "not_applicable_no_distinct_cast"
        if not variants
        else (
            "different_rule_results"
            if changed_rules or changed_controls
            else "same_rule_results_for_supplied_context"
        )
    )
    weather = result["weather"]
    weather["casting_variants"] = variants
    weather["casting_variant_traces"] = details
    weather["casting_comparison"] = {
        "status": status,
        "candidate_count": len(variants),
        "selected_line_sum_basis": cast["seed"].get("line_sum_basis"),
        "changed_rule_ids": changed_rules,
        "changed_control_ids": changed_controls,
        "trigram_counts_differ": any(
            v["trigram_counts"] != variants[0]["trigram_counts"] for v in variants[1:]
        ),
        "policy": "each_retained_cast_same_rules_and_confirmed_context_no_voting_or_outcome_selection",
        "scope": "Agreement concerns only implemented clauses under the supplied conditions; not unique classical adjudication or a weather forecast.",
    }
    result["evidence_scope"]["weather_casting_sensitivity"] = status
    if variants:
        result["comprehensive_judgement"] = (
            (
                "取数候选的天气条款或制约结果有分歧；"
                if changed_rules or changed_controls
                else "取数候选在已提供条件下的所选天气条款结果相同；"
            )
            + "各候选分列，不合并为单一预报。以下为本次所选候选的解读。"
            + result["comprehensive_judgement"]
        )
