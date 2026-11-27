"""Prepare shared output before transport-specific JSON serialization."""

from pydantic import JsonValue

from fatebridge.application.examples import compact_fields
from fatebridge.application.projection import project_fields, project_present_fields
from fatebridge.application.tool_spec import DetailLevel, ToolSpec

_BLOAT_KEYS = frozenset(
    {
        "rule_trace",
        "source_citations",
        "source_catalog",
        "conventions",
    }
)


def _strip_audit_bloat(value: JsonValue) -> JsonValue:
    if isinstance(value, dict):
        changed = False
        cleaned: dict[str, JsonValue] = {}
        for key, item in value.items():
            if key in _BLOAT_KEYS:
                changed = True
                continue
            next_item = _strip_audit_bloat(item)
            if next_item is not item:
                changed = True
            cleaned[key] = next_item
        return cleaned if changed else value
    if isinstance(value, list):
        changed = False
        items: list[JsonValue] = []
        for item in value:
            next_item = _strip_audit_bloat(item)
            if next_item is not item:
                changed = True
            items.append(next_item)
        return items if changed else value
    return value


COMPACT_RUN_METADATA_FIELDS = frozenset(
    {
        "run_id",
        "tool_name",
        "generated_at",
        "engine",
        "engine_is_approximate",
        "effective_time",
        "warnings",
        "replay",
    }
)


def deliver_response(
    payload: dict[str, JsonValue],
    *,
    spec: ToolSpec | None = None,
    fields: list[str] | None = None,
    detail: DetailLevel = "compact",
    failed: bool = False,
) -> dict[str, JsonValue]:
    """Shape detail tier and strictly project requested business fields."""
    if failed:
        return payload

    if fields:
        payload = project_fields(payload, fields)
    elif detail == "compact" and spec is not None:
        if spec.compact_view is not None:
            metadata = payload.get("run_metadata")
            payload = spec.compact_view(payload)
            if metadata is not None and "run_metadata" not in payload:
                payload = {**payload, "run_metadata": metadata}
        else:
            default_fields = compact_fields(spec)
            if default_fields:
                payload = project_present_fields(payload, default_fields)

    if detail == "compact":
        requested = {part for path in fields or () for part in path.split(".")}
        if spec is not None and spec.detail_view is not None:
            payload = spec.detail_view(payload, detail, requested)
        metadata = payload.get("run_metadata")
        if "run_metadata" not in requested and isinstance(metadata, dict) and metadata:
            payload = {
                **payload,
                "run_metadata": {
                    name: value
                    for name, value in metadata.items()
                    if name in COMPACT_RUN_METADATA_FIELDS
                },
            }
    stripped = _strip_audit_bloat(payload)
    assert isinstance(stripped, dict)
    return stripped
