"""
Calendar conversion utilities for BaZi calculations.
Converts Gregorian dates to Chinese sexagenary cycle (干支).
"""

from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Dict, Optional, Tuple

from ..utils.data import (
    EARTHLY_BRANCHES,
    HEAVENLY_STEMS,
    get_hour_branch,
)
from .almanac import (
    DAY_GANZHI_STRATEGY_STANDARD,
    DEFAULT_TIMEZONE,
    get_bazi_month_context,
    get_bazi_year,
    get_day_ganzhi,
    localize_datetime,
)

LATE_ZI_HOUR = 23  # 23:00-23:59 属 late 子时 / 晚子时, 日柱翻至次日


def resolve_bazi_effective_date(
    year: int, month: int, day: int, hour: int
) -> Tuple[int, int, int]:
    """根据晚子时 (夜子时) 规则把 23:00-23:59 的 BaZi 日柱向次日翻转。

    传入参数是一个公历 civil 日期 + 时辰小时（0-23）。返回用于 BaZi 日/时柱
    计算的有效公历日期。对于 0-22 时，返回值就是原日期；对于 23 时，返回值是
    原日期 + 1 天。该函数不处理月/年跨界特殊情况，依赖 datetime.date
    的日期算术正确跨月跨年。
    """
    if hour >= LATE_ZI_HOUR:
        shifted = date(year, month, day) + timedelta(days=1)
        return shifted.year, shifted.month, shifted.day
    return year, month, day


