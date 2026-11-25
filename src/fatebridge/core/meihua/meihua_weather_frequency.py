"""Qualify 多 across declared count scopes, without selecting a preferred omen."""

from __future__ import annotations

from typing import Any


def assess_weather_frequency(
    trigram: str, views: list[dict[str, Any]], threshold: int | None
) -> dict[str, Any]:
    """A count convention can be evaluated without claiming classical uniqueness."""
    variants = []
    for view in views:
        count = view["trigram_counts"][trigram]
        variants.append(
            {
                "frequency_scope": view["scope"],
                "count": count,
                "declared_threshold": threshold,
                "condition_met": (
                    count >= threshold
                    if threshold is not None
                    else False if count < 2 else None
                ),
                "fact_paths": [
                    row["path"]
                    for row in view["trigram_slots"]
                    if row["trigram"] == trigram
                ],
            }
        )
    states = [v["condition_met"] for v in variants]
    if all(state is True for state in states):
        status = "met_under_declared_threshold_and_scope_probes"
    elif True in states and False in states:
        status = "scope_unresolved"
    elif None in states:
        status = "pending_threshold"
    else:
        status = "not_met_in_scope_probes"
    return {
        "status": status,
        "trigram": trigram,
        "counting_variants": variants,
        "scope": "declared_probes_not_unique_classical_adjudication",
    }


def qualify_weather_frequency(traces: list[dict[str, Any]]) -> None:
    """Keep the raw six-slot result, while making a disputed premise explicit."""
    for row in traces:
        row["frequency_assessment"] = next(
            (
                condition["frequency_assessment"]
                for condition in row["conditions"]
                if condition["condition"] == "many"
            ),
            None,
        )
        assessment = row["frequency_assessment"]
        if (
            row["status"] != "matched"
            or assessment is None
            or assessment["status"] != "scope_unresolved"
        ):
            continue
        row["qualification_reasons"].append("unresolved_frequency_scope")
        row["effective_status"] = (
            "conditional_on_unresolved_frequency"
            if row["effective_status"] == "matched"
            else "multiple_qualifications"
        )
        row["conditional_tags"] = sorted(
            (set(row["conditional_tags"]) | set(row["tags"]))
            - set(row["controlled_tags"])
        )
        counts = [v["count"] for v in assessment["counting_variants"]]
        threshold = assessment["counting_variants"][0]["declared_threshold"]
        row["effective_reading"] = (
            f"频数范围未裁定：{assessment['trigram']}在六位置计{counts[0]}、"
            f"只计一次静卦则计{counts[1]}，对明示阈值{threshold}的判断有分歧；"
            f"仅按六位置约定时该条为：{row['effective_reading']}"
        )
