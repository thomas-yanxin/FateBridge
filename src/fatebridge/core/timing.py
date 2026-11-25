"""Compute BaZi time pillars, term boundaries, and pillar relationships."""

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from functools import lru_cache
from typing import Any, Dict

from fatebridge.core.almanac import (
    BAZI_MONTH_START_TERMS,
    DEFAULT_TIMEZONE,
    SolarTerm,
    _solar_term_source_year,
    _solar_terms_for_context_year,
    elapsed_days_between,
    get_bazi_month_boundaries,
    get_bazi_month_context,
    get_bazi_year,
    get_solar_term_environment_key,
    get_solar_terms_for_year,
    localize_datetime,
    require_calculated_solar_term,
)
from fatebridge.core.calendar import BaZiCalendar, resolve_bazi_effective_date
from fatebridge.core.timing_dayun import (
    DayunCalendarOffset,
    DayunStartDetails,
    DayunStartResolution,
    DayunTimeline,
    calculate_dayun_sequence,
    dayun_is_forward,
    dayun_wall_year_preimages,
    resolve_dayun_calendar_boundary,
)
from fatebridge.utils.civil_time import ZonedCalendar, utc_calendar
from fatebridge.utils.data import (
    STEM_ELEMENTS,
    check_branch_combination,
    check_branch_conflict,
    get_nayin,
    get_shishen,
)
from fatebridge.utils.timezones import (
    is_unspecified_local_time,
    timezone_transition_candidates,
    validate_local_clock,
)


def _copy_timing_info(info: Dict) -> Dict:
    """Copy cached fields and detach nested solar-term metadata before delivery."""
    result = info.copy()
    if "solar_term_window" in info:
        result["solar_term_window"] = deepcopy(info["solar_term_window"])
    else:
        pass
    return result


@lru_cache(maxsize=2048)
def _calculate_liuyue_cached(
    target_clock: ZonedCalendar,
    timezone_name: str,
    _solar_environment: tuple[Any, ...] = (),
) -> Dict:
    """Cache deterministic liuyue calculations for repeated timing analysis."""
    local_target_date = target_clock.require_datetime()
    bazi_year = get_bazi_year(local_target_date, timezone_name)
    month_context = get_bazi_month_context(local_target_date, timezone_name)
    liuyue_stem, liuyue_branch = BaZiCalendar.calculate_month_pillar_by_branch(
        bazi_year,
        str(month_context["branch"]),
    )
    stem_element, stem_polarity = STEM_ELEMENTS[liuyue_stem]

    return {
        "year": local_target_date.year,
        "month": local_target_date.month,
        "day": local_target_date.day,
        "analysis_datetime": local_target_date.strftime("%Y-%m-%d %H:%M:%S"),
        "bazi_year": bazi_year,
        "stem": liuyue_stem,
        "branch": liuyue_branch,
        "pillar": f"{liuyue_stem}{liuyue_branch}",
        "element": stem_element.value,
        "polarity": stem_polarity.value,
        "nayin": get_nayin(liuyue_stem, liuyue_branch),
        "solar_term_window": {
            "start_term": month_context["start_term"],
            "next_term": month_context["next_term"],
            "days_since_start": month_context["days_since_start"],
            "days_until_next": month_context["days_until_next"],
        },
    }


@lru_cache(maxsize=4096)
def _calculate_liushi_cached(
    civil_date: date,
    civil_hour: int,
) -> Dict:
    """Cache the civil date/hour rule without constructing a nominal instant."""
    liushi_stem, liushi_branch = BaZiCalendar.calculate_hour_pillar(
        civil_date.year,
        civil_date.month,
        civil_date.day,
        civil_hour,
    )
    stem_element, stem_polarity = STEM_ELEMENTS[liushi_stem]

    return {
        "year": civil_date.year,
        "month": civil_date.month,
        "day": civil_date.day,
        "hour": civil_hour,
        "stem": liushi_stem,
        "branch": liushi_branch,
        "pillar": f"{liushi_stem}{liushi_branch}",
        "element": stem_element.value,
        "polarity": stem_polarity.value,
        "nayin": get_nayin(liushi_stem, liushi_branch),
        "shichen": liushi_branch,
    }


