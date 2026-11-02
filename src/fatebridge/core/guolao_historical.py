"""Facsimile-collated historical Purple Qi table, without a modern epoch.

Gujin lvli kao 58, Wenyuan Siku scan 787-642/643, prints 虚 9.0064 du.
Its table therefore closes at 365.2564 du, unlike the Yuan Shi Shoushi circle
365.2575. Keeping the printed table reproduces its 10227.1792-day cycle.
Neither the table nor its arithmetic establishes a modern physical longitude.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction

from fatebridge.core.guolao_classical import (
    BRANCHES,
    MANSIONS,
    PURPLE_SOURCE_DAYS_PER_DU,
    PURPLE_SOURCE_OFFSET_DAYS,
    PURPLE_SOURCE_PERIOD_DAYS,
    STEMS,
    HistoricalMansions,
)


@dataclass(frozen=True)
class ShoushiWinterCycle:
    elapsed_years: int
    effective_year_days: Fraction
    zhongji_days: Fraction
    winter_cycle_days: Fraction
    winter_sexagenary_day: str
    winter_fraction_of_day: Fraction


def shoushi_winter_cycle(elapsed_years: int) -> ShoushiWinterCycle:
    """授时下算: whole-century 消一分, then multiply the whole 距算.

    Gujin 36 gives 365.2425 days, 55.06-day 气应 and the century rule.
    Its 318-year worked example in juan 43/58 disambiguates the rule:
    318 * (365.2425 - 3/10000) = 116147.0196, not a linear drift or a
    sum of individually shortened years. This reconstructs source arithmetic,
    not the actual tropical year, a modern date, or the disputed header year.
    上考 uses a different prescription and is not inferred by negative input.
    """
    if isinstance(elapsed_years, bool) or not isinstance(elapsed_years, int):
        raise TypeError("距算须为非负整数年数，不接收现代日期或小数年")
    if elapsed_years < 0:
        raise ValueError("这里只复原授时下算；上考不能借负距算套用")
    year_days = Fraction("365.2425") - Fraction(elapsed_years // 100, 10000)
    if year_days <= 0:
        raise ValueError("距算超出此古历算式的有效年长范围")
    middle = elapsed_years * year_days
    winter = (middle + Fraction("55.06")) % 60
    day = winter.numerator // winter.denominator
    return ShoushiWinterCycle(
        elapsed_years=elapsed_years,
        effective_year_days=year_days,
        zhongji_days=middle,
        winter_cycle_days=winter,
        winter_sexagenary_day=STEMS[day % 10] + BRANCHES[day % 12],
        winter_fraction_of_day=winter - day,
    )


GUJIN_58_PURPLE = HistoricalMansions(
    source_id="gujin_58_siku_printed_purple_table",
    coordinate_frame="source_ecliptic",
    circle_du=Fraction("365.2564"),
    widths_du=tuple(
        map(
            Fraction,
            (
                "12.87",
                "9.56",
                "16.40",
                "5.48",
                "6.27",
                "17.95",
                "9.59",
                "23.47",
                "6.90",
                "11.12",
                "9.0064",
                "15.95",
                "18.32",
                "9.34",
                "17.87",
                "12.36",
                "15.81",
                "11.08",
                "16.50",
                "0.05",
                "10.28",
                "31.03",
                "2.11",
                "13",
                "6.31",
                "17.79",
                "20.09",
                "18.75",
            ),
        )
    ),
)
_ORIGIN_INDEX = MANSIONS.index("箕")
_ORDER = MANSIONS[_ORIGIN_INDEX:] + MANSIONS[:_ORIGIN_INDEX]
_WIDTHS = (
    GUJIN_58_PURPLE.widths_du[_ORIGIN_INDEX:]
    + GUJIN_58_PURPLE.widths_du[:_ORIGIN_INDEX]
)
_ENDS_DAYS = tuple(
    sum(_WIDTHS[: i + 1], Fraction()) * PURPLE_SOURCE_DAYS_PER_DU for i in range(28)
)
if _ENDS_DAYS[-1] != PURPLE_SOURCE_PERIOD_DAYS:
    raise ValueError("刊载紫气宿表与刊载周积不符，禁止强制归一化")


@dataclass(frozen=True)
class PurpleHistoricalPosition:
    source_id: str
    mansion: str
    next_mansion: str
    degree_in_mansion_du: Fraction
    phase_days: Fraction
    interval_start_days: Fraction
    interval_end_days: Fraction
    days_until_next_mansion: Fraction


def purple_historical_position(zhongji_days: Fraction) -> PurpleHistoricalPosition:
    """Locate caller-declared 原历中积 in the printed, 箕初-origin table.

    This is an offline source reconstruction. Calendar dates, TT/UT1, site
    meridian and a modern coordinate origin are not supplied or inferred.
    The returned 古度 must never be relabelled modern ecliptic degrees.
    """
    if not isinstance(zhongji_days, Fraction):
        raise TypeError("中积须以Fraction明确提供原历日数，不接收现代JD浮点值")
    phase = (zhongji_days + PURPLE_SOURCE_OFFSET_DAYS) % PURPLE_SOURCE_PERIOD_DAYS
    index = bisect_right(_ENDS_DAYS, phase)
    start = _ENDS_DAYS[index - 1] if index else Fraction()
    end = _ENDS_DAYS[index]
    return PurpleHistoricalPosition(
        source_id=GUJIN_58_PURPLE.source_id,
        mansion=_ORDER[index],
        next_mansion=_ORDER[(index + 1) % 28],
        degree_in_mansion_du=(phase - start) / PURPLE_SOURCE_DAYS_PER_DU,
        phase_days=phase,
        interval_start_days=start,
        interval_end_days=end,
        days_until_next_mansion=end - phase,
    )
