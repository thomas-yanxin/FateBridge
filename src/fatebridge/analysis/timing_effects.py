"""Analyze the effect of timed pillars on a natal BaZi chart."""

from datetime import datetime
from typing import Any

from fatebridge.analysis.timing_element_shares import (
    TimingElementEffects,
    analyze_element_strength_changes,
)
from fatebridge.core.almanac import (
    DEFAULT_TIMEZONE,
    elapsed_days_between,
    localize_datetime,
)
from fatebridge.core.timing import TimingAnalysis
from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.civil_time import (
    datetime_fromisoformat_preserving_offset as parse_iso_datetime,
)
from fatebridge.utils.civil_time import utc_ordering_key
from fatebridge.utils.data import (
    Element,
    check_branch_combination,
    check_branch_conflict,
)


class TimingEffectsAnalysis:
    """时运影响分析类"""

    analyze_element_strength_changes = staticmethod(analyze_element_strength_changes)

    @staticmethod
    def analyze_dayun_effects(
        birth_pillars: dict[str, tuple[str, str]],
        birth_date: datetime,
        gender: str | None,
        analysis_age: int,
        timezone_name: str = DEFAULT_TIMEZONE,
        original_element_counts: dict[Element, float] | None = None,
        *,
        analysis_moment: datetime | None = None,
        allow_missing_gender: bool = False,
    ) -> dict[str, Any]:
        """Select an active Dayun by exact instant or elapsed age, and describe its effects."""
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

        resolution = TimingAnalysis.resolve_dayun_start(
            birth_date, gender, timezone_name
        )
        timeline = TimingAnalysis.build_dayun_timeline(
            resolution, gender, (month_stem, month_branch), timezone_name
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
            instant = utc_ordering_key(moment)
            context["analysis_at"] = moment.isoformat()
            start_at = parse_iso_datetime(timeline["start_at"])
            before_start = instant < utc_ordering_key(start_at)
            period_index = next(
                (
                    index
                    for index, item in enumerate(sequence)
                    if utc_ordering_key(parse_iso_datetime(item["start_at"]))
                    <= instant
                    < utc_ordering_key(parse_iso_datetime(item["end_at"]))
                ),
                len(sequence),
            )
            dayun_age = elapsed_days_between(start_at, moment) / 365.2425
        else:
            elapsed_age = analysis_age - resolution.nominal_days / 3
            before_start = elapsed_age < 0
            period_index = elapsed_age // 10
            dayun_age = analysis_age - start_age

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
                parse_iso_datetime(current_dayun["start_at"]),
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
            "summary": f"大运{current_dayun['pillar']}期间，{element_effects['overall_effect']}。",
        }

    @staticmethod
    def analyze_liunian_effects(
        birth_pillars: dict[str, tuple[str, str]],
        target_year: int,
        original_element_counts: dict[Element, float] | None = None,
        *,
        moment: datetime | None = None,
        timezone_name: str | None = None,
    ) -> dict[str, Any]:
        """Describe annual effects using the Li Chun year when an analysis instant is supplied."""
        # 获取流年信息；传入 moment 使 calculate_liunian 以立春为边界。
        liunian_kwargs: dict[str, Any] = {}
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
        birth_pillars: dict[str, tuple[str, str]],
        target_year: int,
        target_month: int,
        target_day: int = 1,
        timezone_name: str = DEFAULT_TIMEZONE,
        target_date: datetime | None = None,
        liuyue_info: dict[str, Any] | None = None,
        original_element_counts: dict[Element, float] | None = None,
    ) -> dict[str, Any]:
        """Describe the effects of the solar-term month pillar."""
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
        birth_pillars: dict[str, tuple[str, str]],
        target_date: datetime,
        timezone_name: str = DEFAULT_TIMEZONE,
        liuri_info: dict[str, Any] | None = None,
        original_element_counts: dict[Element, float] | None = None,
    ) -> dict[str, Any]:
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
        birth_pillars: dict[str, tuple[str, str]],
        target_datetime: datetime,
        timezone_name: str = DEFAULT_TIMEZONE,
        liushi_info: dict[str, Any] | None = None,
        original_element_counts: dict[Element, float] | None = None,
    ) -> dict[str, Any]:
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
        birth_pillars: dict[str, tuple[str, str]],
        target_year: int,
        target_month: int,
        include_liunian: bool = True,
        target_day: int = 1,
        timezone_name: str = DEFAULT_TIMEZONE,
        target_date: datetime | None = None,
        liuyue_info: dict[str, Any] | None = None,
        liunian_analysis: dict[str, Any] | None = None,
        original_element_counts: dict[Element, float] | None = None,
    ) -> dict[str, Any]:
        """Describe the month and its optional branch relationship with the annual pillar."""
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

        result: dict[str, Any] = {
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
    ) -> dict[str, Any]:
        """Report structural pair relations for the two labeled branches."""
        relations: list[dict[str, Any]] = []

        if check_branch_conflict(branch1, branch2):
            relations.append(
                {
                    "type": "六冲",
                    "description": f"{type1}{branch1}与{type2}{branch2}相冲",
                    "effect": "支冲关系成立，喜忌需结合原局",
                }
            )

        if check_branch_combination(branch1, branch2):
            relations.append(
                {
                    "type": "六合",
                    "description": f"{type1}{branch1}与{type2}{branch2}六合",
                    "effect": "六合关系成立，合化与喜忌尚未判定",
                }
            )

        if not relations:
            relations.append(
                {
                    "type": "普通",
                    "description": f"{type1}{branch1}与{type2}{branch2}关系普通",
                    "effect": "本二元检查未命中六冲或六合；不代表无其他关系",
                }
            )

        return {
            "branch1": branch1,
            "branch2": branch2,
            "relations": relations,
            "assessment_status": "context_required",
            "overall_effect": "关系已核对，吉凶未判定",
        }

    @staticmethod
    def _generate_comprehensive_liuyue_summary(analysis_result: dict[str, Any]) -> str:
        """Summarize the monthly pillar, ten god, and branch relationships."""
        summary_parts = []

        # 流月基础信息
        liuyue_info = analysis_result["liuyue_analysis"]["liuyue_info"]
        summary_parts.append(
            f"{liuyue_info['year']}年{liuyue_info['month']}月流月{liuyue_info['pillar']}"
        )

        # 流月详细分析
        stem_relation = analysis_result["liuyue_analysis"]["detailed_analysis"][
            "shishen_analysis"
        ]["stem_relation"]
        summary_parts.append(f"十神{stem_relation}")

        # 组合效应
        combination_effects = analysis_result.get("combination_effects", {})
        for combo_key, combo_data in combination_effects.items():
            if isinstance(combo_data, dict) and "overall_effect" in combo_data:
                summary_parts.append(
                    f"与{combo_key.replace('_', '、')}组合{combo_data['overall_effect']}"
                )

        return "，".join(summary_parts) + "。"

    @staticmethod
    def _generate_comprehensive_summary(
        dayun_analysis: dict[str, Any],
        liunian_analysis: dict[str, Any],
        liuyue_analysis: dict[str, Any],
        liuri_analysis: dict[str, Any],
        combined_effects: TimingElementEffects,
        liushi_analysis: dict[str, Any] | None = None,
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
