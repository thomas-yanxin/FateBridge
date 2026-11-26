"""Astrology tool declarations and domain binding helpers."""

from __future__ import annotations

from itertools import chain

from fatebridge.application.bindings import lazy_service, raw_invoke
from fatebridge.application.domain_validators import (
    validate_astro_chart_variant,
    validate_chart_variant_roots,
)
from fatebridge.application.tool_spec import EvidenceViews, ServiceResult, ToolSpec
from fatebridge.core.astro.reference import (
    RELATIVE_MODE_EXACT_ALIASES,
    RELATIVE_MODE_FALLBACK_ALIASES,
    RELATIVE_MODE_NUMERIC_MAP,
)
from fatebridge.core.contracts.output_human_design import HumanDesignOutput
from fatebridge.core.requests.astrology import (
    AstroChartPolyRequest,
    AstroChartRequest,
    AstroGermanyRequest,
    AstroGuolaoRequest,
    AstroIndiaRequest,
    AstroRelativeFlatRequest,
    AstroSpecialtyRequest,
    AstroVimshottariRequest,
)
from fatebridge.core.requests.human_design import HumanDesignRequest
from fatebridge.core.response_models import (
    CHART_VARIANT_TOOL_KEYS,
    required_output_fields_for,
)
from fatebridge.services.catalog.astro_bindings import (
    _astro_chart_bind,
    _astro_relative_flat_bind,
    calculate_core_chart_analysis,
    calculate_germany_chart_analysis,
)

RELATIONSHIP_PRIMARY_FIELDS = {
    "directional_synastry": {
        "synastry_aspects",
        "in_to_out_aspects",
        "out_to_in_aspects",
    },
    "composite_chart": {"chart"},
    "influence_chart_pair": {"inner", "outer"},
    "timespace_chart": {"chart"},
    "marks_chart_pair": {"marks_charts"},
}


def _compact_relationship(result: ServiceResult) -> ServiceResult:
    primary_layer = result["relationship_profile"]["primary_layer"]
    fields = {"relationship_profile", "summary", "run_metadata", "snapshot_text"}
    fields.update(RELATIONSHIP_PRIMARY_FIELDS[primary_layer])
    view = {key: value for key, value in result.items() if key in fields}
    planet_fields = {"id", "longitude", "latitude", "sign", "sign_zh", "house"}

    def positions(chart: ServiceResult) -> ServiceResult:
        return {
            **chart,
            "planets": [
                {key: value for key, value in planet.items() if key in planet_fields}
                for planet in chart["planets"]
            ],
        }

    if primary_layer == "marks_chart_pair":
        view["marks_charts"] = {
            role: positions(chart) for role, chart in view["marks_charts"].items()
        }
    elif primary_layer == "influence_chart_pair":
        for role in ("inner", "outer"):
            view[role] = {**view[role], "chart": positions(view[role]["chart"])}
    elif "chart" in view:
        view["chart"] = positions(view["chart"])
    return view


def _relative_evidence_views(
    views: EvidenceViews | None,
) -> EvidenceViews | None:
    if views is None:
        return None
    aliases: dict[str | int, str] = dict(
        chain(
            RELATIVE_MODE_FALLBACK_ALIASES.items(),
            RELATIVE_MODE_EXACT_ALIASES.items(),
            RELATIVE_MODE_NUMERIC_MAP.items(),
        )
    )
    for name, card in views.items():
        if "relative_mode" in card:
            card["aliases"] = [a for a, target in aliases.items() if target == name]
    return views


def _chart_spec(
    key: str,
    rest_path: str,
    mcp_name: str,
    variant: str,
    label: str,
) -> ToolSpec:
    return ToolSpec(
        key=key,
        bind=raw_invoke(
            calculate_core_chart_analysis, fixed={"chart_variant": variant}
        ),
        request_model=(
            AstroIndiaRequest
            if variant == "india_chart"
            else (
                AstroGuolaoRequest
                if variant == "guolao_chart"
                else (
                    AstroSpecialtyRequest if variant == "chart13" else AstroChartRequest
                )
            )
        ),
        summary=(
            "印占 Lahiri 整宫与所选分盘，含未削减PAV/BAV/SAV及七曜占据口径的削减/Pinda；原文缺项保留空值，附生时抽样与实际星历来源。计数不是事件概率。"
            if variant == "india_chart"
            else (
                "果老研究盘：七政四余连续坐标、现代不等赤经宿界、宫主/度主与来源追踪；可显式选择真太阳日安命的冬至日纳入或排除研究口径，回显日界夹逼。可选明确目标时刻的小限逆数及当时十一曜，需要Swiss Ephemeris，完整流年、原典全盘与现实效力尚未验收。"
                if variant == "guolao_chart"
                else f"离线{label}（优先本地高精度星历，缺失时回退近似模型）。"
            )
        ),
        operation_label_zh=label,
        family="astro",
        cpu_bound=True,
        rest_path=rest_path,
        mcp_name=mcp_name,
        output_validators=(validate_astro_chart_variant,),
    )


