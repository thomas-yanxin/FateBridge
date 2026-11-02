"""
Qi Men Dun Jia (奇门遁甲) board construction for the FateBridge metaphysics package.

Time Qimen with explicit ju method, shared rotation and centre hosting.
Source scopes and derivation evidence are in core.qimen_evidence.
"""

from __future__ import annotations

import re
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fatebridge.core.metaphysics.qimen_calendar_tables import QIMEN_FUHEAD_HEAVEN_STEM

from ..almanac import (
    DAY_GANZHI_STRATEGY_STANDARD,
    _solar_terms_for_context_year,
    get_jieqi_year_grid,
    localize_datetime,
)
from ..calendar import BaZiCalendar, resolve_bazi_effective_date
from ..divination import build_hexagram
from ..qimen_profiles import (
    DEFAULT_GOD_PROFILE,
    DEFAULT_SEASON_PROFILE,
    GOD_PROFILES,
    validate_profiles,
)
from ..solar_model_policy import solar_context_input_years
from .common import (
    MetaphysicsSeed,
    ganzhi_text,
    kongwang_for_ganzhi,
    sexagenary_index_for,
    sexagenary_text,
    xun_head_for_ganzhi,
)

QIMEN_SAN_YUAN_FU_TOU = (
    "甲子",
    "甲午",
    "甲寅",
    "甲申",
    "甲辰",
    "甲戌",
    "己卯",
    "己酉",
    "己巳",
    "己亥",
    "己丑",
    "己未",
)


QIMEN_SAN_YUAN_FU_TOU_SET = set(QIMEN_SAN_YUAN_FU_TOU)


QIMEN_PALACES: List[Dict[str, Any]] = [
    {"index": 1, "label": "坎一宫", "trigram": "坎"},
    {"index": 2, "label": "坤二宫", "trigram": "坤"},
    {"index": 3, "label": "震三宫", "trigram": "震"},
    {"index": 4, "label": "巽四宫", "trigram": "巽"},
    {"index": 5, "label": "中五宫", "trigram": "中"},
    {"index": 6, "label": "乾六宫", "trigram": "乾"},
    {"index": 7, "label": "兑七宫", "trigram": "兑"},
    {"index": 8, "label": "艮八宫", "trigram": "艮"},
    {"index": 9, "label": "离九宫", "trigram": "离"},
]


QIMEN_CN_NUMBERS = tuple("一二三四五六七八九")


QIMEN_GUA_SEQUENCE = ("坎", "坤", "震", "巽", "中", "乾", "兑", "艮", "离")


QIMEN_CLOCKWISE_GUA_SEQUENCE = ("坎", "艮", "震", "巽", "离", "坤", "兑", "乾")


QIMEN_DOOR_RING = ("休", "生", "伤", "杜", "景", "死", "惊", "开")


QIMEN_JIU_XING_RING = ("蓬", "芮", "冲", "辅", "禽", "心", "柱", "任", "英")


QIMEN_DOOR_ROUTE = ("休", "死", "伤", "杜", "中", "开", "惊", "生", "景")


QIMEN_STAR_DISPLAY = {
    "蓬": "天蓬",
    "任": "天任",
    "冲": "天冲",
    "辅": "天辅",
    "英": "天英",
    "芮": "天芮",
    "禽": "天禽",
    "柱": "天柱",
    "心": "天心",
}


QIMEN_DOOR_DISPLAY = {
    "休": "休门",
    "生": "生门",
    "伤": "伤门",
    "杜": "杜门",
    "景": "景门",
    "死": "死门",
    "惊": "惊门",
    "开": "开门",
}


QIMEN_STAR_CODE_BY_DISPLAY: Dict[Any, str] = {
    value: key for key, value in QIMEN_STAR_DISPLAY.items()
}


QIMEN_DOOR_CODE_BY_DISPLAY: Dict[Any, str] = {
    value: key for key, value in QIMEN_DOOR_DISPLAY.items()
}


QIMEN_GOD_DISPLAY = {
    "符": "值符",
    "蛇": "螣蛇",
    "阴": "太阴",
    "合": "六合",
    "虎": "白虎",
    "玄": "玄武",
    "地": "九地",
    "天": "九天",
}


