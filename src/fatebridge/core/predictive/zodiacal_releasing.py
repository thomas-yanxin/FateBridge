"""黄道释放（Zodiacal Releasing）推运法。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astrology_tables import RULER_BY_SIGN, SIGNS

from ._common import (
    LOT_LABELS,
    LOT_POINT_NAMES,
    build_lot_payloads,
    classify_releasing_phase,
    next_sign,
    opposite_sign,
    planet_label,
    sign_label,
)

# 各星座的释放年数（黄道释放法）
ZR_SIGN_PERIODS = {
    "Aries": 15,
    "Taurus": 8,
    "Gemini": 20,
    "Cancer": 25,
    "Leo": 19,
    "Virgo": 20,
    "Libra": 8,
    "Scorpio": 15,
    "Sagittarius": 12,
    "Capricorn": 27,
    "Aquarius": 30,
    "Pisces": 12,
}

# 各层级的单位天数及标签
ZR_LEVEL_UNIT_DAYS = {
    1: 360.0,
    2: 30.0,
    3: 2.5,
    4: 5.0 / 24.0,
}
# Labels name the granularity of one step at each level. They must match
# ZR_LEVEL_UNIT_DAYS above: L3 steps are 2.5 days (day-scale, NOT weeks) and L4
# steps are 5 hours (hour-scale, NOT days) under the standard /12 fractal
# subdivision, so calling them "weeks"/"days" misrepresented the magnitude.
ZR_LEVEL_UNIT_LABELS = {
    1: "years",
    2: "months",
    3: "days",
    4: "hours",
}
ZR_LEVEL_UNIT_LABELS_ZH = {
    1: "年",
    2: "月",
    3: "日",
    4: "时",
}


def build_zodiacal_releasing_period(
    *,
    sign_name: str,
    period_start: datetime,
    period_end: datetime,
    root_sign: str,
    parent_sign: str,
    level: int,
    analysis_datetime: datetime,
    loosing_of_bond: bool = False,
) -> Dict[str, Any]:
    ruler = RULER_BY_SIGN[sign_name]
    phase = classify_releasing_phase(sign_name, root_sign)
    return {
        "sign": sign_name,
        "sign_label": sign_label(sign_name),
        "ruler": ruler,
        "ruler_label": planet_label(ruler),
        "level": level,
        "duration_value": ZR_SIGN_PERIODS[sign_name],
        "duration_unit": ZR_LEVEL_UNIT_LABELS[level],
        "duration_unit_label": ZR_LEVEL_UNIT_LABELS_ZH[level],
        "start": period_start.isoformat(),
        "end": period_end.isoformat(),
        "loosing_of_bond": loosing_of_bond,
        "parent_sign": parent_sign,
        "parent_sign_label": sign_label(parent_sign),
        "active": period_start <= analysis_datetime < period_end,
        "_start": period_start,
        "_end": period_end,
        **phase,
    }


def build_releasing_level_preview(
    *,
    start_sign: str,
    period_start: datetime,
    root_sign: str,
    parent_sign: str,
    level: int,
    analysis_datetime: datetime,
    preview_after_active: int = 4,
    max_periods: int = 24,
) -> List[Dict[str, Any]]:
    periods: List[Dict[str, Any]] = []
    current_sign = start_sign
    cursor = period_start
    active_found = False
    future_slots_remaining = preview_after_active

    for _ in range(max_periods):
        duration_days = ZR_SIGN_PERIODS[current_sign] * ZR_LEVEL_UNIT_DAYS[level]
        next_cursor = cursor + timedelta(days=duration_days)
        period = build_zodiacal_releasing_period(
            sign_name=current_sign,
            period_start=cursor,
            period_end=next_cursor,
            root_sign=root_sign,
            parent_sign=parent_sign,
            level=level,
            analysis_datetime=analysis_datetime,
        )
        periods.append(period)
        if period["active"]:
            active_found = True
        elif active_found:
            future_slots_remaining -= 1
            if future_slots_remaining <= 0:
                break
        cursor = next_cursor
        current_sign = next_sign(current_sign)

    return periods


def build_releasing_level_within_interval(
    *,
    start_sign: str,
    period_start: datetime,
    period_end: datetime,
    root_sign: str,
    parent_sign: str,
    level: int,
    analysis_datetime: datetime,
    max_periods: int = 24,
) -> List[Dict[str, Any]]:
    periods: List[Dict[str, Any]] = []
    current_sign = start_sign
    cursor = period_start
    cycle_start_sign = start_sign
    loosing_used = False
    pending_loosing_of_bond = False

    for _ in range(max_periods):
        if cursor >= period_end:
            break
        duration_days = ZR_SIGN_PERIODS[current_sign] * ZR_LEVEL_UNIT_DAYS[level]
        next_cursor = min(period_end, cursor + timedelta(days=duration_days))
        loosing_of_bond = pending_loosing_of_bond
        pending_loosing_of_bond = False
        periods.append(
            build_zodiacal_releasing_period(
                sign_name=current_sign,
                period_start=cursor,
                period_end=next_cursor,
                root_sign=root_sign,
                parent_sign=parent_sign,
                level=level,
                analysis_datetime=analysis_datetime,
                loosing_of_bond=loosing_of_bond,
            )
        )
        cursor = next_cursor
        next_sign_name = next_sign(current_sign)
        if (
            level > 1
            and not loosing_used
            and next_sign_name == cycle_start_sign
            and cursor < period_end
        ):
            current_sign = opposite_sign(cycle_start_sign)
            loosing_used = True
            pending_loosing_of_bond = True
        else:
            current_sign = next_sign_name

    return periods


def clean_releasing_period(
    period: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if period is None:
        return None
    return {key: value for key, value in period.items() if not key.startswith("_")}


def clean_releasing_timeline(periods: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # clean_releasing_period only returns None for a None input; periods here are
    # always real dicts, so the filter keeps every entry and satisfies the type.
    cleaned = [clean_releasing_period(period) for period in periods]
    return [period for period in cleaned if period is not None]


def peak_signs_from_root(root_sign: str) -> List[Dict[str, str]]:
    root_index = SIGNS.index(root_sign)
    offsets = [0, 3, 6, 9]
    signs = [SIGNS[(root_index + offset) % 12] for offset in offsets]
    return [
        {
            "sign": sign_name,
            "sign_label": sign_label(sign_name),
        }
        for sign_name in signs
    ]


def build_zodiacal_releasing_for_lot(
    lot_key: str,
    lot_payload: Dict[str, Any],
    *,
    birth_info: AstroBirthInfo,
    analysis_datetime: datetime,
    start_sign: Optional[str] = None,
) -> Dict[str, Any]:
    root_sign = start_sign or lot_payload["sign"]
    level_one_timeline = build_releasing_level_preview(
        start_sign=root_sign,
        period_start=birth_info.local_datetime,
        root_sign=root_sign,
        parent_sign=root_sign,
        level=1,
        analysis_datetime=analysis_datetime,
    )
    current_level_1 = next(
        (item for item in level_one_timeline if item["active"]), None
    )

    level_two_timeline: List[Dict[str, Any]] = []
    current_level_2 = None
    if current_level_1 is not None:
        level_two_timeline = build_releasing_level_within_interval(
            start_sign=current_level_1["sign"],
            period_start=current_level_1["_start"],
            period_end=current_level_1["_end"],
            root_sign=root_sign,
            parent_sign=current_level_1["sign"],
            level=2,
            analysis_datetime=analysis_datetime,
        )
        current_level_2 = next(
            (item for item in level_two_timeline if item["active"]), None
        )

    level_three_timeline: List[Dict[str, Any]] = []
    current_level_3 = None
    if current_level_2 is not None:
        level_three_timeline = build_releasing_level_within_interval(
            start_sign=current_level_2["sign"],
            period_start=current_level_2["_start"],
            period_end=current_level_2["_end"],
            root_sign=root_sign,
            parent_sign=current_level_2["sign"],
            level=3,
            analysis_datetime=analysis_datetime,
        )
        current_level_3 = next(
            (item for item in level_three_timeline if item["active"]),
            None,
        )

    return {
        "base_point": LOT_POINT_NAMES[lot_key],
        "base_point_label": LOT_LABELS[lot_key],
        "lot": lot_payload,
        "release_start_sign": root_sign,
        "release_start_sign_label": sign_label(root_sign),
        "peak_signs": peak_signs_from_root(root_sign),
        "current_level_1": clean_releasing_period(current_level_1),
        "current_level_2": clean_releasing_period(current_level_2),
        "current_level_3": clean_releasing_period(current_level_3),
        "level_1_timeline": clean_releasing_timeline(level_one_timeline),
        "level_2_timeline": clean_releasing_timeline(level_two_timeline),
        "level_3_timeline": clean_releasing_timeline(level_three_timeline),
    }


def build_zodiacal_releasing_payload(
    birth_info: AstroBirthInfo,
    natal_subject: Any,
    *,
    analysis_datetime: datetime,
) -> Dict[str, Any]:
    lots = build_lot_payloads(natal_subject)
    # Releasing from Spirit always begins at the Lot of Spirit's own sign.
    # Spirit and Fortune may share a sign — there is no rule bumping Spirit on.
    spirit_start_sign = lots["lot_of_spirit"]["sign"]
    return {
        "spirit": build_zodiacal_releasing_for_lot(
            "lot_of_spirit",
            lots["lot_of_spirit"],
            birth_info=birth_info,
            analysis_datetime=analysis_datetime,
            start_sign=spirit_start_sign,
        ),
        "fortune": build_zodiacal_releasing_for_lot(
            "lot_of_fortune",
            lots["lot_of_fortune"],
            birth_info=birth_info,
            analysis_datetime=analysis_datetime,
        ),
    }
