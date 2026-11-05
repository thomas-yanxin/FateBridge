"""Exact line references; local editorial meaning is never personal selection."""

from __future__ import annotations

from copy import deepcopy

from fatebridge.core.human_design_line_catalogue import (
    DOMAIN,
    SOURCE,
    _catalogue,
    _check_end,
    _coverage,
    _provenance,
)
from fatebridge.core.human_design_line_catalogue import (
    read_reference as read_base_reference,
)
from fatebridge.core.human_design_references import (
    coherent_human_design_references,
)


def build_registry() -> dict:
    with coherent_human_design_references():
        from fatebridge.core.human_design_knowledge_v3 import _registry_category

        data, raw = _catalogue()
        provenance = _provenance(data, raw)
        # Preserve the original loaded-vs-changed diagnosis before the child
        # catalogue rereads its parent, rather than relabelling it invalid.
        _check_end(raw)
        versioned_category, versioned_snapshot = _registry_category()
        _check_end(raw)
        raw.update(versioned_snapshot)
        from fatebridge.core.human_design_knowledge_v4 import (
            _registry_category as context_category,
        )

        _check_end(raw)
        context_version, context_snapshot = context_category()
        _check_end(raw)
        raw.update(context_snapshot)
        from fatebridge.core.human_design_knowledge_v5 import (
            _registry_category as gate4_category,
        )

        _check_end(raw)
        gate4_version, gate4_snapshot = gate4_category()
        _check_end(raw)
        raw.update(gate4_snapshot)
        from fatebridge.core.human_design_knowledge_v6 import (
            _registry_category as gate5_category,
        )

        _check_end(raw)
        gate5_version, gate5_snapshot = gate5_category()
        _check_end(raw)
        raw.update(gate5_snapshot)
        from fatebridge.core.human_design_knowledge_v7 import (
            _registry_category as gate6_category,
        )

        _check_end(raw)
        gate6_version, gate6_snapshot = gate6_category()
        _check_end(raw)
        raw.update(gate6_snapshot)
        result = {
            "source": SOURCE,
            "bundle_version": None,
            "provenance": provenance,
            "domains": [
                {
                    "domain": DOMAIN,
                    "source": SOURCE,
                    "bundle_version": None,
                    "provenance": deepcopy(provenance),
                    "categories": [
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
                        versioned_category,
                        context_version,
                        gate4_version,
                        gate5_version,
                        gate6_version,
                    ],
                }
            ],
        }
        _check_end(raw)
        return result


def read_reference(*, category: str | None, key: str | None) -> dict:
    if category == "lines_v7":
        from fatebridge.core.human_design_knowledge_v7 import read_reference as read_v7

        return read_v7(key=key)
    if category == "lines_v6":
        from fatebridge.core.human_design_knowledge_v6 import read_reference as read_v6

        return read_v6(key=key)
    if category == "lines_v5":
        from fatebridge.core.human_design_knowledge_v5 import read_reference as read_v5

        return read_v5(key=key)
    if category == "lines_v4":
        from fatebridge.core.human_design_knowledge_v4 import read_reference as read_v4

        return read_v4(key=key)
    if category == "lines_v3":
        from fatebridge.core.human_design_knowledge_v3 import read_reference as read_v3

        return read_v3(key=key)
    return read_base_reference(category=category, key=key)
