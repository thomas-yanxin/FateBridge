"""Prepare shared output before transport-specific JSON serialization."""

from pydantic import JsonValue

from fatebridge.application.examples import compact_fields
from fatebridge.application.projection import project_fields
from fatebridge.application.result_delivery import bound_public_response
from fatebridge.application.tool_spec import DetailLevel, ToolSpec

COMPACT_RUN_METADATA_FIELDS = frozenset(
    {
        "run_id",
        "trace_id",
        "tool_name",
        "generated_at",
        "engine",
        "engine_is_approximate",
        "duration_ms",
        "effective_time",
        "replay",
        "warnings",
        "parent_run_id",
    }
)


def deliver_response(
    payload: dict[str, JsonValue],
    *,
    spec: ToolSpec | None = None,
    fields: list[str] | None = None,
    strict_fields: bool = False,
    include_snapshot_text: bool | None = None,
    response_char_limit: int = 0,
    compact: bool = True,
    detail: DetailLevel = "standard",
    failed: bool = False,
) -> dict[str, JsonValue]:
    """Shape detail tier, project facts, omit optional text, then bound volume.

    Errors keep their complete envelope and never enter result storage. The
    serialization style controls the same character budget as the final text.
    """
    if not failed:
        should_project_compact_fields = detail == "compact" and not fields
        if should_project_compact_fields and spec is not None:
            if spec.compact_view is not None:
                payload = spec.compact_view(payload)
            fields = compact_fields(spec)
            if (
                fields is not None
                and include_snapshot_text is True
                and "snapshot_text" in payload
            ):
                fields = [*fields, "snapshot_text"]
            strict_fields = False
        payload = project_fields(payload, fields, strict_fields=strict_fields)
        if should_project_compact_fields and fields:
            payload.pop("projection_warnings", None)
        if detail in ("compact", "standard"):
            requested = {part for path in fields or () for part in path.split(".")}
            if spec is not None and spec.detail_view is not None:
                payload = spec.detail_view(payload, detail, requested)
            metadata = payload.get("run_metadata")
            if detail == "compact" and "run_metadata" not in requested and metadata:
                assert isinstance(metadata, dict)
                payload = {
                    **payload,
                    "run_metadata": {
                        name: value
                        for name, value in metadata.items()
                        if name in COMPACT_RUN_METADATA_FIELDS
                    },
                }
    should_keep_snapshot = include_snapshot_text
    if should_keep_snapshot is None:
        should_keep_snapshot = (
            any(path.partition(".")[0] == "snapshot_text" for path in fields or ())
            or (detail == "audit" and spec is not None and spec.optional_snapshot)
            or (detail != "compact" and (spec is None or spec.include_snapshot_text))
        )
    if not should_keep_snapshot and "snapshot_text" in payload:
        payload = payload.copy()
        payload.pop("snapshot_text")
    if failed:
        return payload
    return bound_public_response(
        payload, response_char_limit, compact=compact, selected_fields=fields
    )
