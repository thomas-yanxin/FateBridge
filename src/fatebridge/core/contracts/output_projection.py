"""Projection and stored result delivery contracts."""

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.utils.errors import ValidationIssue


class ResultDelivery(PartialOutput):
    compact_reference: bool | None = None
    mode: str | None = None
    result_id: str | None = None
    total_chars: int | None = None
    total_bytes: int | None = None
    expires_at: float | None = None
    page_chars: int | None = None
    manifest_uri: str | None = None
    first_page_uri: str | None = None
    rest_manifest_path: str | None = None
    file_path: str | None = None
    file_payload_path: str | None = None
    available_fields: list[str] | None = None
    deferred_fields: list[str] | None = None


class ProjectedOutput(PartialOutput):
    projection_warnings: list[ValidationIssue] | None = None
    result_delivery: ResultDelivery | None = None
