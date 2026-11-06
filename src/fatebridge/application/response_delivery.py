"""Prepare shared output before transport-specific JSON serialization."""

from fatebridge.application.projection import project_fields
from fatebridge.application.result_delivery import bound_response
from fatebridge.application.tool_spec import ServiceResult


def deliver_response(
    payload: ServiceResult,
    *,
    fields: list[str] | None = None,
    strict_fields: bool = False,
    include_snapshot_text: bool = True,
    response_char_limit: int = 0,
    compact: bool = True,
    failed: bool = False,
) -> ServiceResult:
    """Project facts, omit optional text, then retain that exact selected run.

    Errors keep their complete envelope and never enter result storage. The
    serialization style controls the same character budget as the final text.
    """
    if not failed:
        payload = project_fields(payload, fields, strict_fields=strict_fields)
    if not include_snapshot_text and "snapshot_text" in payload:
        payload = {
            key: value for key, value in payload.items() if key != "snapshot_text"
        }
    if failed:
        return payload
    return bound_response(payload, response_char_limit, compact=compact)
