"""Compatibility tool declarations and domain binding helpers."""

from __future__ import annotations

from typing import List

from fatebridge.application.bindings import lazy_service, pair_invoke
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.method_contracts import COMPATIBILITY_INDEX
from fatebridge.core.requests.compatibility import TwoPersonCompatibilityRequest

calculate_compatibility_analysis = lazy_service(
    "fatebridge.services.compatibility", "calculate_compatibility_analysis"
)

SPECS: List[ToolSpec] = [
    # --- Compatibility -----------------------------------------------------
    ToolSpec(
        key="two_person_compatibility",
        bind=pair_invoke(calculate_compatibility_analysis),
        request_model=TwoPersonCompatibilityRequest,
        summary="双人关系配合度分析（未知关系用 general；婚姻、友谊、合作、家庭仅按用户明确关系选择）。",
        operation_label_zh="配合度分析",
        family="compatibility",
        rest_path="/api/compatibility",
        mcp_name="two_person_compatibility",
        cpu_bound=True,
        methods=(COMPATIBILITY_INDEX,),
    ),
]
