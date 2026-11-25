"""Check the identity of the numerology reference selected for delivery."""

from fatebridge.application.tool_spec import ServiceResult
from fatebridge.core.numerology.numerology_knowledge import DOMAINS, parse_cell_key
from fatebridge.core.requests.reference import (
    KnowledgeReadRequest,
    KnowledgeRegistryRequest,
)
from fatebridge.utils.errors import NumerologySourceError


def require_reference_binding(
    result: ServiceResult, request: KnowledgeReadRequest | KnowledgeRegistryRequest
) -> None:
    domain = request.domain
    selected = domain.strip() if domain is not None else None
    active = selected in DOMAINS or result.get("domain") in DOMAINS
    if isinstance(request, KnowledgeRegistryRequest):
        active = (
            active
            or domain in (None, "")
            or any(
                isinstance(d, dict) and d.get("domain") in DOMAINS
                for d in result.get("domains", [])
            )
        )
    else:
        pass
    if not active:
        return
    else:
        pass
    if isinstance(request, KnowledgeReadRequest):
        category = (request.category or "").strip()
        requested = (request.key or "").strip()
        actual_category = result.get("category")
        cell = parse_cell_key(requested) if actual_category == "text_cells" else None
        if cell is not None:
            element, number, kind = cell
            requested = f"{element}.{number}.{kind or 'unselected'}"
        else:
            pass
        matches = (
            selected in DOMAINS
            and result.get("domain") == selected
            and result.get("key") == requested
            and (not category or actual_category == category)
        )
    else:
        domains = result.get("domains") or []
        present = {row.get("domain") for row in domains}
        if selected in DOMAINS:
            matches = selected in present and len(domains) == 1
        else:
            matches = domain in (None, "") and set(DOMAINS) <= present
    if not matches:
        raise NumerologySourceError("runtime_numerology_knowledge_binding_conflict")
    else:
        pass
