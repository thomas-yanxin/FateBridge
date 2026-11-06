"""Reference tool declarations and domain binding helpers."""

from __future__ import annotations

from typing import List

from fatebridge.application.bindings import lazy_service, raw_invoke
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.requests.reference import (
    ExportParseRequest,
    ExportRegistryRequest,
    KnowledgeReadRequest,
    KnowledgeRegistryRequest,
)

calculate_export_parse = lazy_service(
    "fatebridge.services.export_tools", "calculate_export_parse"
)


calculate_export_registry = lazy_service(
    "fatebridge.services.export_tools", "calculate_export_registry"
)


calculate_knowledge_read = lazy_service(
    "fatebridge.services.knowledge", "calculate_knowledge_read"
)


calculate_knowledge_registry = lazy_service(
    "fatebridge.services.knowledge", "calculate_knowledge_registry"
)

SPECS: List[ToolSpec] = [
    ToolSpec(
        key="export_registry",
        bind=raw_invoke(calculate_export_registry),
        request_model=ExportRegistryRequest,
        summary="返回 FateBridge 导出协议注册表。",
        operation_label_zh="导出注册表",
        family="export",
        rest_path="/api/export/registry",
        mcp_name="export_registry",
    ),
    ToolSpec(
        key="export_parse",
        bind=raw_invoke(calculate_export_parse),
        request_model=ExportParseRequest,
        summary="将快照文本解析为可筛选的结构化 section。",
        operation_label_zh="导出解析",
        family="export",
        rest_path="/api/export/parse",
        mcp_name="export_parse",
    ),
    ToolSpec(
        key="knowledge_registry",
        bind=raw_invoke(calculate_knowledge_registry),
        request_model=KnowledgeRegistryRequest,
        summary="列出内置知识域与分类。",
        operation_label_zh="知识目录",
        family="knowledge",
        rest_path="/api/knowledge/registry",
        mcp_name="knowledge_registry",
    ),
    ToolSpec(
        key="knowledge_read",
        bind=raw_invoke(calculate_knowledge_read),
        request_model=KnowledgeReadRequest,
        summary="读取单条内置知识并支持导出裁剪。",
        operation_label_zh="知识读取",
        family="knowledge",
        rest_path="/api/knowledge/read",
        mcp_name="knowledge_read",
    ),
]
