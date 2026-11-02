"""NLC3150's printed month/day ruler, with no mapping to a birth or UTC date.

Source ordinal year 1/month 1/day 1 is the start of a LOCAL palace limit.
The 12 by 30 nominal calendar is explicit; its days are not physical days.
Annual printed rates stay separate even where they contradict month/day spans.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

DATA = (
    Path(__file__).resolve().parents[1] / "data/guolao/ruler-calendar-nlc3150-v1.json"
)
SOURCE_ID = "nlc892_411999021002_92845_3150"
METHOD_ID = "nlc3150_printed_month_day_span_v1"


def _integer(value: int, name: str, minimum: int, maximum: int | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name}须为明确整数")
    if value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"{name}超出名义原尺范围")


def _fraction(value: Fraction, name: str) -> None:
    if not isinstance(value, Fraction):
        raise TypeError(f"{name}须为Fraction，不接受隐式浮点或单位")


@dataclass(frozen=True)
class NominalSourceDate:
    """One-based local ruler labels, never a civil date or a person's age."""

    year: int
    month: int
    day: int
    fraction_of_day: Fraction = Fraction(0)

    def __post_init__(self) -> None:
        _integer(self.year, "原尺序年", 1)
        _integer(self.month, "原尺月", 1, 12)
        _integer(self.day, "原尺日", 1, 30)
        _fraction(self.fraction_of_day, "原尺日内分数")
        if not 0 <= self.fraction_of_day < 1:
            raise ValueError("日内分数须在[0,1)；不自动进位")

    @property
    def elapsed_days(self) -> Fraction:
        return (
            Fraction((self.year - 1) * 360 + (self.month - 1) * 30 + self.day - 1)
            + self.fraction_of_day
        )

    @classmethod
    def from_elapsed_days(cls, days: Fraction) -> NominalSourceDate:
        _fraction(days, "已过名义日")
        if days < 0:
            raise ValueError("原尺已过日不能为负")
        whole = days.numerator // days.denominator
        year, remainder = divmod(whole, 360)
        month, day = divmod(remainder, 30)
        return cls(year + 1, month + 1, day + 1, days - whole)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ordinal_year": self.year,
            "month": self.month,
            "day": self.day,
            "fraction_of_nominal_day_exact": str(self.fraction_of_day),
            "calendar": "local_limit_ordinal_12_months_30_days",
        }


