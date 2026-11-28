"""Compatibility tool declarations."""

from __future__ import annotations

from fatebridge.application.bindings import bind_pair, request_model_ref, service_ref
from fatebridge.application.tool_spec import ToolSpec

calculate_compatibility_analysis = service_ref(
    "fatebridge.services.compatibility", "calculate_compatibility_analysis"
)


SPECS: list[ToolSpec] = [
    ToolSpec(
        name="bazi_compatibility",
        bind=bind_pair(calculate_compatibility_analysis),
        request_model_loader=request_model_ref(
            "fatebridge.core.requests.compatibility", "TwoPersonCompatibilityRequest"
        ),
        summary="双人八字合婚与关系分析：四柱、喜用互补、年命纳音、鸳鸯合、跨盘干支、双向十神及神煞互照。",
        operation_label_zh="双人八字合盘",
        family="compatibility",
        rest_path="/api/bazi/compatibility",
        cpu_bound=True,
        default_omit=(
            "natal_contexts.*.calendar_context",
            "natal_contexts.*.day_master",
            "cross_chart_relations.directional_punishments",
            "directional_ten_gods",
        ),
    ),
]
