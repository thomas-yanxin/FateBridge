"""Compatibility tool declarations and domain binding helpers."""

from __future__ import annotations

from fatebridge.application.bindings import bind_pair, service_ref
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.requests.compatibility import TwoPersonCompatibilityRequest

calculate_compatibility_analysis = service_ref(
    "fatebridge.services.compatibility", "calculate_compatibility_analysis"
)

SPECS: list[ToolSpec] = [
    ToolSpec(
        name="bazi_compatibility",
        bind=bind_pair(calculate_compatibility_analysis),
        request_model=TwoPersonCompatibilityRequest,
        summary="双人八字取证，返回双方盘式、跨盘干支接触及双向十神。关系类型只记录用户提供的语境。",
        operation_label_zh="双人八字取证",
        family="compatibility",
        rest_path="/api/bazi/compatibility",
        cpu_bound=True,
    ),
]
