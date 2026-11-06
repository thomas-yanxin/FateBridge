#!/usr/bin/env python3
"""
时运影响分析模块

本模块分析大运、流年、流月对原命局的具体影响：
1. 五行力量变化分析
2. 十神关系变化
3. 格局影响分析
4. 吉凶趋势判断
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..core.almanac import (
    DEFAULT_TIMEZONE,
    current_local_datetime,
    elapsed_days_between,
    localize_datetime,
)
from ..core.elements import ElementAnalysis
from ..core.timing import TimingAnalysis
from ..core.timing_interactions import analyze_timing_interactions
from ..utils.birth_input import normalize_gender
from ..utils.data import BRANCH_ELEMENTS, BRANCH_HIDDEN_STEMS, STEM_ELEMENTS, Element


class TimingEffectsAnalysis:
    """时运影响分析类"""

    @staticmethod
    def _normalize_element_counts(
        element_counts: Optional[Dict[Element, float]],
    ) -> Dict[Element, float]:
        return {
            element: float((element_counts or {}).get(element, 0.0))
            for element in Element
        }

    @staticmethod
    def _count_timing_pillar_elements(timing_pillars: Dict) -> Dict[Element, float]:
        """Count timing-pillar elements using the same weighting as chart counts."""
        element_counts = {element: 0.0 for element in Element}

        for timing_info in timing_pillars.values():
            if not isinstance(timing_info, dict):
                continue
            stem = timing_info.get("stem")
            branch = timing_info.get("branch")
            if not stem or not branch:
                continue

            stem_element, _ = STEM_ELEMENTS[stem]
            branch_element, _ = BRANCH_ELEMENTS[branch]
            element_counts[stem_element] += 1.0
            element_counts[branch_element] += 1.0

            for hidden_stem in BRANCH_HIDDEN_STEMS[branch]:
                hidden_element, _ = STEM_ELEMENTS[hidden_stem]
                element_counts[hidden_element] += 0.5

        return element_counts

    @staticmethod
    def analyze_element_strength_changes(
        original_pillars: Dict,
        timing_pillars: Dict,
        original_element_counts: Optional[Dict[Element, float]] = None,
    ) -> Dict:
        """
        分析时运对五行力量的影响

        Args:
            original_pillars: 原命局四柱
            timing_pillars: 时运干支（大运、流年、流月）

        Returns:
            五行力量变化分析
        """
        raw_original_counts = TimingEffectsAnalysis._normalize_element_counts(
            original_element_counts or ElementAnalysis.count_elements(original_pillars)
        )
        timing_element_counts = TimingEffectsAnalysis._count_timing_pillar_elements(
            timing_pillars
        )
        combined_counts = {
            element: raw_original_counts[element] + timing_element_counts[element]
            for element in Element
        }
        original_distribution = ElementAnalysis.convert_to_percentage(
            raw_original_counts
        )
        new_distribution = ElementAnalysis.convert_to_percentage(combined_counts)

        element_changes = {}
        for element in Element:
            element_name = element.value
            original_count = original_distribution.get(element_name, 0.0)
            new_count = new_distribution.get(element_name, 0.0)
            change = new_count - original_count

            element_changes[element_name] = {
                "original": original_count,
                "new": new_count,
                "change": change,
                "change_type": (
                    "占比上升"
                    if change > 0
                    else "占比下降" if change < 0 else "占比不变"
                ),
            }

        return {
            "method_id": "structural_element_share_v1",
            "counting_basis": {
                "visible_stem": 1.0,
                "branch_element": 1.0,
                "each_hidden_stem": 0.5,
                "timing_layer_weights": "equal",
                "meaning": "structural_token_counts_not_effective_strength",
            },
            "interpretation_scope": "干支与藏干的结构计数占比；未计算行运后有效旺衰、合化和喜忌，不是吉凶评分或成功概率。",
            "original_distribution": original_distribution,
            "new_distribution": new_distribution,
            "element_changes": element_changes,
            "overall_effect": TimingEffectsAnalysis._evaluate_overall_effect(
                element_changes
            ),
        }

    @staticmethod
    def _evaluate_overall_effect(element_changes: Dict) -> str:
        """评估整体影响效果"""
        positive_changes = sum(
            1 for change in element_changes.values() if change["change"] > 0
        )
        negative_changes = sum(
            1 for change in element_changes.values() if change["change"] < 0
        )

        if positive_changes or negative_changes:
            return "五行结构占比发生变化（不代表旺衰或吉凶）"
        return "五行结构占比不变（不代表力量不变）"

    @staticmethod
    def analyze_dayun_effects(
        birth_pillars: Dict,
        birth_date: datetime,
        gender: Optional[str],
        analysis_age: int,
        timezone_name: str = DEFAULT_TIMEZONE,
        original_element_counts: Optional[Dict[Element, float]] = None,
        *,
        analysis_moment: Optional[datetime] = None,
        allow_missing_gender: bool = False,
    ) -> Dict:
        """
        分析指定年龄的大运影响

        Args:
            birth_pillars: 出生四柱
            birth_date: 出生日期
            gender: 性别
            analysis_age: 分析年龄
            allow_missing_gender: 仅综合入口可保留缺性别的大运不可用状态；独立大运默认仍要求性别

        Returns:
            大运影响分析
        """
        if allow_missing_gender and normalize_gender(gender) not in {"男", "女"}:
            return {
                "status": "unavailable_missing_gender",
                "message": "未提供顺逆所需的性别；大运未计算，独立流年等时间层仍可读取。",
                "timing_context": {
                    "status": "unavailable_missing_gender",
                    "selection_basis": (
                        "civil_calendar_moment"
                        if analysis_moment is not None
                        else "explicit_age_reference"
                    ),
                },
            }
        month_stem = birth_pillars["month"][0]
        month_branch = birth_pillars["month"][1]

        timeline = TimingAnalysis.calculate_dayun_timeline(
            birth_date, gender, (month_stem, month_branch), timezone_name
        )
        start_info = timeline["start_details"]
        start_age = start_info["start_age_unrounded"]
        sequence = timeline["periods"]
        selection_basis = (
            "civil_calendar_moment"
            if analysis_moment is not None
            else "explicit_age_reference"
        )
        context = {"selection_basis": selection_basis, "timeline": timeline}
        if analysis_moment is not None:
            moment = localize_datetime(analysis_moment, timezone_name)
            instant = moment.astimezone(timezone.utc)
            context["analysis_at"] = moment.isoformat()
            start_at = datetime.fromisoformat(timeline["start_at"])
            before_start = instant < start_at.astimezone(timezone.utc)
            period_index = next(
                (
                    index
                    for index, item in enumerate(sequence)
                    if datetime.fromisoformat(item["start_at"]).astimezone(timezone.utc)
                    <= instant
                    < datetime.fromisoformat(item["end_at"]).astimezone(timezone.utc)
                ),
                len(sequence),
            )
            dayun_age = elapsed_days_between(start_at, moment) / 365.2425
        else:
            before_start = analysis_age < start_age
            dayun_age = analysis_age - start_age
            period_index = int(dayun_age // 10)

        if before_start:
            return {
                "status": "before_dayun",
                "message": f"尚未起运，约在{start_info['start_age_precise']}岁起运",
                "timing_context": context,
            }
        if period_index >= len(sequence):
            return {
                "status": "beyond_calculation",
                "message": "超出计算范围",
                "timing_context": context,
            }

        current_dayun = sequence[period_index]
        years_in_period = (
            elapsed_days_between(
                datetime.fromisoformat(current_dayun["start_at"]),
                localize_datetime(analysis_moment, timezone_name),
            )
            / 365.2425
            if analysis_moment is not None
            else dayun_age - period_index * 10
        )

        # 分析大运对命局的影响
        timing_pillars = {
            "dayun": {"stem": current_dayun["stem"], "branch": current_dayun["branch"]}
        }

        element_effects = TimingEffectsAnalysis.analyze_element_strength_changes(
            birth_pillars,
            timing_pillars,
            original_element_counts=original_element_counts,
        )

        return {
            "timing_context": context,
            "dayun_info": current_dayun,
            "age_info": {
                "analysis_age": analysis_age,
                "start_age": start_info["start_age_rounded"],
                "start_age_precise": start_info["start_age_precise"],
                "start_age_unrounded": start_info["start_age_unrounded"],
                "dayun_age": round(dayun_age, 2),
                "years_in_period": round(years_in_period, 2),
                "selection_basis": selection_basis,
                "elapsed_year_basis": (
                    "fixed_365.2425_display_only"
                    if analysis_moment is not None
                    else "explicit_age_minus_unrounded_start_age"
                ),
                "direction": "顺行" if start_info["forward_direction"] else "逆行",
                "reference_term": start_info["reference_term"],
            },
            "element_effects": element_effects,
            "summary": TimingEffectsAnalysis._generate_dayun_summary(
                current_dayun, element_effects
            ),
        }

    @staticmethod
    def _generate_dayun_summary(dayun_info: Dict, element_effects: Dict) -> str:
        """生成大运影响总结"""
        dayun_pillar = dayun_info["pillar"]
        overall_effect = element_effects["overall_effect"]

        return f"大运{dayun_pillar}期间，{overall_effect}。"

    @staticmethod
    def analyze_liunian_effects(
        birth_pillars: Dict,
        target_year: int,
        original_element_counts: Optional[Dict[Element, float]] = None,
        *,
        moment: Optional[datetime] = None,
        timezone_name: Optional[str] = None,
    ) -> Dict:
        """
        分析流年影响

        Args:
            birth_pillars: 出生四柱
            target_year: 目标年份
            moment: 可选的具体时间点；若给出，流年会以立春为边界解析，
                避免 1 月 / 早 2 月误判为前一年。
            timezone_name: ``moment`` 的时区（仅在传入 moment 时使用）。

        Returns:
            流年影响分析
        """
        # 获取流年信息；传入 moment 使 calculate_liunian 以立春为边界。
        liunian_kwargs: Dict = {}
        if moment is not None:
            liunian_kwargs["moment"] = moment
            if timezone_name is not None:
                liunian_kwargs["timezone_name"] = timezone_name
        liunian_info = TimingAnalysis.calculate_liunian(target_year, **liunian_kwargs)

        # 分析流年对命局的影响
        timing_pillars = {
            "liunian": {"stem": liunian_info["stem"], "branch": liunian_info["branch"]}
        }

        element_effects = TimingEffectsAnalysis.analyze_element_strength_changes(
            birth_pillars,
            timing_pillars,
            original_element_counts=original_element_counts,
        )

        return {
            "liunian_info": liunian_info,
            "element_effects": element_effects,
            "summary": f"流年{liunian_info['pillar']}，{element_effects['overall_effect']}",
        }

    @staticmethod
    def analyze_liuyue_effects(
        birth_pillars: Dict,
        target_year: int,
        target_month: int,
        target_day: int = 1,
        timezone_name: str = DEFAULT_TIMEZONE,
        target_date: Optional[datetime] = None,
        liuyue_info: Optional[Dict] = None,
        original_element_counts: Optional[Dict[Element, float]] = None,
    ) -> Dict:
        """
        分析流月影响

        Args:
            birth_pillars: 出生四柱
            target_year: 目标年份
            target_month: 目标月份

        Returns:
            流月影响分析
        """
        if liuyue_info is None:
            liuyue_info = TimingAnalysis.calculate_liuyue(
                target_year,
                target_month,
                target_day=target_day,
                timezone_name=timezone_name,
                target_date=target_date,
            )

        detailed_analysis = TimingAnalysis.analyze_liuyue_detailed(
            birth_pillars,
            target_year,
            target_month,
            target_day=target_day,
            timezone_name=timezone_name,
            target_date=target_date,
            liuyue_info=liuyue_info,
        )

        # 分析流月对命局的影响
        timing_pillars = {
            "liuyue": {"stem": liuyue_info["stem"], "branch": liuyue_info["branch"]}
        }

        element_effects = TimingEffectsAnalysis.analyze_element_strength_changes(
            birth_pillars,
            timing_pillars,
            original_element_counts=original_element_counts,
        )

        return {
            "liuyue_info": liuyue_info,
            "detailed_analysis": detailed_analysis,
            "element_effects": element_effects,
            "summary": f"流月{liuyue_info['pillar']}，{element_effects['overall_effect']}",
            "enhanced_summary": detailed_analysis["overall_summary"],
        }

    @staticmethod
    def analyze_liuri_effects(
        birth_pillars: Dict,
        target_date: datetime,
        timezone_name: str = DEFAULT_TIMEZONE,
        liuri_info: Optional[Dict] = None,
        original_element_counts: Optional[Dict[Element, float]] = None,
    ) -> Dict:
        """
        分析流日影响。
        """
        if liuri_info is None:
            liuri_info = TimingAnalysis.calculate_liuri(
                target_date, timezone_name=timezone_name
            )
        detailed_analysis = TimingAnalysis.analyze_liuri_detailed(
            birth_pillars,
            target_date,
            timezone_name=timezone_name,
            liuri_info=liuri_info,
        )

        timing_pillars = {
            "liuri": {"stem": liuri_info["stem"], "branch": liuri_info["branch"]}
        }

        element_effects = TimingEffectsAnalysis.analyze_element_strength_changes(
            birth_pillars,
            timing_pillars,
            original_element_counts=original_element_counts,
        )

        return {
            "liuri_info": liuri_info,
            "detailed_analysis": detailed_analysis,
            "element_effects": element_effects,
            "summary": f"流日{liuri_info['pillar']}，{element_effects['overall_effect']}",
            "enhanced_summary": detailed_analysis["overall_summary"],
        }

    @staticmethod
    def analyze_liushi_effects(
        birth_pillars: Dict,
        target_datetime: datetime,
        timezone_name: str = DEFAULT_TIMEZONE,
        liushi_info: Optional[Dict] = None,
        original_element_counts: Optional[Dict[Element, float]] = None,
    ) -> Dict:
        """
        分析流时影响。
        """
        if liushi_info is None:
            liushi_info = TimingAnalysis.calculate_liushi(
                target_datetime, timezone_name=timezone_name
            )
        detailed_analysis = TimingAnalysis.analyze_liushi_detailed(
            birth_pillars,
            target_datetime,
            timezone_name=timezone_name,
            liushi_info=liushi_info,
        )

        timing_pillars = {
            "liushi": {"stem": liushi_info["stem"], "branch": liushi_info["branch"]}
        }

        element_effects = TimingEffectsAnalysis.analyze_element_strength_changes(
            birth_pillars,
            timing_pillars,
            original_element_counts=original_element_counts,
        )

        return {
            "liushi_info": liushi_info,
            "detailed_analysis": detailed_analysis,
            "element_effects": element_effects,
            "summary": f"流时{liushi_info['pillar']}，{element_effects['overall_effect']}",
            "enhanced_summary": detailed_analysis["overall_summary"],
        }

    @staticmethod
    def analyze_liuyue_comprehensive(
        birth_pillars: Dict,
        target_year: int,
        target_month: int,
        include_liunian: bool = True,
        target_day: int = 1,
        timezone_name: str = DEFAULT_TIMEZONE,
        target_date: Optional[datetime] = None,
        liuyue_info: Optional[Dict] = None,
        liunian_analysis: Optional[Dict] = None,
        original_element_counts: Optional[Dict[Element, float]] = None,
    ) -> Dict:
        """
        流月的综合分析，包括与大运、流年的组合影响

        Args:
            birth_pillars: 出生四柱
            target_year: 目标年份
            target_month: 目标月份
            include_liunian: 是否包含流年分析

        Returns:
            流月综合影响分析
        """
        # 基础流月分析
        liuyue_analysis = TimingEffectsAnalysis.analyze_liuyue_effects(
            birth_pillars,
            target_year,
            target_month,
            target_day=target_day,
            timezone_name=timezone_name,
            target_date=target_date,
            liuyue_info=liuyue_info,
            original_element_counts=original_element_counts,
        )

        result: Dict[str, Any] = {
            "liuyue_analysis": liuyue_analysis,
            "combination_effects": {},
        }

        if include_liunian:
            if liunian_analysis is None:
                liunian_analysis = TimingEffectsAnalysis.analyze_liunian_effects(
                    birth_pillars,
                    target_year,
                    original_element_counts=original_element_counts,
                    moment=target_date
                    or datetime(target_year, target_month, target_day),
                    timezone_name=timezone_name,
                )
            result["liunian_analysis"] = liunian_analysis

            liuyue_branch = liuyue_analysis["liuyue_info"]["branch"]
            liunian_branch = liunian_analysis["liunian_info"]["branch"]

            combination_analysis = TimingEffectsAnalysis._analyze_branch_combination(
                liuyue_branch, liunian_branch, "流月", "流年"
            )
            result["combination_effects"]["liuyue_liunian"] = combination_analysis

        # 大运组合分析需要性别+出生日期等额外输入，本入口未提供这些参数，
        # 故不在此层伪造。需要大运联动时由上层 analyze_dayun_effects 负责。

        result["comprehensive_summary"] = (
            TimingEffectsAnalysis._generate_comprehensive_liuyue_summary(result)
        )

        return result

    @staticmethod
    def _analyze_branch_combination(
        branch1: str, branch2: str, type1: str, type2: str
    ) -> Dict:
        """
        分析两个地支的组合关系

        Args:
            branch1: 第一个地支
            branch2: 第二个地支
            type1: 第一个地支的类型描述
            type2: 第二个地支的类型描述

        Returns:
            组合关系分析
        """
        from ..utils.data import check_branch_combination, check_branch_conflict

        relations: List[Dict[str, Any]] = []

        if check_branch_conflict(branch1, branch2):
            relations.append(
                {
                    "type": "六冲",
                    "description": f"{type1}{branch1}与{type2}{branch2}相冲",
                    "effect": "支冲关系成立，喜忌需结合原局",
                    "impact_score": None,
                }
            )

        if check_branch_combination(branch1, branch2):
            relations.append(
                {
                    "type": "六合",
                    "description": f"{type1}{branch1}与{type2}{branch2}六合",
                    "effect": "六合关系成立，合化与喜忌尚未判定",
                    "impact_score": None,
                }
            )

        if not relations:
            relations.append(
                {
                    "type": "普通",
                    "description": f"{type1}{branch1}与{type2}{branch2}关系普通",
                    "effect": "本二元检查未命中六冲或六合；不代表无其他关系",
                    "impact_score": None,
                }
            )

        return {
            "branch1": branch1,
            "branch2": branch2,
            "relations": relations,
            "total_impact_score": None,
            "assessment_status": "context_required",
            "overall_effect": "关系已核对，吉凶未判定",
        }

    @staticmethod
    def _generate_comprehensive_liuyue_summary(analysis_result: Dict) -> str:
        """
        生成流月综合分析总结

        Args:
            analysis_result: 综合分析结果

        Returns:
            总结文本
        """
        summary_parts = []

        # 流月基础信息
        liuyue_info = analysis_result["liuyue_analysis"]["liuyue_info"]
        summary_parts.append(
            f"{liuyue_info['year']}年{liuyue_info['month']}月流月{liuyue_info['pillar']}"
        )

        # 流月详细分析
        detailed = analysis_result["liuyue_analysis"]["detailed_analysis"]
        fortune = detailed["fortune_analysis"]["overall_fortune"]
        summary_parts.append(f"运势{fortune}")

        # 组合效应
        combination_effects = analysis_result.get("combination_effects", {})
        for combo_key, combo_data in combination_effects.items():
            if isinstance(combo_data, dict) and "overall_effect" in combo_data:
                summary_parts.append(
                    f"与{combo_key.replace('_', '、')}组合{combo_data['overall_effect']}"
                )

        return "，".join(summary_parts) + "。"

    @staticmethod
    def comprehensive_timing_analysis(
        birth_pillars: Dict,
        birth_date: datetime,
        gender: Optional[str],
        analysis_date: Optional[datetime] = None,
        timezone_name: str = DEFAULT_TIMEZONE,
        original_element_counts: Optional[Dict[Element, float]] = None,
        current_age: Optional[int] = None,
        liuyue_info: Optional[Dict] = None,
        liuri_info: Optional[Dict] = None,
        liushi_info: Optional[Dict] = None,
    ) -> Dict:
        """
        综合时运分析

        Args:
            birth_pillars: 出生四柱
            birth_date: 出生日期
            gender: 性别
            analysis_date: 分析日期，默认为当前日期

        Returns:
            综合时运分析结果
        """
        if analysis_date is None:
            analysis_date = current_local_datetime(timezone_name)

        explicit_age = current_age is not None
        if current_age is None:
            current_age = analysis_date.year - birth_date.year
            if analysis_date.month < birth_date.month or (
                analysis_date.month == birth_date.month
                and analysis_date.day < birth_date.day
            ):
                current_age -= 1

        # 大运分析
        dayun_analysis = TimingEffectsAnalysis.analyze_dayun_effects(
            birth_pillars,
            birth_date,
            gender,
            current_age,
            timezone_name=timezone_name,
            original_element_counts=original_element_counts,
            analysis_moment=None if explicit_age else analysis_date,
            allow_missing_gender=True,
        )

        # 流年分析
        liunian_analysis = TimingEffectsAnalysis.analyze_liunian_effects(
            birth_pillars,
            analysis_date.year,
            original_element_counts=original_element_counts,
            moment=analysis_date,
            timezone_name=timezone_name,
        )

        # 流月分析
        liuyue_analysis = TimingEffectsAnalysis.analyze_liuyue_effects(
            birth_pillars,
            analysis_date.year,
            analysis_date.month,
            target_day=analysis_date.day,
            timezone_name=timezone_name,
            target_date=analysis_date,
            liuyue_info=liuyue_info,
            original_element_counts=original_element_counts,
        )
        liuri_analysis = TimingEffectsAnalysis.analyze_liuri_effects(
            birth_pillars,
            analysis_date,
            timezone_name=timezone_name,
            liuri_info=liuri_info,
            original_element_counts=original_element_counts,
        )

        liushi_analysis = TimingEffectsAnalysis.analyze_liushi_effects(
            birth_pillars,
            analysis_date,
            timezone_name=timezone_name,
            liushi_info=liushi_info,
            original_element_counts=original_element_counts,
        )

        # 综合分析
        combined_timing_pillars = {}
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
            birth_pillars,
            combined_timing_pillars,
            original_element_counts=original_element_counts,
        )

        return {
            "analysis_date": analysis_date.strftime("%Y-%m-%d %H:%M"),
            "current_age": current_age,
            "dayun_analysis": dayun_analysis,
            "liunian_analysis": liunian_analysis,
            "liuyue_analysis": liuyue_analysis,
            "liuri_analysis": liuri_analysis,
            "liushi_analysis": liushi_analysis,
            "combined_effects": combined_effects,
            "interaction_analysis": analyze_timing_interactions(
                birth_pillars, combined_timing_pillars
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

    @staticmethod
    def _generate_comprehensive_summary(
        dayun_analysis: Dict,
        liunian_analysis: Dict,
        liuyue_analysis: Dict,
        liuri_analysis: Dict,
        combined_effects: Dict,
        liushi_analysis: Optional[Dict] = None,
    ) -> str:
        """生成综合时运分析总结"""
        summary_parts = []

        if "dayun_info" in dayun_analysis:
            dayun_pillar = dayun_analysis["dayun_info"]["pillar"]
            summary_parts.append(f"大运{dayun_pillar}")

        liunian_pillar = liunian_analysis["liunian_info"]["pillar"]
        liuyue_pillar = liuyue_analysis["liuyue_info"]["pillar"]
        liuri_pillar = liuri_analysis["liuri_info"]["pillar"]

        summary_parts.extend(
            [f"流年{liunian_pillar}", f"流月{liuyue_pillar}", f"流日{liuri_pillar}"]
        )

        if liushi_analysis and "liushi_info" in liushi_analysis:
            liushi_pillar = liushi_analysis["liushi_info"]["pillar"]
            summary_parts.append(f"流时{liushi_pillar}")

        overall_effect = combined_effects["overall_effect"]

        return f"当前时运组合：{' + '.join(summary_parts)}，{overall_effect}。"
