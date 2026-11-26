"""Cast and judge Heluo charts from supplied four pillars."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fatebridge.core.heluo.heluo_body import body_evidence
from fatebridge.core.heluo.heluo_hexagrams import (
    GAN,
    TRIGRAM_BITS,
    ZHI,
    _gua_name,
    _tiaowen,
    _trigram_of,
    gua_lines,
    lines_to_gua,
)
from fatebridge.core.heluo.heluo_lines import line_conditions
from fatebridge.core.heluo.heluo_months import (
    DEFAULT_MONTH_ASSIGNMENT,
    MonthAssignmentMethod,
    month_affinity,
)
from fatebridge.core.heluo.heluo_najia import annotate_positions
from fatebridge.core.heluo.heluo_qi import phase_qi_evidence
from fatebridge.core.heluo.heluo_seasonal import seasonal_number_evidence
from fatebridge.core.heluo.heluo_snapshot import (
    build_snapshot_text as build_snapshot_text,
)
from fatebridge.core.heluo.heluo_snapshot import yao_name as yao_name
from fatebridge.core.heluo.heluo_snapshot import yao_text as yao_text
from fatebridge.core.heluo.heluo_solar_context import solar_term as solar_term
from fatebridge.core.heluo.heluo_solar_context import (
    solar_term_huagong as solar_term_huagong,
)
from fatebridge.core.heluo.heluo_structure import body_structure
from fatebridge.core.heluo.heluo_yuantang import placement as yuantang_placement
from fatebridge.core.heluo.heluo_yuantang import resolve_half_year
from fatebridge.core.heluo.heluo_yuantang import (
    source_profile as yuantang_source_profile,
)
from fatebridge.core.numerology.numerology_pillars import require_pillar_links
from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.civil_time import ZonedCalendar

# ── 八卦（自下而上三爻 bit：1阳 0阴）──
# 洛书数 → 八卦（5 寄中宫，另行处理）
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
# 天干 → 洛书纳甲数
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
# 地支 → 河图数对 [奇, 偶]
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
YANG_ZHI = frozenset({"子", "寅", "辰", "午", "申", "戌"})  # 阳支(年支定阳命)
# 自然象 → 八卦（复合卦名取上下两象）
# 三至尊卦
ZHI_ZUN = frozenset({"坎為水", "水雷屯", "水山蹇"})

# ── 命运篇：元气/反元气/化工 ──
GAN_YUAN: dict[str, str] = {
    "甲": "乾",
    "壬": "乾",
    "乙": "坤",
    "癸": "坤",
    "庚": "震",
    "辛": "巽",
    "戊": "坎",
    "己": "離",
    "丙": "艮",
    "丁": "兌",
}
ZHI_YUAN: dict[str, str] = {
    "戌": "乾",
    "亥": "乾",
    "未": "坤",
    "申": "坤",
    "卯": "震",
    "辰": "巽",
    "巳": "巽",
    "子": "坎",
    "午": "離",
    "丑": "艮",
    "寅": "艮",
    "酉": "兌",
}
GAN_FAN: dict[str, str] = {
    "甲": "坤",
    "壬": "坤",
    "乙": "乾",
    "癸": "乾",
    "庚": "巽",
    "辛": "震",
    "戊": "離",
    "己": "坎",
    "丙": "兌",
    "丁": "艮",
}
ZHI_FAN: dict[str, str] = {
    "戌": "坤",
    "亥": "坤",
    "未": "乾",
    "申": "乾",
    "卯": "巽",
    "辰": "震",
    "巳": "震",
    "子": "離",
    "午": "坎",
    "丑": "兌",
    "寅": "兌",
    "酉": "艮",
}
# 无节气信息时(单测)的月支近似回退
MONTH_HG: dict[str, list[str]] = {
    "卯": ["震"],
    "辰": ["震"],
    "午": ["離"],
    "未": ["離"],
    "酉": ["兌"],
    "戌": ["兌"],
    "子": ["坎"],
    "丑": ["坎"],
    "寅": ["坤", "艮"],
    "巳": ["坤", "艮"],
    "申": ["坤", "艮"],
    "亥": ["坤", "艮"],
}
MONTH_FH: dict[str, list[str]] = {
    "卯": ["巽"],
    "辰": ["巽"],
    "午": ["坎"],
    "未": ["坎"],
    "酉": ["艮"],
    "戌": ["艮"],
    "子": ["離"],
    "丑": ["離"],
    "寅": ["乾", "兌"],
    "巳": ["乾", "兌"],
    "申": ["乾", "兌"],
    "亥": ["乾", "兌"],
}
# 八卦纳甲旧序表（上至初）；命中仅年干支成员关系。
NAJIA: dict[str, list[str]] = {
    "乾": ["壬戌", "壬申", "壬午", "甲辰", "甲寅", "甲子"],
    "坎": ["戊子", "戊戌", "戊申", "戊午", "戊辰", "戊寅"],
    "艮": ["丙寅", "丙子", "丙戌", "丙申", "丙午", "丙辰"],
    "震": ["庚戌", "庚申", "庚午", "庚辰", "庚寅", "庚子"],
    "巽": ["辛卯", "辛巳", "辛未", "辛酉", "辛亥", "辛丑"],
    "離": ["己巳", "己未", "己酉", "己亥", "己丑", "己卯"],
    "坤": ["癸酉", "癸亥", "癸丑", "乙卯", "乙巳", "乙未"],
    "兌": ["丁未", "丁酉", "丁亥", "丁丑", "丁卯", "丁巳"],
}
# 卦属月：四柱月支对应月号；原典农历/节气月界仍未确认。
MONTH_GUA: dict[str, list[str]] = {
    "寅": ["大有", "同人", "泰", "既濟", "咸", "恆", "蠱", "漸"],
    "卯": ["大壯", "晉", "小過", "大過", "革", "訟", "睽", "井"],
    "辰": ["夬", "履", "渙"],
    "巳": ["乾", "艮", "巽", "離"],
    "午": ["姤", "旅", "困", "豫"],
    "未": ["家人", "萃", "遯", "屯"],
    "申": ["比", "隨", "益", "損", "師", "歸妹", "否", "未濟"],
    "酉": ["中孚", "觀", "明夷", "無妄", "升", "蹇", "蒙", "需", "頤"],
    "戌": ["豐", "謙", "噬嗑", "剝"],
    "亥": ["坎", "坤", "兌", "震"],
    "子": ["小畜", "賁", "復", "節"],
    "丑": ["大畜", "解", "鼎", "臨"],
}


def _san_cai(lines: list[int]) -> list[str]:
    return [
        _trigram_of([lines[i] for i in ix])
        for ix in ([0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5])
    ]


# ── 天数(去25)/地数(去30) 归卦数 1-9（5 表示寄中宫）──
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
    if phase == 0:  # 上元
        return "艮" if is_male else "坤"
    if phase == 1:  # 中元
        ay = (yang_gan and is_male) or (not yang_gan and not is_male)  # 阳男 or 阴女
        return "艮" if ay else "坤"
    return "離" if is_male else "兌"  # 下元


def _flip_line(lines: list[int], pos: int) -> list[int]:
    out = lines[:]
    out[pos - 1] = 0 if out[pos - 1] else 1
    return out


def _swap_trigrams(lines: list[int]) -> list[int]:
    return [lines[3], lines[4], lines[5], lines[0], lines[1], lines[2]]


def transform_houtian(
    xian_name: str, xian_lines: list[int], yuan: int, yang_ling: bool
) -> dict[str, Any]:
    """翻元堂爻 → 后天卦（三至尊卦「变而不易」特例）。"""
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
    flipped = _flip_line(xian_lines, yuan)  # ① 元堂爻 阴阳互变
    if xian_name in ZHI_ZUN:
        bu_yi = (yuan == 5 and not yang_ling) or (
            yuan == 6 and yang_ling
        )  # 九五阴令 / 上六阳令
        if bu_yi:  # 变而不易：不互换上下卦、元堂位不动
            return {
                "name": lines_to_gua(flipped)["name"],
                "lines": flipped,
                "yuan": yuan,
            }
    hou_lines = _swap_trigrams(flipped)  # ② 移外卦入内、内卦出外
    hou_yuan = yuan - 3 if yuan > 3 else yuan + 3  # 元堂随上下卦互换而易位
    return {
        "name": lines_to_gua(hou_lines)["name"],
        "lines": hou_lines,
        "yuan": hou_yuan,
    }


def four_pillar_number_totals(four_pillars: dict[str, str]) -> dict[str, Any]:
    """Formal source-number arithmetic, without asserting a realizable birth chart.

    A printed arithmetic example can contain incompatible stem links. Keep its
    literal sums inspectable, but do not construct a birth chart from them.
    """
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
    """起命：天地数→卦→元堂→先天/后天。"""
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
    year_g = four_pillars["year"][0]
    year_z = four_pillars["year"][1]
    totals = four_pillar_number_totals(four_pillars)
    tian, di = totals["tian"], totals["di"]
    is_male = gender == "男"
    # 公历一月及立春前仍可能属于上一干支年；寄宫随干支年换元。
    cycle_year = birth_year
    if cycle[(birth_year - 5) % 60] == four_pillars["year"]:
        cycle_year -= 1
    minguo = cycle_year - 1911
    yang_gan = GAN.index(year_g) % 2 == 0  # 甲丙戊庚壬=阳
    t_num = _reduce_tian(tian)
    d_num = _reduce_di(di)
    t_gua = (
        _wu_ji_gong(minguo, yang_gan, is_male) if t_num == 5 else LUOSHU_TRIGRAM[t_num]
    )
    d_gua = (
        _wu_ji_gong(minguo, yang_gan, is_male) if d_num == 5 else LUOSHU_TRIGRAM[d_num]
    )

    # 相盪：阳男阴女 天上地下，阴男阳女 天下地上
    yang_ming = year_z in YANG_ZHI
    tian_top = (is_male and yang_ming) or (not is_male and not yang_ming)
    up = t_gua if tian_top else d_gua
    low = d_gua if tian_top else t_gua
    xian_lines = gua_lines(up, low)
    xian_name = _gua_name(up, low)

    # 子月、午月跨至点，固定四柱不能据月支选择其中一半。先比较两个
    # 半年的完整结果：只有确实唯一时，才允许缺半年的输入继续计算。
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
            f"阴令：{xian_name}{alternatives[0]['xian_yuan']}爻→{alternatives[0]['hou_name']}{alternatives[0]['hou_yuan']}爻；"
            f"阳令：{xian_name}{alternatives[1]['xian_yuan']}爻→{alternatives[1]['hou_name']}{alternatives[1]['hou_yuan']}爻。"
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
            "birth_instant_utc": None,
            "candidate_values": [False, True] if yang_ling is None else [yang_ling],
            "yuantang_depends_on_half_year": yuan_sensitive,
            "houtian_depends_on_half_year": hou_sensitive,
            "counterfactuals": alternatives,
            "result_selection": (
                "resolved_half_year"
                if yang_ling is not None
                else "invariant_under_both_halves"
            ),
        },
        "placement": layouts[selected_index],
        "houtian_transform": {
            "changed_line": yuan,
            "swap_trigrams": hou["yuan"] != yuan,
            "resulting_yuan": hou["yuan"],
            "source_pdf_pages": [31, 32],
            "policy": (
                "flip_then_swap" if hou["yuan"] != yuan else "flip_only_three_supreme"
            ),
        },
        "scope": "逐时元堂与后天换卦，不是完整得体或葉否。反事实只说明阴阳令敏感性，不代表两个实际出生时刻。子午节月边界为现代四柱输入约定，三至尊沿用所选至点半年解释原文陽月／陰令。",
    }

    return {
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


def _ying(p: int) -> int:
    """应爻：1↔4 2↔5 3↔6。"""
    return p + 3 if p <= 3 else p - 3


def hexagram_najia(lines: list[int]) -> list[dict[str, Any]]:
    """实际六爻纳甲，自初至上；乾坤的甲壬、乙癸借用另列。

    NAJIA 的旧表顺序为上至初。复卦只用内卦初二三、外卦四五上，
    不能把两个纯卦的十二个纳甲合并。八纯卦基础和具名复卦原页读数由
    heluo_najia 维护；judge 核对实际结果并另附直接条目／基础推演源据。
    """
    if len(lines) != 6 or any(type(v) is not int or v not in (0, 1) for v in lines):
        raise ValueError("纳甲须输入自初至上的六个0/1整数。")
    gua = lines_to_gua(lines)
    result = []
    for pos in range(1, 7):
        trigram = gua["low"] if pos <= 3 else gua["up"]
        direct = NAJIA[trigram][6 - pos]
        borrowed = []
        if trigram in {"乾", "坤"}:
            paired_stem = {"甲": "壬", "壬": "甲", "乙": "癸", "癸": "乙"}
            borrowed = [paired_stem[direct[0]] + direct[1]]
        result.append(
            {"pos": pos, "trigram": trigram, "direct": direct, "borrowed": borrowed}
        )
    return result


def da_yun(
    xian: dict[str, Any], hou: dict[str, Any], birth_year: int = 0
) -> dict[str, Any]:
    """大限：先天卦元堂起、自下往上绕行六爻、阳爻9阴爻6年；行完先天接后天。虚岁。"""

    def seg_of(g: dict[str, Any], start_age: int) -> dict[str, Any]:
        age = start_age
        segs: list[dict[str, Any]] = []
        for i in range(6):
            pos = ((g["yuan"] - 1 + i) % 6) + 1
            yang = g["lines"][pos - 1] == 1
            yrs = 9 if yang else 6
            segs.append(
                {
                    "gua": g["name"],
                    "lines": g["lines"][:],
                    "pos": pos,
                    "yang": yang,
                    "years": yrs,
                    "ageStart": age,
                    "ageEnd": age + yrs - 1,
                    "yearStart": birth_year + age - 1 if birth_year else None,
                }
            )
            age += yrs
        return {"segs": segs, "endAge": age - 1}

    a = seg_of(xian, 1)
    b = seg_of(hou, a["endAge"] + 1)
    return {
        "xian": a["segs"],
        "hou": b["segs"],
        "all": [*a["segs"], *b["segs"]],
        "xianEndAge": a["endAge"],
        "endAge": b["endAge"],
    }


def judge(
    chart: dict[str, Any],
    four_pillars: dict[str, str],
    month_zhi: str,
    hg_override: dict[str, Any] | None = None,
    *,
    month_assignment_method: MonthAssignmentMethod = DEFAULT_MONTH_ASSIGNMENT,
    birth_datetime: datetime | None = None,
) -> dict[str, Any]:
    """命运篇：元气/化工/得势得时得体/葉否/二数/元堂。"""
    year_g = four_pillars["year"][0]
    year_z = four_pillars["year"][1]
    tri_set = set(_san_cai(chart["xian"]["lines"]) + _san_cai(chart["hou"]["lines"]))

    def mk(gua: str) -> dict[str, Any]:
        return {"gua": gua, "present": gua in tri_set}

    yuan = {"tian": mk(GAN_YUAN[year_g]), "di": mk(ZHI_YUAN[year_z])}
    fan_yuan = {"tian": mk(GAN_FAN[year_g]), "di": mk(ZHI_FAN[year_z])}
    if hg_override is not None and (
        not isinstance(hg_override, dict)
        or any(
            not isinstance(hg_override.get(key), list)
            or any(
                not isinstance(t, str) or t not in TRIGRAM_BITS
                for t in hg_override[key]
            )
            for key in ("hg", "fh")
        )
    ):
        raise ValueError("显式化工／反化工候选须为八卦名列表，不能静默退回月支近似。")
    hg_list = list(
        hg_override["hg"] if hg_override is not None else MONTH_HG.get(month_zhi, [])
    )
    huagong = {"guas": hg_list, "present": [g for g in hg_list if g in tri_set]}
    fh_list = list(
        hg_override["fh"] if hg_override is not None else MONTH_FH.get(month_zhi, [])
    )
    fanhua = {"guas": fh_list, "present": [g for g in fh_list if g in tri_set]}
    najia = []
    for phase in ("xian", "hou"):
        source = annotate_positions(
            chart[phase]["name"],
            chart[phase]["lines"],
            hexagram_najia(chart[phase]["lines"]),
        )
        entries = source["lines"]
        matches = []
        for entry in entries:
            if four_pillars["year"] == entry["direct"]:
                matches.append({"pos": entry["pos"], "kind": "direct"})
            if four_pillars["year"] in entry["borrowed"]:
                matches.append({"pos": entry["pos"], "kind": "borrowed"})
        najia.append(
            {
                "phase": phase,
                "gua": chart[phase]["name"],
                "year_ganzhi": four_pillars["year"],
                "lines": entries,
                "matches": matches,
                "present": bool(matches),
                "source_scope": source["source_scope"],
                "source_issues": source["source_issues"],
            }
        )
    de_shi = any(item["present"] for item in najia)
    month_evidence = month_affinity(
        chart,
        month_zhi,
        MONTH_GUA,
        najia_assessments=najia,
        assignment_method=month_assignment_method,
    )
    de_time = any(row["assigned_month_match"] for row in month_evidence["phases"])
    de_ti = body_evidence(
        four_pillars["year"],
        {
            phase: {
                "gua": chart[phase]["name"],
                "trigrams": _san_cai(chart[phase]["lines"]),
            }
            for phase in ("xian", "hou")
        },
        {"tian": yuan["tian"]["gua"], "di": yuan["di"]["gua"]},
    )
    qi_phases = phase_qi_evidence(
        de_ti["bodies"],
        {k: v["gua"] for k, v in yuan.items()},
        {k: v["gua"] for k, v in fan_yuan.items()},
        hg_list,
        fh_list,
        hg_override,
        year_ganzhi=four_pillars["year"],
    )
    xie = (
        yuan["tian"]["present"] or yuan["di"]["present"] or len(huagong["present"]) > 0
    )
    er_shu = {
        "tian": chart["tian"],
        "di": chart["di"],
        "tianState": (
            "有余" if chart["tian"] > 25 else ("不足" if chart["tian"] < 25 else "正数")
        ),
        "diState": (
            "有余" if chart["di"] > 30 else ("不足" if chart["di"] < 30 else "正数")
        ),
    }
    y_pos = chart["xian"]["yuan"]
    y_yang = chart["xian"]["lines"][y_pos - 1] == 1
    ying_pos = _ying(y_pos)
    line_evidence = line_conditions(chart)
    yuan_tang_info = {
        "pos": y_pos,
        "yang": y_yang,
        "position_polarity_match": line_evidence["phases"][0][
            "position_polarity_match"
        ],
        "youYing": chart["xian"]["lines"][ying_pos - 1]
        != chart["xian"]["lines"][y_pos - 1],
        "youYing_policy": "xian_selected_and_corresponding_line_opposed_only; not_source_youyuan_clause",
        "heLi": chart["yangLing"] == y_yang if chart["yangLing"] is not None else None,
        "heLi_policy": "used_line_polarity_equals_selected_half_year_only_v1",
    }
    return {
        "assessment_status": "partial",
        "xie_policy": "basic_yuan_or_huagong_presence_only_v1",
        "deSheng_policy": "year_najia_by_actual_six_lines_with_qiankun_borrowed_v2",
        "najia": najia,
        "deTime_policy": "selected_month_source_profile_v4; five_intra_edition_conflicts_retained; distinct_month_clauses_not_complete_detime",
        "deTi_policy": "source_separated_year_nayin_body_relations_v2; complete_deti_present_null",
        "yuan": yuan,
        "fanYuan": fan_yuan,
        "fanYuan_policy": "opposite_trigram_body_presence_union_only; absence_premise_in_qi_phases.yuanqi_opposition",
        "huagong": huagong,
        "fanhua": fanhua,
        "qi_phases": qi_phases,
        "deSheng": de_shi,
        "deTime": de_time,
        "month_affinity": month_evidence,
        "deTi": de_ti,
        "xie": xie,
        "erShu": er_shu,
        "seasonal_numbers": seasonal_number_evidence(
            chart["tian"],
            chart["di"],
            (
                birth_datetime
                if birth_datetime is not None
                else (
                    ZonedCalendar.from_isoformat(hg_override["anchor_utc"])
                    if hg_override and hg_override.get("precision") == "birth_instant"
                    else None
                )
            ),
            context_timezone=(hg_override or {})
            .get("boundary_context", {})
            .get("context_timezone", "+00:00"),
        ),
        "yuanTang": yuan_tang_info,
        "line_conditions": line_evidence,
        "body_structure": body_structure(chart),
    }


# ── 爻辞查找 ──
