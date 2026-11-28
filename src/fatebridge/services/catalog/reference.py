"""Reference tool declarations and domain binding helpers."""

from __future__ import annotations

from fatebridge.application.bindings import bind_kwargs, request_model_ref, service_ref
from fatebridge.application.tool_spec import ToolSpec

calculate_knowledge_read = service_ref(
    "fatebridge.services.knowledge", "calculate_knowledge_read"
)


calculate_knowledge_registry = service_ref(
    "fatebridge.services.knowledge", "calculate_knowledge_registry"
)

calculate_place_lookup = service_ref("fatebridge.utils.places", "lookup_place")


SPECS: list[ToolSpec] = [
    ToolSpec(
        name="knowledge_catalog",
        bind=bind_kwargs(calculate_knowledge_registry),
        request_model_loader=request_model_ref(
            "fatebridge.core.requests.reference", "KnowledgeRegistryRequest"
        ),
        required_output_fields=("domains", "provenance"),
        summary="列出内置知识域与分类。",
        operation_label_zh="知识目录",
        family="knowledge",
        rest_path="/api/knowledge/catalog",
        uses_astronomy_runtime=False,
        default_omit=("provenance",),
    ),
    ToolSpec(
        name="knowledge_read",
        bind=bind_kwargs(calculate_knowledge_read),
        request_model_loader=request_model_ref(
            "fatebridge.core.requests.reference", "KnowledgeReadRequest"
        ),
        required_output_fields=("lines", "provenance"),
        summary="读取单条内置知识与出处依据。",
        operation_label_zh="知识读取",
        family="knowledge",
        rest_path="/api/knowledge/read",
        uses_astronomy_runtime=False,
        default_omit=("provenance", "reference_details"),
    ),
    ToolSpec(
        name="place_lookup",
        bind=bind_kwargs(calculate_place_lookup),
        request_model_loader=request_model_ref(
            "fatebridge.core.requests.reference", "PlaceLookupRequest"
        ),
        required_output_fields=("query", "status", "candidates", "summary"),
        summary="查询内置地名坐标、时区与行政层级，同名地名返回消歧候选。",
        operation_label_zh="地名坐标查询",
        family="knowledge",
        rest_path="/api/places/lookup",
        uses_astronomy_runtime=False,
        default_omit=(),
    ),
]