@lru_cache(maxsize=4096)
def _calculate_liuri_cached(
    target_clock: ZonedCalendar,
    timezone_name: str,
    _solar_environment: tuple[Any, ...] = (),
) -> Dict:
    """Cache daily timing with the day pillar rolled over at 23:00."""
    local_target_date = target_clock.require_datetime()
    liuri_stem, liuri_branch = BaZiCalendar.calculate_day_pillar(
        local_target_date.year,
        local_target_date.month,
        local_target_date.day,
        hour=local_target_date.hour,
    )
    effective_year, effective_month, effective_day = resolve_bazi_effective_date(
        local_target_date.year,
        local_target_date.month,
        local_target_date.day,
        local_target_date.hour,
    )
    applied_late_zi_rollover = (
        effective_year != local_target_date.year
        or effective_month != local_target_date.month
        or effective_day != local_target_date.day
    )
    stem_element, stem_polarity = STEM_ELEMENTS[liuri_stem]
    month_context = get_bazi_month_context(local_target_date, timezone_name)
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    return {
        # note (calendar): Keep the civil date label even after the pillar changes at 23:00.
        "year": local_target_date.year,
        "month": local_target_date.month,
        "day": local_target_date.day,
        "analysis_datetime": local_target_date.strftime("%Y-%m-%d %H:%M:%S"),
        "effective_date": (
            f"{effective_year:04d}-{effective_month:02d}-{effective_day:02d}"
        ),
        "late_zi_rollover_applied": applied_late_zi_rollover,
        "stem": liuri_stem,
        "branch": liuri_branch,
        "pillar": f"{liuri_stem}{liuri_branch}",
        "element": stem_element.value,
        "polarity": stem_polarity.value,
        "nayin": get_nayin(liuri_stem, liuri_branch),
        "weekday": weekday_names[local_target_date.weekday()],
        "solar_term_window": {
            "start_term": month_context["start_term"],
            "next_term": month_context["next_term"],
            "days_since_start": month_context["days_since_start"],
            "days_until_next": month_context["days_until_next"],
        },
    }


DEFAULT_DAYUN_PERIODS = 12


