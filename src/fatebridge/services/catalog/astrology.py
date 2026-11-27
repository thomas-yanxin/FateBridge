"""Astrology tool declarations and domain binding helpers."""

from __future__ import annotations

from itertools import chain

from fatebridge.application.bindings import bind_kwargs, request_model_ref, service_ref
from fatebridge.application.domain_validators import validate_astro_chart_variant
from fatebridge.application.tool_spec import EvidenceViews, ServiceResult, ToolSpec
from fatebridge.services.catalog.astro_bindings import (
    bind_astro_natal_chart,
    bind_relationship_chart,
    calculate_core_chart_analysis,
    calculate_germany_chart_analysis,
)

_ASTRO_REQ = "fatebridge.core.requests.astrology"

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
            **{k: v for k, v in chart.items() if k not in {"houses", "aspects"}},
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


def _compact_astrology_chart(result: ServiceResult) -> ServiceResult:
    keep = {
        "person_info",
        "chart_profile",
        "angles",
        "element_balance",
        "modality_balance",
        "summary",
        "run_metadata",
    }
    view = {k: v for k, v in result.items() if k in keep}
    planet_fields = {
        "id",
        "name",
        "sign",
        "sign_zh",
        "degree",
        "longitude",
        "house",
        "retrograde",
    }
    if isinstance(result.get("planets"), list):
        view["planets"] = [
            {k: v for k, v in p.items() if k in planet_fields}
            for p in result["planets"]
            if isinstance(p, dict)
        ]
    if isinstance(result.get("aspects"), list):
        view["aspects"] = result["aspects"][:16]
    classical = result.get("classical")
    if isinstance(classical, dict):
        view["classical"] = {
            "sect": classical.get("sect"),
            "almuten_figuris": (
                {
                    k: classical["almuten_figuris"].get(k)
                    for k in ("winner", "winners", "total_scores")
                    if k in classical["almuten_figuris"]
                }
                if isinstance(classical.get("almuten_figuris"), dict)
                else classical.get("almuten_figuris")
            ),
            "temperament": classical.get("temperament"),
            "syzygy": (
                {
                    k: classical["syzygy"].get(k)
                    for k in (
                        "type",
                        "longitude",
                        "sign",
                        "degree_in_sign",
                        "event_datetime_utc",
                    )
                }
                if isinstance(classical.get("syzygy"), dict)
                else None
            ),
        }
    return view


def _compact_hamburg(result: ServiceResult) -> ServiceResult:
    ma = result.get("midpoint_analysis")
    compact_ma = ma
    if isinstance(ma, dict):
        dials = ma.get("dials") or {}
        compact_dials = {
            dial: {
                "period_degrees": data.get("period_degrees"),
                "two_factor_contacts": (data.get("two_factor_contacts") or [])[:3],
                "three_factor_contacts": (data.get("three_factor_contacts") or [])[:3],
                "four_factor_contacts": (data.get("four_factor_contacts") or [])[:3],
                "four_factor_total_count": data.get("four_factor_total_count"),
            }
            for dial, data in dials.items()
            if isinstance(data, dict)
        }
        compact_ma = {
            k: v
            for k, v in ma.items()
            if k
            in {
                "status",
                "ruleset_id",
                "profile",
                "contact_counts",
                "unique_two_factor_pair_count",
                "sensitive_point_query",
            }
        }
        compact_ma["dials"] = compact_dials
    view = {
        k: v
        for k, v in result.items()
        if k
        in {
            "chart_profile",
            "summary",
            "run_metadata",
        }
    }
    view["midpoint_analysis"] = compact_ma
    return view


