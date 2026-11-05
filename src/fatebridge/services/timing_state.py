"""Shared timing-layer computation and timeline enrichment from one birth context."""

from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

from fatebridge.analysis.life_dimensions import (
    LIFE_DIMENSION_METHOD,
    LifeDimensionAnalysis,
)
from fatebridge.analysis.timing_effects import TimingEffectsAnalysis
from fatebridge.core.timing import TimingAnalysis
from fatebridge.core.timing_interactions import analyze_timing_interactions
from fatebridge.core.timing_strength import StrengthProjectionBaseline
from fatebridge.services.birth_context import BirthComputationContext


class LifeDimensionAssessment(TypedDict):
    method_id: str
    status: str
    score_kind: str
    scores: Dict[str, Optional[float]]
    included_layers: List[str]
    unavailable_layers: Dict[str, str]
    not_applicable_layers: List[str]
    unavailable_dimensions: List[str]
    score_basis: str
    interpretation_scope: str


def calculate_analysis_age(
    birth_datetime: datetime,
    analysis_date: datetime,
    explicit_age: Optional[int] = None,
) -> int:
    if explicit_age is not None:
        return explicit_age

    age = analysis_date.year - birth_datetime.year
    if (analysis_date.month, analysis_date.day) < (
        birth_datetime.month,
        birth_datetime.day,
    ):
        age -= 1
    return age


def compute_life_dimensions_for_moment(
    birth_context: BirthComputationContext,
    analysis_date: datetime,
    *,
    liushi_pillar: Optional[tuple[str, str]] = None,
) -> LifeDimensionAssessment:
    """
    为指定时刻计算用户的五维生命维度分值（爱情/财富/事业/学习/人际）。

    必需时间层失败交给服务错误边界；大运缺资料与尚未起运分别披露。
    已算流时可以由同次服务传入，避免重复计算。
    """
    normalized = birth_context.normalized_birth_time
    zone = normalized.timezone
    gender = birth_context.person.gender
    if liushi_pillar is None:
        liushi = TimingAnalysis.calculate_liushi(analysis_date, timezone_name=zone)
        liushi_pillar = (liushi["stem"], liushi["branch"])
    liuri = TimingAnalysis.calculate_liuri(analysis_date, timezone_name=zone)
    liuyue = TimingAnalysis.calculate_liuyue(
        analysis_date.year,
        analysis_date.month,
        analysis_date.day,
        timezone_name=zone,
        target_date=analysis_date,
    )
    liunian = TimingAnalysis.calculate_liunian(
        analysis_date.year, moment=analysis_date, timezone_name=zone
    )
    current_pillars = {
        "liushi": liushi_pillar,
        "liuri": (liuri["stem"], liuri["branch"]),
        "liuyue": (liuyue["stem"], liuyue["branch"]),
        "liunian": (liunian["stem"], liunian["branch"]),
    }
    dayun = TimingEffectsAnalysis.analyze_dayun_effects(
        birth_context.birth_pillars,
        normalized.input_datetime,
        gender,
        calculate_analysis_age(normalized.input_datetime, analysis_date),
        timezone_name=zone,
        original_element_counts=birth_context.original_element_counts,
        analysis_moment=analysis_date,
        allow_missing_gender=True,
    )
    unavailable_layers = {}
    not_applicable_layers = []
    if "dayun_info" in dayun:
        info = dayun["dayun_info"]
        current_pillars["dayun"] = (info["stem"], info["branch"])
    elif dayun["status"] == "before_dayun":
        not_applicable_layers.append("dayun")
    else:
        unavailable_layers["dayun"] = dayun["status"]
    scores = LifeDimensionAnalysis.calculate_life_dimensions(
        birth_context.birth_pillars, current_pillars, gender
    )
    unavailable_dimensions = [name for name, value in scores.items() if value is None]
    return {
        "method_id": LIFE_DIMENSION_METHOD,
        "status": (
            "partial" if unavailable_layers or unavailable_dimensions else "calculated"
        ),
        "score_kind": "uncalibrated_rule_index",
        "scores": scores,
        "included_layers": ["natal", *current_pillars],
        "unavailable_layers": unavailable_layers,
        "not_applicable_layers": not_applicable_layers,
        "unavailable_dimensions": unavailable_dimensions,
        "score_basis": "全部已知计数统一使用50+50*tanh((raw-3)/3)，保留一位小数；零计数同式，未知不填50。",
        "interpretation_scope": "固定权重的文化规则索引，非心理测量或成功概率；只比较相同方法和相同可用层。缺性别时爱情为空且大运不可用，尚未起运另列不适用。",
    }


