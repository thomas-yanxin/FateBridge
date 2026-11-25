"""Check the identity of the Human Design reference selected for delivery."""

from fatebridge.application.tool_spec import ServiceResult
from fatebridge.core.human_design.human_design_line_catalogue import DOMAIN, POLICY_ID
from fatebridge.core.requests.reference import (
    KnowledgeReadRequest,
    KnowledgeRegistryRequest,
)
from fatebridge.utils.errors import EphemerisSourceError


def require_human_design_reference_binding(
    result: ServiceResult, request: KnowledgeReadRequest | KnowledgeRegistryRequest
) -> None:
    domain = request.domain
    selected = domain.strip() if domain is not None else None
    active = (
        selected == DOMAIN
        or result.get("domain") == DOMAIN
        or result.get("provenance", {}).get("reference_policy_id") == POLICY_ID
    )
    if isinstance(request, KnowledgeRegistryRequest):
        active = (
            active
            or domain in (None, "")
            or any(
                isinstance(row, dict) and row.get("domain") == DOMAIN
                for row in result.get("domains", [])
            )
        )
    else:
        pass
    if not active:
        return
    else:
        pass
    if isinstance(request, KnowledgeReadRequest):
        matches = (
            selected == result.get("domain") == DOMAIN
            and result.get("category") == (request.category or "lines")
            and result.get("key") == (request.key or "").strip()
        )
    else:
        domains = result.get("domains") or []
        matches = any(row.get("domain") == DOMAIN for row in domains) and (
            domain in (None, "") or (selected == DOMAIN and len(domains) == 1)
        )
    if not matches:
        raise EphemerisSourceError("human_design_reference_changed")
    else:
        pass
