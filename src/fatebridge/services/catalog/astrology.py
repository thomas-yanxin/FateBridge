"""Astrology tool declarations and domain binding helpers."""

from __future__ import annotations

from typing import List

from fatebridge.application.bindings import lazy_service, raw_invoke
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.output_human_design import HumanDesignOutput
from fatebridge.core.requests.astrology import (
    AstroChartPolyRequest,
    AstroChartRequest,
    AstroGermanyRequest,
    AstroGuolaoRequest,
    AstroIndiaRequest,
    AstroRelativeFlatRequest,
    AstroRelativeRequest,
    AstroSpecialtyRequest,
    AstroVimshottariRequest,
)
from fatebridge.core.requests.human_design import HumanDesignRequest
from fatebridge.services.catalog.astro_bindings import (
    _astro_chart_bind,
    _astro_relative_flat_bind,
    _astro_relative_rest_bind,
    calculate_core_chart_analysis,
    calculate_germany_chart_analysis,
)


def _chart_spec(
    key: str,
    rest_path: str,
    mcp_name: str,
    variant: str,
    label: str,
    metadata_name: str,
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
        rest_path=rest_path,
        mcp_name=mcp_name,
        metadata_name=metadata_name,
    )


SPECS: List[ToolSpec] = [
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
        rest_path="/api/astro/human-design",
        mcp_name="human_design",
        include_snapshot_text=False,
    ),
    # --- Astrology charts --------------------------------------------------
    ToolSpec(
        key="astro_chart",
        bind=_astro_chart_bind,
        request_model=AstroChartPolyRequest,
        summary=(
            "离线核心星盘：默认本命盘；可选 chart_variant 切换盘式"
            "（chart13=13等分扇区 / hellen_chart=希腊 / guolao_chart=果老星宗 / "
            "india_chart=印度 / germany=德国盘引擎），等价于对应的 astro_chart13 等专用工具。"
        ),
        operation_label_zh="星盘",
        family="astro",
        rest_path="/api/astro/chart",
        mcp_name="astro_chart",
        metadata_name="chart",
    ),
    _chart_spec(
        "astro_chart13",
        "/api/astro/chart13",
        "astro_chart13",
        "chart13",
        "13等分扇区盘",
        "chart13",
    ),
    _chart_spec(
        "astro_hellen",
        "/api/astro/hellen",
        "astro_hellen_chart",
        "hellen_chart",
        "希腊盘",
        "astro_hellen_chart",
    ),
    _chart_spec(
        "astro_guolao",
        "/api/astro/guolao",
        "astro_guolao_chart",
        "guolao_chart",
        "果老星宗盘",
        "astro_guolao_chart",
    ),
    _chart_spec(
        "astro_india",
        "/api/astro/india",
        "astro_india_chart",
        "india_chart",
        "印度盘",
        "astro_india_chart",
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
        rest_path="/api/astro/vimshottari",
        mcp_name="astro_vimshottari",
    ),
    ToolSpec(
        key="astro_germany",
        bind=raw_invoke(calculate_germany_chart_analysis),
        request_model=AstroGermanyRequest,
        summary="德国中点盘：22因素、253中点轴、90/45度盘三/四因素式及来源；可选目标时刻的真太阳弧和具名1924黄道日推运天顶。含八个数学假设点，象征推运不等于目标日观测或事件概率。旧七曜视图保留。",
        operation_label_zh="德国盘",
        family="astro",
        rest_path="/api/astro/germany",
        mcp_name="astro_germany_chart",
        metadata_name="germany",
    ),
    # The relative/合盘 tool is exposed as ONE logical tool through two request
    # shapes: a nested inner/outer model on REST, and a flat inner_/outer_ model
    # on MCP. They INTENTIONALLY share a single provenance name
    # (``astro_relative_chart``) so downstream metrics/logs treat them as one
    # tool regardless of surface — this parity is locked by
    # tests/test_api_alignment.py (both surfaces assert the same run_metadata
    # tool_name). The ``metadata_name`` override on the REST spec is what aligns
    # its provenance to the MCP name; do not split them without updating that test.
    ToolSpec(
        key="astro_relative",
        bind=_astro_relative_rest_bind,
        request_model=AstroRelativeRequest,
        summary="关系／合盘：比较、影响、组合中点、三种Davison变体及双方Marks个人盘。附原生坐标、时间与方法来源；几何汇总分非概率。嵌套inner/outer，REST端，与astro_relative_chart同计算。",
        operation_label_zh="关系星盘分析",
        family="astro",
        rest_path="/api/astro/relative",
        mcp_name=None,
        metadata_name="astro_relative_chart",
    ),
    ToolSpec(
        key="astro_relative_chart",
        bind=_astro_relative_flat_bind,
        request_model=AstroRelativeFlatRequest,
        summary="关系／合盘：比较、影响、组合中点、三种Davison变体及双方Marks个人盘。附原生坐标、时间与方法来源；几何汇总分非概率。扁平inner_/outer_，MCP端，与astro_relative同计算。",
        operation_label_zh="关系星盘分析",
        family="astro",
        rest_path=None,
        mcp_name="astro_relative_chart",
    ),
]
