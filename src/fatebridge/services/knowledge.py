"""Serve bundled knowledge and render its source attribution."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import JsonValue

from fatebridge.core.human_design import knowledge as human_design_knowledge
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


_CATALOG_PROVENANCE_KEYS = (
    "source_domain",
    "domain",
    "bundle_version",
    "reference_policy_id",
    "source_catalogue_version",
    "reference_only",
    "personal_applicability_assessed",
    "whole_books_collated",
    "independent_whole_corpus_review_completed",
)


def _slim_catalog_provenance(provenance: dict[str, Any] | None) -> dict[str, Any]:
    data = provenance or {}
    slim: dict[str, Any] = {
        key: data[key] for key in _CATALOG_PROVENANCE_KEYS if key in data
    }
    slim.setdefault("reference_only", True)
    slim.setdefault("personal_applicability_assessed", False)
    return slim


def _slim_catalog_domain(domain_record: dict[str, Any]) -> dict[str, Any]:
    categories = []
    for cat in domain_record.get("categories", []):
        entry: dict[str, Any] = {
            "name": cat["name"],
            "count": cat["count"],
        }
        if "keys" in cat:
            entry["keys"] = list(cat["keys"][:2])
        elif "keys_sample" in cat:
            entry["keys_sample"] = list(cat["keys_sample"][:2])
        if cat.get("key_format"):
            entry["key_format"] = cat["key_format"]
        if "supports" in cat:
            entry["supports"] = list(cat["supports"])
        categories.append(entry)
    slim_domain: dict[str, Any] = {
        "domain": domain_record["domain"],
        "source": domain_record["source"],
        "categories": categories,
    }
    if domain_record.get("bundle_version") is not None:
        slim_domain["bundle_version"] = domain_record["bundle_version"]
    return slim_domain


@lru_cache(maxsize=16)
def _cached_registry(lookup_domain: str | None) -> dict[str, Any]:
    if lookup_domain == human_design_knowledge.DOMAIN:
        raw = human_design_knowledge.build_registry()
    elif lookup_domain in DOMAINS:
        raw = build_registry(lookup_domain)
    elif lookup_domain is None or lookup_domain == "":
        base_registry = build_knowledge_registry(domain=lookup_domain)
        added = [build_registry(name) for name in DOMAINS]
        added.append(human_design_knowledge.build_registry())
        return {
            "source": "fatebridge_mixed_knowledge",
            "bundle_version": None,
            "domains": [
                _slim_catalog_domain(domain_record)
                for domain_record in (
                    *base_registry["domains"],
                    *(
                        record
                        for provider in added
                        for record in provider["domains"]
                    ),
                )
            ],
            "provenance": {
                "source_domain": "fatebridge_mixed_knowledge",
                "reference_only": True,
                "personal_applicability_assessed": False,
                "whole_books_collated": False,
                "independent_whole_corpus_review_completed": False,
            },
        }
    else:
        raw = build_knowledge_registry(domain=lookup_domain)
    return {
        **raw,
        "domains": [_slim_catalog_domain(d) for d in raw.get("domains", [])],
        "provenance": _slim_catalog_provenance(raw.get("provenance")),
    }


def calculate_knowledge_registry(
    *,
    domain: str | None = None,
) -> dict[str, Any]:
    """List bundled knowledge domains and their available categories."""
    try:
        lookup_domain = domain.strip() if domain is not None else None
        return _cached_registry(lookup_domain)
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
