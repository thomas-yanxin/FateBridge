"""Bazi tool declarations and domain binding helpers."""

from __future__ import annotations

from pydantic import BaseModel

from fatebridge.application.bindings import (
    LazyService,
    lazy_service,
    person_invoke,
    raw_invoke,
)
from fatebridge.application.domain_validators import validate_bazi_anchors
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.requests.bazi import (
    BaziBirthRequest,
    BaziCareerRequest,
    BaziChildrenRequest,
    BaziEducationRequest,
    BaziHealthRequest,
    BaziMarriageRequest,
    BaziPersonalityRequest,
    BaziRelativesRequest,
    BaziRomanceRequest,
    BaziSourceCompareRequest,
    BaziWealthRequest,
)
from fatebridge.core.requests.birth import BaziClockRequest

calculate_bazi_birth = lazy_service("fatebridge.services.bazi", "calculate_bazi_birth")
calculate_bazi_source_compare = lazy_service(
    "fatebridge.services.source_comparison", "calculate_bazi_source_compare"
)


calculate_bazi_career = lazy_service(
    "fatebridge.services.bazi", "calculate_bazi_career"
)


calculate_bazi_children = lazy_service(
    "fatebridge.services.bazi", "calculate_bazi_children"
)


calculate_bazi_education = lazy_service(
    "fatebridge.services.bazi", "calculate_bazi_education"
)


calculate_bazi_health = lazy_service(
    "fatebridge.services.bazi", "calculate_bazi_health"
)


calculate_bazi_marriage = lazy_service(
    "fatebridge.services.bazi", "calculate_bazi_marriage"
)


calculate_bazi_personality = lazy_service(
    "fatebridge.services.bazi", "calculate_bazi_personality"
)


calculate_bazi_relatives = lazy_service(
    "fatebridge.services.bazi", "calculate_bazi_relatives"
)


calculate_bazi_romance = lazy_service(
    "fatebridge.services.bazi", "calculate_bazi_romance"
)


calculate_bazi_wealth = lazy_service(
    "fatebridge.services.bazi", "calculate_bazi_wealth"
)


calculate_destiny_analysis = lazy_service(
    "fatebridge.services.calculation", "calculate_destiny_analysis"
)


def _bazi_dimension_spec(
    name: str, service: LazyService, model: type[BaseModel], label: str
) -> ToolSpec:
    return ToolSpec(
        key=f"bazi_{name}",
        bind=person_invoke(service),
        request_model=model,
        summary=(
            f"{label}取证：四柱星位、传统前提与当前大运／流年触点。"
            "先读 evidence_chain.topic.first_view，按需读取深层事实。"
            "大运、流年默认随分析日期推算，支持显式柱覆盖。"
        ),
        operation_label_zh=label,
        family="bazi",
        rest_path=f"/api/bazi/{name}",
        mcp_name=f"bazi_{name}",
        cpu_bound=True,
        output_validators=(validate_bazi_anchors,),
        optional_snapshot=True,
    )


SPECS: list[ToolSpec] = [
    ToolSpec(
        key="analyze_destiny",
        bind=person_invoke(calculate_destiny_analysis),
        request_model=BaziClockRequest,
        summary=(
            "八字综合命理分析：在命盘之上叠加喜用神判定与格局识别，"
            "输出最完整的命理画像；只需四柱/十神原始命盘用 bazi_birth_chart。"
        ),
        operation_label_zh="命理分析",
        family="bazi",
        rest_path="/api/bazi/overview",
        mcp_name="bazi_overview",
        cpu_bound=True,
        output_validators=(validate_bazi_anchors,),
    ),
    ToolSpec(
        key="bazi_birth",
        bind=person_invoke(calculate_bazi_birth),
        request_model=BaziBirthRequest,
        summary=(
            "八字标准命盘：返回完整 snapshot_text 与可按 section 裁剪的 "
            "snapshot_export，是获取四柱/十神/五行的首选；喜用与格局分析用 bazi_overview。"
        ),
        operation_label_zh="八字命盘",
        family="bazi",
        rest_path="/api/bazi/birth-chart",
        mcp_name="bazi_birth_chart",
        cpu_bound=True,
        optional_snapshot=True,
        output_validators=(validate_bazi_anchors,),
    ),
    _bazi_dimension_spec(
        "marriage", calculate_bazi_marriage, BaziMarriageRequest, "八字婚姻分析"
    ),
    _bazi_dimension_spec(
        "career", calculate_bazi_career, BaziCareerRequest, "八字事业分析"
    ),
    _bazi_dimension_spec(
        "wealth", calculate_bazi_wealth, BaziWealthRequest, "八字财运分析"
    ),
    _bazi_dimension_spec(
        "health", calculate_bazi_health, BaziHealthRequest, "八字健康分析"
    ),
    _bazi_dimension_spec(
        "children", calculate_bazi_children, BaziChildrenRequest, "八字子女分析"
    ),
    _bazi_dimension_spec(
        "education", calculate_bazi_education, BaziEducationRequest, "八字学业分析"
    ),
    _bazi_dimension_spec(
        "personality",
        calculate_bazi_personality,
        BaziPersonalityRequest,
        "八字性格分析",
    ),
    _bazi_dimension_spec(
        "relatives", calculate_bazi_relatives, BaziRelativesRequest, "八字六亲分析"
    ),
    _bazi_dimension_spec(
        "romance", calculate_bazi_romance, BaziRomanceRequest, "八字正缘桃花分析"
    ),
    ToolSpec(
        key="bazi_source_compare",
        bind=raw_invoke(calculate_bazi_source_compare),
        request_model=BaziSourceCompareRequest,
        summary="按明确给出的字面四柱计算当前旺衰，并与全部已登记同柱原典编释核对。显示差异、未裁定及未收录；不改计算、不反推生日、不认证完整原典或现实预测。",
        operation_label_zh="原典四柱核对",
        family="bazi",
        rest_path="/api/bazi/compare-sources",
        mcp_name="compare_bazi_sources",
        cpu_bound=True,
        include_snapshot_text=False,
    ),
]