class TimingAnalysis:
    """Compute the Dayun timeline and the annual through hourly BaZi layers."""

    _dayun_wall_year_preimages = staticmethod(dayun_wall_year_preimages)
    _resolve_dayun_calendar_boundary = staticmethod(resolve_dayun_calendar_boundary)
    calculate_dayun_sequence = staticmethod(calculate_dayun_sequence)

    @staticmethod
    def resolve_dayun_start(
        birth_date: datetime,
        gender: str | None,
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> DayunStartResolution:
        """Select the existing direction and actual Jie without serializing it."""
        local_birth_date = localize_datetime(birth_date, timezone_name)
        bazi_year = get_bazi_year(local_birth_date, timezone_name)
        year_stem, _ = BaZiCalendar.calculate_year_pillar(bazi_year)
        forward_direction = dayun_is_forward(gender, year_stem)

        start_term, next_term, _, _ = get_bazi_month_boundaries(
            local_birth_date, timezone_name
        )
        target_term = next_term if forward_direction else start_term
        nominal_days = abs(
            target_term.point.day - utc_calendar(local_birth_date).julian_day_exact()
        )
        return DayunStartResolution(
            local_birth_date, target_term, forward_direction, year_stem, nominal_days
        )

    @staticmethod
    def calculate_dayun_start_details(
        birth_date: datetime,
        gender: str | None,
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> DayunStartDetails:
        """JSON/SDK details for the same selected source used by event owners."""
        return TimingAnalysis.resolve_dayun_start(
            birth_date, gender, timezone_name
        ).to_details()

    @staticmethod
    def _dayun_calendar_wall_context(
        birth_date: datetime,
        gender: str | None,
        timezone_name: str,
    ) -> tuple[datetime, DayunStartDetails, datetime, DayunCalendarOffset]:
        """Quantize the retained span once, then apply the civil calendar policy."""
        resolution = TimingAnalysis.resolve_dayun_start(
            birth_date, gender, timezone_name
        )
        start_wall, offset = resolution.calendar_wall_offset()
        return resolution.birth, resolution.to_details(), start_wall, offset

    @staticmethod
    def calculate_dayun_timeline(
        birth_date: datetime,
        gender: str | None,
        month_pillar: tuple[str, str],
        timezone_name: str = DEFAULT_TIMEZONE,
        periods: int = DEFAULT_DAYUN_PERIODS,
    ) -> dict[str, Any]:
        """Add the nominal three-days-per-year Dayun conversion to the civil birth clock."""
        resolution = TimingAnalysis.resolve_dayun_start(
            birth_date, gender, timezone_name
        )
        return dict(
            TimingAnalysis.build_dayun_timeline(
                resolution, gender, month_pillar, timezone_name, periods
            )
        )

    @staticmethod
    def build_dayun_timeline(
        resolution: DayunStartResolution,
        gender: str | None,
        month_pillar: tuple[str, str],
        timezone_name: str,
        periods: int = DEFAULT_DAYUN_PERIODS,
    ) -> DayunTimeline:
        """Build boundaries and displays from a caller's selected source point."""
        birth = resolution.birth
        details = resolution.to_details()
        start_wall, calendar_offset = resolution.calendar_wall_offset()
        initial_fold_adjusted = False

        def civil_boundary(year_offset: int) -> datetime:
            nonlocal initial_fold_adjusted
            resolved, adjusted = TimingAnalysis._resolve_dayun_calendar_boundary(
                birth, start_wall, year_offset, timezone_name
            )
            initial_fold_adjusted = initial_fold_adjusted or adjusted
            return resolved

        initial_boundary = civil_boundary(0)
        sequence = TimingAnalysis.calculate_dayun_sequence(
            month_pillar[0],
            month_pillar[1],
            gender,
            details["year_stem"],
            periods=periods,
            start_age=details["start_age_unrounded"],
        )
        for index, period in enumerate(sequence):
            period["start_at"] = (
                initial_boundary if index == 0 else civil_boundary(index * 10)
            ).isoformat()
            period["end_at"] = civil_boundary((index + 1) * 10).isoformat()
        return {
            "method_id": "three_days_one_year_calendar_v1",
            "timezone": timezone_name,
            "birth_at": birth.isoformat(),
            "start_at": initial_boundary.isoformat(),
            "start_details": details,
            "calendar_offset": calendar_offset,
            "boundary_policy": "start_inclusive_end_exclusive",
            "calendar_policy": "360_nominal_days_to_year_30_to_month_then_civil_addition",
            "dst_policy": (
                "fold_0_gap_forward_initial_not_before_birth"
                if initial_fold_adjusted
                else "fold_0_gap_forward"
            ),
            "reference_policy": "next_jie_strict_for_forward_previous_jie_inclusive_for_reverse",
            "source": {
                "title": "三命通会·卷二·论大运",
                "url": "https://zh.wikisource.org/zh-hant/三命通會/卷二#論大運",
            },
            "scope": "三日一年及十年一运为传统规则；公历加法、秒级延拓和DST处理是工程约定。边界精度受出生时间和节气精度限制，覆盖期数不是寿命估计。",
            "periods": sequence,
        }

    @staticmethod
    def calculate_liunian(
        target_year: int,
        *,
        moment: datetime | None = None,
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> Dict:
        """Return the Li Chun year pillar when a moment is supplied, or the requested year pillar."""
        if moment is not None:
            resolved_year = get_bazi_year(moment, timezone_name)
        else:
            resolved_year = target_year

        liunian_stem, liunian_branch = BaZiCalendar.calculate_year_pillar(resolved_year)
        stem_element, _ = STEM_ELEMENTS[liunian_stem]

        return {
            "year": resolved_year,
            "stem": liunian_stem,
            "branch": liunian_branch,
            "pillar": f"{liunian_stem}{liunian_branch}",
            "element": stem_element.value,
        }

    @staticmethod
    def calculate_liuyue(
        target_year: int,
        target_month: int,
        target_day: int = 1,
        timezone_name: str = DEFAULT_TIMEZONE,
        target_date: datetime | None = None,
    ) -> Dict:
        """Calculate the solar-term month pillar at the supplied or constructed analysis instant."""
        local_target_date = localize_datetime(
            target_date or datetime(target_year, target_month, target_day),
            timezone_name,
        )
        return _copy_timing_info(
            _calculate_liuyue_cached(
                ZonedCalendar.from_datetime(local_target_date),
                timezone_name,
                get_solar_term_environment_key(year=local_target_date.year),
            )
        )

    @staticmethod
    def _next_supported_analysis_anchor(
        start_term: SolarTerm,
        timezone_name: str = DEFAULT_TIMEZONE,
        *,
        end_term: SolarTerm | None = None,
    ) -> datetime | None:
        """Find the earliest replayable local minute strictly within the term interval."""
        local_moment = localize_datetime(start_term.moment, timezone_name)
        anchor = local_moment.replace(second=0, microsecond=0)
        start_day = start_term.point.day
        end_day = end_term.point.day if end_term is not None else None
        instant = local_moment.astimezone(timezone.utc)
        if end_term is not None and is_unspecified_local_time(local_moment):
            end = end_term.calendar.utc.as_datetime()
            zone = local_moment.tzinfo
            assert zone is not None
            if end is not None:
                cuts = timezone_transition_candidates(zone, instant, end)
                if cuts is not None:
                    reopened = next(
                        (
                            local
                            for cut in cuts
                            if not is_unspecified_local_time(
                                local := cut.astimezone(zone)
                            )
                        ),
                        None,
                    )
                    if reopened is None:
                        return None
                    else:
                        pass
                    anchor = reopened.replace(second=0, microsecond=0)
                    if anchor != reopened:
                        anchor += timedelta(minutes=1)
                    else:
                        pass
                else:
                    pass
            else:
                pass
        else:
            pass
        while True:
            try:
                validate_local_clock(anchor)
            except ValueError:
                anchor += timedelta(minutes=1)
                continue
            anchor_day = utc_calendar(anchor).julian_day_exact()
            if end_day is not None and anchor_day >= end_day:
                return None
            else:
                pass
            if anchor_day > start_day:
                return anchor
            else:
                pass
            anchor += timedelta(minutes=1)

    @staticmethod
    def calculate_liuyue_timeline(
        target_year: int,
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> list[Dict]:
        """
        生成目标年份的 12 个节令月时间轴。
        """
        current_year_terms = [
            term
            for term in get_solar_terms_for_year(target_year, timezone_name)
            if term.name in BAZI_MONTH_START_TERMS
        ]
        next_year_terms = _solar_terms_for_context_year(
            target_year + 1,
            timezone_name,
            _solar_term_source_year(target_year + 1, target_year),
            term_index=0,
        )

        timeline: list[Dict] = []

        for index, start_term in enumerate(current_year_terms):
            next_term = (
                current_year_terms[index + 1]
                if index + 1 < len(current_year_terms)
                else next_year_terms[0]
            )
            require_calculated_solar_term(start_term)
            require_calculated_solar_term(next_term)
            start = start_term.as_dict()
            end = next_term.as_dict()
            window: dict[str, str | float] = {
                "days": round(
                    elapsed_days_between(start_term.point, next_term.point), 4
                )
            }
            for key, record in (("start", start), ("end", end)):
                if "datetime" in record:
                    window[key] = record["datetime"]
                else:
                    window[f"{key}_utc"] = record["datetime_utc"]
            item = {
                "order": index + 1,
                "gregorian_window": window,
                "start_term": start,
                "next_term": end,
            }
            anchor = TimingAnalysis._next_supported_analysis_anchor(
                start_term, timezone_name, end_term=next_term
            )
            if anchor is None:
                item["analysis_anchor_status"] = "no_replayable_local_minute_in_window"
            else:
                item["analysis_anchor"] = anchor.strftime("%Y-%m-%d %H:%M:%S")
                item["liuyue"] = TimingAnalysis.calculate_liuyue(
                    anchor.year,
                    anchor.month,
                    anchor.day,
                    timezone_name=timezone_name,
                    target_date=anchor,
                )
            timeline.append(item)

        return timeline

    @staticmethod
    def calculate_liuri(
        target_date: datetime,
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> Dict:
        """
        计算指定时点的流日干支。
        """
        local_target_date = localize_datetime(target_date, timezone_name)
        return _copy_timing_info(
            _calculate_liuri_cached(
                ZonedCalendar.from_datetime(local_target_date),
                timezone_name,
                get_solar_term_environment_key(year=local_target_date.year),
            )
        )

    @staticmethod
    def calculate_liushi(
        target_datetime: datetime,
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> Dict:
        """
        计算指定时刻的流时干支。

        按有效本地日期和小时缓存时柱，另交付实际查询时刻。
        """
        local_dt = localize_datetime(target_datetime, timezone_name)
        # A valid local query can follow a partial-hour gap whose nominal
        # xx:00 does not exist. The pillar needs civil fields, not that instant.
        result = _copy_timing_info(
            _calculate_liushi_cached(local_dt.date(), local_dt.hour)
        )
        result["analysis_datetime"] = local_dt.strftime("%Y-%m-%d %H:%M:%S")
        return result

    @staticmethod
    def analyze_liushi_detailed(
        birth_pillars: Dict,
        target_datetime: datetime,
        day_stem: str | None = None,
        timezone_name: str = DEFAULT_TIMEZONE,
        liushi_info: Dict | None = None,
    ) -> Dict:
        """
        流时详细分析，包括十神关系与冲合。
        """
        if liushi_info is None:
            liushi_info = TimingAnalysis.calculate_liushi(
                target_datetime, timezone_name=timezone_name
            )
        else:
            pass

        if day_stem is None:
            day_stem = birth_pillars["day"][0]
        else:
            pass

        stem_shishen = get_shishen(day_stem, liushi_info["stem"])
        branch_relations = TimingAnalysis._collect_branch_relations(
            liushi_info["branch"], birth_pillars, "流时"
        )

        return {
            "basic_info": liushi_info,
            "shishen_analysis": {
                "stem_relation": stem_shishen,
                "description": f"流时天干{liushi_info['stem']}对日主{day_stem}为{stem_shishen}",
            },
            "branch_relations": branch_relations,
            "overall_summary": TimingAnalysis._generate_liushi_summary(
                liushi_info, stem_shishen, branch_relations
            ),
        }

    @staticmethod
    def _generate_liushi_summary(
        liushi_info: Dict,
        stem_shishen: str,
        branch_relations: list[Dict],
    ) -> str:
        """生成流时分析总结。"""
        dt_label = (
            f"{liushi_info['year']}年{liushi_info['month']}月"
            f"{liushi_info['day']}日{liushi_info['hour']}时"
        )
        pillar = liushi_info["pillar"]
        nayin = liushi_info["nayin"]

        summary_parts = [
            f"{dt_label}流时{pillar}({nayin})",
            f"十神{stem_shishen}",
        ]

        if branch_relations:
            relation_desc = "、".join([r["type"] for r in branch_relations])
            summary_parts.append(f"有{relation_desc}关系")
        else:
            pass

        return "，".join(summary_parts) + "。"

    @staticmethod
    def calculate_jieqi_transition_timeline(
        target_year: int,
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> list[Dict]:
        """
        生成目标年份 24 节气切换节点的时运时间轴。
        """
        terms = tuple(get_solar_terms_for_year(target_year, timezone_name))
        following = _solar_terms_for_context_year(
            target_year + 1,
            timezone_name,
            _solar_term_source_year(target_year + 1, target_year),
            term_index=0,
        )
        timeline: list[Dict] = []
        for index, (term, next_term) in enumerate(zip(terms, terms[1:] + following)):
            require_calculated_solar_term(term)
            require_calculated_solar_term(next_term)
            item = {"order": index + 1, "jieqi": term.as_dict()}
            anchor = TimingAnalysis._next_supported_analysis_anchor(
                term, timezone_name, end_term=next_term
            )
            if anchor is None:
                item["analysis_anchor_status"] = "no_replayable_local_minute_in_window"
            else:
                item["analysis_anchor"] = anchor.strftime("%Y-%m-%d %H:%M:%S")
                item["liuyue"] = TimingAnalysis.calculate_liuyue(
                    anchor.year,
                    anchor.month,
                    anchor.day,
                    timezone_name=timezone_name,
                    target_date=anchor,
                )
                item["liuri"] = TimingAnalysis.calculate_liuri(
                    anchor, timezone_name=timezone_name
                )
            timeline.append(item)
        return timeline

    @staticmethod
    def _collect_branch_relations(
        target_branch: str,
        birth_pillars: Dict,
        label: str,
    ) -> list[Dict]:
        """收集目标支与命局四支的冲合关系。"""
        branch_relations = []
        for pillar_name, pillar_data in birth_pillars.items():
            pillar_branch = pillar_data[1]

            if check_branch_conflict(target_branch, pillar_branch):
                branch_relations.append(
                    {
                        "type": "六冲",
                        "with_pillar": pillar_name,
                        "with_branch": pillar_branch,
                        "description": f"{label}{target_branch}与{pillar_name}柱{pillar_branch}相冲",
                    }
                )
            else:
                pass

            if check_branch_combination(target_branch, pillar_branch):
                branch_relations.append(
                    {
                        "type": "六合",
                        "with_pillar": pillar_name,
                        "with_branch": pillar_branch,
                        "description": f"{label}{target_branch}与{pillar_name}柱{pillar_branch}六合",
                    }
                )
            else:
                pass

        return branch_relations

    @staticmethod
    def analyze_liuyue_detailed(
        birth_pillars: Dict,
        target_year: int,
        target_month: int,
        day_stem: str | None = None,
        target_day: int = 1,
        timezone_name: str = DEFAULT_TIMEZONE,
        target_date: datetime | None = None,
        liuyue_info: Dict | None = None,
    ) -> Dict:
        """Describe ten-god and branch relationships for the monthly pillar."""
        if liuyue_info is None:
            liuyue_info = TimingAnalysis.calculate_liuyue(
                target_year,
                target_month,
                target_day=target_day,
                timezone_name=timezone_name,
                target_date=target_date,
            )
        else:
            pass

        if day_stem is None:
            day_stem = birth_pillars["day"][0]
        else:
            pass

        stem_shishen = get_shishen(day_stem, liuyue_info["stem"])

        branch_relations = TimingAnalysis._collect_branch_relations(
            liuyue_info["branch"], birth_pillars, "流月"
        )

        return {
            "basic_info": liuyue_info,
            "shishen_analysis": {
                "stem_relation": stem_shishen,
                "description": f"流月天干{liuyue_info['stem']}对日主{day_stem}为{stem_shishen}",
            },
            "branch_relations": branch_relations,
            "overall_summary": TimingAnalysis._generate_liuyue_summary(
                liuyue_info, stem_shishen, branch_relations
            ),
        }

    @staticmethod
    def analyze_liuri_detailed(
        birth_pillars: Dict,
        target_date: datetime,
        day_stem: str | None = None,
        timezone_name: str = DEFAULT_TIMEZONE,
        liuri_info: Dict | None = None,
    ) -> Dict:
        """
        流日详细分析，包括十神关系与冲合。
        """
        if liuri_info is None:
            liuri_info = TimingAnalysis.calculate_liuri(
                target_date, timezone_name=timezone_name
            )
        else:
            pass

        if day_stem is None:
            day_stem = birth_pillars["day"][0]
        else:
            pass

        stem_shishen = get_shishen(day_stem, liuri_info["stem"])
        branch_relations = TimingAnalysis._collect_branch_relations(
            liuri_info["branch"], birth_pillars, "流日"
        )

        return {
            "basic_info": liuri_info,
            "shishen_analysis": {
                "stem_relation": stem_shishen,
                "description": f"流日天干{liuri_info['stem']}对日主{day_stem}为{stem_shishen}",
            },
            "branch_relations": branch_relations,
            "overall_summary": TimingAnalysis._generate_liuri_summary(
                liuri_info, stem_shishen, branch_relations
            ),
        }

    @staticmethod
    def _generate_liuyue_summary(
        liuyue_info: Dict,
        stem_shishen: str,
        branch_relations: list[Dict],
    ) -> str:
        """Summarize monthly stem and branch relationships."""
        year_month = f"{liuyue_info['year']}年{liuyue_info['month']}月"
        pillar = liuyue_info["pillar"]
        nayin = liuyue_info["nayin"]

        summary_parts = [
            f"{year_month}流月{pillar}({nayin})",
            f"十神{stem_shishen}",
        ]

        if branch_relations:
            relation_desc = "、".join([r["type"] for r in branch_relations])
            summary_parts.append(f"有{relation_desc}关系")
        else:
            pass

        return "，".join(summary_parts) + "。"

    @staticmethod
    def _generate_liuri_summary(
        liuri_info: Dict,
        stem_shishen: str,
        branch_relations: list[Dict],
    ) -> str:
        """生成流日分析总结。"""
        year_month_day = (
            f"{liuri_info['year']}年{liuri_info['month']}月{liuri_info['day']}日"
        )
        pillar = liuri_info["pillar"]
        nayin = liuri_info["nayin"]

        summary_parts = [
            f"{year_month_day}流日{pillar}({nayin})",
            f"十神{stem_shishen}",
        ]

        if branch_relations:
            relation_desc = "、".join([r["type"] for r in branch_relations])
            summary_parts.append(f"有{relation_desc}关系")
        else:
            pass

        return "，".join(summary_parts) + "。"
