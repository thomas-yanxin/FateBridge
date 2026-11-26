"""Qimen calendar anchors, continuous Zhirun state machine, and Ju resolution."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, TypedDict

from typing_extensions import NotRequired

from fatebridge.core.almanac import (
    SolarTerm,
    _solar_term_source_year,
    _solar_terms_for_context_year,
)
from fatebridge.core.calendar import BaZiCalendar, resolve_bazi_effective_date
from fatebridge.core.metaphysics.common import (
    MetaphysicsSeed,
    ganzhi_text,
    sexagenary_index_for,
    sexagenary_text,
)
from fatebridge.utils.civil_time import gregorian_date_parts, utc_calendar
from fatebridge.utils.errors import ParameterError

QIMEN_ZHIRUN_MIN_LEAD_DAYS = 8
QIMEN_CONTINUOUS_LOOKBACK_YEARS = 8

QIMEN_FUHEAD_HEAVEN_STEM: dict[str, str] = {
    "甲子": "戊",
    "甲戌": "己",
    "甲申": "庚",
    "甲午": "辛",
    "甲辰": "壬",
    "甲寅": "癸",
}

QIMEN_ZHIRUN_TERM_SEQUENCE: tuple[str, ...] = (
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
    "小寒",
    "大寒",
    "立春",
    "雨水",
    "惊蛰",
)

QIMEN_YANG_TERMS: frozenset[str] = frozenset(
    {
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
    }
)

QIMEN_JU_BY_TERM: dict[str, tuple[int, int, int]] = {
    "冬至": (1, 7, 4),
    "小寒": (2, 8, 5),
    "大寒": (3, 9, 6),
    "立春": (8, 5, 2),
    "雨水": (9, 6, 3),
    "惊蛰": (1, 7, 4),
    "春分": (3, 9, 6),
    "清明": (4, 1, 7),
    "谷雨": (5, 2, 8),
    "立夏": (4, 1, 7),
    "小满": (5, 2, 8),
    "芒种": (6, 3, 9),
    "夏至": (9, 3, 6),
    "小暑": (8, 2, 5),
    "大暑": (7, 1, 4),
    "立秋": (2, 5, 8),
    "处暑": (1, 4, 7),
    "白露": (9, 3, 6),
    "秋分": (7, 1, 4),
    "寒露": (6, 9, 3),
    "霜降": (5, 8, 2),
    "立冬": (6, 9, 3),
    "小雪": (5, 8, 2),
    "大雪": (4, 7, 1),
}

JuMethod = Literal["zhirun", "chaibu", "maoshan"]


class JuDecision(TypedDict):
    current_term: str
    yuan: str
    ju_number: int
    dun_type: Literal["阳遁", "阴遁"]
    method: JuMethod
    day_ganzhi: NotRequired[str]
    effective_date: NotRequired[str]
    elapsed_days: NotRequired[float]


def qimen_day_key(day_number: int) -> str:
    year, month, day = gregorian_date_parts(day_number)
    label = f"{year:04d}" if 0 <= year <= 9999 else f"{year:+07d}"
    return f"{label}{month:02d}{day:02d}"


def next_term(name: str) -> str:
    if name not in QIMEN_ZHIRUN_TERM_SEQUENCE:
        raise ValueError(f"未知奇门节气：{name!r}")
    index = QIMEN_ZHIRUN_TERM_SEQUENCE.index(name)
    return QIMEN_ZHIRUN_TERM_SEQUENCE[(index + 1) % len(QIMEN_ZHIRUN_TERM_SEQUENCE)]


def qimen_futou_for_ganzhi(text: str) -> str:
    cycle_index = sexagenary_index_for(text)
    return sexagenary_text(cycle_index - cycle_index % 5)


def qimen_yuan_for_ganzhi(day_ganzhi: str) -> str:
    cycle_index = sexagenary_index_for(day_ganzhi) % 15
    if cycle_index < 5:
        return "上元"
    if cycle_index < 10:
        return "中元"
    return "下元"


def ju_number_for_term(*, current_term: str, yuan: str) -> int:
    table = QIMEN_JU_BY_TERM.get(current_term)
    if not table:
        raise ValueError(f"未知奇门定局节气：{current_term!r}")
    return table[{"上元": 0, "中元": 1, "下元": 2}[yuan]]


def zhirun_calendar_anchors(year: int, timezone_name: str) -> tuple[SolarTerm, ...]:
    """Fetch previous Daxue, current Mangzhong, and current Daxue for one year."""
    anchors = tuple(
        term
        for source_year, index in ((year - 1, 22), (year, 10), (year, 22))
        for term in _solar_terms_for_context_year(
            source_year,
            timezone_name,
            _solar_term_source_year(source_year, year),
            term_index=index,
        )
    )
    for term in anchors:
        if not term.has_defined_local_clock:
            raise ParameterError(
                f"unresolved local time：时区规则未定义奇门置闰锚点{term.name}的当地日序。",
                [{"path": "request", "code": "unresolved_timezone_offset"}],
            )
    return anchors


@lru_cache(maxsize=16)
def build_zhirun_schedule(
    previous_daxue: tuple[int, str],
    mangzhong_start_day: int,
    current_daxue_start_day: int,
) -> dict[str, tuple[str, str]]:
    """Single-year Zhirun schedule builder retained for direct seed-cache testing."""
    return build_continuous_zhirun_schedule(
        (previous_daxue,), ((mangzhong_start_day, current_daxue_start_day),)
    )


@lru_cache(maxsize=32)
def build_continuous_zhirun_schedule(
    initial_daxue: tuple[tuple[int, str]],
    yearly_anchors: tuple[tuple[int, int], ...],
) -> dict[str, tuple[str, str]]:
    """Continuous multi-year Zhirun state machine carrying intercalations across years.

    Every 15-day solar term block stays locked to the sexagenary Futou cycle.
    Intercalations (置闰) repeat 芒种 or 大雪 when the astronomical term falls
    at least 8 days after the start of the running Qimen 芒种/大雪 block; any
    resultant carry-over propagates seamlessly across year boundaries.
    """
    result: dict[str, tuple[str, str]] = {}
    prev_dx_ord, prev_dx_gz = initial_daxue[0]
    dx_idx = sexagenary_index_for(prev_dx_gz)
    futou_idx = (dx_idx // 15) * 15
    cur_ord = prev_dx_ord - (dx_idx - futou_idx)
    rz_idx = futou_idx

    def emit_term(term_name: str) -> int:
        nonlocal cur_ord, rz_idx
        start_ord = cur_ord
        for _ in range(15):
            result[qimen_day_key(cur_ord)] = (term_name, sexagenary_text(rz_idx))
            cur_ord += 1
            rz_idx = (rz_idx + 1) % 60
        return start_ord

    first_start = emit_term("大雪")
    if prev_dx_ord - first_start >= QIMEN_ZHIRUN_MIN_LEAD_DAYS:
        emit_term("大雪")

    term = "冬至"
    for mangzhong_ord, daxue_ord in yearly_anchors:
        while True:
            term_start = emit_term(term)
            if (
                term == "芒种"
                and mangzhong_ord - term_start >= QIMEN_ZHIRUN_MIN_LEAD_DAYS
            ):
                emit_term("芒种")
            elif (
                term == "大雪" and daxue_ord - term_start >= QIMEN_ZHIRUN_MIN_LEAD_DAYS
            ):
                emit_term("大雪")
            if term == "立春" and cur_ord > daxue_ord:
                term = next_term(term)
                break
            term = next_term(term)
    return result


def build_zhirun_map(year: int, timezone_name: str) -> dict[str, tuple[str, str]]:
    """Build a continuous Zhirun schedule covering `year` with multi-year state."""
    start_year = max(1, year - QIMEN_CONTINUOUS_LOOKBACK_YEARS)
    first_prev_dx, _, _ = zhirun_calendar_anchors(start_year, timezone_name)
    yearly_anchors = tuple(
        (mz.calendar.local_ordinal, dx.calendar.local_ordinal)
        for y in range(start_year, year + 1)
        for _, mz, dx in (zhirun_calendar_anchors(y, timezone_name),)
    )
    return build_continuous_zhirun_schedule(
        ((first_prev_dx.calendar.local_ordinal, first_prev_dx.day_ganzhi),),
        yearly_anchors,
    )


def resolve_effective_ganzhi(seed: MetaphysicsSeed) -> tuple[str, str]:
    year, month, day = seed.clock.date_parts
    hour, _, _, _ = seed.clock.time_parts
    if hour != 23:
        return ganzhi_text(seed.pillars["day"]), ganzhi_text(seed.pillars["hour"])

    day_pillar = BaZiCalendar.calculate_day_pillar(
        *resolve_bazi_effective_date(year, month, day, hour),
    )
    hour_pillar = BaZiCalendar.calculate_hour_pillar(year, month, day, hour)
    return ganzhi_text(day_pillar), ganzhi_text(hour_pillar)


def resolve_ju_decision(seed: MetaphysicsSeed, ju_method: JuMethod) -> JuDecision:
    """Resolve current Qimen Ju (遁型/局数/三元/节气) under zhirun, chaibu, or maoshan."""
    day_ganzhi, _ = resolve_effective_ganzhi(seed)
    if ju_method == "zhirun":
        target_day_number = seed.clock.ordinal
        hour, _, _, _ = seed.clock.time_parts
        if hour == 23:
            target_day_number += 1
        target_key = qimen_day_key(target_day_number)
        yinyangdun_map = build_zhirun_map(seed.input_datetime.year, seed.timezone)
        if target_key not in yinyangdun_map:
            raise ValueError("无法确定置闰局，不以月份、日支或时支凑局数")
        resolved_term, resolved_day_ganzhi = yinyangdun_map[target_key]
        if resolved_day_ganzhi != day_ganzhi:
            raise ValueError("置闰历表与有效日柱不一致，不能继续起局")
        yuan = qimen_yuan_for_ganzhi(day_ganzhi)
        return {
            "current_term": resolved_term,
            "day_ganzhi": day_ganzhi,
            "yuan": yuan,
            "ju_number": ju_number_for_term(current_term=resolved_term, yuan=yuan),
            "dun_type": "阳遁" if resolved_term in QIMEN_YANG_TERMS else "阴遁",
            "effective_date": target_key,
            "method": "zhirun",
        }

    current_term_info = seed.calendar_context["current_solar_term"]
    current_term = current_term_info["name"]
    if current_term not in QIMEN_JU_BY_TERM:
        raise ValueError(f"无法确定{ju_method}定局的实际节气")

    if ju_method == "chaibu":
        yuan = qimen_yuan_for_ganzhi(day_ganzhi)
        return {
            "current_term": current_term,
            "yuan": yuan,
            "ju_number": ju_number_for_term(current_term=current_term, yuan=yuan),
            "dun_type": "阳遁" if current_term in QIMEN_YANG_TERMS else "阴遁",
            "method": "chaibu",
        }

    if ju_method == "maoshan":
        delta_days = _maoshan_elapsed_days(seed, current_term_info)
        yuan = "上元" if delta_days < 5.0 else ("中元" if delta_days < 10.0 else "下元")
        return {
            "current_term": current_term,
            "yuan": yuan,
            "ju_number": ju_number_for_term(current_term=current_term, yuan=yuan),
            "dun_type": "阳遁" if current_term in QIMEN_YANG_TERMS else "阴遁",
            "elapsed_days": round(delta_days, 4),
            "method": "maoshan",
        }

    raise ValueError(f"不支持的奇门定局法：{ju_method!r}")


def _maoshan_elapsed_days(seed: MetaphysicsSeed, current_term_info: dict) -> float:
    """Compute exact elapsed days since astronomical current solar term for Maoshan."""
    delta = seed.calendar_context.get("solar_term_delta") or {}
    if isinstance(delta.get("days_since_current"), (int, float)):
        return float(delta["days_since_current"])
    at_utc = utc_calendar(seed.input_datetime)
    term_iso = current_term_info.get("datetime_with_offset") or current_term_info.get(
        "datetime_utc"
    )
    if isinstance(term_iso, str):
        from fatebridge.utils.civil_time import ZonedCalendar

        term_utc = ZonedCalendar.from_isoformat(term_iso).utc
        return float(at_utc.julian_day_exact() - term_utc.julian_day_exact())
    raise ValueError("茅山法需要当前节气精确时刻")
