#!/usr/bin/env python3
"""
时运分析模块 - 大运、流年、流月计算

本模块提供八字时运分析的核心功能：
1. 大运计算 - 10年一个周期的运势变化
2. 流年计算 - 每年的运势影响
3. 流月计算 - 每月的运势变化
"""

import math
from calendar import isleap
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple, cast

from dateutil.relativedelta import relativedelta
from dateutil.tz import resolve_imaginary

from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.timezones import validate_local_clock

from ..utils.data import (
    EARTHLY_BRANCHES,
    HEAVENLY_STEMS,
    STEM_ELEMENTS,
    check_branch_combination,
    check_branch_conflict,
    get_nayin,
    get_shishen,
)
from .almanac import (
    BAZI_MONTH_START_TERMS,
    DEFAULT_TIMEZONE,
    elapsed_days_between,
    get_bazi_month_boundaries,
    get_bazi_month_context,
    get_bazi_year,
    get_solar_term_environment_key,
    get_solar_terms_for_year,
    localize_datetime,
    require_calculated_solar_term,
)
from .calendar import BaZiCalendar, resolve_bazi_effective_date


def _copy_timing_info(info: Dict) -> Dict:
    """Detach the cached scalar payload and all nested solar-term metadata.

    The window contains model dictionaries and lists below its term records.
    Copy the entire window so caller edits cannot corrupt subsequent hits.
    The remaining cache-owned fields are immutable scalars.
    """
    result = info.copy()
    if "solar_term_window" in info:
        result["solar_term_window"] = deepcopy(info["solar_term_window"])
    return result