@dataclass(frozen=True)
class RulerCalendarScale:
    palaces: tuple[str, ...]
    source_duration_years: Fraction
    printed_annual_rate: Fraction
    printed_annual_rate_text: str
    printed_month_day_text: str
    months_per_degree: int
    days_per_degree_remainder: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "palaces", tuple(self.palaces))
        if not self.palaces or len(set(self.palaces)) != len(self.palaces):
            raise ValueError("须明确给出不重复的具名宫限")
        _fraction(self.source_duration_years, "原刊宫限年数")
        _fraction(self.printed_annual_rate, "原刊年速率")
        if self.source_duration_years <= 0 or self.printed_annual_rate <= 0:
            raise ValueError("宫限年数及原刊年速率须为正")
        _integer(self.months_per_degree, "每度月数", 0)
        _integer(self.days_per_degree_remainder, "每度余日", 0, 29)
        if not self.nominal_days_per_degree:
            raise ValueError("每度所需名义日须为正")

    @property
    def nominal_days_per_degree(self) -> int:
        return self.months_per_degree * 30 + self.days_per_degree_remainder

    @property
    def total_nominal_days(self) -> int:
        return 30 * self.nominal_days_per_degree

    def _degrees(self, degrees: Fraction) -> None:
        _fraction(degrees, "本限尺格度")
        if not 0 <= degrees <= 30:
            raise ValueError("本限位置须在[0,30]，不取模或推定下一宫")

    def days_from_degrees(self, degrees: Fraction) -> Fraction:
        self._degrees(degrees)
        return degrees * self.nominal_days_per_degree

    def degrees_from_days(self, days: Fraction) -> Fraction:
        _fraction(days, "已过名义日")
        if not 0 <= days <= self.total_nominal_days:
            raise ValueError("日期超出本局部限；不能将公历年份或周岁代入原尺序年")
        return days / self.nominal_days_per_degree

    def position(self, date: NominalSourceDate) -> dict[str, Any]:
        if not isinstance(date, NominalSourceDate):
            raise TypeError("须明确提供NominalSourceDate，不推断公历或出生年龄")
        days = date.elapsed_days
        degrees = self.degrees_from_days(days)
        complete = degrees == 30
        printed_degrees = days * self.printed_annual_rate / 360
        return {
            "source_id": SOURCE_ID,
            "method_id": METHOD_ID,
            "palaces": list(self.palaces),
            "nominal_source_date": date.as_dict(),
            "elapsed_nominal_days_exact": str(days),
            "nominal_days_per_degree": self.nominal_days_per_degree,
            "limit_scale_degrees_exact": str(degrees),
            "printed_annual_rate_scale_degrees_exact": str(printed_degrees),
            "month_day_minus_printed_annual_degrees_exact": str(
                degrees - printed_degrees
            ),
            "status": "local_limit_complete" if complete else "within_local_limit",
            "cell": None if complete else degrees.numerator // degrees.denominator + 1,
            "calendar_date": None,
            "birth_age": None,
            "mansion": None,
            "next_palace": None,
            "used_in_native_birth_chart": False,
            "real_world_efficacy_tested": False,
        }

    def at_degrees(self, degrees: Fraction) -> dict[str, Any]:
        return self.position(
            NominalSourceDate.from_elapsed_days(self.days_from_degrees(degrees))
        )

    def cell_interval(self, cell: int) -> dict[str, Any]:
        _integer(cell, "尺格序号", 1, 30)
        start = Fraction((cell - 1) * self.nominal_days_per_degree)
        end = Fraction(cell * self.nominal_days_per_degree)
        return {
            "source_id": SOURCE_ID,
            "method_id": METHOD_ID,
            "palaces": list(self.palaces),
            "cell": cell,
            "interval_start_nominal_days_exact": str(start),
            "interval_end_nominal_days_exact": str(end),
            "start_nominal_source_date": NominalSourceDate.from_elapsed_days(
                start
            ).as_dict(),
            "last_included_nominal_day": NominalSourceDate.from_elapsed_days(
                end - 1
            ).as_dict(),
            "end_exclusive_nominal_source_date": NominalSourceDate.from_elapsed_days(
                end
            ).as_dict(),
            "interval_convention": "start_inclusive_end_exclusive",
            "last_included_day_includes_all_its_fractional_instants": True,
            "computed_from_printed_month_day_span_not_full_table_transcription": True,
            "calendar_date": None,
            "birth_age": None,
        }

    def audit(self) -> dict[str, Any]:
        rate = Fraction(360, self.nominal_days_per_degree)
        full = self.printed_annual_rate * self.source_duration_years
        return {
            "palaces": list(self.palaces),
            "source_duration_years_exact": str(self.source_duration_years),
            "printed_annual_rate_text": self.printed_annual_rate_text,
            "printed_annual_rate_exact": str(self.printed_annual_rate),
            "printed_month_day_text": self.printed_month_day_text,
            "nominal_days_per_degree": self.nominal_days_per_degree,
            "month_day_degrees_per_nominal_year_exact": str(rate),
            "annual_and_month_day_rates_agree": rate == self.printed_annual_rate,
            "printed_annual_full_limit_degrees_exact": str(full),
            "printed_annual_full_limit_minus_30_exact": str(full - 30),
            "month_day_full_limit_nominal_days": self.total_nominal_days,
            "month_day_full_limit_minus_source_duration_days_exact": str(
                self.total_nominal_days - self.source_duration_years * 360
            ),
        }


def load_ruler_calendar() -> tuple[RulerCalendarScale, ...]:
    data = json.loads(DATA.read_bytes())
    if data["source_id"] != SOURCE_ID or data["method_id"] != METHOD_ID:
        raise ValueError("名义尺历须使用具名NLC3150来源，不跨底本替换")
    return tuple(
        RulerCalendarScale(
            palaces=tuple(row["palaces"]),
            source_duration_years=Fraction(row["source_duration_years_exact"]),
            printed_annual_rate=Fraction(row["printed_annual_rate_exact"]),
            printed_annual_rate_text=row["printed_annual_rate_text"],
            printed_month_day_text=row["printed_month_day_text"],
            months_per_degree=row["months_per_degree"],
            days_per_degree_remainder=row["days_per_degree_remainder"],
        )
        for row in data["scales"]
    )


def ruler_calendar_scale(palace: str) -> RulerCalendarScale:
    for scale in load_ruler_calendar():
        if palace in scale.palaces:
            return scale
    raise ValueError("须明确提供本来源十一宫限之一；命宫起限尚未复原")


def ruler_calendar_audit() -> dict[str, Any]:
    raw = DATA.read_bytes()
    data = json.loads(raw)
    scales = load_ruler_calendar()
    return {
        "source_id": SOURCE_ID,
        "method_id": METHOD_ID,
        "source": data["source"],
        "data_sha256": hashlib.sha256(raw).hexdigest(),
        "nominal_calendar": data["nominal_calendar"],
        "scales": [scale.audit() for scale in scales],
        "contradictory_rate_groups": sum(
            Fraction(360, s.nominal_days_per_degree) != s.printed_annual_rate
            for s in scales
        ),
        "full_210_printed_cells_collated": False,
        "modern_calendar_mapping_accepted": False,
        "life_degree_accepted": False,
        "full_birth_limit_schedule_accepted": False,
        "real_world_efficacy_tested": False,
    }
