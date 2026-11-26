"""
Calendar conversion utilities for BaZi calculations.
Converts Gregorian dates to Chinese sexagenary cycle (干支).
"""

from datetime import datetime
from functools import lru_cache
from typing import Any

from ..utils.civil_time import (
    NominalClockLabel,
    ZonedCalendar,
    gregorian_date_parts,
    gregorian_ordinal,
)
from ..utils.data import (
    EARTHLY_BRANCHES,
    HEAVENLY_STEMS,
    get_hour_branch,
)
from .almanac import (
    DEFAULT_TIMEZONE,
    get_bazi_month_context,
    get_bazi_year,
    get_day_ganzhi,
    get_solar_term_environment_key,
    localize_datetime,
)

LATE_ZI_HOUR = 23  # 23:00-23:59 属 late 子时 / 晚子时, 日柱翻至次日


def resolve_bazi_effective_date(
    year: int, month: int, day: int, hour: int
) -> tuple[int, int, int]:
    """根据晚子时 (夜子时) 规则把 23:00-23:59 的 BaZi 日柱向次日翻转。

    传入参数是一个公历 civil 日期 + 时辰小时（0-23）。返回用于 BaZi 日/时柱
    计算的有效公历日期。对于 0-22 时，返回值就是原日期；对于 23 时，返回值是
    原日期 + 1 天。通过格里高利日序处理跨月跨年，末年晚子时仍可取得
    下一日的干支。
    """
    if hour >= LATE_ZI_HOUR:
        return gregorian_date_parts(gregorian_ordinal(year, month, day) + 1)
    return year, month, day


class BaZiCalendar:
    """Resolve solar-boundary year/month pillars and selected day/hour labels."""

    BASE_YEAR = 1984

    @classmethod
    def calculate_year_pillar(cls, year: int) -> tuple[str, str]:
        """Calculate the year pillar (年柱) for a given year."""
        year_offset = year - cls.BASE_YEAR

        stem_index = year_offset % len(HEAVENLY_STEMS)
        branch_index = year_offset % len(EARTHLY_BRANCHES)

        return HEAVENLY_STEMS[stem_index], EARTHLY_BRANCHES[branch_index]

    @classmethod
    def calculate_month_pillar_by_branch(
        cls, year: int, month_branch: str
    ) -> tuple[str, str]:
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

        year_stem, _ = cls.calculate_year_pillar(year)
        year_stem_index = HEAVENLY_STEMS.index(year_stem)

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
        hour: int | None = None,
        apply_late_zi_rollover: bool = True,
    ) -> tuple[str, str]:
        """Resolve the civil day, advancing at 23:00 when hour rollover is enabled.

        Omit hour or disable rollover when the supplied date is already effective.
        """
        if hour is not None and apply_late_zi_rollover:
            year, month, day = resolve_bazi_effective_date(year, month, day, hour)
        day_ganzhi = get_day_ganzhi(year, month, day)
        return day_ganzhi[0], day_ganzhi[1]

    @classmethod
    def calculate_hour_pillar(
        cls,
        year: int,
        month: int,
        day: int,
        hour: int,
        *,
        apply_late_zi_rollover: bool = True,
    ) -> tuple[str, str]:
        """Calculate the hour pillar (时柱) for a given datetime.

        当 apply_late_zi_rollover 为 True (默认) 且 hour 为 23 时，
        时柱所依赖的日柱会翻至次日（晚子时/夜子时 翻日规则）。
        该默认与 get_four_pillars 保持一致；如果调用方自行维护了
        翻日逻辑，可显式传入 apply_late_zi_rollover=False。
        """
        hour_branch = get_hour_branch(hour)

        effective_year, effective_month, effective_day = (
            resolve_bazi_effective_date(year, month, day, hour)
            if apply_late_zi_rollover
            else (year, month, day)
        )

        day_stem, _ = cls.calculate_day_pillar(
            effective_year,
            effective_month,
            effective_day,
        )
        day_stem_index = HEAVENLY_STEMS.index(day_stem)

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

        hour_branch_index = EARTHLY_BRANCHES.index(hour_branch)

        hour_stem_index = (base_stem_index + hour_branch_index) % 10
        hour_stem = HEAVENLY_STEMS[hour_stem_index]

        return hour_stem, hour_branch

    @classmethod
    @lru_cache(maxsize=2048)
    def _get_four_pillars_cached(
        cls,
        label: NominalClockLabel,
        civil_calendar: ZonedCalendar,
        timezone_name: str,
        _solar_environment: tuple[Any, ...] = (),
    ) -> tuple[tuple[str, str], tuple[str, str], tuple[str, str], tuple[str, str]]:
        """Cache a day/hour wall label plus a distinct physical civil instant.

        The label has no zone or physical epoch. The civil key retains fold
        through its exact UTC coordinate.
        """
        year, month, day = label.date_parts
        hour = label.time_parts[0]

        civil_datetime = civil_calendar.require_datetime()
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
            ),
            cls.calculate_hour_pillar(
                year,
                month,
                day,
                hour,
            ),
        )

    @classmethod
    def get_four_pillars(
        cls,
        birth_datetime: datetime | NominalClockLabel,
        timezone_name: str = DEFAULT_TIMEZONE,
        *,
        civil_datetime: datetime | None = None,
    ) -> dict[str, tuple[str, str]]:
        """
        Calculate all four pillars (四柱) for a given birth datetime.

        birth_datetime is the day/hour clock (possibly solar-corrected).
        Pass the original civil_datetime when corrected: year/month solar
        term boundaries are physical instants, not solar-clock readings.

        Returns:
            Dict with keys: 'year', 'month', 'day', 'hour'
            Each value is a tuple of (heavenly_stem, earthly_branch)
        """
        if isinstance(birth_datetime, datetime):
            label = NominalClockLabel.from_local_datetime(
                localize_datetime(birth_datetime, timezone_name)
            )
            civil_input = (
                civil_datetime if civil_datetime is not None else birth_datetime
            )
        else:
            label = birth_datetime
            if civil_datetime is None:
                raise ValueError("名义日时钟须另附真实民用时刻，不能反推年月交节")
            civil_input = civil_datetime
        civil = localize_datetime(civil_input, timezone_name)
        year_pillar, month_pillar, day_pillar, hour_pillar = (
            cls._get_four_pillars_cached(
                label,
                ZonedCalendar.from_datetime(civil),
                timezone_name,
                get_solar_term_environment_key(year=civil.year),
            )
        )
        return {
            "year": year_pillar,
            "month": month_pillar,
            "day": day_pillar,
            "hour": hour_pillar,
        }
