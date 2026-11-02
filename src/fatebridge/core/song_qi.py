"""Exact, explicitly selected Song calendar qi arithmetic from printed Songshi.

This is a source-arithmetic component, not a historical UTC ephemeris. It does
not select the calendar actually used by an author, resolve a lunar date, or
replace the year/month boundaries of the public Heluo/Canping calculators.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import Any

TERMS = (
    "冬至",
    "小寒",
    "大寒",
    "立春",
    "雨水",
    "惊蛰",
    "春分",
    "清明",
    "谷雨",
    "立夏",
    "小满",
    "芒种",
    "夏至",
    "小暑",
    "大暑",
    "立秋",
    "处暑",
    "白露",
    "秋分",
    "寒露",
    "霜降",
    "立冬",
    "小雪",
    "大雪",
    "冬至",
)
CYCLE = tuple(
    "甲乙丙丁戊己庚辛壬癸"[i % 10] + "子丑寅卯辰巳午未申酉戌亥"[i % 12]
    for i in range(60)
)
SOURCE_77_82 = "https://upload.wikimedia.org/wikipedia/commons/b/b7/SSID-12529624_%E6%AC%BD%E5%AE%9A%E5%AE%8B%E5%8F%B2_%E5%8D%B777-82.pdf"
SOURCE_83_86 = "https://upload.wikimedia.org/wikipedia/commons/9/9e/SSID-12529625_%E6%AC%BD%E5%AE%9A%E5%AE%8B%E5%8F%B2_%E5%8D%B783-86.pdf"


@dataclass(frozen=True)
class _WinterCorrection:
    gas_offset_units: int
    distance_reference: int
    distance_rate: int


@dataclass(frozen=True)
class _Profile:
    title: str
    base_year: int
    base_year_caption: str
    accumulated_years: int
    day_divisor: int
    year_units: int
    cycle_origin: int
    qi_small: int
    qi_subdivision: int
    subdivision_divisor: int
    source_url: str
    source_sha256: str
    source_pages: tuple[int, ...]
    winter_correction: _WinterCorrection | None = None

    @property
    def ticks_per_day(self) -> int:
        return self.day_divisor * self.subdivision_divisor

    @property
    def qi_ticks(self) -> int:
        return (
            15 * self.day_divisor + self.qi_small
        ) * self.subdivision_divisor + self.qi_subdivision


_PROFILES = MappingProxyType(
    {
        # Volume 79: the day count is named from 己卯, not 甲子. 太=3/4;
        # subdivision 45/60 is an exact representation, not modern seconds.
        "songshi_jiyuan_v1": _Profile(
            "宋史卷七十九·崇宁纪元历步气朔",
            1100,
            "元符三年庚辰",
            28613460,
            7290,
            2662626,
            15,
            1592,
            45,
            60,
            SOURCE_77_82,
            "b49475698fafa4248db7cfdd32eb6b8fc8b5ef6998115feecd76a99182ef9f7a",
            (55, 56, 58),
        ),
        # Volume 83: qi seconds use 180 per source small unit. The subsequent
        # solar-motion section uses a different 100-based subdivision.
        "songshi_tongyuan_v1": _Profile(
            "宋史卷八十三·绍兴统元历步气朔",
            1135,
            "绍兴五年乙卯",
            94251591,
            6930,
            2531138,
            0,
            1514,
            15,
            180,
            SOURCE_83_86,
            "0d262f3efed31b79907762c3f81374cf61540be0b50a8d524644607149f9dedf",
            (3, 4, 6, 7),
        ),
        # Volume 84's main text is Tongtian. Its smaller interlinear Kai-xi
        # and Chengtian constants are separate algorithms. 少 is 1/4 of a
        # source small unit; the parallel decimal-day annotation is not added.
        "songshi_tongtian_mei_v1": _Profile(
            "宋史卷八十四·绍熙统天历步气朔（梅文鼎三位躔差读法）",
            1194,
            "绍熙五年甲寅",
            3830,
            12000,
            4382910,
            0,
            2621,
            1,
            4,
            SOURCE_83_86,
            "0d262f3efed31b79907762c3f81374cf61540be0b50a8d524644607149f9dedf",
            (91, 92, 93),
            _WinterCorrection(237811, 3830, 127),
        ),
    }
)


def _profile(profile_id: str) -> _Profile:
    if not isinstance(profile_id, str) or profile_id not in _PROFILES:
        raise ValueError(
            "profile_id须显式指定songshi_jiyuan_v1、songshi_tongyuan_v1"
            "或songshi_tongtian_mei_v1。"
        )
    return _PROFILES[profile_id]


def _rational(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _winter_units(p: _Profile, accumulated: int) -> tuple[int, dict[str, Any] | None]:
    raw = accumulated * p.year_units
    c = p.winter_correction
    if c is None:
        return raw, None
    distance = abs(accumulated - c.distance_reference)
    # Mei's explicit 三位 reading: first round 127*d/10000 to a tenth
    # (e.g. 26.3652 -> 26.4); multiply by d, then half-up to a whole source
    # unit. Rounding only the final quadratic, or using Python round, differs.
    tenths = (c.distance_rate * distance + 500) // 1000
    correction = (tenths * distance + 5) // 10
    fan = raw - c.gas_offset_units
    return fan - correction, {
        "reading": "Mei_Wending_three_place; first_tenth_then_whole_half_up",
        "distance_reference_accumulated_years": c.distance_reference,
        "distance_years": distance,
        "gas_offset_source_units": c.gas_offset_units,
        "distance_rate": c.distance_rate,
        "unrounded_chant_source_units": _rational(
            Fraction(c.distance_rate * distance, 10000)
        ),
        "rounded_chant_source_units": _rational(Fraction(tenths, 10)),
        "rounded_correction_source_units": correction,
        "fan_accumulation_source_units": fan,
        "corrected_accumulation_source_units": fan - correction,
        "before_reference_sign": "subtract_also_before_reference; not_add",
        "reading_source": {
            "title": "梅文鼎·冬至攷卷一（三位与二位躔差辨析）",
            "url": "https://upload.wikimedia.org/wikipedia/commons/6/69/CADAL01020102_%E6%AD%B7%E7%AE%97%E5%85%A8%E6%9B%B8%C2%B7%E5%86%AC%E8%87%B4%E6%94%B7%E6%AD%B7%E7%AE%97%E5%85%A8%E6%9B%B8%C2%B7%E8%AB%B8%E6%96%B9%E6%97%A5%E8%BB%8C%E6%AD%B7%E7%AE%97%E5%85%A8%E6%9B%B8%C2%B7%E4%BA%94%E6%98%9F%E7%B4%80%E8%A6%81.djvu",
            "sha256": "b7649ab3cbee6cd2d172a7741265e09cb88d63de0fe7d55731fcdf0aeb0c8589",
            "pages": [9, 10, 96, 97, 98, 99, 100],
        },
    }


def source_term_remainder(
    *, profile_id: str, accumulated_years: int, term_index: int
) -> dict[str, Any]:
    """Compute a qi remainder from an explicit source accumulated-year count.

    Index 0 is the source year's 天正冬至; index 24 is the 24-qi cumulative
    endpoint. With secular corrections this may differ from a separately
    recomputed next-year winter. No western date, place or UTC offset is
    inferred from a sexagenary day and its source fraction.
    """
    p = _profile(profile_id)
    if type(accumulated_years) is not int or accumulated_years < 0:
        raise ValueError("积年须为非负整数，不能以布尔值、浮点或字符串代入。")
    if type(term_index) is not int or not 0 <= term_index <= 24:
        raise ValueError("节气序须为0至24整数，0为天正冬至、24为累加端点。")
    winter_units, correction = _winter_units(p, accumulated_years)
    winter_ticks = winter_units * p.subdivision_divisor
    total = winter_ticks + term_index * p.qi_ticks
    whole_days, within_day = divmod(total, p.ticks_per_day)
    small, subdivision = divmod(within_day, p.subdivision_divisor)
    # A sequence row's day offset includes the starting day's fractional carry.
    winter_day = winter_ticks // p.ticks_per_day
    result: dict[str, Any] = {
        "term_index_from_winter_solstice": term_index,
        "term": TERMS[term_index],
        "source_big_remainder": whole_days % 60,
        "source_small_remainder": small,
        "source_subdivision_remainder": subdivision,
        "source_subdivision_divisor": p.subdivision_divisor,
        "source_day_divisor": p.day_divisor,
        "ganzhi_day": CYCLE[(whole_days + p.cycle_origin) % 60],
        "cycle_origin_ganzhi": CYCLE[p.cycle_origin],
        "source_day_fraction": _rational(Fraction(within_day, p.ticks_per_day)),
        "interval_days_from_winter_solstice": _rational(
            Fraction(term_index * p.qi_ticks, p.ticks_per_day)
        ),
        "whole_day_offset_from_winter_day": whole_days - winter_day,
    }
    if correction is not None:
        result["winter_correction"] = correction
        if term_index == 24:
            result["endpoint_policy"] = (
                "24th_constant_qi_endpoint; not_separately_recomputed_next_winter"
            )
    return result


def source_qi_sequence(*, profile_id: str, year_label: int) -> dict[str, Any]:
    """Project a named printed algorithm, without asserting historical use.

    year_label is related to the printed reference year by integer year
    difference. Projections outside an algorithm's period are arithmetic only;
    a western year alone never selects a historical calendar.
    """
    p = _profile(profile_id)
    if type(year_label) is not int or not 1 <= year_label <= 9999:
        raise ValueError(
            "year_label须为1至9999整数；该范围仅为年标签范围，不是历史验收范围。"
        )
    accumulated = p.accumulated_years + year_label - p.base_year
    result: dict[str, Any] = {
        "profile_id": profile_id,
        "source_title": p.title,
        "source_url": p.source_url,
        "source_pdf_sha256": p.source_sha256,
        "source_pdf_pages": list(p.source_pages),
        "source_reference_year": p.base_year,
        "source_reference_year_caption": p.base_year_caption,
        "source_reference_accumulated_years": p.accumulated_years,
        "year_label": year_label,
        "accumulated_years": accumulated,
        "source_year_days": _rational(Fraction(p.year_units, p.day_divisor)),
        "source_qi_interval_days": _rational(Fraction(p.qi_ticks, p.ticks_per_day)),
        "terms": [
            source_term_remainder(
                profile_id=profile_id, accumulated_years=accumulated, term_index=i
            )
            for i in range(25)
        ],
        "calendar_selection": "explicit_printed_algorithm; actual_historical_use_not_established",
        "time_frame": "source_day_and_subdivisions; no_UTC_or_modern_seconds_mapping",
        "review_status": "selected_source_pages_visually_read_once; independent_second_review_pending",
        "applied_to_public_four_pillars": False,
        "complete_historical_calendar": False,
    }
    winter, correction = _winter_units(p, accumulated)
    if correction is not None:
        following, _ = _winter_units(p, accumulated + 1)
        result["winter_correction"] = correction
        result["recomputed_next_winter_minus_endpoint_days"] = _rational(
            Fraction(following - winter - p.year_units, p.day_divisor)
        )
        result["endpoint_policy"] = (
            "source_constant_qi_accumulation; next_winter_recomputed_separately; "
            "no_interpolated_secular_correction"
        )
    return result
