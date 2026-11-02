"""Exact local limit-scale arithmetic, with the printed rates kept separate.

Lu Wei, Tohoku 10020000001141, images 76-77: eleven named palaces have
durations and a thirty-cell limit ruler. Dividing this ruler by the duration
is an explicit reconstruction, not a correction to the printed annual rates.
It is neither a modern longitude nor a complete 大限 schedule. The caller
must already know which palace limit has begun and its elapsed source years.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

SOURCE_ID = "tohoku_luwei_10020000001141"
METHOD_ID = "guolao_local_limit_duration_ratio_v1"
SCALE_CELLS = 30


def _exact(value: Fraction, label: str) -> Fraction:
    if not isinstance(value, Fraction):
        raise TypeError(f"{label}须以Fraction提供原尺数值，不能混入浮点或现代日期")
    return value


@dataclass(frozen=True)
class LimitScale:
    palaces: tuple[str, ...]
    years: Fraction
    printed_rate_text: str
    printed_rate: Fraction | None
    printed_rate_status: str = "transcribed_not_emended"

    def __post_init__(self) -> None:
        _exact(self.years, "宫限年数")
        if self.years <= 0 or not self.palaces:
            raise ValueError("原尺须有宫限名及正的年数")
        if self.printed_rate is not None:
            _exact(self.printed_rate, "刊载速率")
            if self.printed_rate <= 0:
                raise ValueError("刊载速率须为正")

    @property
    def degrees_per_year(self) -> Fraction:
        return SCALE_CELLS / self.years

    @property
    def years_per_degree(self) -> Fraction:
        return self.years / SCALE_CELLS

    def elapsed_years(self, scale_degrees: Fraction) -> Fraction:
        """Invert only this local ruler, including its endpoint without wrapping."""
        value = _exact(scale_degrees, "行限尺度")
        if not 0 <= value <= SCALE_CELLS:
            raise ValueError("局部行限尺只接收0至30；不能按周天取模或猜下一限")
        return value * self.years_per_degree

    def position(self, elapsed_source_years: Fraction) -> dict[str, Any]:
        value = _exact(elapsed_source_years, "已入本限的原尺年数")
        if not 0 <= value <= self.years:
            raise ValueError("年数须在所选宫限内；不自动推定起限岁数或接续其他宫")
        degrees = value * self.degrees_per_year
        complete = value == self.years
        return {
            "method_id": METHOD_ID,
            "source_id": SOURCE_ID,
            "palaces": list(self.palaces),
            "elapsed_source_years_exact": str(value),
            "duration_source_years_exact": str(self.years),
            "limit_scale_degrees_exact": str(degrees),
            "printed_rate_scale_degrees_exact": (
                str(value * self.printed_rate)
                if self.printed_rate is not None
                else None
            ),
            "cell": None if complete else int(degrees) + 1,
            "cell_fraction_exact": None if complete else str(degrees % 1),
            "status": "local_limit_complete" if complete else "within_local_limit",
            "coordinate_basis": "thirty_cell_source_limit_ruler_not_sky_longitude",
            "rate_policy": "duration_ratio_reconstruction_not_printed_rate_emendation",
            "calendar_date": None,
            "birth_age": None,
            "mansion": None,
            "next_palace": None,
            "full_limit_schedule_accepted": False,
        }

    def cell_interval(self, cell: int) -> tuple[Fraction, Fraction]:
        """Zero-based source-year interval [start,end) of a printed 1..30 cell."""
        if isinstance(cell, bool) or not isinstance(cell, int):
            raise TypeError("行限表格号须为1至30的整数")
        if not 1 <= cell <= SCALE_CELLS:
            raise ValueError("行限表格号须为1至30")
        return (cell - 1) * self.years_per_degree, cell * self.years_per_degree


LIMIT_SCALES = (
    LimitScale(("相貌",), Fraction(10), "一年行三度", Fraction(3)),
    LimitScale(("官禄",), Fraction(15), "一年行二度", Fraction(2)),
    LimitScale(
        ("福德", "妻妾"),
        Fraction(11),
        "一年行二度七十二分七抄",
        Fraction("2.7207"),
    ),
    LimitScale(("迁移",), Fraction(8), "一年行三度七十五分", Fraction("3.75")),
    LimitScale(
        ("疾厄",),
        Fraction(7),
        "一年行四度二十八分五十分",
        None,
        "final_unit_printed_as_分_reading_retained_not_silently_changed_to_抄",
    ),
    LimitScale(
        ("奴仆", "男女", "田宅"),
        Fraction(9, 2),
        "一年行六度六十分六抄",
        Fraction("6.6006"),
    ),
    LimitScale(("兄弟", "财帛"), Fraction(5), "一年行六度", Fraction(6)),
)


def limit_scale(palace: str) -> LimitScale:
    """Canonical modern spellings of the image's eleven labels, no default 命限."""
    for scale in LIMIT_SCALES:
        if palace in scale.palaces:
            return scale
    raise ValueError("须选择已校读的十一宫限；命宫起限规则尚未复原，不能补默认值")


def limit_scale_audit() -> dict[str, Any]:
    """Expose both rates and discrepancies; never normalize the printed values."""
    scales = []
    for scale in LIMIT_SCALES:
        printed_span = (
            scale.printed_rate * scale.years if scale.printed_rate is not None else None
        )
        scales.append(
            {
                "palaces": list(scale.palaces),
                "duration_source_years_exact": str(scale.years),
                "reconstructed_scale_degrees_per_year_exact": str(
                    scale.degrees_per_year
                ),
                "source_years_per_scale_degree_exact": str(scale.years_per_degree),
                "printed_rate_text": scale.printed_rate_text,
                "printed_rate_status": scale.printed_rate_status,
                "printed_scale_degrees_per_year_exact": (
                    str(scale.printed_rate) if scale.printed_rate is not None else None
                ),
                "printed_full_span_scale_degrees_exact": (
                    str(printed_span) if printed_span is not None else None
                ),
                "printed_full_span_minus_30_exact": (
                    str(printed_span - SCALE_CELLS)
                    if printed_span is not None
                    else None
                ),
            }
        )
    return {
        "method_id": METHOD_ID,
        "source_id": SOURCE_ID,
        "locator": "馆藏卷1–2·图像76定行限度法、77逐年行限度法",
        "scale_cells": SCALE_CELLS,
        "scales": scales,
        "table_discrepancies": [
            {
                "locator": "图像77·福德/妻妾行第15格",
                "printed_start_month_day_reading": "二月十五",
                "duration_ratio_reconstruction_start_month_day": "二月十九",
                "status": "reading_difference_unadjudicated_not_emended",
            }
        ],
        "palace_correction_note": {
            "locator": "图像86·命度图上方校注",
            "short_palaces": list("亥戌酉申未卯"),
            "text": "六宮咸少一度",
            "rejected_old_examples": ["氐二過卯", "畢七過申"],
            "used_as_modern_longitude_correction": False,
        },
        "calendar_basis": "source_year_fractions_no_UTC_or_Gregorian_conversion",
        "source_table_fully_collated": False,
        "full_limit_schedule_accepted": False,
        "modern_sky_mapping_accepted": False,
        "real_world_efficacy_tested": False,
        "limitations": [
            "年数比例是30格限尺重建，刊载速率及其差额分别保留",
            "命度、入限时点和出生岁数尚未由此模块求得",
            "限尺30格不等于每个天文宫恒有现代黄经30度",
            "第86幅另述亥戌酉申未卯六宫少一度，不可据此统一平移宿界",
            "未按原表年/月/日数字直接指定物理日长或现代公历日期",
        ],
    }
