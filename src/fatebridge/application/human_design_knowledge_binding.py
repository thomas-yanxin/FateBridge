"""Bind Human Design reference facts to their original request before projection."""

from pydantic import BaseModel

from fatebridge.core.human_design_line_catalogue import DOMAIN, POLICY_ID
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.json_digest import canonical_bytes


def require_human_design_reference_binding(
    key: str, result: dict, request: BaseModel | None
) -> None:
    if request is None or key not in {"knowledge_read", "knowledge_registry"}:
        return
    data = request.model_dump()
    domain = data["domain"]
    selected = domain.strip() if domain is not None else None
    active = (
        selected == DOMAIN
        or result.get("domain") == DOMAIN
        or result.get("provenance", {}).get("reference_policy_id") == POLICY_ID
    )
    if key == "knowledge_registry":
        active = (
            active
            or selected in (None, "")
            or any(
                isinstance(row, dict) and row.get("domain") == DOMAIN
                for row in result.get("domains", [])
            )
        )
    if not active:
        return
    from fatebridge.services.knowledge import (
        calculate_knowledge_read,
        calculate_knowledge_registry,
    )

    service = (
        calculate_knowledge_read
        if key == "knowledge_read"
        else calculate_knowledge_registry
    )
    expected = service(**data)
    try:
        matches = "error" not in expected and all(
            field in result and canonical_bytes(result[field]) == canonical_bytes(value)
            for field, value in expected.items()
        )
    except (TypeError, ValueError) as exc:
        raise EphemerisSourceError("human_design_reference_changed") from exc
    if not matches:
        raise EphemerisSourceError("human_design_reference_changed")