class BaZiCalendar:
    """
    八字历法转换工具类，负责将公历日期转换为中国传统干支历法

    该类提供了完整的四柱（年月日时）计算功能，包括：
    - 年柱计算：基于六十甲子循环
    - 月柱计算：根据年干和月份确定月干支
    - 日柱计算：基于基准日期的偏移量计算
    - 时柱计算：根据日干和时辰确定时干支

    基准参考点：
    - 基准年份：1984年（甲子年）
    - 基准日期：1984-03-31（甲子日）

    Attributes:
        BASE_YEAR (int): 基准年份，用于年柱计算
    """

    # Base reference point: 甲子年甲子月甲子日甲子时
    # Using 1984-02-02 as base year (甲子年)
    BASE_YEAR = 1984

    @staticmethod
    def get_stem_branch_index(base_index: int, offset: int, cycle_length: int) -> int:
        """Calculate index in stem-branch cycle."""
        return (base_index + offset) % cycle_length

    @classmethod
    def calculate_year_pillar(cls, year: int) -> Tuple[str, str]:
        """Calculate the year pillar (年柱) for a given year."""
        # Calculate offset from base year
        year_offset = year - cls.BASE_YEAR

        # Calculate indices
        stem_index = cls.get_stem_branch_index(0, year_offset, 10)  # 甲 is index 0
        branch_index = cls.get_stem_branch_index(0, year_offset, 12)  # 子 is index 0

        return HEAVENLY_STEMS[stem_index], EARTHLY_BRANCHES[branch_index]

    @classmethod
    def calculate_month_pillar_by_branch(
        cls, year: int, month_branch: str
    ) -> Tuple[str, str]:
        """Calculate the month pillar using a resolved BaZi month branch."""
        month_index = [
            "寅",
            "卯",
            "辰",
            "巳",
            "午",
            "未",
            "申",
            "酉",
            "戌",
            "亥",
            "子",
            "丑",
        ].index(month_branch)

        # Calculate heavenly stem based on year stem
        year_stem, _ = cls.calculate_year_pillar(year)
        year_stem_index = HEAVENLY_STEMS.index(year_stem)

        # Month stem calculation based on year stem
        # 甲己年丙作首，乙庚年戊为头，丙辛年庚上起，丁壬年壬位流，戊癸年甲好求
        month_stem_base_mapping = {
            0: 2,  # 甲年 -> 丙寅月开始 (丙 is index 2)
            5: 2,  # 己年 -> 丙寅月开始
            1: 4,  # 乙年 -> 戊寅月开始 (戊 is index 4)
            6: 4,  # 庚年 -> 戊寅月开始
            2: 6,  # 丙年 -> 庚寅月开始 (庚 is index 6)
            7: 6,  # 辛年 -> 庚寅月开始
            3: 8,  # 丁年 -> 壬寅月开始 (壬 is index 8)
            8: 8,  # 壬年 -> 壬寅月开始
            4: 0,  # 戊年 -> 甲寅月开始 (甲 is index 0)
            9: 0,  # 癸年 -> 甲寅月开始
        }

        base_stem_index = month_stem_base_mapping[year_stem_index]

        month_stem_index = (base_stem_index + month_index) % 10
        month_stem = HEAVENLY_STEMS[month_stem_index]

        return month_stem, month_branch

    @classmethod
    def calculate_day_pillar(
        cls,
        year: int,
        month: int,
        day: int,
        *,
        hour: Optional[int] = None,
        apply_late_zi_rollover: bool = True,
        strategy: str = DAY_GANZHI_STRATEGY_STANDARD,
    ) -> Tuple[str, str]:
        """Calculate the day pillar (日柱) for a given date.

        When ``hour`` is provided and ``apply_late_zi_rollover`` is True
        (default), times at 23:00-23:59 automatically roll to the next day's
        pillar per the 晚子时/夜子时 rule. Callers that only have a civil
        date (no hour context) can omit ``hour`` to get the original date's
        pillar with no rollover applied — this preserves the pre-rollover
        signature so existing callers who already did their own
        ``resolve_bazi_effective_date`` need no changes.

        Prefer passing ``hour`` when you have it: this keeps the rollover
        invariant encapsulated here rather than scattered across callers,
        which is what allowed _calculate_liuri_cached to silently skip it
        for months.
        """
        if hour is not None and apply_late_zi_rollover:
            year, month, day = resolve_bazi_effective_date(year, month, day, hour)
        day_ganzhi = get_day_ganzhi(year, month, day, strategy=strategy)
        return day_ganzhi[0], day_ganzhi[1]

    @classmethod
    def calculate_hour_pillar(
        cls,
        year: int,
        month: int,
        day: int,
        hour: int,
        *,
        day_pillar_strategy: str = DAY_GANZHI_STRATEGY_STANDARD,
        apply_late_zi_rollover: bool = True,
    ) -> Tuple[str, str]:
        """Calculate the hour pillar (时柱) for a given datetime.

        当 ``apply_late_zi_rollover`` 为 True (默认) 且 ``hour`` 为 23 时，
        时柱所依赖的日柱会翻至次日（晚子时/夜子时 翻日规则）。
        该默认与 ``get_four_pillars`` 保持一致；如果调用方自行维护了
        翻日逻辑，可显式传入 ``apply_late_zi_rollover=False``。
        """
        # Get the earthly branch for the hour
        hour_branch = get_hour_branch(hour)

        effective_year, effective_month, effective_day = (
            resolve_bazi_effective_date(year, month, day, hour)
            if apply_late_zi_rollover
            else (year, month, day)
        )

        # Calculate heavenly stem based on day stem
        day_stem, _ = cls.calculate_day_pillar(
            effective_year,
            effective_month,
            effective_day,
            strategy=day_pillar_strategy,
        )
        day_stem_index = HEAVENLY_STEMS.index(day_stem)

        # Hour stem calculation based on day stem
        # 甲己还加甲，乙庚丙作初，丙辛从戊起，丁壬庚子居，戊癸何方发，壬子是真途
        hour_stem_base_mapping = {
            0: 0,  # 甲日 -> 甲子时开始
            5: 0,  # 己日 -> 甲子时开始
            1: 2,  # 乙日 -> 丙子时开始
            6: 2,  # 庚日 -> 丙子时开始
            2: 4,  # 丙日 -> 戊子时开始
            7: 4,  # 辛日 -> 戊子时开始
            3: 6,  # 丁日 -> 庚子时开始
            8: 6,  # 壬日 -> 庚子时开始
            4: 8,  # 戊日 -> 壬子时开始
            9: 8,  # 癸日 -> 壬子时开始
        }

        base_stem_index = hour_stem_base_mapping[day_stem_index]

        # Get hour branch index to calculate offset
        hour_branch_index = EARTHLY_BRANCHES.index(hour_branch)

        # Calculate hour stem
        hour_stem_index = (base_stem_index + hour_branch_index) % 10
        hour_stem = HEAVENLY_STEMS[hour_stem_index]

        return hour_stem, hour_branch

    @classmethod
    @lru_cache(maxsize=2048)
    def _get_four_pillars_cached(
        cls,
        local_birth_datetime: datetime,
        civil_datetime: datetime,
        timezone_name: str,
        day_pillar_strategy: str,
    ) -> Tuple[Tuple[str, str], Tuple[str, str], Tuple[str, str], Tuple[str, str]]:
        """Cache deterministic four-pillar derivation for repeated service calls."""
        year = local_birth_datetime.year
        month = local_birth_datetime.month
        day = local_birth_datetime.day
        hour = local_birth_datetime.hour

        bazi_year = get_bazi_year(civil_datetime, timezone_name)
        month_context = get_bazi_month_context(civil_datetime, timezone_name)
        month_branch = str(month_context["branch"])

        # 晚子时 (23:00-23:59) 的日柱翻到次日; 年柱 / 月柱 分别由 立春 / 节气
        # 决定，使用真实 civil_datetime，与修正后的日/时太阳钟分开。
        effective_year, effective_month, effective_day = resolve_bazi_effective_date(
            year, month, day, hour
        )

        return (
            cls.calculate_year_pillar(bazi_year),
            cls.calculate_month_pillar_by_branch(bazi_year, month_branch),
            cls.calculate_day_pillar(
                effective_year,
                effective_month,
                effective_day,
                strategy=day_pillar_strategy,
            ),
            cls.calculate_hour_pillar(
                year,
                month,
                day,
                hour,
                day_pillar_strategy=day_pillar_strategy,
            ),
        )

    @classmethod
    def get_four_pillars(
        cls,
        birth_datetime: datetime,
        timezone_name: str = DEFAULT_TIMEZONE,
        *,
        day_pillar_strategy: str = DAY_GANZHI_STRATEGY_STANDARD,
        civil_datetime: Optional[datetime] = None,
    ) -> Dict[str, Tuple[str, str]]:
        """
        Calculate all four pillars (四柱) for a given birth datetime.

        ``birth_datetime`` is the day/hour clock (possibly solar-corrected).
        Pass the original ``civil_datetime`` when corrected: year/month solar
        term boundaries are physical instants, not solar-clock readings.

        Returns:
            Dict with keys: 'year', 'month', 'day', 'hour'
            Each value is a tuple of (heavenly_stem, earthly_branch)
        """
        local_birth_datetime = localize_datetime(birth_datetime, timezone_name)
        year_pillar, month_pillar, day_pillar, hour_pillar = (
            cls._get_four_pillars_cached(
                local_birth_datetime,
                localize_datetime(civil_datetime or birth_datetime, timezone_name),
                timezone_name,
                day_pillar_strategy,
            )
        )
        return {
            "year": year_pillar,
            "month": month_pillar,
            "day": day_pillar,
            "hour": hour_pillar,
        }
