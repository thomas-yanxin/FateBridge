"""Bind Human Design reference facts to their original request before projection."""

from pydantic import BaseModel

from fatebridge.core.human_design_line_catalogue import DOMAIN, POLICY_ID, _canonical
from fatebridge.utils.errors import EphemerisSourceError


def require_human_design_reference_binding(
    key: str, result: dict, request: BaseModel | None
) -> None:
    if request is None or key not in {"knowledge_read", "knowledge_registry"}:
        return
    domain = getattr(request, "domain", None)
    selected = domain.strip() if isinstance(domain, str) else domain
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
    expected = service(**request.model_dump())
    try:
        if "error" in expected or any(
            field not in result or _canonical(result[field]) != _canonical(value)
            for field, value in expected.items()
        ):
            raise ValueError("Human Design reference differs from query or source")
    except (KeyError, TypeError, ValueError) as exc:
        raise EphemerisSourceError("human_design_reference_changed") from exc
