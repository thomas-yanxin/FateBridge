"""Optional detail views for the catalog's traditional calculation results."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fatebridge.application.tool_spec import DetailLevel, ServiceResult

if TYPE_CHECKING:
    from pydantic import JsonValue

COMPACT_FIELDS = {
    ("", "solar_model_details"),
    ("structure_profile", "evidence_chain"),
    ("day_master", "assessment"),
    ("", "analysis_calendar_context"),
    ("", "calendar_context"),
    ("structure_profile", "candidate_selection"),
    ("structure_profile", "from_child_reference"),
}


def traditional_detail_view(
    result: ServiceResult,
    detail: DetailLevel,
    requested: set[str],
    *,
    keep_lunar_meihua: bool = False,
) -> ServiceResult:
    omitted = set(COMPACT_FIELDS) if detail == "compact" else set()
    if not keep_lunar_meihua:
        omitted.add(("lunar_calendar", "meihua"))

    def shape(value: JsonValue, parent: str) -> JsonValue:
        if isinstance(value, dict):
            return {
                key: shape(child, key)
                for key, child in value.items()
                if key in requested
                or (("", key) not in omitted and (parent, key) not in omitted)
            }
        if isinstance(value, list):
            return [shape(child, parent) for child in value]
        return value

    return {
        key: shape(value, key)
        for key, value in result.items()
        if key in requested or ("", key) not in omitted
    }