QIMEN_DOOR_TO_TRIGRAM: Dict[Any, str] = {
    "休门": "坎",
    "生门": "艮",
    "伤门": "震",
    "杜门": "巽",
    "景门": "离",
    "死门": "坤",
    "惊门": "兑",
    "开门": "乾",
    "中门": "坤",
}


QIMEN_YANG_TERMS = {
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


QIMEN_JU_BY_TERM = {
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


QIMEN_ZHIRUN_TERM_SEQUENCE = (
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


QIMEN_GUA_BY_NUMERAL = dict(zip(QIMEN_CN_NUMBERS, QIMEN_GUA_SEQUENCE))


QIMEN_JIU_XING_BY_NUMERAL = dict(zip(QIMEN_CN_NUMBERS, QIMEN_JIU_XING_RING))


QIMEN_DOOR_ROUTE_BY_NUMERAL = dict(zip(QIMEN_CN_NUMBERS, QIMEN_DOOR_ROUTE))


QIMEN_EARTH_PLATE_YANG = tuple("戊己庚辛壬癸丁丙乙")


def qimen_futou_for_ganzhi(text: str) -> str:
    cycle_index = sexagenary_index_for(text)
    for offset in range(60):
        candidate = sexagenary_text(cycle_index - offset)
        if candidate in QIMEN_SAN_YUAN_FU_TOU_SET:
            return candidate
    return xun_head_for_ganzhi(text)


def _qimen_new_list(values: Iterable[str], start_value: str) -> List[str]:
    ordered = list(values)
    if start_value not in ordered:
        return ordered
    start_index = ordered.index(start_value)
    return ordered[start_index:] + ordered[:start_index]


def _qimen_rotate_gua_sequence(yinyang: str) -> Tuple[str, ...]:
    if yinyang == "阴":
        return tuple(reversed(QIMEN_CLOCKWISE_GUA_SEQUENCE))
    return QIMEN_CLOCKWISE_GUA_SEQUENCE


def _qimen_key_to_day_number(key: str) -> int:
    if len(key or "") != 8:
        raise ValueError(f"Invalid qimen day key: {key!r}")
    year = int(key[0:4])
    month = int(key[4:6])
    day = int(key[6:8])
    return datetime(year, month, day).date().toordinal()


def _qimen_day_number_to_key(day_number: int) -> str:
    return datetime.fromordinal(day_number).strftime("%Y%m%d")


def _qimen_next_term(name: str) -> str:
    if name not in QIMEN_ZHIRUN_TERM_SEQUENCE:
        raise ValueError(f"未知奇门节气：{name!r}")
    index = QIMEN_ZHIRUN_TERM_SEQUENCE.index(name)
    return QIMEN_ZHIRUN_TERM_SEQUENCE[(index + 1) % len(QIMEN_ZHIRUN_TERM_SEQUENCE)]


def _qimen_build_year_term_seed(
    year: int,
    timezone_name: str,
    context_year: Optional[int] = None,
) -> Dict[str, Dict[str, str]]:
    low, high = solar_context_input_years(
        context_year if context_year is not None else year
    )
    # An input's previous Daxue can belong to the private guard year. Fetch
    # fresh source-validated terms before using any derived schedule cache.
    grid = (
        [
            t.as_dict()
            for t in _solar_terms_for_context_year(year, timezone_name, context_year)
        ]
        if context_year is not None
        and low <= context_year <= high
        and not low <= year <= high
        else get_jieqi_year_grid(year, timezone_name)
    )
    return {
        item["name"]: {
            "term": item["name"],
            "date_key": item["date_key"],
            "day_ganzhi": item["day_ganzhi"],
        }
        for item in grid
        if item.get("name")
    }


def _qimen_build_yinyangdun_map(
    year: int,
    timezone_name: str,
) -> Dict[str, Tuple[str, str]]:
    previous_year = _qimen_build_year_term_seed(year - 1, timezone_name, year)
    current_year = _qimen_build_year_term_seed(year, timezone_name, year)
    # The schedule depends on these exact civil dates and day names. A model
    # or data change must be checked by the almanac before a cached schedule
    # may be reused, even when both models happen to yield identical dates.
    return _qimen_build_yinyangdun_map_from_seeds(
        tuple(
            (n, v["date_key"], v["day_ganzhi"])
            for n, v in sorted(previous_year.items())
        ),
        tuple(
            (n, v["date_key"], v["day_ganzhi"]) for n, v in sorted(current_year.items())
        ),
    )


@lru_cache(maxsize=16)
def _qimen_build_yinyangdun_map_from_seeds(
    previous_seed: Tuple[Tuple[str, str, str], ...],
    current_seed: Tuple[Tuple[str, str, str], ...],
) -> Dict[str, Tuple[str, str]]:
    previous_year = {
        n: {"term": n, "date_key": d, "day_ganzhi": g} for n, d, g in previous_seed
    }
    current_year = {
        n: {"term": n, "date_key": d, "day_ganzhi": g} for n, d, g in current_seed
    }
    if (
        not previous_year
        or not current_year
        or "大雪" not in previous_year
        or "芒种" not in current_year
        or "大雪" not in current_year
    ):
        return {}

    result: Dict[str, Tuple[str, str]] = {}

    previous_daxue = previous_year["大雪"]
    daxue_start_key = previous_daxue["date_key"]
    daxue_day_ganzhi = previous_daxue["day_ganzhi"]
    daxue_index = sexagenary_index_for(daxue_day_ganzhi)
    futou_index = (daxue_index // 15) * 15
    current_day_number = _qimen_key_to_day_number(daxue_start_key)
    rizhu_index = daxue_index

    for _ in range(daxue_index, futou_index + 15):
        result[_qimen_day_number_to_key(current_day_number)] = (
            "大雪",
            sexagenary_text(rizhu_index),
        )
        current_day_number += 1
        rizhu_index = (rizhu_index + 1) % 60

    # One convention throughout the schedule: a civil-date lead of nine days
    # triggers intercalation. Annual initialization and both later tests must
    # agree, or the same January date changes ju when the cache year changes.
    current_term = "大雪" if daxue_index - futou_index >= 9 else "冬至"
    term_days = 0
    mangzhong_day_number: Optional[int] = None

    for _ in range(300):
        result[_qimen_day_number_to_key(current_day_number)] = (
            current_term,
            sexagenary_text(rizhu_index),
        )
        current_day_number += 1
        rizhu_index = (rizhu_index + 1) % 60
        term_days += 1
        if term_days == 15:
            term_days = 0
            current_term = _qimen_next_term(current_term)
            if current_term == "芒种":
                mangzhong_day_number = current_day_number
                for _ in range(15):
                    result[_qimen_day_number_to_key(current_day_number)] = (
                        current_term,
                        sexagenary_text(rizhu_index),
                    )
                    current_day_number += 1
                    rizhu_index = (rizhu_index + 1) % 60
                break

    mangzhong_start_day = _qimen_key_to_day_number(
        current_year["芒种"].get("date_key") or ""
    )
    current_term = (
        "芒种"
        if (
            mangzhong_day_number is not None
            and mangzhong_start_day >= mangzhong_day_number + 9
        )
        else "夏至"
    )
    term_days = 0
    daxue_day_number: Optional[int] = None

    for _ in range(300):
        result[_qimen_day_number_to_key(current_day_number)] = (
            current_term,
            sexagenary_text(rizhu_index),
        )
        current_day_number += 1
        rizhu_index = (rizhu_index + 1) % 60
        term_days += 1
        if term_days == 15:
            term_days = 0
            current_term = _qimen_next_term(current_term)
            if current_term == "大雪":
                daxue_day_number = current_day_number
                for _ in range(15):
                    result[_qimen_day_number_to_key(current_day_number)] = (
                        current_term,
                        sexagenary_text(rizhu_index),
                    )
                    current_day_number += 1
                    rizhu_index = (rizhu_index + 1) % 60
                break

    current_daxue_start_day = _qimen_key_to_day_number(
        current_year["大雪"].get("date_key") or ""
    )
    current_term = (
        "大雪"
        if (
            daxue_day_number is not None
            and current_daxue_start_day >= daxue_day_number + 9
        )
        else "冬至"
    )
    term_days = 0

    for _ in range(300):
        result[_qimen_day_number_to_key(current_day_number)] = (
            current_term,
            sexagenary_text(rizhu_index),
        )
        current_day_number += 1
        rizhu_index = (rizhu_index + 1) % 60
        term_days += 1
        if term_days == 15:
            term_days = 0
            current_term = _qimen_next_term(current_term)
            if current_term == "立春":
                result[_qimen_day_number_to_key(current_day_number)] = (
                    current_term,
                    sexagenary_text(rizhu_index),
                )
                break

    return result


def _qimen_effective_ganzhi(seed: MetaphysicsSeed) -> Tuple[str, str]:
    # 晚子时 (23:00-23:59) 翻日规则现已由 BaZiCalendar 统一处理：
    # - calculate_hour_pillar 会把 23 时的 day stem 对齐到次日
    # - get_four_pillars 的 day pillar 同样已翻日
    # 所以只要 seed.pillars 是走 get_four_pillars 得到的，就与 Qimen 预期一致，
    # 这里不再需要手动 +1 天。
    local_datetime = localize_datetime(seed.corrected_datetime, seed.timezone)
    if local_datetime.hour != 23:
        return ganzhi_text(seed.pillars["day"]), ganzhi_text(seed.pillars["hour"])

    day_pillar = BaZiCalendar.calculate_day_pillar(
        *resolve_bazi_effective_date(
            local_datetime.year,
            local_datetime.month,
            local_datetime.day,
            local_datetime.hour,
        ),
        strategy=DAY_GANZHI_STRATEGY_STANDARD,
    )
    hour_pillar = BaZiCalendar.calculate_hour_pillar(
        local_datetime.year,
        local_datetime.month,
        local_datetime.day,
        local_datetime.hour,
        day_pillar_strategy=DAY_GANZHI_STRATEGY_STANDARD,
    )
    return ganzhi_text(day_pillar), ganzhi_text(hour_pillar)


def _qimen_resolve_zhirun_meta(
    *,
    seed: MetaphysicsSeed,
) -> Dict[str, Any]:
    local_datetime = localize_datetime(seed.corrected_datetime, seed.timezone)
    target_day_number = _qimen_key_to_day_number(local_datetime.strftime("%Y%m%d"))
    if local_datetime.hour == 23:
        target_day_number += 1
    target_key = _qimen_day_number_to_key(target_day_number)
    # The annual map already covers previous Daxue through next Lichun.
    # Corrected-clock or late-Zi rollover can cross a year without changing
    # the civil input year that authorizes the selected solar model.
    context_year = localize_datetime(seed.input_datetime, seed.timezone).year
    yinyangdun_map = _qimen_build_yinyangdun_map(context_year, seed.timezone)
    if target_key not in yinyangdun_map:
        raise ValueError("无法确定置闰局，不以月份、日支或时支凑局数")
    resolved_term, resolved_day_ganzhi = yinyangdun_map[target_key]
    effective_day_ganzhi, _ = _qimen_effective_ganzhi(seed)
    if resolved_day_ganzhi != effective_day_ganzhi:
        raise ValueError("置闰历表与有效日柱不一致，不能继续起局")
    ju_day_ganzhi = resolved_day_ganzhi
    yuan = _qimen_find_yuan(ju_day_ganzhi)
    ju_number = _qimen_ju_number_for_term(
        current_term=resolved_term,
        yuan=yuan,
    )
    dun_type = "阳遁" if resolved_term in QIMEN_YANG_TERMS else "阴遁"
    return {
        "current_term": resolved_term,
        "day_ganzhi": ju_day_ganzhi,
        "yuan": yuan,
        "ju_number": ju_number,
        "dun_type": dun_type,
        "effective_date": target_key,
        "method": "zhirun",
    }


def _qimen_find_yuan(day_ganzhi: str) -> str:
    cycle_index = sexagenary_index_for(day_ganzhi) % 15
    if cycle_index < 5:
        return "上元"
    if cycle_index < 10:
        return "中元"
    return "下元"


def _qimen_ju_number_for_term(
    *,
    current_term: str,
    yuan: str,
) -> int:
    table = QIMEN_JU_BY_TERM.get(current_term)
    if not table:
        raise ValueError(f"未知奇门定局节气：{current_term!r}")
    yuan_index = {"上元": 0, "中元": 1, "下元": 2}[yuan]
    return table[yuan_index]


def _qimen_build_ju_text(dun_type: str, ju_number: int, yuan: str) -> str:
    if dun_type not in {"阳遁", "阴遁"} or yuan not in {"上元", "中元", "下元"}:
        raise ValueError("未知奇门遁型或三元")
    if type(ju_number) is not int or not 1 <= ju_number <= 9:
        raise ValueError("奇门局数必须是1至9的整数")
    index = ju_number - 1
    return f"{dun_type}{QIMEN_CN_NUMBERS[index]}局{yuan}"


def _qimen_parse_meta(ju_text: str) -> Dict[str, str]:
    text = ju_text
    if not re.fullmatch(r"[阴阳]遁[一二三四五六七八九]局[上中下]元", text):
        raise ValueError(f"无效奇门局：{text!r}")
    return {
        "text": text,
        "yy": "阴" if "阴遁" in text else "阳",
        "kook": next((char for char in text if char in QIMEN_CN_NUMBERS), "一"),
        "yuan": "上元" if "上元" in text else ("中元" if "中元" in text else "下元"),
    }


def _qimen_resolve_special_zhishi(
    *, dun_type: str, current_term: Optional[str] = None
) -> str:
    """遁甲演义·时家奇门：天禽为直符时，死门为直使。"""
    return "死"


def _qimen_zhifu_zhishi(
    time_ganzhi: str,
    ju_text: str,
    *,
    dun_type: str,
    current_term: Optional[str] = None,
) -> Dict[str, str]:
    """Derive leaders from the actual earth plate, not a parallel lookup table.

    The star follows the hour stem (甲 follows its concealed 六仪); the door
    counts the elapsed hours of the xun through nine numeric palaces. Only
    after that count is the centre hosted in 坤. The native 天禽 identity stays.
    """
    meta = _qimen_parse_meta(ju_text)
    earth = _qimen_pan_earth(ju_text)
    reverse = {stem: palace for palace, stem in earth.items()}
    head = xun_head_for_ganzhi(time_ganzhi)
    hidden = QIMEN_FUHEAD_HEAVEN_STEM[head]
    origin = reverse[hidden]
    star = QIMEN_JIU_XING_BY_NUMERAL[QIMEN_CN_NUMBERS[QIMEN_GUA_SEQUENCE.index(origin)]]
    door = QIMEN_DOOR_ROUTE[QIMEN_GUA_SEQUENCE.index(origin)]
    if door == "中":
        door = "死"
    stem = hidden if time_ganzhi[0] == "甲" else time_ganzhi[0]
    raw_star_gong = reverse[stem]
    elapsed = sexagenary_index_for(time_ganzhi) % 10
    step = -1 if meta["yy"] == "阴" else 1
    raw_door_gong = QIMEN_GUA_SEQUENCE[
        (QIMEN_GUA_SEQUENCE.index(origin) + step * elapsed) % 9
    ]
    return {
        "xun_head": head,
        "zhifu_heaven_stem": hidden,
        "source_gong": origin,
        "star": star,
        "star_gong": "坤" if raw_star_gong == "中" else raw_star_gong,
        "raw_star_gong": raw_star_gong,
        "door": door,
        "door_gong": "坤" if raw_door_gong == "中" else raw_door_gong,
        "raw_door_gong": raw_door_gong,
        "dun_type": meta["yy"],
    }


def _qimen_pan_earth(ju_text: str) -> Dict[str, str]:
    meta = _qimen_parse_meta(ju_text)
    step = -1 if meta["yy"] == "阴" else 1
    start = QIMEN_CN_NUMBERS.index(meta["kook"])
    return {
        QIMEN_GUA_SEQUENCE[(start + step * offset) % 9]: stem
        for offset, stem in enumerate(QIMEN_EARTH_PLATE_YANG)
    }


def _qimen_rotation_origins(leader: Dict[str, str]) -> Dict[str, str]:
    """All eight star/stem pairs rotate together, in both yin and yang dun."""
    ring = QIMEN_CLOCKWISE_GUA_SEQUENCE
    source = "坤" if leader["source_gong"] == "中" else leader["source_gong"]
    offset = ring.index(leader["star_gong"]) - ring.index(source)
    return {ring[(index + offset) % 8]: palace for index, palace in enumerate(ring)}


def _qimen_build_palaces(
    *,
    time_ganzhi: str,
    ju_text: str,
    dun_type: str,
    current_term: str,
    god_profile: str = DEFAULT_GOD_PROFILE,
) -> List[Dict[str, Any]]:
    validate_profiles(god_profile, DEFAULT_SEASON_PROFILE)
    earth = _qimen_pan_earth(ju_text)
    leader = _qimen_zhifu_zhishi(
        time_ganzhi, ju_text, dun_type=dun_type, current_term=current_term
    )
    origins = _qimen_rotation_origins(leader)
    ring = QIMEN_CLOCKWISE_GUA_SEQUENCE
    door_source = QIMEN_DOOR_TO_TRIGRAM[QIMEN_DOOR_DISPLAY[leader["door"]]]
    door_offset = ring.index(leader["door_gong"]) - ring.index(door_source)
    doors = {
        ring[(index + door_offset) % 8]: QIMEN_DOOR_RING[index] for index in range(8)
    }
    god_route = _qimen_new_list(
        _qimen_rotate_gua_sequence(leader["dun_type"]), leader["star_gong"]
    )
    gods = dict(zip(god_route, GOD_PROFILES[god_profile]["sequence"]))
    god_indices = {trigram: index for index, trigram in enumerate(god_route)}
    palaces: List[Dict[str, Any]] = []
    for palace in QIMEN_PALACES:
        trigram = palace["trigram"]
        center = trigram == "中"
        origin = origins.get(trigram)
        star_code = (
            QIMEN_JIU_XING_RING[QIMEN_GUA_SEQUENCE.index(origin)] if origin else None
        )
        sky_stems = [earth[origin]] if origin else []
        if origin == "坤":
            sky_stems.append(earth["中"])
        earth_stems = [earth[trigram]]
        if trigram == "坤":
            earth_stems.append(earth["中"])
        door = None if center else QIMEN_DOOR_DISPLAY[doors[trigram]]
        hexagram = (
            build_hexagram(upper_name=trigram, lower_name=QIMEN_DOOR_TO_TRIGRAM[door])
            if door
            else None
        )
        palaces.append(
            {
                "name": palace["label"],
                "index": palace["index"],
                "trigram": trigram,
                "content_palace": palace["label"],
                "content_trigram": trigram,
                "heaven_origin_trigram": origin,
                "heaven_stem": sky_stems[0] if sky_stems else None,
                "heaven_stems": sky_stems,
                "earth_stem": earth[trigram],
                "earth_stems": earth_stems,
                "god": None if center else gods[trigram],
                "god_sequence_index": None if center else god_indices[trigram],
                "door": door,
                "star": QIMEN_STAR_DISPLAY[star_code] if star_code else None,
                "hosted_stars": ["天禽"] if origin == "坤" else [],
                "door_hexagram": (
                    {"name": hexagram["name"], "binary_code": hexagram["binary_code"]}
                    if hexagram
                    else None
                ),
            }
        )
    return palaces


def build_qimen_board(
    seed: MetaphysicsSeed,
    *,
    ju_method: str = "zhirun",
    god_profile: str = DEFAULT_GOD_PROFILE,
    season_profile: str = DEFAULT_SEASON_PROFILE,
) -> Dict[str, Any]:
    validate_profiles(god_profile, season_profile)
    current_term_info = seed.calendar_context["current_solar_term"]
    current_term = current_term_info["name"]
    day_ganzhi, time_ganzhi = _qimen_effective_ganzhi(seed)
    # 时家奇门的符头与三元都应从当前日干支回推，不应直接借用节气元数据里的日柱。
    fu_tou = qimen_futou_for_ganzhi(day_ganzhi)
    if ju_method == "zhirun":
        ju_meta = _qimen_resolve_zhirun_meta(seed=seed)
    elif ju_method == "chaibu":
        yuan = _qimen_find_yuan(day_ganzhi)
        if current_term not in QIMEN_JU_BY_TERM:
            raise ValueError("无法确定拆补局的实际节气")
        ju_meta = {
            "current_term": current_term,
            "yuan": yuan,
            "ju_number": QIMEN_JU_BY_TERM[current_term][
                {"上元": 0, "中元": 1, "下元": 2}[yuan]
            ],
            "dun_type": "阳遁" if current_term in QIMEN_YANG_TERMS else "阴遁",
            "method": "chaibu",
        }
    else:
        raise ValueError(f"不支持的奇门定局法：{ju_method!r}")
    current_term = ju_meta["current_term"]
    dun_type = ju_meta["dun_type"]
    yuan = ju_meta["yuan"]
    ju_number = ju_meta["ju_number"]
    ju_text = _qimen_build_ju_text(dun_type, ju_number, yuan)
    zfzs = _qimen_zhifu_zhishi(
        time_ganzhi,
        ju_text,
        dun_type=dun_type,
        current_term=current_term,
    )
    xun_head = xun_head_for_ganzhi(time_ganzhi)
    kongwang = kongwang_for_ganzhi(time_ganzhi)
    palaces = _qimen_build_palaces(
        time_ganzhi=time_ganzhi,
        ju_text=ju_text,
        dun_type=dun_type,
        current_term=current_term,
        god_profile=god_profile,
    )

    palace_map = {palace["trigram"]: palace for palace in palaces}
    zhifu_palace = palace_map[zfzs["star_gong"]]
    zhifu_star = QIMEN_STAR_DISPLAY[zfzs["star"]]
    zhifu_star_code = zfzs["star"]

    zhishi_palace = palace_map[zfzs["door_gong"]]
    if zhifu_star not in [zhifu_palace["star"], *zhifu_palace["hosted_stars"]]:
        raise ValueError("值符身份与九星盘不一致")
    if zhishi_palace["door"] != QIMEN_DOOR_DISPLAY[zfzs["door"]]:
        raise ValueError("值使身份与八门盘不一致")
    zhishi_door = zhishi_palace["door"]
    zhishi_door_code = QIMEN_DOOR_CODE_BY_DISPLAY.get(zhishi_door, zfzs["door"])

    fushi_hexagram = build_hexagram(
        upper_name=zhifu_palace["trigram"] if zhifu_palace["trigram"] != "中" else "坤",
        lower_name=QIMEN_DOOR_TO_TRIGRAM.get(zhishi_door, "坤"),
    )

    board = {
        "dun_type": dun_type,
        "ju_number": ju_number,
        "ju_text": ju_text,
        "yuan": yuan,
        "yuan_order": yuan,
        "fu_tou": fu_tou,
        "xun_head": xun_head,
        "kongwang": kongwang,
        "zhifu": {
            "star": zhifu_star,
            "palace": zhifu_palace["name"],
            "trigram": zhifu_palace["trigram"],
            "content_palace": zhifu_palace.get("content_palace", zhifu_palace["name"]),
            "content_trigram": zhifu_palace.get(
                "content_trigram", zhifu_palace["trigram"]
            ),
            "code": zhifu_star_code,
        },
        "zhishi": {
            "door": zhishi_door,
            "palace": zhishi_palace["name"],
            "trigram": zhishi_palace["trigram"],
            "content_palace": zhishi_palace.get(
                "content_palace", zhishi_palace["name"]
            ),
            "content_trigram": zhishi_palace.get(
                "content_trigram", zhishi_palace["trigram"]
            ),
            "code": zhishi_door_code,
        },
        "fushi_hexagram": {
            "name": fushi_hexagram["name"],
            "binary_code": fushi_hexagram["binary_code"],
        },
        "palaces": palaces,
    }
    from ..qimen_evidence import enrich_qimen_evidence

    board.update(
        {
            "layout": "direct",
            "ju_method": ju_method,
            "god_profile": god_profile,
            "season_profile": season_profile,
            "ju_decision": dict(ju_meta),
            "day_ganzhi": day_ganzhi,
            "time_ganzhi": time_ganzhi,
            "day_xun_head": xun_head_for_ganzhi(day_ganzhi),
            "day_kongwang": kongwang_for_ganzhi(day_ganzhi),
            "ju_term": current_term,
        }
    )
    return enrich_qimen_evidence(board, seed=seed, leader=zfzs)
