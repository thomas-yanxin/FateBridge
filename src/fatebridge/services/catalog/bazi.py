"""Bazi tool declarations and domain binding helpers."""

from __future__ import annotations

from fatebridge.application.bindings import (
    ServiceRef,
    bind_kwargs,
    bind_person,
    request_model_ref,
    service_ref,
)
from fatebridge.application.domain_validators import validate_bazi_anchors
from fatebridge.application.tool_spec import ToolSpec
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


calculate_destiny_analysis = service_ref(
    "fatebridge.services.calculation", "calculate_destiny_analysis"
)


def _bazi_dimension_spec(
    name: str, service: ServiceRef, model_name: str, label: str
) -> ToolSpec:
    return ToolSpec(
        name=f"bazi_{name}",
        bind=bind_person(service),
        request_model_loader=request_model_ref(_BAZI_REQ, model_name),
        summary=f"{label}取证：四柱星位、传统前提与大运流年触点。",
        operation_label_zh=label,
        family="bazi",
        rest_path=f"/api/bazi/{name}",
        cpu_bound=True,
        output_validators=(validate_bazi_anchors,),
    )


SPECS: list[ToolSpec] = [
    ToolSpec(
        name="bazi_overview",
        bind=bind_person(calculate_destiny_analysis),
        request_model_loader=request_model_ref(
            "fatebridge.core.requests.birth", "BaziClockRequest"
        ),
        summary="八字综合命理：命盘、喜用神与格局；仅需四柱十神用 bazi_birth_chart。",
        operation_label_zh="命理分析",
        family="bazi",
        rest_path="/api/bazi/overview",
        cpu_bound=True,
        reproducibility=ReproducibilityPolicy(implicit_current_time=True),
        output_validators=(validate_bazi_anchors,),
    ),
    ToolSpec(
        name="bazi_birth_chart",
        bind=bind_person(calculate_bazi_birth),
        request_model_loader=request_model_ref(_BAZI_REQ, "BaziBirthRequest"),
        summary="八字标准命盘：四柱、十神、五行与大运概略；喜用格局用 bazi_overview。",
        operation_label_zh="八字命盘",
        family="bazi",
        rest_path="/api/bazi/birth-chart",
        cpu_bound=True,
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
        cpu_bound=True,
    ),
]
