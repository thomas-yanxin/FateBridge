"""Serve bundled knowledge and render its source attribution."""

from __future__ import annotations

from typing import Any

from pydantic import JsonValue

from fatebridge.core.human_design import human_design_knowledge
from fatebridge.core.knowledge_store import (
    ToolValidationError,
    build_knowledge_registry,
    read_knowledge_entry,
)
from fatebridge.core.numerology.numerology_knowledge import (
    DOMAINS,
    SCOPE,
    SOURCE,
    build_registry,
    read_reference,
)
from fatebridge.utils.errors import handle_calculation_error


def _validation_error_payload(error: ToolValidationError) -> dict[str, JsonValue]:
    # note (REST): Status 400 keeps a lookup validation failure distinct from a service failure.
    return {
        "error": str(error),
        "error_code": error.code or "validation_error",
        "code": error.code,
        "details": error.details,
        "status_code": 400,
        "retryable": False,
    }


def calculate_knowledge_registry(
    *,
    domain: str | None = None,
) -> dict[str, Any]:
    """List bundled knowledge domains and their available categories."""
    try:
        lookup_domain = domain.strip() if domain is not None else None
        if lookup_domain == human_design_knowledge.DOMAIN:
            registry = human_design_knowledge.build_registry()
        elif lookup_domain in DOMAINS:
            registry = build_registry(lookup_domain)
        elif domain is None or domain == "":
            base_registry = build_knowledge_registry(domain=domain)
            added = [build_registry(name) for name in DOMAINS]
            added.append(human_design_knowledge.build_registry())
            registry = {
                **base_registry,
                "source": "fatebridge_mixed_knowledge",
                "bundle_version": None,
                "domains": [
                    *base_registry["domains"],
                    *(
                        domain_record
                        for provider in added
                        for domain_record in provider["domains"]
                    ),
                ],
                "provenance": {
                    "source_domain": "fatebridge_mixed_knowledge",
                    "components": [
                        base_registry["provenance"],
                        *(provider["provenance"] for provider in added),
                    ],
                    "added_reference_source": SOURCE,
                    "added_reference_scope": SCOPE,
                },
            }
        else:
            registry = build_knowledge_registry(domain=domain)
        return registry
    except ToolValidationError as exc:
        return _validation_error_payload(exc)
    except Exception as exc:
        return handle_calculation_error(exc, "知识目录")


def calculate_knowledge_read(
    *,
    domain: str,
    category: str | None = None,
    key: str | None = None,
    aspect_degree: int | str | None = None,
    object_a: str | None = None,
    object_b: str | None = None,
    jiang_name: str | None = None,
    tian_branch: str | None = None,
    di_branch: str | None = None,
) -> dict[str, Any]:
    """Read a knowledge card or source-bound reference.

    An omitted category requires a unique match in a domain that supports key lookup.
    """
    try:
        payload = {
            "domain": domain,
            "category": category,
            "key": key,
            "aspect_degree": aspect_degree,
            "object_a": object_a,
            "object_b": object_b,
            "jiang_name": jiang_name,
            "tian_branch": tian_branch,
            "di_branch": di_branch,
        }
        lookup_domain = domain.strip()
        if lookup_domain == human_design_knowledge.DOMAIN:
            irrelevant_fields: list[JsonValue] = [
                field_name
                for field_name, value in sorted(payload.items())
                if field_name not in {"domain", "category", "key"} and value is not None
            ]
            if irrelevant_fields:
                raise ToolValidationError(
                    "人类图线参考只接受category与key定位，不接受相位或其他域对象",
                    code="knowledge.human_design.irrelevant_fields",
                    details={"fields": irrelevant_fields},
                )
            entry = human_design_knowledge.read_reference(category=category, key=key)
        elif lookup_domain in DOMAINS:
            entry = read_reference(domain=lookup_domain, category=category, key=key)
        else:
            entry = read_knowledge_entry(payload)
        return entry
    except ToolValidationError as exc:
        return _validation_error_payload(exc)
    except Exception as exc:
        return handle_calculation_error(exc, "知识读取")
