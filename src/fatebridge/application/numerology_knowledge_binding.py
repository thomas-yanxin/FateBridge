"""Bind new knowledge facts to the actual request and source revision pre-projection."""

from pydantic import BaseModel

from fatebridge.core.numerology_knowledge import DOMAINS, canonical_bytes
from fatebridge.utils.errors import NumerologySourceError


def require_reference_binding(
    key: str, result: dict, request: BaseModel | None
) -> None:
    if request is None or key not in {"knowledge_read", "knowledge_registry"}:
        return
    domain = getattr(request, "domain", None)
    selected = domain.strip() if isinstance(domain, str) else domain
    active = selected in DOMAINS or result.get("domain") in DOMAINS
    if key == "knowledge_registry":
        active = (
            active
            or selected in (None, "")
            or any(
                isinstance(d, dict) and d.get("domain") in DOMAINS
                for d in result.get("domains", [])
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
            field not in result
            or canonical_bytes(result[field]) != canonical_bytes(value)
            for field, value in expected.items()
        ):
            raise ValueError(
                "Reference facts/citation differ from original query and pinned sources"
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError(
            "runtime_numerology_knowledge_binding_conflict"
        ) from exc
