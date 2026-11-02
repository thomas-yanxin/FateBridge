"""Published Ganzhi anchor and explicit proleptic calendar *date labels*.

An integer noon JDN is used only as a calendar-label serial. Matching a
source cycle day does not calibrate its local midnight, UT1, TT or UTC.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from fractions import Fraction as F
from pathlib import Path
from typing import Any

from fatebridge.core import guolao_year_labels
from fatebridge.core.guolao_classical import BRANCHES, STEMS

DATA = Path(__file__).resolve().parents[1] / "data/guolao/calendar-date-bridge-v1.json"
PROFILE = "hko2016_ganzhi_date_label_bridge_v1"
CALENDARS = ("proleptic_gregorian", "proleptic_julian")
SEARCH_POLICY = "preceding_winter_year_gregorian_december"
COUNTER_BASIS = "named_unwrapped_cycle_day"


def _integer(value: int) -> None:
    if type(value) is not int:
        raise TypeError("日期标签及序号须为整数，不接收布尔或隐式转换")


def _calendar(calendar: str) -> None:
    if calendar not in CALENDARS:
        raise ValueError("须明确选择前推格里历或前推儒略历，不自动采用1582切换")


def calendar_label_noon_jdn(year: int, month: int, day: int, *, calendar: str) -> int:
    """Pure CE 1..9999 arithmetic, no assertion of historical local usage."""
    _calendar(calendar)
    for value in (year, month, day):
        _integer(value)
    if not 1 <= year <= 9999 or not 1 <= month <= 12:
        raise ValueError("仅支持公元1至9999年的有效日期标签")
    if calendar == "proleptic_gregorian":
        return date(year, month, day).toordinal() + 1721425
    leap = year % 4 == 0
    lengths = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    if not 1 <= day <= lengths[month - 1]:
        raise ValueError("无效的前推儒略历日期标签")
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return day + (153 * m + 2) // 5 + 365 * y + y // 4 - 32083


def calendar_label_from_noon_jdn(jdn: int, *, calendar: str) -> list[int]:
    """Reverse a label serial; refuse labels outside the declared CE range."""
    _calendar(calendar)
    _integer(jdn)
    if not (
        calendar_label_noon_jdn(1, 1, 1, calendar=calendar)
        <= jdn
        <= calendar_label_noon_jdn(9999, 12, 31, calendar=calendar)
    ):
        raise ValueError("序号超出公元1至9999年的日期标签范围")
    if calendar == "proleptic_gregorian":
        label = date.fromordinal(jdn - 1721425)
        return [label.year, label.month, label.day]
    c = jdn + 32082
    d = (4 * c + 3) // 1461
    e = c - (1461 * d) // 4
    m = (5 * e + 2) // 153
    day = e - (153 * m + 2) // 5 + 1
    month = m + 3 - 12 * (m // 10)
    year = d - 4800 + m // 10
    calendar_label_noon_jdn(year, month, day, calendar=calendar)
    return [year, month, day]


class CalendarDateBridge:
    """Conditional source-date research, separate from the birth engine."""

    def __init__(self, source: dict[str, Any], fingerprint: str):
        self.source = source
        self.fingerprint = fingerprint
        self.anchor_serial = calendar_label_noon_jdn(
            *source["anchor"]["date"], calendar=source["anchor"]["calendar"]
        )

    def label(
        self, year: int, month: int, day: int, *, calendar: str
    ) -> dict[str, Any]:
        serial = calendar_label_noon_jdn(year, month, day, calendar=calendar)
        index = (serial - self.anchor_serial) % 60
        return {
            "calendar": calendar,
            "date": [year, month, day],
            "calendar_label_noon_jdn": serial,
            "sexagenary_index": index,
            "ganzhi": STEMS[index % 10] + BRANCHES[index % 12],
            "profile_id": PROFILE,
            "source_data_sha256": self.fingerprint,
            "published_anchor": self.source["anchor"],
            "physical_julian_day": None,
            "timezone": None,
        }

    def winter_candidates(
        self, *, source_year: int, search_policy: str
    ) -> dict[str, Any]:
        if search_policy != SEARCH_POLICY:
            raise ValueError("未支持的搜索政策，不扩大窗口或移锚以凑合冬至")
        _integer(source_year)
        if not 1281 <= source_year <= 9999:
            raise ValueError("具名历书标年仅支持1281至9999，不推断上考")
        context = guolao_year_labels.shoushi_year_context(source_year=source_year)
        winter_year = context["preceding_winter_year_label_ce"]
        matches = []
        for day in range(1, 32):
            label = self.label(winter_year, 12, day, calendar=CALENDARS[0])
            if label["ganzhi"] == context["winter_sexagenary_day"]:
                matches.append(
                    {
                        "gregorian_date": label["date"],
                        "julian_date": calendar_label_from_noon_jdn(
                            label["calendar_label_noon_jdn"], calendar=CALENDARS[1]
                        ),
                        "calendar_label_noon_jdn": label["calendar_label_noon_jdn"],
                        "ganzhi": label["ganzhi"],
                    }
                )
        return {
            "profile_id": PROFILE,
            "source_data_sha256": self.fingerprint,
            "source_year_context": context,
            "search_policy": search_policy,
            "searched_gregorian_date_range": [
                [winter_year, 12, 1],
                [winter_year, 12, 31],
            ],
            "status": (
                "conditional_unique_date_label" if len(matches) == 1 else "no_match"
            ),
            "candidates": matches,
            "source_midnight_to_published_date_label_continuity_accepted": False,
            "modern_epoch_calibrated": False,
            "physical_julian_day": None,
            "timezone": None,
            "used_in_native_birth_chart": False,
        }

    def source_counter_label(
        self,
        counter: F,
        *,
        source_year: int,
        search_policy: str,
        counter_basis: str,
    ) -> dict[str, Any]:
        """Preserve an explicitly unwrapped source fraction without clock mapping."""
        if not isinstance(counter, F):
            raise TypeError("须传入精确Fraction原历完整循环日数")
        if counter_basis != COUNTER_BASIS:
            raise ValueError("须声明未取模的具名循环日数，不把干支余数猜成完整日数")
        winter = self.winter_candidates(
            source_year=source_year, search_policy=search_policy
        )
        context = winter["source_year_context"]
        start = F(context["winter_cycle_days_exact"])
        day_offset = (
            counter.numerator // counter.denominator
            - start.numerator // start.denominator
        )
        if not 0 <= day_offset <= 365:
            raise ValueError("日数超出具名冬至日开始的366日标签窗口，不取模或补上一岁")
        candidate = winter["candidates"]
        labels = None
        if len(candidate) == 1:
            serial = candidate[0]["calendar_label_noon_jdn"] + day_offset
            labels = {
                "gregorian_date": calendar_label_from_noon_jdn(
                    serial, calendar=CALENDARS[0]
                ),
                "julian_date": calendar_label_from_noon_jdn(
                    serial, calendar=CALENDARS[1]
                ),
                "calendar_label_noon_jdn": serial,
            }
        return {
            "winter_mapping": winter,
            "counter_basis": counter_basis,
            "source_counter_exact": str(counter),
            "source_fraction_of_day_exact": str(counter % 1),
            "integer_day_offset_from_source_winter_day": day_offset,
            "conditional_date_labels": labels,
            "source_fraction_converted_to_modern_clock": False,
            "physical_julian_day": None,
            "timezone": None,
        }


def load_calendar_date_bridge(profile: str) -> CalendarDateBridge:
    if profile != PROFILE:
        raise ValueError("未支持的具名日期标签政策")
    blob = DATA.read_bytes()
    source = json.loads(blob)
    anchor = source["anchor"]
    if (
        source["profile_id"] != PROFILE
        or source["schema"] != PROFILE
        or anchor["date"] != [2016, 10, 9]
        or anchor["calendar"] != CALENDARS[0]
        or type(anchor["sexagenary_index"]) is not int
        or anchor["sexagenary_index"] != 0
        or anchor["printed_ganzhi"] != "甲子"
        or anchor["source_pdf_sha256"]
        != "bd94c44d64d8e35f16ecedecbc1aa080ba943a039c1eef050a3fffb746d77b61"
        or source["search_policy"] != SEARCH_POLICY
        or source["source_counter_basis"] != COUNTER_BASIS
        or source["source_year_labels_data_sha256"]
        != hashlib.sha256(guolao_year_labels.DATA.read_bytes()).hexdigest()
        or source["source_midnight_to_published_date_label_continuity_accepted"]
        is not False
        or source["source_local_clock_or_timezone_assigned"] is not False
        or source["native_birth_chart_integration"] is not False
    ):
        raise ValueError("固定纪日锚点或具名来源不一致，不移动锚点以凑合算例")
    return CalendarDateBridge(source, hashlib.sha256(blob).hexdigest())
