"""Cross-chapter weather controls with explicit frequency-scope sensitivity."""

from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

_WEATHER_LABELS = {"thunder": "雷", "wind": "风", "rain": "雨", "clear": "晴"}


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "data/meihua/weather-controls-v1.json"
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def weather_control_profile() -> dict[str, Any]:
    return deepcopy(_profile())


def weather_frequency_views(
    slots: list[dict[str, str]], moving_line: int, *, fact_prefix: str = "meihua"
) -> list[dict[str, Any]]:
    if type(moving_line) is not int or not 1 <= moving_line <= 6:
        raise ValueError("Weather frequency diagnostics require the actual moving line")
    static_position = "upper" if moving_line <= 3 else "lower"
    repeated_static = f"{fact_prefix}.changed_hexagram.{static_position}"
    five_slots = [row for row in slots if row["path"] != repeated_static]
    if len(slots) != 6 or len(five_slots) != 5:
        raise ValueError(
            "Weather frequency diagnostics require the six actual positions"
        )
    variants = []
    for name, selected, rows in [
        ("six_positions", True, slots),
        ("five_roles_static_once", False, five_slots),
    ]:
        counts = Counter(row["trigram"] for row in rows)
        variants.append(
            {
                "scope": name,
                "selected_for_main_frequency_rules": selected,
                "slot_count": len(rows),
                "trigram_slots": deepcopy(rows),
                "trigram_counts": {name: counts[name] for name in "乾兑离震巽坎艮坤"},
                "excluded_repeated_static_path": (
                    repeated_static if not selected else None
                ),
            }
        )
    return variants


def assess_weather_controls(
    frequency_views: list[dict[str, Any]], threshold: int | None
) -> list[dict[str, Any]]:
    """Keep all stated probes; never choose a count scope using observed weather."""
    results = []
    for rule in weather_control_profile()["rules"]:
        variants = []
        for view in frequency_views:
            controller_counts = [view["trigram_counts"][t] for t in rule["controllers"]]
            groupings = {"combined_controllers": sum(controller_counts)}
            if len(controller_counts) > 1:
                groupings["either_controller_trigram"] = max(controller_counts)
            for grouping, count in groupings.items():
                variants.append(
                    {
                        "frequency_scope": view["scope"],
                        "grouping": grouping,
                        "count": count,
                        "declared_threshold": threshold,
                        "condition_met": (
                            count >= threshold
                            if threshold is not None
                            else False if count < 2 else None
                        ),
                        "controller_fact_paths": [
                            row["path"]
                            for row in view["trigram_slots"]
                            if row["trigram"] in rule["controllers"]
                        ],
                    }
                )
        affected = {
            trigram: tags
            for trigram, tags in rule["targets"].items()
            if frequency_views[0]["trigram_counts"][trigram] > 0
        }
        states = [v["condition_met"] for v in variants]
        if not affected:
            status = "not_applicable"
        elif all(state is True for state in states):
            status = "met_under_declared_threshold_and_scope_probes"
        elif True in states and False in states:
            status = "scope_unresolved"
        elif None in states:
            status = "pending_threshold"
        else:
            status = "not_met_in_scope_probes"
        results.append(
            {
                "rule_id": rule["id"],
                "status": status,
                "source_id": rule["source_id"],
                "section": rule["section"],
                "quote": rule["quote"],
                "reading": rule["reading"],
                "affected_targets": affected,
                "counting_variants": variants,
                "scope": "declared_probes_not_unique_classical_adjudication",
            }
        )
    return results


def qualify_weather_rules(
    traces: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    controls: list[dict[str, Any]],
) -> None:
    """Qualify the actual dependent symbol, without cancelling every rain tag."""
    by_id = {rule["id"]: rule for rule in rules}
    for row in traces:
        conditions = by_id[row["rule_id"]]["conditions"]
        dependencies = set(conditions.get("present", []))
        dependencies.update(conditions.get("present_any", []))
        if "many" in conditions:
            dependencies.add(conditions["many"])
        for pair in conditions.get("pairs", []):
            dependencies.update(pair)
        checks = []
        controlled, conditional = set(), set()
        for control in controls:
            affected_tags = {
                tag
                for trigram, tags in control["affected_targets"].items()
                if trigram in dependencies
                for tag in tags
                if tag in row["tags"]
            }
            if not affected_tags:
                continue
            checks.append(
                {
                    "rule_id": control["rule_id"],
                    "status": control["status"],
                    "tags": sorted(affected_tags),
                }
            )
            if control["status"] == "met_under_declared_threshold_and_scope_probes":
                controlled.update(affected_tags)
            elif control["status"] in {"scope_unresolved", "pending_threshold"}:
                conditional.update(affected_tags)
        row["control_checks"] = checks
        row["qualification_reasons"] = []
        row["controlled_tags"] = (
            sorted(controlled) if row["status"] == "matched" else []
        )
        row["conditional_tags"] = (
            sorted(conditional - controlled) if row["status"] == "matched" else []
        )
        row["effective_tags"] = (
            [t for t in row["tags"] if t not in controlled]
            if row["status"] == "matched"
            else []
        )
        row["effective_status"] = row["status"]
        row["effective_reading"] = row["traditional_reading"]
        if row["status"] != "matched":
            continue
        if controlled:
            row["qualification_reasons"].append("source_control")
            row["effective_status"] = "qualified_by_source_control"
            row["effective_reading"] += (
                "；其中"
                + "、".join(_WEATHER_LABELS[t] for t in sorted(controlled))
                + "象在本次明示阈值及所列计数候选下受制，不作未受制的独立判断"
            )
        if conditional - controlled:
            row["qualification_reasons"].append("unresolved_control")
            if not controlled:
                row["effective_status"] = "conditional_on_unresolved_control"
            row["effective_reading"] += (
                "；其中"
                + "、".join(
                    _WEATHER_LABELS[t] for t in sorted(conditional - controlled)
                )
                + "象的制约阈值或计数范围尚未确定"
            )
