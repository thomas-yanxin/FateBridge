"""Bazi tool declarations and domain binding helpers."""

from __future__ import annotations

from typing import Any, Dict, List

from fatebridge.application.bindings import lazy_service, person_invoke
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
    BaziWealthRequest,
)
from fatebridge.core.requests.birth import FateBridgeRequest

calculate_bazi_birth = lazy_service("fatebridge.services.bazi", "calculate_bazi_birth")


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


def _bazi_dimension_spec(name: str, service: Any, model: Any, label: str) -> ToolSpec:
    return ToolSpec(
        key=f"bazi_{name}",
        bind=person_invoke(service),
        request_model=model,
        summary=(
            f"{label}：已按出生资料与分析日期自动推算大运、流年和时机依据；"
            "首轮无需先调用 timing_analysis 或手动传大运柱。"
            "仅有明确外部口径时用 dayun_pillar / liunian_pillar 覆盖。"
            + (
                "仅解释盘内五行权重、寒暖分类与传统对应；不作中医体质辨识、疾病风险、诊断或调理处方。"
                if name == "health"
                else (
                    "命主子女星／宫的传统对应，不是孩子本人测算；不预测子女数量、生育能力或生育时间。"
                    if name == "children"
                    else ""
                )
            )
        ),
        operation_label_zh=label,
        family="bazi",
        rest_path=f"/api/cn/bazi/{name}",
        mcp_name=f"bazi_{name}",
        cpu_bound=True,
        # The dimension factory now renders a structured snapshot_text, so this
        # tool participates in the standard snapshot contract (default True).
    )


SPECS: List[ToolSpec] = [
    ToolSpec(
        key="analyze_destiny",
        bind=person_invoke(calculate_destiny_analysis),
        request_model=FateBridgeRequest,
        summary=(
            "八字综合命理分析：在命盘之上叠加喜用神判定与格局识别，"
            "输出最完整的命理画像；只需四柱/十神原始命盘用 bazi_birth。"
        ),
        operation_label_zh="命理分析",
        family="bazi",
        rest_path=None,
        mcp_name="analyze_destiny",
        cpu_bound=True,
    ),
    ToolSpec(
        key="bazi_birth",
        bind=person_invoke(calculate_bazi_birth),
        request_model=BaziBirthRequest,
        summary=(
            "八字标准命盘：返回完整 snapshot_text 与可按 section 裁剪的 "
            "snapshot_export，是获取四柱/十神/五行的首选；要喜用+格局解读用 analyze_destiny。"
        ),
        operation_label_zh="八字命盘",
        family="bazi",
        rest_path="/api/cn/bazi/birth",
        mcp_name="bazi_birth",
        cpu_bound=True,
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
]
