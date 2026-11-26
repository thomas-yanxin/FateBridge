"""Reference tool declarations and domain binding helpers."""

from __future__ import annotations

from fatebridge.application.bindings import bind_kwargs, request_model_ref, service_ref
from fatebridge.application.domain_validators import validate_knowledge_bindings
from fatebridge.application.tool_spec import ToolSpec

calculate_knowledge_read = service_ref(
    "fatebridge.services.knowledge", "calculate_knowledge_read"
)


calculate_knowledge_registry = service_ref(
    "fatebridge.services.knowledge", "calculate_knowledge_registry"
)


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
    ),
]
