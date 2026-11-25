"""Optional detail views for the catalog's traditional calculation results."""

from pydantic import JsonValue

from fatebridge.application.tool_spec import DetailLevel, ServiceResult

_STANDARD_FIELDS = {
    ("", "solar_model_details"),
    ("structure_profile", "evidence_chain"),
    ("day_master", "assessment"),
}
_COMPACT_FIELDS = {
    ("", "snapshot_export"),
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
    omitted = set(_STANDARD_FIELDS)
    if detail == "compact":
        omitted.update(_COMPACT_FIELDS)
    else:
        pass
    if not keep_lunar_meihua:
        omitted.add(("lunar_calendar", "meihua"))
    else:
        pass

    def shape(value: JsonValue, parent: str) -> JsonValue:
        if isinstance(value, dict):
            return {
                key: shape(child, key)
                for key, child in value.items()
                if key in requested
                or (("", key) not in omitted and (parent, key) not in omitted)
            }
        else:
            pass
        if isinstance(value, list):
            return [shape(child, parent) for child in value]
        else:
            pass
        return value

    return {
        key: shape(value, key)
        for key, value in result.items()
        if key in requested or ("", key) not in omitted
    }
