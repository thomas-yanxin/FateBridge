"""Prepare shared output before transport-specific JSON serialization."""

from pydantic import JsonValue

from fatebridge.application.examples import compact_fields
from fatebridge.application.projection import project_fields, project_present_fields
from fatebridge.application.tool_spec import DetailLevel, ToolSpec

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
            payload = spec.compact_view(payload)
        default_fields = compact_fields(spec)
        if default_fields:
            payload = project_present_fields(payload, default_fields)

    if detail == "compact":
        requested = {part for path in fields or () for part in path.split(".")}
        if spec is not None and spec.detail_view is not None:
            payload = spec.detail_view(payload, detail, requested)
        metadata = payload.get("run_metadata")
        if "run_metadata" not in requested and metadata:
            assert isinstance(metadata, dict)
            payload = {
                **payload,
                "run_metadata": {
                    name: value
                    for name, value in metadata.items()
                    if name in COMPACT_RUN_METADATA_FIELDS
                },
            }
    return payload