@lru_cache(maxsize=2048)
def _calculate_liuyue_cached(
    target_year: int,
    target_month: int,
    target_day: int,
    timezone_name: str,
    target_date: Optional[datetime],
    _solar_environment: Tuple[Any, ...] = (),
) -> Dict:
    """Cache deterministic liuyue calculations for repeated timing analysis."""
    effective_target_date = target_date or datetime(
        target_year, target_month, target_day
    )
    local_target_date = localize_datetime(effective_target_date, timezone_name)
    bazi_year = get_bazi_year(local_target_date, timezone_name)
    month_context = get_bazi_month_context(local_target_date, timezone_name)
    liuyue_stem, liuyue_branch = BaZiCalendar.calculate_month_pillar_by_branch(
        bazi_year,
        str(month_context["branch"]),
    )
    stem_element, stem_polarity = STEM_ELEMENTS[liuyue_stem]

    return {
        "year": target_year,
        "month": target_month,
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
    target_hour_dt: datetime,
    timezone_name: str,
) -> Dict:
    """Cache deterministic liushi calculations. target_hour_dt must be truncated to the hour."""
    local_dt = localize_datetime(target_hour_dt, timezone_name)
    liushi_stem, liushi_branch = BaZiCalendar.calculate_hour_pillar(
        local_dt.year,
        local_dt.month,
        local_dt.day,
        local_dt.hour,
    )
    stem_element, stem_polarity = STEM_ELEMENTS[liushi_stem]

    return {
        "year": local_dt.year,
        "month": local_dt.month,
        "day": local_dt.day,
        "hour": local_dt.hour,
        "analysis_datetime": local_dt.strftime("%Y-%m-%d %H:%M:%S"),
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
    target_date: datetime,
    timezone_name: str,
    _solar_environment: Tuple[Any, ...] = (),
) -> Dict:
    """Cache deterministic liuri calculations for repeated timeline analysis.

    BaZi day pillars roll over at 23:00 (晚子时/夜子时) - times at or after
    23:00 belong to the NEXT day's pillar. We pass ``hour=`` to
    ``calculate_day_pillar`` so the rollover is handled atomically with the
    pillar calculation and cannot be forgotten again.
    """
    local_target_date = localize_datetime(target_date, timezone_name)
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
        # Civil year/month/day so callers can locate the sample on their own
        # calendar timeline. The pillar above is computed on the BaZi-effective
        # date per the 晚子时 rollover rule, handled by calculate_day_pillar.
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
        # Weekday stays on the civil calendar - 23:30 is still "today"
        # for the wall-clock user, even though the BaZi day pillar has
        # advanced.
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
    """
    时运分析工具类，负责计算和分析八字中的时间运势变化

    该类提供了完整的时运分析功能，包括：
    - 大运计算：10年一个周期的长期运势变化
    - 流年计算：每年的运势影响和变化
    - 流月计算：每月的短期运势波动
    - 起运年龄：根据出生时间和性别计算开始行运的年龄
    - 运势组合：分析大运、流年、流月与原局的相互作用

    计算原理：
    - 大运：根据月柱和性别确定顺逆行方向
    - 流年：基于年份的天干地支循环
    - 流月：基于月份的天干地支组合
    - 起运：考虑性别、年干阴阳和节气因素

    注意事项：
    - 男命阳年、女命阴年为顺行大运
    - 男命阴年、女命阳年为逆行大运
    - 起运年龄通常在1-10岁之间
    """

    @staticmethod
    def calculate_dayun_start_details(
        birth_date: datetime,
        gender: Optional[str],
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> Dict:
        """
        计算起运细节，按节令边界而不是固定月中日。

        Returns:
            包含顺逆行方向、参考节令和精确起运岁数的字典
        """
        local_birth_date = localize_datetime(birth_date, timezone_name)
        bazi_year = get_bazi_year(local_birth_date, timezone_name)
        year_stem, _ = BaZiCalendar.calculate_year_pillar(bazi_year)
        is_yang_year = HEAVENLY_STEMS.index(year_stem) % 2 == 0

        canonical_gender = normalize_gender(gender)
        if canonical_gender not in ("男", "女"):
            raise ValueError(
                "大运方向需要明确性别（男/女）；请提供 gender，或显式传入 dayun_pillar。"
            )
        if (canonical_gender == "男" and is_yang_year) or (
            canonical_gender == "女" and not is_yang_year
        ):
            forward_direction = True
        else:
            forward_direction = False

        start_term, next_term, _, _ = get_bazi_month_boundaries(
            local_birth_date, timezone_name
        )
        target_term = next_term if forward_direction else start_term
        delta_days = abs(elapsed_days_between(local_birth_date, target_term.moment))
        start_age_unrounded = delta_days / 3
        start_age_precise = round(start_age_unrounded, 2)

        return {
            "forward_direction": forward_direction,
            "year_stem": year_stem,
            "reference_term": target_term.as_dict(),
            "reference_term_resolution": target_term.resolution_provider,
            "days_to_boundary": round(delta_days, 4),
            "start_age_precise": start_age_precise,
            "start_age_unrounded": start_age_unrounded,
            # Integer display policy; the actual timeline uses the raw age.
            # Two-decimal rounding first can erase a crossed integer age.
            "start_age_rounded": max(1, math.ceil(start_age_unrounded)),
            "elapsed_seconds": delta_days * 86400,
            "elapsed_scale": "nominal_utc_label_seconds",
            "leap_second_policy": "not_counted",
        }

    @staticmethod
    def _dayun_calendar_wall_context(
        birth_date: datetime,
        gender: Optional[str],
        timezone_name: str,
    ) -> Tuple[datetime, Dict, datetime, Dict[str, int]]:
        """Keep the existing wall-start arithmetic shared with event inverses."""
        birth = localize_datetime(birth_date, timezone_name)
        details = TimingAnalysis.calculate_dayun_start_details(
            birth, gender, timezone_name
        )
        nominal_us = round(details["elapsed_seconds"] * 120 * 1_000_000)
        day_us = 86400 * 1_000_000
        years, remainder = divmod(nominal_us, 360 * day_us)
        months, remainder = divmod(remainder, 30 * day_us)
        days, remainder = divmod(remainder, day_us)
        wall_birth = birth.replace(tzinfo=None)
        start_wall = wall_birth + relativedelta(
            years=years, months=months, days=days, microseconds=remainder
        )
        offset = {
            "years": years,
            "months": months,
            "days": days,
            "microseconds": remainder,
        }
        return birth, details, start_wall, offset

    @staticmethod
    def _dayun_wall_year_preimages(
        boundary_wall: datetime, year_offset: int
    ) -> Tuple[datetime, ...]:
        """Invert decade year addition, retaining both leap-day preimages."""
        if boundary_wall.tzinfo is not None:
            raise ValueError("大运年份逆像需要未附民用时区的钟面标签")
        year = boundary_wall.year - year_offset
        if not 1 <= year <= 9999:
            return ()
        try:
            targets = [boundary_wall.replace(year=year)]
        except ValueError:
            return ()
        if (
            boundary_wall.month == 2
            and boundary_wall.day == 28
            and not isleap(boundary_wall.year)
            and isleap(year)
        ):
            targets.append(boundary_wall.replace(year=year, day=29))
        return tuple(targets)

    @staticmethod
    def calculate_dayun_timeline(
        birth_date: datetime,
        gender: Optional[str],
        month_pillar: tuple[str, str],
        timezone_name: str = DEFAULT_TIMEZONE,
        periods: int = DEFAULT_DAYUN_PERIODS,
    ) -> Dict:
        """Calendar boundaries under an explicit three-days/one-year policy.

        The traditional 360-day conversion gives years/months/days, which are
        added to the civil birth clock in one calendar operation. It is neither
        a fixed tropical-year duration nor an integer-birthday selector.
        """
        # One nominal UTC-label birth-to-jie second becomes 120 offset seconds.
        # Leap seconds are excluded by the disclosed elapsed-time policy.
        # Keep all precision until the final microsecond representation.
        birth, details, start_wall, calendar_offset = (
            TimingAnalysis._dayun_calendar_wall_context(
                birth_date, gender, timezone_name
            )
        )
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
        for index, item in enumerate(sequence):
            item["start_at"] = (
                initial_boundary if index == 0 else civil_boundary(index * 10)
            ).isoformat()
            item["end_at"] = civil_boundary((index + 1) * 10).isoformat()
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
    def _resolve_dayun_calendar_boundary(
        birth: datetime, start_wall: datetime, year_offset: int, timezone_name: str
    ) -> Tuple[datetime, bool]:
        """Shared existing year-clipping/fold policy for timelines and inverses."""
        wall = start_wall + relativedelta(years=year_offset)
        local = localize_datetime(wall, timezone_name).replace(fold=0)
        resolved = cast(
            datetime,
            resolve_imaginary(local).astimezone(timezone.utc).astimezone(birth.tzinfo),
        )
        if year_offset == 0 and resolved.astimezone(timezone.utc) < birth.astimezone(
            timezone.utc
        ):
            later = wall.replace(tzinfo=birth.tzinfo, fold=1)
            instant = later.astimezone(timezone.utc)
            roundtrip = instant.astimezone(birth.tzinfo)
            if roundtrip.replace(tzinfo=None) == wall and instant >= birth.astimezone(
                timezone.utc
            ):
                return cast(datetime, roundtrip), True
            raise ValueError("首运边界不能早于已确认的出生时刻")
        return resolved, False

    @staticmethod
    def calculate_dayun_sequence(
        month_pillar_stem: str,
        month_pillar_branch: str,
        gender: Optional[str],
        year_stem: str,
        periods: int = 8,
        start_age: float = 1.0,
    ) -> List[Dict]:
        """
        计算大运序列

        Args:
            month_pillar_stem: 月柱天干
            month_pillar_branch: 月柱地支
            gender: 性别
            periods: 计算的大运期数，默认8期（80年）
            year_stem: 八字年干，用于判定顺逆

        Returns:
            大运序列列表
        """
        # 判断大运方向
        is_yang_year = HEAVENLY_STEMS.index(year_stem) % 2 == 0

        canonical_gender = normalize_gender(gender)
        if canonical_gender not in ("男", "女"):
            raise ValueError(
                "大运方向需要明确性别（男/女）；请提供 gender，或显式传入 dayun_pillar。"
            )
        if (canonical_gender == "男" and is_yang_year) or (
            canonical_gender == "女" and not is_yang_year
        ):
            direction = 1  # 顺行
        else:
            direction = -1  # 逆行

        # 获取月柱干支的索引
        month_stem_index = HEAVENLY_STEMS.index(month_pillar_stem)
        month_branch_index = EARTHLY_BRANCHES.index(month_pillar_branch)

        dayun_sequence = []

        for period_index in range(periods):
            # 计算当前大运的干支索引
            current_stem_index = (
                month_stem_index + direction * (period_index + 1)
            ) % 10
            current_branch_index = (
                month_branch_index + direction * (period_index + 1)
            ) % 12

            dayun_stem = HEAVENLY_STEMS[current_stem_index]
            dayun_branch = EARTHLY_BRANCHES[current_branch_index]

            dayun_info = {
                "period": period_index + 1,
                "stem": dayun_stem,
                "branch": dayun_branch,
                "pillar": f"{dayun_stem}{dayun_branch}",
                "age_range": {
                    "start": round(start_age + period_index * 10, 2),
                    "end": round(start_age + (period_index + 1) * 10, 2),
                },
            }

            dayun_sequence.append(dayun_info)

        return dayun_sequence

    @staticmethod
    def calculate_liunian(
        target_year: int,
        *,
        moment: Optional[datetime] = None,
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> Dict:
        """
        计算指定年份的流年干支。

        Args:
            target_year: 目标年份（公历 / civil year）。当同时提供 ``moment`` 时，
                该参数只作为 fallback；``moment`` 所在的立春 BaZi 年优先。
            moment: 可选的具体日期-时间。若给出，该方法会用 ``get_bazi_year``
                以立春为分界解析真正的 BaZi 年，从而避免 1 月 / 早 2 月的流年
                误差。生产调用强烈建议传入 ``moment``。
            timezone_name: ``moment`` 的时区，默认为模块 ``DEFAULT_TIMEZONE``。

        Returns:
            流年信息 dict，包含 `year`（解析后的 BaZi 年，可能与 `target_year`
            不同）、`stem`、`branch`、`pillar`、`element`。
        """
        if moment is not None:
            resolved_year = get_bazi_year(moment, timezone_name)
        else:
            resolved_year = target_year

        # 计算年干支（以甲子年为基准：1984年）
        base_year = 1984  # 甲子年
        year_offset = resolved_year - base_year

        stem_index = year_offset % 10
        branch_index = year_offset % 12

        liunian_stem = HEAVENLY_STEMS[stem_index]
        liunian_branch = EARTHLY_BRANCHES[branch_index]

        # 获取天干五行
        stem_element, stem_polarity = STEM_ELEMENTS[liunian_stem]

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
        target_date: Optional[datetime] = None,
    ) -> Dict:
        """
        按节气月令计算指定时点的流月干支

        Args:
            target_year: 目标年份
            target_month: 目标月份 (1-12)
            target_day: 目标日期，默认 1
            timezone_name: 时区
            target_date: 完整的分析时刻；提供时优先使用

        Returns:
            流月信息
        """
        return _copy_timing_info(
            _calculate_liuyue_cached(
                target_year,
                target_month,
                target_day,
                timezone_name,
                (
                    target_date.astimezone(timezone.utc)
                    if target_date is not None and target_date.utcoffset() is not None
                    else target_date
                ),
                get_solar_term_environment_key(
                    year=localize_datetime(
                        target_date or datetime(target_year, target_month, target_day),
                        timezone_name,
                    ).year
                ),
            )
        )

    @staticmethod
    def _next_supported_analysis_anchor(
        moment: datetime,
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> datetime:
        """
        将节气切换点规范到外部接口可复现的最早分钟锚点。

        FastMCP / REST 当前只暴露到小时、分钟精度，因此时间轴里的
        analysis_anchor 需要落在节气后最早可接受的无歧义整分钟。
        重复区间不能用现有分钟字段和IANA名称区分fold，跳过重复或不存在
        的钟时，避免给出无法回放的锚点。锚点不是节气本身的天文时刻。
        """
        local_moment = localize_datetime(moment, timezone_name)
        anchor = local_moment.replace(second=0, microsecond=0) + timedelta(minutes=1)
        instant = local_moment.astimezone(timezone.utc)
        while True:
            try:
                validate_local_clock(anchor)
            except ValueError:
                anchor += timedelta(minutes=1)
                continue
            if anchor.astimezone(timezone.utc) > instant:
                return anchor
            anchor += timedelta(minutes=1)

    @staticmethod
    def calculate_liuyue_timeline(
        target_year: int,
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> List[Dict]:
        """
        生成目标年份的 12 个节令月时间轴。
        """
        current_year_terms = [
            term
            for term in get_solar_terms_for_year(target_year, timezone_name)
            if term.name in BAZI_MONTH_START_TERMS
        ]
        next_year_terms = [
            term
            for term in get_solar_terms_for_year(target_year + 1, timezone_name)
            if term.name in BAZI_MONTH_START_TERMS
        ]

        timeline: List[Dict] = []

        for index, start_term in enumerate(current_year_terms):
            next_term = (
                current_year_terms[index + 1]
                if index + 1 < len(current_year_terms)
                else next_year_terms[0]
            )
            require_calculated_solar_term(start_term)
            require_calculated_solar_term(next_term)
            anchor = TimingAnalysis._next_supported_analysis_anchor(
                start_term.moment,
                timezone_name=timezone_name,
            )
            liuyue_info = TimingAnalysis.calculate_liuyue(
                anchor.year,
                anchor.month,
                anchor.day,
                timezone_name=timezone_name,
                target_date=anchor,
            )
            timeline.append(
                {
                    "order": index + 1,
                    "analysis_anchor": anchor.strftime("%Y-%m-%d %H:%M:%S"),
                    "gregorian_window": {
                        "start": start_term.moment.replace(tzinfo=None).isoformat(
                            sep=" "
                        ),
                        "end": next_term.moment.replace(tzinfo=None).isoformat(sep=" "),
                        "days": round(
                            elapsed_days_between(start_term.moment, next_term.moment),
                            4,
                        ),
                    },
                    "start_term": start_term.as_dict(),
                    "next_term": next_term.as_dict(),
                    "liuyue": liuyue_info,
                }
            )

        return timeline

    @staticmethod
    def calculate_liuri(
        target_date: datetime,
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> Dict:
        """
        计算指定时点的流日干支。
        """
        return _copy_timing_info(
            _calculate_liuri_cached(
                (
                    target_date.astimezone(timezone.utc)
                    if target_date.utcoffset() is not None
                    else target_date
                ),
                timezone_name,
                get_solar_term_environment_key(
                    year=localize_datetime(target_date, timezone_name).year
                ),
            )
        )

    @staticmethod
    def calculate_liushi(
        target_datetime: datetime,
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> Dict:
        """
        计算指定时刻的流时干支。

        target_datetime 会被截断到小时粒度以命中缓存；
        分钟/秒级偏差不影响时柱归属。
        """
        # Truncate the target's local wall clock. Truncating a UTC (or other
        # source-zone) input first shifts the hour in fractional-offset zones,
        # potentially crossing a shichen or the 23:00 day-pillar boundary.
        local_dt = localize_datetime(target_datetime, timezone_name)
        hour_dt = local_dt.replace(minute=0, second=0, microsecond=0)
        return _copy_timing_info(_calculate_liushi_cached(hour_dt, timezone_name))

    @staticmethod
    def analyze_liushi_detailed(
        birth_pillars: Dict,
        target_datetime: datetime,
        day_stem: Optional[str] = None,
        timezone_name: str = DEFAULT_TIMEZONE,
        liushi_info: Optional[Dict] = None,
    ) -> Dict:
        """
        流时详细分析，包括十神关系、冲合与时级建议。
        """
        if liushi_info is None:
            liushi_info = TimingAnalysis.calculate_liushi(
                target_datetime, timezone_name=timezone_name
            )

        if day_stem is None:
            day_stem = birth_pillars["day"][0]

        stem_shishen = get_shishen(day_stem, liushi_info["stem"])
        branch_relations = TimingAnalysis._collect_branch_relations(
            liushi_info["branch"], birth_pillars, "流时"
        )
        fortune_analysis = TimingAnalysis._analyze_liuyue_fortune(
            stem_shishen, branch_relations, liushi_info, scope_label="本时"
        )
        suggestions = TimingAnalysis._generate_liuyue_suggestions(
            stem_shishen, branch_relations, fortune_analysis, scope_label="本时"
        )

        return {
            "basic_info": liushi_info,
            "shishen_analysis": {
                "stem_relation": stem_shishen,
                "description": f"流时天干{liushi_info['stem']}对日主{day_stem}为{stem_shishen}",
            },
            "branch_relations": branch_relations,
            "fortune_analysis": fortune_analysis,
            "suggestions": suggestions,
            "overall_summary": TimingAnalysis._generate_liushi_summary(
                liushi_info, stem_shishen, branch_relations, fortune_analysis
            ),
        }

    @staticmethod
    def _generate_liushi_summary(
        liushi_info: Dict,
        stem_shishen: str,
        branch_relations: List[Dict],
        fortune_analysis: Dict,
    ) -> str:
        """生成流时分析总结。"""
        dt_label = (
            f"{liushi_info['year']}年{liushi_info['month']}月"
            f"{liushi_info['day']}日{liushi_info['hour']}时"
        )
        pillar = liushi_info["pillar"]
        nayin = liushi_info["nayin"]
        overall_fortune = fortune_analysis["overall_fortune"]

        summary_parts = [
            f"{dt_label}流时{pillar}({nayin})",
            f"十神{stem_shishen}",
            f"总体运势{overall_fortune}",
        ]

        if branch_relations:
            relation_desc = "、".join([r["type"] for r in branch_relations])
            summary_parts.append(f"有{relation_desc}关系")

        return "，".join(summary_parts) + "。"

    @staticmethod
    def calculate_jieqi_transition_timeline(
        target_year: int,
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> List[Dict]:
        """
        生成目标年份 24 节气切换节点的时运时间轴。
        """
        timeline: List[Dict] = []
        for index, term in enumerate(
            get_solar_terms_for_year(target_year, timezone_name)
        ):
            require_calculated_solar_term(term)
            anchor = TimingAnalysis._next_supported_analysis_anchor(
                term.moment,
                timezone_name=timezone_name,
            )
            timeline.append(
                {
                    "order": index + 1,
                    "jieqi": term.as_dict(),
                    "analysis_anchor": anchor.strftime("%Y-%m-%d %H:%M:%S"),
                    "liuyue": TimingAnalysis.calculate_liuyue(
                        anchor.year,
                        anchor.month,
                        anchor.day,
                        timezone_name=timezone_name,
                        target_date=anchor,
                    ),
                    "liuri": TimingAnalysis.calculate_liuri(
                        anchor, timezone_name=timezone_name
                    ),
                }
            )
        return timeline

    @staticmethod
    def _collect_branch_relations(
        target_branch: str,
        birth_pillars: Dict,
        label: str,
    ) -> List[Dict]:
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

            if check_branch_combination(target_branch, pillar_branch):
                branch_relations.append(
                    {
                        "type": "六合",
                        "with_pillar": pillar_name,
                        "with_branch": pillar_branch,
                        "description": f"{label}{target_branch}与{pillar_name}柱{pillar_branch}六合",
                    }
                )

        return branch_relations

    @staticmethod
    def analyze_liuyue_detailed(
        birth_pillars: Dict,
        target_year: int,
        target_month: int,
        day_stem: Optional[str] = None,
        target_day: int = 1,
        timezone_name: str = DEFAULT_TIMEZONE,
        target_date: Optional[datetime] = None,
        liuyue_info: Optional[Dict] = None,
    ) -> Dict:
        """
        流月的详细分析，包括十神关系、吉凶判断等

        Args:
            birth_pillars: 出生四柱
            target_year: 目标年份
            target_month: 目标月份
            day_stem: 日主天干，如果未提供则从birth_pillars中获取

        Returns:
            流月详细分析结果
        """
        # 获取基础流月信息
        if liuyue_info is None:
            liuyue_info = TimingAnalysis.calculate_liuyue(
                target_year,
                target_month,
                target_day=target_day,
                timezone_name=timezone_name,
                target_date=target_date,
            )

        # 获取日主
        if day_stem is None:
            day_stem = birth_pillars["day"][0]

        # 分析流月天干与日主的十神关系
        stem_shishen = get_shishen(day_stem, liuyue_info["stem"])

        # 分析流月与命局的冲合关系
        branch_relations = TimingAnalysis._collect_branch_relations(
            liuyue_info["branch"], birth_pillars, "流月"
        )

        # 分析吉凶趋势
        fortune_analysis = TimingAnalysis._analyze_liuyue_fortune(
            stem_shishen, branch_relations, liuyue_info, scope_label="本月"
        )

        # 生成运势建议
        suggestions = TimingAnalysis._generate_liuyue_suggestions(
            stem_shishen, branch_relations, fortune_analysis, scope_label="本月"
        )

        return {
            "basic_info": liuyue_info,
            "shishen_analysis": {
                "stem_relation": stem_shishen,
                "description": f"流月天干{liuyue_info['stem']}对日主{day_stem}为{stem_shishen}",
            },
            "branch_relations": branch_relations,
            "fortune_analysis": fortune_analysis,
            "suggestions": suggestions,
            "overall_summary": TimingAnalysis._generate_liuyue_summary(
                liuyue_info, stem_shishen, branch_relations, fortune_analysis
            ),
        }

    @staticmethod
    def analyze_liuri_detailed(
        birth_pillars: Dict,
        target_date: datetime,
        day_stem: Optional[str] = None,
        timezone_name: str = DEFAULT_TIMEZONE,
        liuri_info: Optional[Dict] = None,
    ) -> Dict:
        """
        流日详细分析，包括十神关系、冲合与日级建议。
        """
        if liuri_info is None:
            liuri_info = TimingAnalysis.calculate_liuri(
                target_date, timezone_name=timezone_name
            )

        if day_stem is None:
            day_stem = birth_pillars["day"][0]

        stem_shishen = get_shishen(day_stem, liuri_info["stem"])
        branch_relations = TimingAnalysis._collect_branch_relations(
            liuri_info["branch"], birth_pillars, "流日"
        )
        fortune_analysis = TimingAnalysis._analyze_liuyue_fortune(
            stem_shishen, branch_relations, liuri_info, scope_label="本日"
        )
        suggestions = TimingAnalysis._generate_liuyue_suggestions(
            stem_shishen, branch_relations, fortune_analysis, scope_label="本日"
        )

        return {
            "basic_info": liuri_info,
            "shishen_analysis": {
                "stem_relation": stem_shishen,
                "description": f"流日天干{liuri_info['stem']}对日主{day_stem}为{stem_shishen}",
            },
            "branch_relations": branch_relations,
            "fortune_analysis": fortune_analysis,
            "suggestions": suggestions,
            "overall_summary": TimingAnalysis._generate_liuri_summary(
                liuri_info, stem_shishen, branch_relations, fortune_analysis
            ),
        }

    @staticmethod
    def _analyze_liuyue_fortune(
        stem_shishen: str,
        branch_relations: List[Dict],
        liuyue_info: Dict,
        scope_label: str = "本阶段",
    ) -> Dict:
        """
        分析流月的吉凶趋势

        Args:
            stem_shishen: 天干十神关系
            branch_relations: 地支关系列表
            liuyue_info: 流月基础信息

        Returns:
            吉凶分析结果
        """
        # A ten-god name or a combine/clash table hit alone cannot establish
        # favourability. Preserve the old keys with an explicit null score.
        return {
            "method_id": "context_required_no_fortune_score_v1",
            "assessment_status": "context_required",
            "fortune_score": None,
            "fortune_factors": [f"天干十神：{stem_shishen}"]
            + [relation["description"] for relation in branch_relations],
            "overall_fortune": "未判定",
            "nayin_description": f"纳音{liuyue_info['nayin']}仅作传统分类，不参与吉凶判断",
            "detailed_analysis": f"{scope_label}关系已列出；未完成原局喜忌与制化核验，不作吉凶定级",
            "required_context": [
                "原局用神与相神",
                "旺衰及根气",
                "会合能否成立及制化救应",
            ],
        }

    @staticmethod
    def _generate_liuyue_suggestions(
        stem_shishen: str,
        branch_relations: List[Dict],
        fortune_analysis: Dict,
        scope_label: str = "本阶段",
    ) -> List[str]:
        """Return a reading aid rather than advice inferred from a bare label."""
        suggestions = [
            f"{scope_label}十神{stem_shishen}是关系分类，需结合原局判断其作用。"
        ]
        if any(r["type"] == "六冲" for r in branch_relations):
            suggestions.append("六冲须辨所冲位置及喜忌，不能直接据此否定行动。")
        if any(r["type"] == "六合" for r in branch_relations):
            suggestions.append("六合只确认配对，尚未证明合化、助益或现实合作顺利。")
        return suggestions

    @staticmethod
    def _generate_liuyue_summary(
        liuyue_info: Dict,
        stem_shishen: str,
        branch_relations: List[Dict],
        fortune_analysis: Dict,
    ) -> str:
        """
        生成流月分析总结

        Args:
            liuyue_info: 流月基础信息
            stem_shishen: 十神关系
            branch_relations: 地支关系
            fortune_analysis: 吉凶分析

        Returns:
            分析总结
        """
        year_month = f"{liuyue_info['year']}年{liuyue_info['month']}月"
        pillar = liuyue_info["pillar"]
        nayin = liuyue_info["nayin"]
        overall_fortune = fortune_analysis["overall_fortune"]

        summary_parts = [
            f"{year_month}流月{pillar}({nayin})",
            f"十神{stem_shishen}",
            f"总体运势{overall_fortune}",
        ]

        if branch_relations:
            relation_desc = "、".join([r["type"] for r in branch_relations])
            summary_parts.append(f"有{relation_desc}关系")

        return "，".join(summary_parts) + "。"

    @staticmethod
    def _generate_liuri_summary(
        liuri_info: Dict,
        stem_shishen: str,
        branch_relations: List[Dict],
        fortune_analysis: Dict,
    ) -> str:
        """生成流日分析总结。"""
        year_month_day = (
            f"{liuri_info['year']}年{liuri_info['month']}月{liuri_info['day']}日"
        )
        pillar = liuri_info["pillar"]
        nayin = liuri_info["nayin"]
        overall_fortune = fortune_analysis["overall_fortune"]

        summary_parts = [
            f"{year_month_day}流日{pillar}({nayin})",
            f"十神{stem_shishen}",
            f"总体运势{overall_fortune}",
        ]

        if branch_relations:
            relation_desc = "、".join([r["type"] for r in branch_relations])
            summary_parts.append(f"有{relation_desc}关系")

        return "，".join(summary_parts) + "。"