SPECS: list[ToolSpec] = [
    ToolSpec(
        key="human_design",
        bind=raw_invoke(
            lazy_service("fatebridge.services.human_design", "calculate_human_design")
        ),
        request_model=HumanDesignRequest,
        output_model=HumanDesignOutput,
        required_output_fields=(
            "activations",
            "variables",
            "bodygraph",
            "profile",
            "design_solver",
            "rulesets",
            "rule_trace",
            "source_consistency",
            "gate_evidence",
            "historical_polarity_context",
            "gate_activation_context",
            "profile_partition_context",
            "apparent_position_context",
            "depth_evidence",
            "definition_bridging",
            "incarnation_cross",
            "cycle_context",
            "cycle_summary",
            "interpretation",
            "validation",
        ),
        summary="人类图：连续TT求解88°双时刻、26激活、门线、Variable、通道、类型权威、人生角色与交叉名称；区分定义中心active与未定义中心dormant，保留悬挂门宽窄口径。最少门桥接、原典线极性及固定依据。可选明确评估时刻计算土星回归、天王星对冲、凯龙星回归的多次交会；有限搜索不认证穷尽或现实预测。",
        operation_label_zh="人类图",
        family="astro",
        cpu_bound=True,
        rest_path="/api/human-design/chart",
        mcp_name="human_design",
        include_snapshot_text=False,
    ),
    ToolSpec(
        key="astro_chart",
        bind=_astro_chart_bind,
        request_model=AstroChartPolyRequest,
        summary=(
            "离线核心星盘：默认本命盘；可选 chart_variant 切换盘式"
            "（chart13=13等分扇区 / hellen_chart=希腊 / guolao_chart=果老星宗 / "
            "india_chart=印度 / germany=德国盘引擎），等价于对应的 thirteen_sector_chart 等专用工具。"
        ),
        operation_label_zh="星盘",
        family="astro",
        cpu_bound=True,
        rest_path="/api/astrology/chart",
        mcp_name="astrology_chart",
        required_output_validator=validate_chart_variant_roots,
        required_output_fields_by_variant={
            variant: tuple(required_output_fields_for(owner))
            for variant, owner in CHART_VARIANT_TOOL_KEYS.items()
        },
        output_validators=(validate_astro_chart_variant,),
    ),
    _chart_spec(
        "astro_chart13",
        "/api/astrology/thirteen-sector-chart",
        "thirteen_sector_chart",
        "chart13",
        "13等分扇区盘",
    ),
    _chart_spec(
        "astro_hellen",
        "/api/astrology/hellenistic-chart",
        "hellenistic_chart",
        "hellen_chart",
        "希腊盘",
    ),
    _chart_spec(
        "astro_guolao",
        "/api/astrology/guolao-chart",
        "guolao_chart",
        "guolao_chart",
        "果老星宗盘",
    ),
    _chart_spec(
        "astro_india",
        "/api/astrology/vedic-chart",
        "vedic_chart",
        "india_chart",
        "印度盘",
    ),
    ToolSpec(
        key="astro_vimshottari",
        bind=raw_invoke(
            lazy_service("fatebridge.services.jyotish", "calculate_vimshottari")
        ),
        request_model=AstroVimshottariRequest,
        summary="印度占星 Moon-nakshatra Vimshottari：出生剩余运、目标主运/次运及所在120年规则周期；dasha_depth可选2至6层，增加当前路径与逐层九个子期，生时网格保留完整运主链。各边界在同一出生历元上保留有理数，最终量化一次；time_quantization明示实现约定。附分盘和具名八分法／Pinda，原文缺项为空，细分层级不代表事件精度或概率。",
        operation_label_zh="印占 Vimshottari 分期",
        family="astro",
        cpu_bound=True,
        rest_path="/api/astrology/vimshottari-dasha",
        mcp_name="vimshottari_dasha",
    ),
    ToolSpec(
        key="astro_germany",
        bind=raw_invoke(calculate_germany_chart_analysis),
        request_model=AstroGermanyRequest,
        summary="德国中点盘：22因素、253中点轴、90/45度盘三/四因素式及来源；可选目标时刻的真太阳弧和具名1924黄道日推运天顶。含八个数学假设点，象征推运不等于目标日观测或事件概率。旧七曜视图保留。",
        operation_label_zh="德国盘",
        family="astro",
        cpu_bound=True,
        rest_path="/api/astrology/hamburg-midpoint-chart",
        mcp_name="hamburg_midpoint_chart",
        output_validators=(validate_astro_chart_variant,),
    ),
    ToolSpec(
        key="astro_relative_chart",
        bind=_astro_relative_flat_bind,
        request_model=AstroRelativeFlatRequest,
        summary="关系／合盘：比较、影响、组合中点、三种Davison变体及双方Marks个人盘。请求使用 inner_ 和 outer_ 字段，返回原生坐标、时间与方法来源。",
        operation_label_zh="关系星盘分析",
        family="astro",
        cpu_bound=True,
        rest_path="/api/astrology/relationship-chart",
        mcp_name="relationship_chart",
        evidence_views_builder=_relative_evidence_views,
        compact_view=_compact_relationship,
    ),
]
