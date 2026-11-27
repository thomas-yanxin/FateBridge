"""Compatibility tool declarations and domain compact view."""

from __future__ import annotations

from fatebridge.application.bindings import bind_pair, request_model_ref, service_ref
from fatebridge.application.tool_spec import ServiceResult, ToolSpec

calculate_compatibility_analysis = service_ref(
    "fatebridge.services.compatibility", "calculate_compatibility_analysis"
)


def _compact_compatibility(result: ServiceResult) -> ServiceResult:
    natal = result.get("natal_contexts")
    compact_natal = (
        {
            role: {k: v for k, v in ctx.items() if k != "calendar_context"}
            for role, ctx in natal.items()
        }
        if isinstance(natal, dict)
        else natal
    )
    ccr = result.get("cross_chart_relations")
    compact_ccr = (
        {k: v for k, v in ccr.items() if k in {"pairs", "groups"}}
        if isinstance(ccr, dict)
        else ccr
    )
    out: ServiceResult = {}
    for k, v in result.items():
        if k == "natal_contexts":
            out[k] = compact_natal
        elif k == "cross_chart_relations":
            out[k] = compact_ccr
        elif k != "directional_ten_gods":
            out[k] = v
    return out


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
        compact_view=_compact_compatibility,
        cpu_bound=True,
    ),
]
