"""Shared timing-layer computation and timeline enrichment from one birth context."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fatebridge.analysis.life_dimensions import LifeDimensionAnalysis
from fatebridge.analysis.timing_effects import TimingEffectsAnalysis
from fatebridge.core.timing import TimingAnalysis
from fatebridge.core.timing_interactions import analyze_timing_interactions
from fatebridge.services.birth_context import BirthComputationContext

logger = logging.getLogger(__name__)


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
) -> Optional[Dict[str, float]]:
    """
    为指定时刻计算用户的五维生命维度分值（爱情/财富/事业/学习/人际）。

    汇总本命四柱 + 当前可用的时间层柱（大运/流年/流月/流日/流时），
    任何一层失败都不会让整体崩溃 —— 只是少一个层级权重，
    最终 dimension 分数仍然有意义。
    """
    try:
        normalized_birth_time = birth_context.normalized_birth_time
        timezone_name = normalized_birth_time.timezone
        gender = birth_context.person.gender

        current_pillars: Dict[str, tuple] = {}

        # 流时（小时粒度）
        try:
            liushi = TimingAnalysis.calculate_liushi(
                analysis_date, timezone_name=timezone_name
            )
            current_pillars["liushi"] = (liushi["stem"], liushi["branch"])
        except Exception:
            logger.warning("life_dimensions: liushi 计算失败", exc_info=True)

        # 流日
        try:
            liuri = TimingAnalysis.calculate_liuri(
                analysis_date, timezone_name=timezone_name
            )
            current_pillars["liuri"] = (liuri["stem"], liuri["branch"])
        except Exception:
            logger.warning("life_dimensions: liuri 计算失败", exc_info=True)

        # 流月
        try:
            liuyue = TimingAnalysis.calculate_liuyue(
                analysis_date.year,
                analysis_date.month,
                analysis_date.day,
                timezone_name=timezone_name,
                target_date=analysis_date,
            )
            current_pillars["liuyue"] = (liuyue["stem"], liuyue["branch"])
        except Exception:
            logger.warning("life_dimensions: liuyue 计算失败", exc_info=True)

        # 流年
        try:
            liunian = TimingAnalysis.calculate_liunian(
                analysis_date.year, moment=analysis_date, timezone_name=timezone_name
            )
            current_pillars["liunian"] = (liunian["stem"], liunian["branch"])
        except Exception:
            logger.warning("life_dimensions: liunian 计算失败", exc_info=True)

        # 大运（依赖 gender + age）
        try:
            birth_date = normalized_birth_time.input_datetime
            analysis_age = calculate_analysis_age(birth_date, analysis_date)
            dayun_result = TimingEffectsAnalysis.analyze_dayun_effects(
                birth_context.birth_pillars,
                birth_date,
                gender,
                analysis_age,
                timezone_name=timezone_name,
                original_element_counts=birth_context.original_element_counts,
                analysis_moment=analysis_date,
            )
            dayun_info = (
                dayun_result.get("dayun_info")
                if isinstance(dayun_result, dict)
                else None
            )
            if dayun_info and dayun_info.get("stem") and dayun_info.get("branch"):
                current_pillars["dayun"] = (dayun_info["stem"], dayun_info["branch"])
        except Exception:
            logger.warning("life_dimensions: dayun 计算失败", exc_info=True)

        return LifeDimensionAnalysis.calculate_life_dimensions(
            birth_pillars=birth_context.birth_pillars,
            current_pillars=current_pillars,
            gender=gender,
        )
    except Exception:
        logger.warning("life_dimensions 计算整体失败，返回 None", exc_info=True)
        return None


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
            birth_context.birth_pillars, combined_timing_pillars
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
