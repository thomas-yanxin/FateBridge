"""Heluo chart calculation, Yuantang placement, 12 sovereign hexagrams, and 60 Jiazi Nayin table."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from fatebridge.core.heluo.texts import (
    GAN,
    TRIGRAM_BITS,
    ZHI,
    _gua_name,
    _trigram_of,
    gua_lines,
    lines_to_gua,
)
from fatebridge.core.numerology.numerology_inputs import require_pillar_links
from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.data import get_nayin

YUANTANG_RULESET_ID = "heluo_yuantang_nlc_v1"
YANG_HOURS = list("子丑寅卯辰巳")
YIN_HOURS = list("午未申酉戌亥")
PURE_HOUR_TO_YAO = dict(
    zip(YANG_HOURS + YIN_HOURS, [1, 2, 3, 1, 2, 3, 4, 5, 6, 4, 5, 6])
)

LUOSHU_TRIGRAM: dict[int, str] = {
    1: "坎",
    2: "坤",
    3: "震",
    4: "巽",
    6: "乾",
    7: "兌",
    8: "艮",
    9: "離",
}
GAN_NUM: dict[str, int] = {
    "甲": 6,
    "乙": 2,
    "丙": 8,
    "丁": 7,
    "戊": 1,
    "己": 9,
    "庚": 3,
    "辛": 4,
    "壬": 6,
    "癸": 2,
}
ZHI_PAIR: dict[str, list[int]] = {
    "子": [1, 6],
    "亥": [1, 6],
    "寅": [3, 8],
    "卯": [3, 8],
    "巳": [7, 2],
    "午": [7, 2],
    "申": [9, 4],
    "酉": [9, 4],
    "辰": [5, 10],
    "戌": [5, 10],
    "丑": [5, 10],
    "未": [5, 10],
}
YANG_ZHI = frozenset({"子", "寅", "辰", "午", "申", "戌"})
ZHI_ZUN = frozenset({"坎為水", "水雷屯", "水山蹇"})
NAYIN_GENERATES = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
NAYIN_CONTROLS = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

# 元堂十二辟卦（十二消息卦）: month branch -> sovereign hexagram & waxing/waning phase.
TWELVE_SOVEREIGN_HEXAGRAMS: tuple[dict[str, Any], ...] = (
    {
        "month_branch": "子",
        "lunar_month": 11,
        "gua": "地雷復",
        "phase": "息",
        "yang_count": 1,
        "active_line": 1,
        "lines": [1, 0, 0, 0, 0, 0],
    },
    {
        "month_branch": "丑",
        "lunar_month": 12,
        "gua": "地澤臨",
        "phase": "息",
        "yang_count": 2,
        "active_line": 2,
        "lines": [1, 1, 0, 0, 0, 0],
    },
    {
        "month_branch": "寅",
        "lunar_month": 1,
        "gua": "地天泰",
        "phase": "息",
        "yang_count": 3,
        "active_line": 3,
        "lines": [1, 1, 1, 0, 0, 0],
    },
    {
        "month_branch": "卯",
        "lunar_month": 2,
        "gua": "雷天大壯",
        "phase": "息",
        "yang_count": 4,
        "active_line": 4,
        "lines": [1, 1, 1, 1, 0, 0],
    },
    {
        "month_branch": "辰",
        "lunar_month": 3,
        "gua": "澤天夬",
        "phase": "息",
        "yang_count": 5,
        "active_line": 5,
        "lines": [1, 1, 1, 1, 1, 0],
    },
    {
        "month_branch": "巳",
        "lunar_month": 4,
        "gua": "乾為天",
        "phase": "息",
        "yang_count": 6,
        "active_line": 6,
        "lines": [1, 1, 1, 1, 1, 1],
    },
    {
        "month_branch": "午",
        "lunar_month": 5,
        "gua": "天風姤",
        "phase": "消",
        "yang_count": 5,
        "active_line": 1,
        "lines": [0, 1, 1, 1, 1, 1],
    },
    {
        "month_branch": "未",
        "lunar_month": 6,
        "gua": "天山遯",
        "phase": "消",
        "yang_count": 4,
        "active_line": 2,
        "lines": [0, 0, 1, 1, 1, 1],
    },
    {
        "month_branch": "申",
        "lunar_month": 7,
        "gua": "天地否",
        "phase": "消",
        "yang_count": 3,
        "active_line": 3,
        "lines": [0, 0, 0, 1, 1, 1],
    },
    {
        "month_branch": "酉",
        "lunar_month": 8,
        "gua": "風地觀",
        "phase": "消",
        "yang_count": 2,
        "active_line": 4,
        "lines": [0, 0, 0, 0, 1, 1],
    },
    {
        "month_branch": "戌",
        "lunar_month": 9,
        "gua": "山地剝",
        "phase": "消",
        "yang_count": 1,
        "active_line": 5,
        "lines": [0, 0, 0, 0, 0, 1],
    },
    {
        "month_branch": "亥",
        "lunar_month": 10,
        "gua": "坤為地",
        "phase": "消",
        "yang_count": 0,
        "active_line": 6,
        "lines": [0, 0, 0, 0, 0, 0],
    },
)
_SOVEREIGN_BY_BRANCH: dict[str, dict[str, Any]] = {
    row["month_branch"]: row for row in TWELVE_SOVEREIGN_HEXAGRAMS
}
_SOVEREIGN_BY_GUA: dict[str, dict[str, Any]] = {
    row["gua"]: row for row in TWELVE_SOVEREIGN_HEXAGRAMS
}


@lru_cache(maxsize=1)
def sixty_jiazi_nayin_table() -> tuple[dict[str, Any], ...]:
    """Return the complete 60 Jiazi Nayin lookup table."""
    rows = []
    for idx in range(60):
        gz = GAN[idx % 10] + ZHI[idx % 12]
        nayin = get_nayin(gz[0], gz[1])
        rows.append(
            {
                "index": idx + 1,
                "ganzhi": gz,
                "nayin": nayin,
                "element": nayin[-1],
                "pair_index": idx // 2 + 1,
            }
        )
    return tuple(rows)


def assess_nayin_relation(natal_ganzhi: str, other_ganzhi: str) -> dict[str, Any]:
    """Compare two sexagenary pillars by 60-Jiazi Nayin element generation/control."""
    a = get_nayin(natal_ganzhi[0], natal_ganzhi[1])
    b = get_nayin(other_ganzhi[0], other_ganzhi[1])
    if "未知" in (a, b):
        raise ValueError("纳音吉凶评估须提供有效六十甲子干支。")
    ea, eb = a[-1], b[-1]
    if ea == eb:
        rel, level = "比和", "吉"
    elif NAYIN_GENERATES[eb] == ea:
        rel, level = "岁生本命", "吉"
    elif NAYIN_GENERATES[ea] == eb:
        rel, level = "本命生岁", "平吉"
    elif NAYIN_CONTROLS[eb] == ea:
        rel, level = "岁克本命", "凶"
    else:
        rel, level = "本命克岁", "平凶"
    return {
        "natal_ganzhi": natal_ganzhi,
        "natal_nayin": a,
        "natal_element": ea,
        "target_ganzhi": other_ganzhi,
        "target_nayin": b,
        "target_element": eb,
        "relation": rel,
        "auspiciousness": level,
    }


def yuantang_sovereign_status(chart: dict[str, Any], month_zhi: str) -> dict[str, Any]:
    """Assess chart hexagrams & Yuantang line against the 12 sovereign hexagrams."""
    month_sov = _SOVEREIGN_BY_BRANCH[month_zhi]
    xian_name = chart["xian"]["name"]
    hou_name = chart["hou"]["name"]
    yuan_pos = chart["xian"]["yuan"]
    yuan_yang = bool(chart["xian"]["lines"][yuan_pos - 1])
    phase_match = (month_sov["phase"] == "息" and yuan_yang) or (
        month_sov["phase"] == "消" and not yuan_yang
    )
    return {
        "month_branch": month_zhi,
        "month_sovereign": {
            "gua": month_sov["gua"],
            "phase": month_sov["phase"],
            "lunar_month": month_sov["lunar_month"],
            "active_line": month_sov["active_line"],
        },
        "xian_is_sovereign": xian_name in _SOVEREIGN_BY_GUA,
        "hou_is_sovereign": hou_name in _SOVEREIGN_BY_GUA,
        "yuantang_pos": yuan_pos,
        "yuantang_yang": yuan_yang,
        "phase_alignment": phase_match,
    }


def resolve_half_year(month_zhi: str, explicit: bool | None) -> tuple[bool | None, str]:
    """A sexagenary month pillar spans its Jie boundaries, not a solstice."""
    if month_zhi not in YANG_HOURS + YIN_HOURS:
        raise ValueError("月支须为十二地支。")
    if explicit is not None:
        if type(explicit) is not bool:
            raise ValueError("阴阳令须为布尔值，不能以字符串或数字代替。")
        return explicit, "explicit_half_year"
    if month_zhi in {"子", "午"}:
        return None, "boundary_month_unresolved"
    return month_zhi in "丑寅卯辰巳", "month_branch_half_year"


def yuantang_placement(
    lines: list[int], hour_zhi: str, is_male: bool, yang_ling: bool | None
) -> dict[str, Any]:
    """NLC Wenming Shuju Yuantang line placement by hour branch and half-year."""
    if (
        not isinstance(lines, list)
        or len(lines) != 6
        or any(type(b) is not int or b not in (0, 1) for b in lines)
    ):
        raise ValueError("元堂须输入自初至上的六个0/1整数。")
    if hour_zhi not in YANG_HOURS + YIN_HOURS:
        raise ValueError("元堂时支须为十二地支。")
    if type(is_male) is not bool or (
        yang_ling is not None and type(yang_ling) is not bool
    ):
        raise ValueError("元堂性别标志及阴阳令不得隐式强转。")
    yang_hour = hour_zhi in YANG_HOURS
    hours = YANG_HOURS if yang_hour else YIN_HOURS
    matching = [p for p, bit in enumerate(lines, 1) if bit == int(yang_hour)]
    other = [p for p in range(1, 7) if p not in matching]
    count = len(matching)
    direction = None
    if count in (0, 6):
        qian = lines[0] == 1
        needs_half = (qian and not is_male) or (not qian and is_male)
        if needs_half and yang_ling is None:
            raise ValueError("纯乾女命或纯坤男命的元堂须明确至点阴阳令。")
        reverse = (qian and not is_male and yang_ling is True) or (
            not qian and is_male and yang_ling is False
        )
        slots = [
            7 - PURE_HOUR_TO_YAO[h] if reverse else PURE_HOUR_TO_YAO[h] for h in hours
        ]
        direction = "descending" if reverse else "ascending"
        rule = "pure_qian" if qian else "pure_kun"
        pages = [30, 31] if qian else [31]
    else:
        slots = (matching + matching + other if count <= 3 else matching + other)[:6]
        rule = (
            "repeat_matching_then_borrow" if count <= 3 else "matching_once_then_borrow"
        )
        pages = {
            (True, 1): [26, 27],
            (False, 1): [27],
            (True, 2): [27],
            (False, 2): [28],
            (True, 3): [28],
            (False, 3): [28, 29],
            (True, 4): [29],
            (False, 4): [29],
            (True, 5): [29, 30],
            (False, 5): [30],
        }[(yang_hour, count)]
    index = hours.index(hour_zhi)
    return {
        "rule_id": rule,
        "hour_zhi": hour_zhi,
        "hour_half": "yang" if yang_hour else "yin",
        "hour_index": index + 1,
        "matching_positions": matching,
        "other_positions": other,
        "slot_positions": slots,
        "selected_pos": slots[index],
        "pure_direction": direction,
        "source_pdf_pages": pages,
    }


def yuantang_source_profile() -> dict[str, Any]:
    return {
        "ruleset_id": YUANTANG_RULESET_ID,
        "version": "1.0.0",
        "source_title": "河洛理數（上海文明書局印行本）卷一",
        "source_pdf_pages": [26, 27, 28, 29, 30, 31, 32],
    }


def _san_cai(lines: list[int]) -> list[str]:
    """下卦、下互(2-4)、上互(3-5)、上卦。"""
    return [
        _trigram_of(lines[0:3]),
        _trigram_of(lines[1:4]),
        _trigram_of(lines[2:5]),
        _trigram_of(lines[3:6]),
    ]


def _reduce_tian(t: int) -> int:
    v = t
    if v > 25:
        v -= 25
    if v == 25:
        return 5
    if v >= 10:
        u = v % 10
        return v // 10 if u == 0 else u
    return v


def _reduce_di(d: int) -> int:
    v = d
    if v > 30:
        v -= 30
    if v == 30:
        return 3
    if v >= 10:
        u = v % 10
        return v // 10 if u == 0 else u
    return v


def _wu_ji_gong(minguo_year: int, yang_gan: bool, is_male: bool) -> str:
    """五寄宫：弘治十七年1504上元甲子起，三元各六十年，180年循环。"""
    phase = ((minguo_year + 1911 - 1504) % 180) // 60
    if phase == 0:
        return "艮" if is_male else "坤"
    if phase == 1:
        ay = (yang_gan and is_male) or (not yang_gan and not is_male)
        return "艮" if ay else "坤"
    return "離" if is_male else "兌"


def _flip_line(lines: list[int], pos: int) -> list[int]:
    out = lines[:]
    out[pos - 1] = 1 - out[pos - 1]
    return out


def _swap_trigrams(lines: list[int]) -> list[int]:
    return lines[3:6] + lines[0:3]


def transform_houtian(
    xian_name: str,
    xian_lines: list[int],
    yuan: int,
    yang_ling: bool,
) -> dict[str, Any]:
    """变元堂，并按三至尊或常规换体 rules 得后天卦。"""
    if type(yang_ling) is not bool:
        raise ValueError("阴阳令须为布尔值，不能以字符串或数字代替。")
    if type(yuan) is not int or not 1 <= yuan <= 6:
        raise ValueError("元堂须为1至6的整数爻位。")
    if (
        not isinstance(xian_lines, list)
        or len(xian_lines) != 6
        or any(type(v) is not int or v not in (0, 1) for v in xian_lines)
    ):
        raise ValueError("后天换卦须输入自初至上的六个0/1整数。")
    if lines_to_gua(xian_lines)["name"] != xian_name:
        raise ValueError("先天卦名必须与六爻一致，不能据不一致的卦名选择特例。")
    flipped = _flip_line(xian_lines, yuan)
    if xian_name in ZHI_ZUN:
        bu_yi = (yuan == 5 and not yang_ling) or (yuan == 6 and yang_ling)
        if bu_yi:
            return {
                "name": lines_to_gua(flipped)["name"],
                "lines": flipped,
                "yuan": yuan,
            }
    hou_lines = _swap_trigrams(flipped)
    hou_yuan = yuan - 3 if yuan > 3 else yuan + 3
    return {
        "name": lines_to_gua(hou_lines)["name"],
        "lines": hou_lines,
        "yuan": hou_yuan,
    }


def four_pillar_number_totals(four_pillars: dict[str, str]) -> dict[str, Any]:
    """Compute Tian/Di sum arithmetic for four valid sexagenary pillars."""
    cycle = {GAN[i % 10] + ZHI[i % 12] for i in range(60)}
    if not isinstance(four_pillars, dict) or any(
        not isinstance(four_pillars.get(k), str) or four_pillars[k] not in cycle
        for k in ("year", "month", "day", "hour")
    ):
        raise ValueError("形式取数仍需要四个有效六十甲子。")
    tian = di = 0
    for key in ("year", "month", "day", "hour"):
        gz = four_pillars[key]
        gn = GAN_NUM[gz[0]]
        if gn % 2 == 1:
            tian += gn
        else:
            di += gn
        odd, even = ZHI_PAIR[gz[1]]
        tian += odd
        di += even
    return {
        "tian": tian,
        "di": di,
        "tianNum": _reduce_tian(tian),
        "diNum": _reduce_di(di),
        "scope": "formal_four_pillar_number_arithmetic_only; not_birth_chart_validation",
    }


def calculate(
    *,
    four_pillars: dict[str, str],
    gender: str,
    hour_zhi: str,
    birth_year: int,
    month_zhi: str,
    month_yang_ling: bool | None = None,
) -> dict[str, Any]:
    """Calculate Heluo natal chart: Tian/Di -> Xian/Hou hexagrams and Yuantang."""
    if not isinstance(gender, str) or normalize_gender(gender) not in {"男", "女"}:
        raise ValueError("河洛相荡、寄宫和元堂需要明确gender为男或女，不能默认性别。")
    if month_yang_ling is not None and type(month_yang_ling) is not bool:
        raise ValueError("阴阳令须为布尔值或None，不能以字符串或数字代替。")
    gender = normalize_gender(gender)
    cycle = [GAN[i % 10] + ZHI[i % 12] for i in range(60)]
    if type(birth_year) is not int or not 1 <= birth_year <= 9999:
        raise ValueError("出生公历年须为1至9999的整数。")
    if any(four_pillars.get(k) not in cycle for k in ("year", "month", "day", "hour")):
        raise ValueError("四柱必须是有效的六十甲子。")
    if hour_zhi != four_pillars["hour"][1] or month_zhi != four_pillars["month"][1]:
        raise ValueError("月支、时支必须与四柱一致。")
    require_pillar_links(four_pillars)
    if four_pillars["year"] not in (
        cycle[(birth_year - 4) % 60],
        cycle[(birth_year - 5) % 60],
    ):
        raise ValueError("出生年与年柱不一致；仅允许公历当年或立春前上一干支年。")

    year_g, year_z = four_pillars["year"][0], four_pillars["year"][1]
    totals = four_pillar_number_totals(four_pillars)
    tian, di = totals["tian"], totals["di"]
    is_male = gender == "男"

    cycle_year = birth_year
    if cycle[(birth_year - 5) % 60] == four_pillars["year"]:
        cycle_year -= 1
    minguo = cycle_year - 1911
    yang_gan = GAN.index(year_g) % 2 == 0
    t_num, d_num = _reduce_tian(tian), _reduce_di(di)
    t_gua = (
        _wu_ji_gong(minguo, yang_gan, is_male) if t_num == 5 else LUOSHU_TRIGRAM[t_num]
    )
    d_gua = (
        _wu_ji_gong(minguo, yang_gan, is_male) if d_num == 5 else LUOSHU_TRIGRAM[d_num]
    )

    yang_ming = year_z in YANG_ZHI
    tian_top = (is_male and yang_ming) or (not is_male and not yang_ming)
    up = t_gua if tian_top else d_gua
    low = d_gua if tian_top else t_gua
    xian_lines = gua_lines(up, low)
    xian_name = _gua_name(up, low)

    yang_ling, half_basis = resolve_half_year(month_zhi, month_yang_ling)
    alternatives = []
    layouts = []
    for half in (False, True):
        layout = yuantang_placement(xian_lines, hour_zhi, is_male, half)
        candidate_pos = layout["selected_pos"]
        candidate_hou = transform_houtian(xian_name, xian_lines, candidate_pos, half)
        layouts.append(layout)
        alternatives.append(
            {
                "yang_ling": half,
                "xian_yuan": candidate_pos,
                "hou_name": candidate_hou["name"],
                "hou_yuan": candidate_hou["yuan"],
                "hou_lines": candidate_hou["lines"],
            }
        )
    yuan_sensitive = alternatives[0]["xian_yuan"] != alternatives[1]["xian_yuan"]
    hou_sensitive = any(
        alternatives[0][k] != alternatives[1][k]
        for k in ("hou_name", "hou_yuan", "hou_lines")
    )
    if yang_ling is None and (yuan_sensitive or hou_sensitive):
        raise ValueError(
            f"{month_zhi}月跨至点，阴阳令会改变元堂或后天卦；须明确month_yang_ling，不能按整月猜测。"
        )
    selected_index = int(yang_ling is True)
    selected = alternatives[selected_index]
    yuan = selected["xian_yuan"]
    hou = {
        "name": selected["hou_name"],
        "lines": selected["hou_lines"][:],
        "yuan": selected["hou_yuan"],
    }
    derivation = {
        **yuantang_source_profile(),
        "gender": gender,
        "half_year": {
            "value": yang_ling,
            "basis": half_basis,
            "candidate_values": [False, True] if yang_ling is None else [yang_ling],
            "yuantang_depends_on_half_year": yuan_sensitive,
            "houtian_depends_on_half_year": hou_sensitive,
            "result_selection": (
                "resolved_half_year"
                if yang_ling is not None
                else "invariant_under_both_halves"
            ),
        },
        "placement": {
            "rule_id": layouts[selected_index]["rule_id"],
            "hour_zhi": layouts[selected_index]["hour_zhi"],
            "hour_half": layouts[selected_index]["hour_half"],
            "selected_pos": layouts[selected_index]["selected_pos"],
            "pure_direction": layouts[selected_index]["pure_direction"],
        },
        "houtian_transform": {
            "changed_line": yuan,
            "swap_trigrams": hou["yuan"] != yuan,
            "resulting_yuan": hou["yuan"],
            "source_pdf_pages": [31, 32],
            "policy": (
                "flip_then_swap" if hou["yuan"] != yuan else "flip_only_three_supreme"
            ),
        },
    }

    chart_data: dict[str, Any] = {
        "gender": "男" if is_male else "女",
        "tian": tian,
        "di": di,
        "tianNum": t_num,
        "diNum": d_num,
        "tianGua": t_gua,
        "diGua": d_gua,
        "tianTop": tian_top,
        "yangMing": yang_ming,
        "yangGan": yang_gan,
        "yangLing": yang_ling,
        "yangLingBasis": half_basis,
        "yuantang_derivation": derivation,
        "cycleYear": cycle_year,
        "yuanCycle": ["上元", "中元", "下元"][((cycle_year - 1504) % 180) // 60],
        "hourZhi": hour_zhi,
        "xian": {
            "name": xian_name,
            "up": up,
            "low": low,
            "lines": xian_lines,
            "yuan": yuan,
        },
        "hou": {
            **lines_to_gua(hou["lines"]),
            "lines": hou["lines"],
            "yuan": hou["yuan"],
        },
    }
    chart_data["sovereign_hexagram"] = yuantang_sovereign_status(chart_data, month_zhi)
    return chart_data


def _ying(p: int) -> int:
    return p + 3 if p <= 3 else p - 3


_NAJIA_MAP: dict[str, dict[str, Any]] = {
    "乾": {"inner": ("甲", ["子", "寅", "辰"]), "outer": ("壬", ["午", "申", "戌"])},
    "震": {"inner": ("庚", ["子", "寅", "辰"]), "outer": ("庚", ["午", "申", "戌"])},
    "坎": {"inner": ("戊", ["寅", "辰", "午"]), "outer": ("戊", ["申", "戌", "子"])},
    "艮": {"inner": ("丙", ["辰", "午", "申"]), "outer": ("丙", ["戌", "子", "寅"])},
    "坤": {"inner": ("乙", ["未", "巳", "卯"]), "outer": ("癸", ["丑", "亥", "酉"])},
    "巽": {"inner": ("辛", ["丑", "亥", "酉"]), "outer": ("辛", ["未", "巳", "卯"])},
    "離": {"inner": ("己", ["卯", "丑", "亥"]), "outer": ("己", ["酉", "未", "巳"])},
    "兌": {"inner": ("丁", ["巳", "卯", "丑"]), "outer": ("丁", ["亥", "酉", "未"])},
}


def hexagram_najia(lines: list[int]) -> list[dict[str, Any]]:
    """Return six-line Najia stems/branches with borrowed-stem candidates."""
    g = lines_to_gua(lines)
    res: list[dict[str, Any]] = []
    for half_idx, tri in enumerate([g["low"], g["up"]]):
        side = "inner" if half_idx == 0 else "outer"
        stem, branches = _NAJIA_MAP[tri][side]
        borrowed: list[str] = []
        if tri == "乾":
            borrowed = ["壬"] if side == "inner" else ["甲"]
        elif tri == "坤":
            borrowed = ["癸"] if side == "inner" else ["乙"]
        for k, br in enumerate(branches):
            pos = half_idx * 3 + k + 1
            res.append(
                {
                    "pos": pos,
                    "trigram": tri,
                    "direct": stem + br,
                    "borrowed": [bs + br for bs in borrowed],
                }
            )
    return res


def da_yun(
    xian: dict[str, Any], hou: dict[str, Any], birth_year: int
) -> dict[str, Any]:
    """Compute the 12 Xian/Hou major fortune periods from Yuantang upward."""
    periods: list[dict[str, Any]] = []
    age = 1
    for phase, gua in [("xian", xian), ("hou", hou)]:
        start = gua["yuan"]
        lines = gua["lines"]
        for i in range(6):
            pos = (start - 1 + i) % 6 + 1
            yang = lines[pos - 1] == 1
            years = 9 if yang else 6
            period_lines = _flip_line(lines, pos)
            periods.append(
                {
                    "phase": phase,
                    "pos": pos,
                    "yang": yang,
                    "years": years,
                    "ageStart": age,
                    "ageEnd": age + years - 1,
                    "yearStart": birth_year + age - 1,
                    "yearEnd": birth_year + age + years - 2,
                    "changedGua": lines_to_gua(period_lines)["name"],
                    "lines": period_lines,
                }
            )
            age += years
    return {"xian": periods[:6], "hou": periods[6:], "all": periods}
