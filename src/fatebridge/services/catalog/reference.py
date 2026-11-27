"""Reference tool declarations and domain binding helpers."""

from __future__ import annotations

from fatebridge.application.bindings import bind_kwargs, request_model_ref, service_ref
from fatebridge.application.domain_validators import validate_knowledge_bindings
from fatebridge.application.tool_spec import ServiceResult, ToolSpec

calculate_knowledge_read = service_ref(
    "fatebridge.services.knowledge", "calculate_knowledge_read"
)


calculate_knowledge_registry = service_ref(
    "fatebridge.services.knowledge", "calculate_knowledge_registry"
)

calculate_place_lookup = service_ref(
    "fatebridge.services.places", "calculate_place_lookup"
)


def compact_knowledge_catalog(result: ServiceResult) -> ServiceResult:
    """Return a concise (<5 KB) domain/category index without duplicate provenance trees."""
    compact_domains = []
    for domain in result.get("domains", []):
        compact_categories = []
        for cat in domain.get("categories", []):
            sample = cat.get("keys_sample") or cat.get("keys") or []
            entry: dict[str, object] = {
                "name": cat["name"],
                "count": cat["count"],
                "keys_sample": list(sample[:4]),
            }
            if cat.get("key_format"):
                entry["key_format"] = cat["key_format"]
            compact_categories.append(entry)
        compact_domains.append(
            {
                "domain": domain["domain"],
                "categories": compact_categories,
            }
        )
    return {
        "source": result.get("source"),
        "domains": compact_domains,
    }


def compact_knowledge_read(result: ServiceResult) -> ServiceResult:
    """Strip bloated provenance trees in compact mode while keeping core card facts."""
    return {
        key: value
        for key, value in result.items()
        if key not in {"provenance", "reference_details"}
    }


SPECS: list[ToolSpec] = [
    ToolSpec(
        name="knowledge_catalog",
        bind=bind_kwargs(calculate_knowledge_registry),
        request_model_loader=request_model_ref(
            "fatebridge.core.requests.reference", "KnowledgeRegistryRequest"
        ),
        summary="列出内置知识域与分类。",
        operation_label_zh="知识目录",
        family="knowledge",
        rest_path="/api/knowledge/catalog",
        uses_astronomy_runtime=False,
        output_validators=(validate_knowledge_bindings,),
        compact_view=compact_knowledge_catalog,
    ),
    ToolSpec(
        name="knowledge_read",
        bind=bind_kwargs(calculate_knowledge_read),
        request_model_loader=request_model_ref(
            "fatebridge.core.requests.reference", "KnowledgeReadRequest"
        ),
        summary="读取单条内置知识与出处依据。",
        operation_label_zh="知识读取",
        family="knowledge",
        rest_path="/api/knowledge/read",
        uses_astronomy_runtime=False,
        output_validators=(validate_knowledge_bindings,),
        compact_view=compact_knowledge_read,
    ),
    ToolSpec(
        name="place_lookup",
        bind=bind_kwargs(calculate_place_lookup),
        request_model_loader=request_model_ref(
            "fatebridge.core.requests.reference", "PlaceLookupRequest"
        ),
        summary="查询内置地名坐标、时区与行政层级，同名地名返回消歧候选。",
        operation_label_zh="地名坐标查询",
        family="knowledge",
        rest_path="/api/places/lookup",
        uses_astronomy_runtime=False,
    ),
]
