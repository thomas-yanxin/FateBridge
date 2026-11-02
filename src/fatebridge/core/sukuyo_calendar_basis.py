"""Host calendar choice is separate from birth timezone and mansion method."""

from __future__ import annotations

from datetime import date
from types import ModuleType
from typing import Literal

SukuyoCalendarBasis = Literal[
    "chinese_hko_utc08",
    "japanese_hutime_1002_1_utc09",
    "japanese_naoj_historical_utc09",
]
DEFAULT_CALENDAR_BASIS = "chinese_hko_utc08"
JAPANESE_CALENDAR_BASIS = "japanese_hutime_1002_1_utc09"
HISTORICAL_CALENDAR_BASIS = "japanese_naoj_historical_utc09"
JAPANESE_CALENDAR_BASES = frozenset(
    {JAPANESE_CALENDAR_BASIS, HISTORICAL_CALENDAR_BASIS}
)


def basis_identifiers(basis: str) -> tuple[str, str]:
    if basis == DEFAULT_CALENDAR_BASIS:
        return "modern_chinese_lunisolar", "lunardate"
    if basis == JAPANESE_CALENDAR_BASIS:
        return "japanese_hutime_old_calendar_reference", "frozen_hutime_daily_reference"
    if basis == HISTORICAL_CALENDAR_BASIS:
        return (
            "japanese_naoj_historical_month_start_reference",
            "frozen_naoj_historical_month_starts",
        )
    raise ValueError("未知的宿曜宿主历法标识")


def japanese_calendar_reader(basis: str) -> ModuleType:
    if basis == JAPANESE_CALENDAR_BASIS:
        from fatebridge.core import sukuyo_japanese_calendar

        return sukuyo_japanese_calendar
    if basis == HISTORICAL_CALENDAR_BASIS:
        from fatebridge.core import sukuyo_historical_calendar

        return sukuyo_historical_calendar
    raise ValueError("未知的日本参考历法，不能回退其他资料")


def basis_parameters(basis: str) -> tuple[int, date, date, str]:
    if basis == DEFAULT_CALENDAR_BASIS:
        return 8, date(1901, 1, 1), date(2099, 12, 31), "中国"
    if basis in JAPANESE_CALENDAR_BASES:
        first, last = japanese_calendar_reader(basis).supported_range()
        return (
            9,
            first,
            last,
            (
                "日本历史历日参考"
                if basis == HISTORICAL_CALENDAR_BASIS
                else "日本旧历参考"
            ),
        )
    raise ValueError(
        "calendar_basis仅支持chinese_hko_utc08、japanese_hutime_1002_1_utc09或japanese_naoj_historical_utc09"
    )


def range_provenance(basis: str) -> str:
    """A selected implementation's range is not a provider-wide absence claim."""
    labels = {
        DEFAULT_CALENDAR_BASIS: (
            "当前所选中国宿主计算及HKO校正范围",
            "香港天文台全部资料",
        ),
        JAPANESE_CALENDAR_BASIS: (
            "所选HuTime1002.1冻结参考",
            "HuTime所有服务或可能数据",
        ),
        HISTORICAL_CALENDAR_BASIS: (
            "所选NAOJ冻结历史月首参考",
            "NAOJ全部资料",
        ),
    }
    if basis not in labels:
        raise ValueError("未知宿主历法，不能推定范围来源")
    selected, provider = labels[basis]
    return (
        f"此限制仅指{selected}（calendar_basis={basis}），"
        f"不代表{provider}均无该年代记录；未补造范围外历日。"
    )
