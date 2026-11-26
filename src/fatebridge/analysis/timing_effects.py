"""Analyze the effect of timed pillars on a natal BaZi chart."""

from __future__ import annotations

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
from fatebridge.core.bazi.calendar import ZiHourPolicy
from fatebridge.core.bazi.relations import collect_target_branch_relations
from fatebridge.core.bazi.shensha import timing_shensha
from fatebridge.core.bazi.timing import (
    TimingAnalysis,
    calculate_xiaoyun_pillar,
    calculate_xiaoyun_timeline,
)
from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.civil_time import (
    datetime_fromisoformat_preserving_offset as parse_iso_datetime,
)
from fatebridge.utils.civil_time import utc_ordering_key
from fatebridge.utils.data import Element, get_shishen


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
        """Select active Dayun (or pre-Dayun 小运 + ChildLimit) and compute element effects."""
        if allow_missing_gender and normalize_gender(gender) not in {"男", "女"}:
            return {
                "status": "unavailable_missing_gender",
                "message": "未提供顺逆所需的性别；大运未计算。",
                "timing_context": {
                    "status": "unavailable_missing_gender",
                    "selection_basis": (
                        "civil_calendar_moment"
                        if analysis_moment is not None
                        else "explicit_age_reference"
                    ),
                },
            }
        month_stem, month_branch = birth_pillars["month"]
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
        context: dict[str, Any] = {
            "selection_basis": selection_basis,
            "timeline": timeline,
        }
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
            period_index = int(elapsed_age // 10)
            dayun_age = analysis_age - start_age

        if before_start:
            nominal_age = max(1, int(analysis_age) + 1)
            xiaoyun = calculate_xiaoyun_pillar(
                birth_pillars["hour"], gender, start_info["year_stem"], nominal_age
            )
            day_stem = birth_pillars["day"][0]
            xiaoyun["stem_ten_god"] = get_shishen(day_stem, xiaoyun["stem"])
            xiaoyun["natal_relations"] = collect_target_branch_relations(
                xiaoyun["branch"],
                birth_pillars,
                "小运",
                target_stem=xiaoyun["stem"],
            )
            xiaoyun["shensha"] = timing_shensha(
                birth_pillars, xiaoyun["stem"], xiaoyun["branch"]
            )
            xiaoyun_timeline = calculate_xiaoyun_timeline(
                birth_pillars["hour"],
                gender,
                start_info["year_stem"],
                start_info["start_age_rounded"],
                birth_date.year,
            )
            timing_pillars = {
                "xiaoyun": {"stem": xiaoyun["stem"], "branch": xiaoyun["branch"]}
            }
            element_effects = TimingEffectsAnalysis.analyze_element_strength_changes(
                birth_pillars,
                timing_pillars,
                original_element_counts=original_element_counts,
            )
            return {
                "status": "before_dayun",
                "child_limit": timeline["child_limit"],
                "xiaoyun_info": xiaoyun,
                "xiaoyun_timeline": xiaoyun_timeline,
                "first_dayun": sequence[0],
                "element_effects": element_effects,
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
        timing_pillars = {
            "dayun": {"stem": current_dayun["stem"], "branch": current_dayun["branch"]}
        }
        element_effects = TimingEffectsAnalysis.analyze_element_strength_changes(
            birth_pillars,
            timing_pillars,
            original_element_counts=original_element_counts,
        )
        day_stem = birth_pillars["day"][0]
        return {
            "timing_context": context,
            "dayun_info": {
                **current_dayun,
                "stem_ten_god": get_shishen(day_stem, current_dayun["stem"]),
                "natal_relations": collect_target_branch_relations(
                    current_dayun["branch"],
                    birth_pillars,
                    "大运",
                    target_stem=current_dayun["stem"],
                ),
                "shensha": timing_shensha(
                    birth_pillars, current_dayun["stem"], current_dayun["branch"]
                ),
            },
            "child_limit": timeline["child_limit"],
            "age_info": {
                "analysis_age": analysis_age,
                "start_age": start_info["start_age_rounded"],
                "start_age_precise": start_info["start_age_precise"],
                "start_age_unrounded": start_info["start_age_unrounded"],
                "dayun_age": round(dayun_age, 2),
                "years_in_period": round(years_in_period, 2),
                "selection_basis": selection_basis,
                "direction": "顺行" if start_info["forward_direction"] else "逆行",
                "reference_term": start_info["reference_term"],
            },
            "element_effects": element_effects,
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
        liunian_kwargs: dict[str, Any] = {}
        if moment is not None:
            liunian_kwargs["moment"] = moment
            if timezone_name is not None:
                liunian_kwargs["timezone_name"] = timezone_name
        liunian_info = TimingAnalysis.calculate_liunian(target_year, **liunian_kwargs)
        day_stem = birth_pillars["day"][0]
        liunian_info["stem_ten_god"] = get_shishen(day_stem, liunian_info["stem"])
        liunian_info["hidden_stems"] = [
            {"stem": h, "ten_god": get_shishen(day_stem, h)}
            for h in (
                __import__(
                    "fatebridge.utils.data", fromlist=["BRANCH_HIDDEN_STEMS"]
                ).BRANCH_HIDDEN_STEMS[liunian_info["branch"]]
            )
        ]
        liunian_info["natal_relations"] = collect_target_branch_relations(
            liunian_info["branch"],
            birth_pillars,
            "流年",
            target_stem=liunian_info["stem"],
        )
        liunian_info["shensha"] = timing_shensha(
            birth_pillars, liunian_info["stem"], liunian_info["branch"]
        )

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
        }

    @staticmethod
    def analyze_liuri_effects(
        birth_pillars: dict[str, tuple[str, str]],
        target_date: datetime,
        timezone_name: str = DEFAULT_TIMEZONE,
        liuri_info: dict[str, Any] | None = None,
        original_element_counts: dict[Element, float] | None = None,
        zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    ) -> dict[str, Any]:
        if liuri_info is None:
            liuri_info = TimingAnalysis.calculate_liuri(
                target_date, timezone_name=timezone_name, zi_hour_policy=zi_hour_policy
            )
        detailed_analysis = TimingAnalysis.analyze_liuri_detailed(
            birth_pillars,
            target_date,
            timezone_name=timezone_name,
            liuri_info=liuri_info,
            zi_hour_policy=zi_hour_policy,
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
        }

    @staticmethod
    def analyze_liushi_effects(
        birth_pillars: dict[str, tuple[str, str]],
        target_datetime: datetime,
        timezone_name: str = DEFAULT_TIMEZONE,
        liushi_info: dict[str, Any] | None = None,
        original_element_counts: dict[Element, float] | None = None,
        zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    ) -> dict[str, Any]:
        if liushi_info is None:
            liushi_info = TimingAnalysis.calculate_liushi(
                target_datetime,
                timezone_name=timezone_name,
                zi_hour_policy=zi_hour_policy,
            )
        detailed_analysis = TimingAnalysis.analyze_liushi_detailed(
            birth_pillars,
            target_datetime,
            timezone_name=timezone_name,
            liushi_info=liushi_info,
            zi_hour_policy=zi_hour_policy,
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
            liuyue_b = liuyue_analysis["liuyue_info"]["branch"]
            liunian_b = liunian_analysis["liunian_info"]["branch"]
            liuyue_s = liuyue_analysis["liuyue_info"]["stem"]
            liunian_s = liunian_analysis["liunian_info"]["stem"]
            rels = collect_target_branch_relations(
                liuyue_b,
                {
                    "year": (liunian_s, liunian_b),
                    "month": (liunian_s, liunian_b),
                    "day": (liunian_s, liunian_b),
                    "hour": (liunian_s, liunian_b),
                },
                "流月",
                target_stem=liuyue_s,
            )
            # Filter deduplicated relations against the single liunian pillar
            seen = set()
            pair_rels = []
            for r in rels:
                if r.get("with_pillar") not in (None, "year"):
                    continue
                key = (r["type"], r.get("with_branch"), r.get("group"))
                if key not in seen:
                    seen.add(key)
                    pair_rels.append(r)
            result["combination_effects"]["liuyue_liunian"] = {
                "liuyue_pillar": liuyue_analysis["liuyue_info"]["pillar"],
                "liunian_pillar": liunian_analysis["liunian_info"]["pillar"],
                "relations": pair_rels,
            }
        return result