def serialize_element_effects(element_effects: Dict[str, Any]) -> Dict[str, Any]:
    serialized = {
        "overall_effect": element_effects["overall_effect"],
        "element_changes": {},
        "method_id": element_effects.get("method_id"),
        "interpretation_scope": element_effects.get("interpretation_scope"),
        "counting_basis": element_effects.get("counting_basis"),
    }
    for element, change_info in (element_effects.get("element_changes") or {}).items():
        if change_info.get("change") != 0:
            serialized["element_changes"][element] = {
                "original": change_info["original"],
                "new": change_info["new"],
                "change": change_info["change"],
                "change_type": change_info["change_type"],
            }
    return serialized


def build_current_timing_state(
    birth_context: BirthComputationContext,
    *,
    analysis_date: datetime,
    analysis_age: Optional[int] = None,
) -> Dict[str, Any]:
    """Build the current timing analyses once from shared birth context."""
    timezone_name = birth_context.normalized_birth_time.timezone
    current_age = calculate_analysis_age(
        birth_context.normalized_birth_time.input_datetime,
        analysis_date,
        explicit_age=analysis_age,
    )
    liuyue_info = TimingAnalysis.calculate_liuyue(
        analysis_date.year,
        analysis_date.month,
        target_day=analysis_date.day,
        timezone_name=timezone_name,
        target_date=analysis_date,
    )
    liuri_info = TimingAnalysis.calculate_liuri(
        analysis_date,
        timezone_name=timezone_name,
    )
    liushi_info = TimingAnalysis.calculate_liushi(
        analysis_date,
        timezone_name=timezone_name,
    )
    dayun_analysis = TimingEffectsAnalysis.analyze_dayun_effects(
        birth_context.birth_pillars,
        birth_context.normalized_birth_time.input_datetime,
        birth_context.person.gender,
        current_age,
        timezone_name=timezone_name,
        original_element_counts=birth_context.original_element_counts,
        analysis_moment=analysis_date if analysis_age is None else None,
        allow_missing_gender=True,
    )
    liunian_analysis = TimingEffectsAnalysis.analyze_liunian_effects(
        birth_context.birth_pillars,
        analysis_date.year,
        original_element_counts=birth_context.original_element_counts,
        moment=analysis_date,
        timezone_name=timezone_name,
    )
    liuyue_analysis = TimingEffectsAnalysis.analyze_liuyue_effects(
        birth_context.birth_pillars,
        analysis_date.year,
        analysis_date.month,
        target_day=analysis_date.day,
        timezone_name=timezone_name,
        target_date=analysis_date,
        liuyue_info=liuyue_info,
        original_element_counts=birth_context.original_element_counts,
    )
    liuri_analysis = TimingEffectsAnalysis.analyze_liuri_effects(
        birth_context.birth_pillars,
        analysis_date,
        timezone_name=timezone_name,
        liuri_info=liuri_info,
        original_element_counts=birth_context.original_element_counts,
    )
    liushi_analysis = TimingEffectsAnalysis.analyze_liushi_effects(
        birth_context.birth_pillars,
        analysis_date,
        timezone_name=timezone_name,
        liushi_info=liushi_info,
        original_element_counts=birth_context.original_element_counts,
    )

    combined_timing_pillars: Dict[str, Dict[str, str]] = {}
    if "dayun_info" in dayun_analysis:
        combined_timing_pillars["dayun"] = {
            "stem": dayun_analysis["dayun_info"]["stem"],
            "branch": dayun_analysis["dayun_info"]["branch"],
        }
    combined_timing_pillars["liunian"] = {
        "stem": liunian_analysis["liunian_info"]["stem"],
        "branch": liunian_analysis["liunian_info"]["branch"],
    }
    combined_timing_pillars["liuyue"] = {
        "stem": liuyue_analysis["liuyue_info"]["stem"],
        "branch": liuyue_analysis["liuyue_info"]["branch"],
    }
    combined_timing_pillars["liuri"] = {
        "stem": liuri_analysis["liuri_info"]["stem"],
        "branch": liuri_analysis["liuri_info"]["branch"],
    }
    combined_timing_pillars["liushi"] = {
        "stem": liushi_analysis["liushi_info"]["stem"],
        "branch": liushi_analysis["liushi_info"]["branch"],
    }

    combined_effects = TimingEffectsAnalysis.analyze_element_strength_changes(
        birth_context.birth_pillars,
        combined_timing_pillars,
        original_element_counts=birth_context.original_element_counts,
    )
    natal_assessment = birth_context.element_analysis["day_master"]["assessment"]

    return {
        "analysis_date": analysis_date,
        "current_age": current_age,
        "dayun_analysis": dayun_analysis,
        "liunian_analysis": liunian_analysis,
        "liuyue_analysis": liuyue_analysis,
        "liuri_analysis": liuri_analysis,
        "liushi_analysis": liushi_analysis,
        "combined_effects": combined_effects,
        "interaction_analysis": analyze_timing_interactions(
            birth_context.birth_pillars,
            combined_timing_pillars,
            strength_baseline=StrengthProjectionBaseline(
                method_id=natal_assessment["method_id"],
                strength_level=natal_assessment["strength_level"],
                numerical_label=natal_assessment["threshold_arithmetic"][
                    "numerical_label"
                ],
                support_share_exact=natal_assessment["threshold_arithmetic"][
                    "share_exact"
                ],
                energies_exact=natal_assessment["threshold_arithmetic"][
                    "energies_exact"
                ],
                parameters=natal_assessment["parameters"],
                seasonal_phases=natal_assessment["seasonal_phases"],
                seasonal_factors=natal_assessment["seasonal_factors"],
                relations=natal_assessment["relations"],
            ),
        ),
        "comprehensive_summary": TimingEffectsAnalysis._generate_comprehensive_summary(
            dayun_analysis,
            liunian_analysis,
            liuyue_analysis,
            liuri_analysis,
            combined_effects,
            liushi_analysis=liushi_analysis,
        ),
    }


