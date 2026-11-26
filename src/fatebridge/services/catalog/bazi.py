"""Bazi tool declarations and domain compact views."""

from __future__ import annotations

from fatebridge.application.bindings import (
    ServiceRef,
    bind_kwargs,
    bind_person,
    request_model_ref,
    service_ref,
)
from fatebridge.application.domain_validators import validate_bazi_anchors
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.core.reproducibility import ReproducibilityPolicy

_BAZI_REQ = "fatebridge.core.requests.bazi"

calculate_bazi_birth = service_ref("fatebridge.services.bazi", "calculate_bazi_birth")
calculate_bazi_source_compare = service_ref(
    "fatebridge.services.source_comparison", "calculate_bazi_source_compare"
)
calculate_bazi_career = service_ref("fatebridge.services.bazi", "calculate_bazi_career")
calculate_bazi_children = service_ref(
    "fatebridge.services.bazi", "calculate_bazi_children"
)
calculate_bazi_education = service_ref(
    "fatebridge.services.bazi", "calculate_bazi_education"
)
calculate_bazi_health = service_ref("fatebridge.services.bazi", "calculate_bazi_health")
calculate_bazi_marriage = service_ref(
    "fatebridge.services.bazi", "calculate_bazi_marriage"
)
calculate_bazi_personality = service_ref(
    "fatebridge.services.bazi", "calculate_bazi_personality"
)
calculate_bazi_relatives = service_ref(
    "fatebridge.services.bazi", "calculate_bazi_relatives"
)
calculate_bazi_romance = service_ref(
    "fatebridge.services.bazi", "calculate_bazi_romance"
)
calculate_bazi_wealth = service_ref("fatebridge.services.bazi", "calculate_bazi_wealth")
calculate_bazi_overview = service_ref(
    "fatebridge.services.bazi", "calculate_bazi_overview"
)


def _compact_bazi_overview(result: ServiceResult) -> ServiceResult:
    return {
        k: v for k, v in result.items() if k not in {"calendar_context", "patterns"}
    }


def _compact_bazi_birth(result: ServiceResult) -> ServiceResult:
    birth = result.get("bazi_birth")
    if not isinstance(birth, dict):
        return result
    compact_birth = {
        k: v
        for k, v in birth.items()
        if k
        not in {"calendar_context", "analysis_calendar_context", "patterns", "shensha"}
    }
    return {"analysis_type": result.get("analysis_type"), "bazi_birth": compact_birth}


def _compact_bazi_dimension(result: ServiceResult) -> ServiceResult:
    cleaned: ServiceResult = {}
    for key, val in result.items():
        if key.endswith("_analysis") and isinstance(val, dict):
            cleaned[key] = {k: v for k, v in val.items() if k != "calendar_context"}
        else:
            cleaned[key] = val
    return cleaned


def _bazi_dimension_spec(
    name: str, service: ServiceRef, model_name: str, label: str
) -> ToolSpec:
    return ToolSpec(
        name=f"bazi_{name}",
        bind=bind_person(service),
        request_model_loader=request_model_ref(_BAZI_REQ, model_name),
        summary=f"{label}：四柱星宫、大运流年交互与专题取证。",
        operation_label_zh=label,
        family="bazi",
        rest_path=f"/api/bazi/{name}",
        cpu_bound=True,
        compact_view=_compact_bazi_dimension,
        output_validators=(validate_bazi_anchors,),
    )


SPECS: list[ToolSpec] = [
    ToolSpec(
        name="bazi_overview",
        bind=bind_person(calculate_bazi_overview),
        request_model_loader=request_model_ref(
            "fatebridge.core.requests.birth", "BaziClockRequest"
        ),
        summary="八字综合命理：命盘、格局、调候、喜用神与司令分野；完整盘式用 bazi_birth_chart。",
        operation_label_zh="命理分析",
        family="bazi",
        rest_path="/api/bazi/overview",
        cpu_bound=True,
        compact_view=_compact_bazi_overview,
        reproducibility=ReproducibilityPolicy(implicit_current_time=True),
        output_validators=(validate_bazi_anchors,),
    ),
    ToolSpec(
        name="bazi_birth_chart",
        bind=bind_person(calculate_bazi_birth),
        request_model_loader=request_model_ref(_BAZI_REQ, "BaziBirthRequest"),
        summary="八字标准命盘：四柱、三垣/胎息、十神、神煞、空亡、司令、大运/小运概略。",
        operation_label_zh="八字命盘",
        family="bazi",
        rest_path="/api/bazi/birth-chart",
        cpu_bound=True,
        compact_view=_compact_bazi_birth,
        output_validators=(validate_bazi_anchors,),
    ),
    _bazi_dimension_spec(
        "marriage", calculate_bazi_marriage, "BaziMarriageRequest", "八字婚姻分析"
    ),
    _bazi_dimension_spec(
        "career", calculate_bazi_career, "BaziCareerRequest", "八字事业分析"
    ),
    _bazi_dimension_spec(
        "wealth", calculate_bazi_wealth, "BaziWealthRequest", "八字财运分析"
    ),
    _bazi_dimension_spec(
        "health", calculate_bazi_health, "BaziHealthRequest", "八字健康分析"
    ),
    _bazi_dimension_spec(
        "children", calculate_bazi_children, "BaziChildrenRequest", "八字子女分析"
    ),
    _bazi_dimension_spec(
        "education", calculate_bazi_education, "BaziEducationRequest", "八字学业分析"
    ),
    _bazi_dimension_spec(
        "personality",
        calculate_bazi_personality,
        "BaziPersonalityRequest",
        "八字性格分析",
    ),
    _bazi_dimension_spec(
        "relatives", calculate_bazi_relatives, "BaziRelativesRequest", "八字六亲分析"
    ),
    _bazi_dimension_spec(
        "romance", calculate_bazi_romance, "BaziRomanceRequest", "八字正缘桃花分析"
    ),
    ToolSpec(
        name="compare_bazi_sources",
        bind=bind_kwargs(calculate_bazi_source_compare),
        request_model_loader=request_model_ref(_BAZI_REQ, "BaziSourceCompareRequest"),
        summary="按字面四柱计算旺衰并核对同柱原典编释，列出差异与未收录；不反推生日。",
        operation_label_zh="原典四柱核对",
        family="bazi",
        rest_path="/api/bazi/compare-sources",
        required_output_fields=(
            "four_pillars",
            "input_context",
            "current_calculation",
            "source_comparison",
        ),
        cpu_bound=True,
    ),
]