def _relative_evidence_views(
    views: EvidenceViews | None,
) -> EvidenceViews | None:
    if views is None:
        return None
    from fatebridge.core.astro.reference import (
        RELATIVE_MODE_EXACT_ALIASES,
        RELATIVE_MODE_FALLBACK_ALIASES,
        RELATIVE_MODE_NUMERIC_MAP,
    )

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
        request_model_loader=request_model_ref(
            _ASTRO_REQ,
            "AstroSpecialtyRequest" if variant == "chart13" else "AstroChartRequest",
        ),
        summary=f"离线{label}（高精度星历或近似回退）。",
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
        request_model_loader=request_model_ref(
            "fatebridge.core.requests.human_design", "HumanDesignRequest"
        ),
        required_output_fields=(
            "activations",
            "variables",
            "bodygraph",
            "profile",
            "incarnation_cross",
        ),
        summary="人类图：88°双时刻、26激活、通道与类型权威；区分已定义/未定义中心。",
        operation_label_zh="人类图",
        family="astro",
        cpu_bound=True,
        rest_path="/api/human-design/chart",
        compact_view=service_ref(
            "fatebridge.services.human_design", "compact_human_design"
        ),
    ),
    ToolSpec(
        name="astrology_chart",
        bind=bind_astro_natal_chart,
        request_model_loader=request_model_ref(_ASTRO_REQ, "AstroNatalChartRequest"),
        summary="离线西占本命盘（高精度星历或近似回退）；可选 opaque_solar 偏折层。",
        operation_label_zh="星盘",
        family="astro",
        cpu_bound=True,
        rest_path="/api/astrology/chart",
        output_validators=(validate_astro_chart_variant,),
        compact_view=_compact_astrology_chart,
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
    ToolSpec(
        name="guolao_chart",
        bind=bind_kwargs(
            service_ref("fatebridge.services.guolao", "calculate_guolao_chart")
        ),
        request_model_loader=request_model_ref(
            "fatebridge.core.requests.guolao", "GuolaoChartRequest"
        ),
        required_output_fields=("guolao",),
        summary="果老研究盘：七政四余坐标、赤经宿界、宫度主、命度身宫、十干化曜、神煞与洞微大限。",
        operation_label_zh="果老星宗盘",
        family="astro",
        cpu_bound=True,
        rest_path="/api/astrology/guolao-chart",
        output_validators=(validate_astro_chart_variant,),
        compact_view=service_ref("fatebridge.services.guolao", "compact_guolao_chart"),
    ),
    ToolSpec(
        name="vedic_chart",
        bind=bind_kwargs(
            service_ref("fatebridge.services.jyotish", "calculate_vedic_chart")
        ),
        request_model_loader=request_model_ref(
            "fatebridge.core.requests.jyotish", "VedicChartRequest"
        ),
        required_output_fields=("vedic_chart",),
        summary="印占整宫与十六分盘，含 Shadbala、Bhava Bala、Yoga、Arudha 与 Ashtakavarga。",
        operation_label_zh="印度盘",
        family="astro",
        cpu_bound=True,
        rest_path="/api/astrology/vedic-chart",
        compact_view=service_ref("fatebridge.services.jyotish", "compact_vedic_chart"),
    ),
    ToolSpec(
        name="vimshottari_dasha",
        bind=bind_kwargs(
            service_ref("fatebridge.services.jyotish", "calculate_vimshottari")
        ),
        request_model_loader=request_model_ref(
            "fatebridge.core.requests.jyotish", "VimshottariDashaRequest"
        ),
        required_output_fields=(
            "analysis_context",
            "person_info",
            "vimshottari",
            "summary",
        ),
        summary="印占 Vimshottari 分期（及可选 Yogini / Ashtottari / Chara）：2–6层大运子期与出生剩余运。",
        operation_label_zh="印占 Vimshottari 分期",
        family="astro",
        cpu_bound=True,
        rest_path="/api/astrology/vimshottari-dasha",
        compact_view=service_ref("fatebridge.services.jyotish", "compact_vimshottari"),
    ),
    ToolSpec(
        name="hamburg_midpoint_chart",
        bind=bind_kwargs(calculate_germany_chart_analysis),
        request_model_loader=request_model_ref(_ASTRO_REQ, "AstroGermanyRequest"),
        summary="德国中点盘：22因素、253中点轴、90/45/22.5度盘及可选真太阳弧。",
        operation_label_zh="德国盘",
        family="astro",
        cpu_bound=True,
        rest_path="/api/astrology/hamburg-midpoint-chart",
        output_validators=(validate_astro_chart_variant,),
        compact_view=_compact_hamburg,
    ),
    ToolSpec(
        name="relationship_chart",
        bind=bind_relationship_chart,
        request_model_loader=request_model_ref(_ASTRO_REQ, "AstroRelativeFlatRequest"),
        summary="关系/合盘：比较、影响、组合盘、Davison 变体及 Marks 个人盘。",
        operation_label_zh="关系星盘分析",
        family="astro",
        cpu_bound=True,
        rest_path="/api/astrology/relationship-chart",
        evidence_views_builder=_relative_evidence_views,
        compact_view=_compact_relationship,
    ),
]
