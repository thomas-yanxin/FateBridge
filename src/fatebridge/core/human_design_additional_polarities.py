"""Bounded additional planet-role facts explicitly printed in the2001text."""

from copy import deepcopy
from typing import Any

from fatebridge.core.human_design_references import reference_data, reference_sha256


def _catalog() -> dict[str, Any]:
    return reference_data("additional-polarities-2001.json")


def catalog_sha256() -> str:
    return reference_sha256("additional-polarities-2001.json")


def facts_for(gate: int, line: int) -> list[dict[str, Any]]:
    return [
        deepcopy(r)
        for r in _catalog()["facts"]
        if (r["gate"], r["line"]) == (gate, line)
    ]


def evidence() -> dict[str, Any]:
    return {**deepcopy(_catalog()), "source_catalog_sha256": catalog_sha256()}


def triggered_basis(
    facts: list[dict[str, Any]], triggers: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    catalog = _catalog()
    return [
        {
            **deepcopy(fact),
            "source_catalog_sha256": catalog_sha256(),
            "source_url": catalog["source"]["url"],
            "source_pdf_sha256": catalog["source"]["pdf_sha256"],
        }
        for fact in facts
        if any(
            row["body"] == fact["additional_planet"] for row in triggers[fact["role"]]
        )
    ]
