"""Exact line references; local editorial meaning is never personal selection."""

from __future__ import annotations

from copy import deepcopy

from fatebridge.core.human_design import (
    human_design_knowledge_v3,
    human_design_knowledge_v4,
    human_design_knowledge_v5,
    human_design_knowledge_v6,
    human_design_knowledge_v7,
)
from fatebridge.core.human_design.human_design_line_catalogue import (
    DOMAIN,
    SOURCE,
    _catalogue,
    _coverage,
    _provenance,
)
from fatebridge.core.human_design.human_design_line_catalogue import (
    read_reference as read_base_reference,
)
from fatebridge.core.human_design.human_design_references import (
    coherent_human_design_references,
)


def build_registry() -> dict:
    with coherent_human_design_references():
        data, raw = _catalogue()
        provenance = _provenance(data, raw)
        categories = [
            {
                "name": "lines",
                "count": len(data["rows"]),
                "keys_sample": [r["key"] for r in data["rows"][:12]],
                "keys_complete": False,
                "key_format": "gate.line；门1..64，线1..6；例如1.1",
                "supports": ["key"],
                "reference_only": True,
                "coverage": _coverage(data),
            },
        ]
        current = human_design_knowledge_v3._catalogue((data, raw))
        categories.append(human_design_knowledge_v3._registry_category(current))
        for version in (
            human_design_knowledge_v4,
            human_design_knowledge_v5,
            human_design_knowledge_v6,
            human_design_knowledge_v7,
        ):
            current = version._catalogue(current)
            categories.append(version._registry_category(current))
        return {
            "source": SOURCE,
            "bundle_version": None,
            "provenance": provenance,
            "domains": [
                {
                    "domain": DOMAIN,
                    "source": SOURCE,
                    "bundle_version": None,
                    "provenance": deepcopy(provenance),
                    "categories": categories,
                }
            ],
        }


def read_reference(*, category: str | None, key: str | None) -> dict:
    if category == "lines_v7":
        return human_design_knowledge_v7.read_reference(key=key)
    elif category == "lines_v6":
        return human_design_knowledge_v6.read_reference(key=key)
    elif category == "lines_v5":
        return human_design_knowledge_v5.read_reference(key=key)
    elif category == "lines_v4":
        return human_design_knowledge_v4.read_reference(key=key)
    elif category == "lines_v3":
        return human_design_knowledge_v3.read_reference(key=key)
    else:
        return read_base_reference(category=category, key=key)
