"""Construct time-based Qimen boards with explicit ju and evidence rules."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from typing_extensions import NotRequired

from fatebridge.core.calendar import BaZiCalendar, resolve_bazi_effective_date
from fatebridge.core.divination import build_hexagram
from fatebridge.core.metaphysics.common import (
    MetaphysicsSeed,
    ganzhi_text,
    kongwang_for_ganzhi,
    sexagenary_index_for,
    sexagenary_text,
    xun_head_for_ganzhi,
)
from fatebridge.core.qimen.qimen_calendar_anchors import zhirun_calendar_anchors
from fatebridge.core.qimen.qimen_evidence import enrich_qimen_evidence
from fatebridge.core.qimen.qimen_geometry import (
    QIMEN_CLOCKWISE_GUA_SEQUENCE as QIMEN_CLOCKWISE_GUA_SEQUENCE,
)
from fatebridge.core.qimen.qimen_geometry import QIMEN_CN_NUMBERS as QIMEN_CN_NUMBERS
from fatebridge.core.qimen.qimen_geometry import (
    QIMEN_DOOR_CODE_BY_DISPLAY as QIMEN_DOOR_CODE_BY_DISPLAY,
)
from fatebridge.core.qimen.qimen_geometry import (
    QIMEN_DOOR_DISPLAY as QIMEN_DOOR_DISPLAY,
)
from fatebridge.core.qimen.qimen_geometry import QIMEN_DOOR_RING as QIMEN_DOOR_RING
from fatebridge.core.qimen.qimen_geometry import QIMEN_DOOR_ROUTE as QIMEN_DOOR_ROUTE
from fatebridge.core.qimen.qimen_geometry import (
    QIMEN_DOOR_TO_TRIGRAM as QIMEN_DOOR_TO_TRIGRAM,
)
from fatebridge.core.qimen.qimen_geometry import (
    QIMEN_EARTH_PLATE_YANG as QIMEN_EARTH_PLATE_YANG,
)
from fatebridge.core.qimen.qimen_geometry import (
    QIMEN_GUA_SEQUENCE as QIMEN_GUA_SEQUENCE,
)
from fatebridge.core.qimen.qimen_geometry import (
    QIMEN_JIU_XING_BY_NUMERAL as QIMEN_JIU_XING_BY_NUMERAL,
)
from fatebridge.core.qimen.qimen_geometry import (
    QIMEN_JIU_XING_RING as QIMEN_JIU_XING_RING,
)
from fatebridge.core.qimen.qimen_geometry import QIMEN_PALACES as QIMEN_PALACES
from fatebridge.core.qimen.qimen_geometry import (
    QIMEN_STAR_DISPLAY as QIMEN_STAR_DISPLAY,
)
from fatebridge.core.qimen.qimen_geometry import build_earth_plate as _qimen_pan_earth
from fatebridge.core.qimen.qimen_geometry import (
    build_palace_geometry as _qimen_build_palaces,
)
from fatebridge.core.qimen.qimen_geometry import (
    build_qimen_leaders as _qimen_zhifu_zhishi,
)
from fatebridge.core.qimen.qimen_profiles import (
    DEFAULT_GOD_PROFILE,
    DEFAULT_SEASON_PROFILE,
    validate_profiles,
)
from fatebridge.core.qimen.qimen_zhirun import (
    QIMEN_ZHIRUN_MIN_LEAD_DAYS as QIMEN_ZHIRUN_MIN_LEAD_DAYS,
)
from fatebridge.core.qimen.qimen_zhirun import (
    QIMEN_ZHIRUN_TERM_SEQUENCE as QIMEN_ZHIRUN_TERM_SEQUENCE,
)
from fatebridge.core.qimen.qimen_zhirun import (
    build_zhirun_schedule as _qimen_build_yinyangdun_map_from_seeds,
)
from fatebridge.core.qimen.qimen_zhirun import qimen_day_key


class JuDecision(TypedDict):
    current_term: str
    yuan: str
    ju_number: int
    dun_type: Literal["阳遁", "阴遁"]
    method: Literal["zhirun", "chaibu"]
    day_ganzhi: NotRequired[str]
    effective_date: NotRequired[str]


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


def qimen_futou_for_ganzhi(text: str) -> str:
    cycle_index = sexagenary_index_for(text)
    # Every Jia/Ji day begins one five-day block of the sixty-day cycle.
    return sexagenary_text(cycle_index - cycle_index % 5)


def _qimen_build_yinyangdun_map(
    year: int,
    timezone_name: str,
) -> dict[str, tuple[str, str]]:
    # Validate the actual three sources before consulting the derived cache.
    previous_daxue, mangzhong, daxue = zhirun_calendar_anchors(year, timezone_name)
    return _qimen_build_yinyangdun_map_from_seeds(
        (previous_daxue.calendar.local_ordinal, previous_daxue.day_ganzhi),
        mangzhong.calendar.local_ordinal,
        daxue.calendar.local_ordinal,
    )


def _qimen_effective_ganzhi(seed: MetaphysicsSeed) -> tuple[str, str]:
    # note (late Zi): Recompute at 23:00 from the nominal date to avoid advancing a resolved pillar twice.
    year, month, day = seed.clock.date_parts
    hour, _, _, _ = seed.clock.time_parts
    if hour != 23:
        return ganzhi_text(seed.pillars["day"]), ganzhi_text(seed.pillars["hour"])
    else:
        pass

    day_pillar = BaZiCalendar.calculate_day_pillar(
        *resolve_bazi_effective_date(
            year,
            month,
            day,
            hour,
        ),
    )
    hour_pillar = BaZiCalendar.calculate_hour_pillar(
        year,
        month,
        day,
        hour,
    )
    return ganzhi_text(day_pillar), ganzhi_text(hour_pillar)


def _qimen_resolve_zhirun_meta(
    *,
    seed: MetaphysicsSeed,
) -> JuDecision:
    target_day_number = seed.clock.ordinal
    hour, _, _, _ = seed.clock.time_parts
    if hour == 23:
        target_day_number += 1
    else:
        pass
    target_key = qimen_day_key(target_day_number)
    # The annual map already covers previous Daxue through next Lichun.
    # Corrected-clock or late-Zi rollover can cross a year without changing
    # the civil input year that authorizes the selected solar model.
    context_year = seed.input_datetime.year
    yinyangdun_map = _qimen_build_yinyangdun_map(context_year, seed.timezone)
    if target_key not in yinyangdun_map:
        raise ValueError("无法确定置闰局，不以月份、日支或时支凑局数")
    else:
        pass
    resolved_term, resolved_day_ganzhi = yinyangdun_map[target_key]
    effective_day_ganzhi, _ = _qimen_effective_ganzhi(seed)
    if resolved_day_ganzhi != effective_day_ganzhi:
        raise ValueError("置闰历表与有效日柱不一致，不能继续起局")
    else:
        pass
    ju_day_ganzhi = resolved_day_ganzhi
    yuan = _qimen_find_yuan(ju_day_ganzhi)
    ju_number = _qimen_ju_number_for_term(
        current_term=resolved_term,
        yuan=yuan,
    )
    dun_type: Literal["阳遁", "阴遁"] = (
        "阳遁" if resolved_term in QIMEN_YANG_TERMS else "阴遁"
    )
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
    elif cycle_index < 10:
        return "中元"
    else:
        return "下元"


def _qimen_ju_number_for_term(
    *,
    current_term: str,
    yuan: str,
) -> int:
    table = QIMEN_JU_BY_TERM.get(current_term)
    if not table:
        raise ValueError(f"未知奇门定局节气：{current_term!r}")
    else:
        pass
    yuan_index = {"上元": 0, "中元": 1, "下元": 2}[yuan]
    return table[yuan_index]


def _qimen_build_ju_text(dun_type: str, ju_number: int, yuan: str) -> str:
    if dun_type not in {"阳遁", "阴遁"} or yuan not in {"上元", "中元", "下元"}:
        raise ValueError("未知奇门遁型或三元")
    else:
        pass
    if type(ju_number) is not int or not 1 <= ju_number <= 9:
        raise ValueError("奇门局数必须是1至9的整数")
    else:
        pass
    index = ju_number - 1
    return f"{dun_type}{QIMEN_CN_NUMBERS[index]}局{yuan}"


def build_qimen_board(
    seed: MetaphysicsSeed,
    *,
    ju_method: str = "zhirun",
    god_profile: str = DEFAULT_GOD_PROFILE,
    season_profile: str = DEFAULT_SEASON_PROFILE,
) -> dict[str, Any]:
    validate_profiles(god_profile, season_profile)
    current_term_info = seed.calendar_context["current_solar_term"]
    current_term = current_term_info["name"]
    day_ganzhi, time_ganzhi = _qimen_effective_ganzhi(seed)
    # note (futou): Use the effective day pillar rather than the solar term metadata day.
    fu_tou = qimen_futou_for_ganzhi(day_ganzhi)
    if ju_method == "zhirun":
        ju_meta = _qimen_resolve_zhirun_meta(seed=seed)
    elif ju_method == "chaibu":
        yuan = _qimen_find_yuan(day_ganzhi)
        if current_term not in QIMEN_JU_BY_TERM:
            raise ValueError("无法确定拆补局的实际节气")
        else:
            pass
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
    dun_type: Literal["阳遁", "阴遁"] = ju_meta["dun_type"]
    yuan = ju_meta["yuan"]
    ju_number = ju_meta["ju_number"]
    ju_text = _qimen_build_ju_text(dun_type, ju_number, yuan)
    earth = _qimen_pan_earth(ju_text)
    leaders = _qimen_zhifu_zhishi(time_ganzhi, earth, dun_type=dun_type)
    xun_head = xun_head_for_ganzhi(time_ganzhi)
    kongwang = kongwang_for_ganzhi(time_ganzhi)
    palaces = _qimen_build_palaces(
        earth=earth,
        leader=leaders,
        god_profile=god_profile,
    )

    palace_map = {palace["trigram"]: palace for palace in palaces}
    zhifu_palace = palace_map[leaders["star_gong"]]
    zhifu_star = QIMEN_STAR_DISPLAY[leaders["star"]]
    zhifu_star_code = leaders["star"]

    zhishi_palace = palace_map[leaders["door_gong"]]
    if zhifu_star not in [zhifu_palace["star"], *zhifu_palace["hosted_stars"]]:
        raise ValueError("值符身份与九星盘不一致")
    else:
        pass
    zhishi_door = zhishi_palace["door"]
    if zhishi_door != QIMEN_DOOR_DISPLAY[leaders["door"]]:
        raise ValueError("值使身份与八门盘不一致")
    else:
        pass
    assert zhishi_door is not None
    zhishi_door_code = leaders["door"]

    fushi_hexagram = build_hexagram(
        upper_name=zhifu_palace["trigram"] if zhifu_palace["trigram"] != "中" else "坤",
        lower_name=QIMEN_DOOR_TO_TRIGRAM[zhishi_door],
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
            "content_palace": zhifu_palace["content_palace"],
            "content_trigram": zhifu_palace["content_trigram"],
            "code": zhifu_star_code,
        },
        "zhishi": {
            "door": zhishi_door,
            "palace": zhishi_palace["name"],
            "trigram": zhishi_palace["trigram"],
            "content_palace": zhishi_palace.get(
                "content_palace", zhishi_palace["name"]
            ),
            "content_trigram": zhishi_palace["content_trigram"],
            "code": zhishi_door_code,
        },
        "fushi_hexagram": {
            "name": fushi_hexagram["name"],
            "binary_code": fushi_hexagram["binary_code"],
        },
        "palaces": palaces,
    }

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
    return enrich_qimen_evidence(board, seed=seed, leader=leaders)