def enrich_liuyue_timeline(
    birth_context: BirthComputationContext,
    *,
    target_year: int,
) -> List[Dict[str, Any]]:
    timezone_name = birth_context.normalized_birth_time.timezone
    liuyue_timeline = TimingAnalysis.calculate_liuyue_timeline(
        target_year,
        timezone_name=timezone_name,
    )
    for item in liuyue_timeline:
        anchor = datetime.strptime(item["analysis_anchor"], "%Y-%m-%d %H:%M:%S")
        liuyue_effect = TimingEffectsAnalysis.analyze_liuyue_effects(
            birth_context.birth_pillars,
            anchor.year,
            anchor.month,
            target_day=anchor.day,
            timezone_name=timezone_name,
            target_date=anchor,
            liuyue_info=item["liuyue"],
            original_element_counts=birth_context.original_element_counts,
        )
        item["overall_effect"] = liuyue_effect["element_effects"]["overall_effect"]
        item["summary"] = liuyue_effect["enhanced_summary"]
    return liuyue_timeline


def enrich_jieqi_timeline(
    birth_context: BirthComputationContext,
    *,
    target_year: int,
) -> List[Dict[str, Any]]:
    timezone_name = birth_context.normalized_birth_time.timezone
    jieqi_timeline = TimingAnalysis.calculate_jieqi_transition_timeline(
        target_year,
        timezone_name=timezone_name,
    )
    for item in jieqi_timeline:
        anchor = datetime.strptime(item["analysis_anchor"], "%Y-%m-%d %H:%M:%S")
        liuyue_pillar = item["liuyue"]
        liuri_pillar = item["liuri"]
        node_effect = TimingEffectsAnalysis.analyze_element_strength_changes(
            birth_context.birth_pillars,
            {
                "liuyue": {
                    "stem": liuyue_pillar["stem"],
                    "branch": liuyue_pillar["branch"],
                },
                "liuri": {
                    "stem": liuri_pillar["stem"],
                    "branch": liuri_pillar["branch"],
                },
            },
            original_element_counts=birth_context.original_element_counts,
        )
        liuri_effect = TimingEffectsAnalysis.analyze_liuri_effects(
            birth_context.birth_pillars,
            anchor,
            timezone_name=timezone_name,
            liuri_info=liuri_pillar,
            original_element_counts=birth_context.original_element_counts,
        )
        item["overall_effect"] = node_effect["overall_effect"]
        item["liuri_summary"] = liuri_effect["enhanced_summary"]
        item["summary"] = (
            f"{item['jieqi']['name']}节点，流月{liuyue_pillar['pillar']}，"
            f"流日{liuri_pillar['pillar']}，{node_effect['overall_effect']}"
        )
    return jieqi_timeline
