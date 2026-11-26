"""Bounded additional planet-role facts explicitly printed in the2001text."""

from copy import deepcopy
from typing import Any

from fatebridge.core.human_design.human_design_references import reference_data


def _catalog() -> dict[str, Any]:
    return reference_data("additional-polarities-2001.json")


def facts_for(gate: int, line: int) -> list[dict[str, Any]]:
    return [
        deepcopy(r)
        for r in _catalog()["facts"]
        if (r["gate"], r["line"]) == (gate, line)
    ]


def evidence() -> dict[str, Any]:
    return deepcopy(_catalog())


def triggered_basis(
    facts: list[dict[str, Any]], triggers: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    return [
        deepcopy(fact)
        for fact in facts
        if any(
            row["body"] == fact["additional_planet"] for row in triggers[fact["role"]]
        )
    ]
