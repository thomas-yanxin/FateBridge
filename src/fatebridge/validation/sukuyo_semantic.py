"""Prepare disclosed calculation views without copying the answer under review.

Sukuyo-only suzhan explanations project params, Sukuyo and rulesets; physical
star-chart evaluation is separate. Compatibility keeps every domain field,
including candidate_relation_analysis, and removes only presentation wrappers
and run metadata. A reused agent context is still not a pristine holdout.

Complete Suzhan review uses complete_suzhan_calculation_view instead: the sky,
normalised input, validation and future domain fields all remain available.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

PAIR_PRESENTATION_FIELDS = frozenset(
    {"summary", "snapshot_export", "snapshot_text", "export_text", "run_metadata"}
)


def _without_reading(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _without_reading(v) for k, v in value.items() if k != "reading_text"}
    if isinstance(value, list):
        return [_without_reading(v) for v in value]
    return deepcopy(value)


def semantic_calculation_view(tool: str, result: dict[str, Any]) -> dict[str, Any]:
    if tool == "suzhan":
        selected = {key: result[key] for key in ("params", "sukuyo", "rulesets")}
    elif tool == "sukuyo_compatibility":
        selected = {
            k: v for k, v in result.items() if k not in PAIR_PRESENTATION_FIELDS
        }
    else:
        raise ValueError("Only suzhan and sukuyo_compatibility views are supported")
    return {
        key: _without_reading(value)
        for key, value in selected.items()
        if key != "reading_text"
    }


def complete_suzhan_calculation_view(result: dict[str, Any]) -> dict[str, Any]:
    """Copy all non-presentation 宿占 evidence without certifying its truth.

    The required branches distinguish a complete result from a calendar-only
    projection. An explicitly null astronomy branch remains null; unknown and
    adverse evidence is retained. Nested ``summary`` fields are not discarded.
    """
    for key in (
        "analysis_type",
        "input_normalized",
        "params",
        "chart",
        "sukuyo",
        "astronomy",
        "rulesets",
        "validation",
    ):
        result[key]
    return {
        key: _without_reading(value)
        for key, value in result.items()
        if key not in PAIR_PRESENTATION_FIELDS and key != "reading_text"
    }
