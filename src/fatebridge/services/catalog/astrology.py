"""Astrology tool declarations and domain binding helpers."""

from __future__ import annotations

from itertools import chain

from fatebridge.application.bindings import bind_kwargs, service_ref
from fatebridge.application.domain_validators import validate_astro_chart_variant
from fatebridge.application.tool_spec import EvidenceViews, ServiceResult, ToolSpec
from fatebridge.core.astro.reference import (
    RELATIVE_MODE_EXACT_ALIASES,
    RELATIVE_MODE_FALLBACK_ALIASES,
    RELATIVE_MODE_NUMERIC_MAP,
)
from fatebridge.core.contracts.output_human_design import HumanDesignOutput
from fatebridge.core.requests.astrology import (
    AstroChartRequest,
    AstroGermanyRequest,
    AstroGuolaoRequest,
    AstroIndiaRequest,
    AstroNatalChartRequest,
    AstroRelativeFlatRequest,
    AstroSpecialtyRequest,
    AstroVimshottariRequest,
)
from fatebridge.core.requests.human_design import HumanDesignRequest
from fatebridge.services.catalog.astro_bindings import (
    bind_astro_natal_chart,
    bind_relationship_chart,
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
    fields = {"relationship_profile", "summary", "run_metadata"}
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
    name: str,
    rest_path: str,
    variant: str,
    label: str,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        bind=bind_kwargs(
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
            "印占 Lahiri 整宫与分盘，含 PAV/BAV/SAV 计数及生时抽样。"
            if variant == "india_chart"
            else (
                "果老研究盘：七政四余坐标、赤经宿界、宫度主与可选目标小限。"
                if variant == "guolao_chart"
                else f"离线{label}（高精度星历或近似回退）。"
            )
        ),
        operation_label_zh=label,
        family="astro",
        cpu_bound=True,
        rest_path=rest_path,
        output_validators=(validate_astro_chart_variant,),
    )


SPECS: list[ToolSpec] = [
    ToolSpec(
        name="human_design",
        bind=bind_kwargs(
            service_ref("fatebridge.services.human_design", "calculate_human_design")
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
        summary="人类图：88°双时刻、26激活、通道与类型权威；区分已定义/未定义中心。",
        operation_label_zh="人类图",
        family="astro",
        cpu_bound=True,
        rest_path="/api/human-design/chart",
    ),
    ToolSpec(
        name="astrology_chart",
        bind=bind_astro_natal_chart,
        request_model=AstroNatalChartRequest,
        summary="离线西占本命盘（高精度星历或近似回退）；可选 opaque_solar 偏折层。",
        operation_label_zh="星盘",
        family="astro",
        cpu_bound=True,
        rest_path="/api/astrology/chart",
        output_validators=(validate_astro_chart_variant,),
    ),
    _chart_spec(
        "thirteen_sector_chart",
        "/api/astrology/thirteen-sector-chart",
        "chart13",
        "13等分扇区盘",
    ),
    _chart_spec(
        "hellenistic_chart",
        "/api/astrology/hellenistic-chart",
        "hellen_chart",
        "希腊盘",
    ),
    _chart_spec(
        "guolao_chart",
        "/api/astrology/guolao-chart",
        "guolao_chart",
        "果老星宗盘",
    ),
    _chart_spec(
        "vedic_chart",
        "/api/astrology/vedic-chart",
        "india_chart",
        "印度盘",
    ),
    ToolSpec(
        name="vimshottari_dasha",
        bind=bind_kwargs(
            service_ref("fatebridge.services.jyotish", "calculate_vimshottari")
        ),
        request_model=AstroVimshottariRequest,
        summary="印占 Vimshottari 分期：2–6层大运子期、出生剩余运及分盘八分法。",
        operation_label_zh="印占 Vimshottari 分期",
        family="astro",
        cpu_bound=True,
        rest_path="/api/astrology/vimshottari-dasha",
    ),
    ToolSpec(
        name="hamburg_midpoint_chart",
        bind=bind_kwargs(calculate_germany_chart_analysis),
        request_model=AstroGermanyRequest,
        summary="德国中点盘：22因素、253中点轴、90/45度盘及可选真太阳弧。",
        operation_label_zh="德国盘",
        family="astro",
        cpu_bound=True,
        rest_path="/api/astrology/hamburg-midpoint-chart",
        output_validators=(validate_astro_chart_variant,),
    ),
    ToolSpec(
        name="relationship_chart",
        bind=bind_relationship_chart,
        request_model=AstroRelativeFlatRequest,
        summary="关系/合盘：比较、影响、组合盘、Davison 变体及 Marks 个人盘。",
        operation_label_zh="关系星盘分析",
        family="astro",
        cpu_bound=True,
        rest_path="/api/astrology/relationship-chart",
        evidence_views_builder=_relative_evidence_views,
        compact_view=_compact_relationship,
    ),
]
