"""Compatibility tool declarations and domain binding helpers."""

from __future__ import annotations

from fatebridge.application.bindings import lazy_service, pair_invoke
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.requests.compatibility import TwoPersonCompatibilityRequest

calculate_compatibility_analysis = lazy_service(
    "fatebridge.services.compatibility", "calculate_compatibility_analysis"
)

SPECS: list[ToolSpec] = [
    ToolSpec(
        key="two_person_compatibility",
        bind=pair_invoke(calculate_compatibility_analysis),
        request_model=TwoPersonCompatibilityRequest,
        summary="双人八字取证，返回双方盘式、跨盘干支接触及双向十神。关系类型只记录用户提供的语境。",
        operation_label_zh="双人八字取证",
        family="compatibility",
        rest_path="/api/bazi/compatibility",
        mcp_name="bazi_compatibility",
        cpu_bound=True,
    ),
]
