"""河洛理数 (heluo) — 原生离线计算。

Native Python port of horosa's ``heluoLocal.js`` (+ the ``solarTerm`` helper from
``tools/heluo.js``). Like canping, heluo is computed entirely in-process: four
pillars come from FateBridge's own calendar engine; this module does 起命
(天地数→卦→元堂→后天), 起运 (大限), 命运篇 judge, and 爻辞查表.

The 命运篇 化工/反化 layer is节气-coupled: it needs the real solar term at birth.
We source that from FateBridge's own 24-term engine (``core.almanac``) rather than
lunar-javascript — heluo only consumes the term *name* → 化工象限 + the 土用 flag.

Originally ported from horosa. Source agreement is audited separately against
《河洛理數》卷一 (史應選校訂本); port parity is not a classical certification.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fatebridge.core.almanac import localize_datetime
from fatebridge.core.heluo_body import body_evidence, body_snapshot
from fatebridge.core.heluo_hexagrams import (
    _DATA_PATH,
    GAN,
    NATURAL,
    TRIGRAM_BITS,
    ZHI,
    _gua_name,
    _gua_tables,
    _tiaowen,
    _trigram_of,
    gua_lines,
    lines_to_gua,
)
from fatebridge.core.heluo_lines import line_conditions, line_snapshot
from fatebridge.core.heluo_months import (
    DEFAULT_MONTH_ASSIGNMENT,
    MonthAssignmentMethod,
    month_affinity,
)
from fatebridge.core.heluo_najia import annotate_positions, najia_snapshot
from fatebridge.core.heluo_qi import phase_qi_evidence, phase_qi_snapshot
from fatebridge.core.heluo_seasonal import seasonal_number_evidence, seasonal_snapshot
from fatebridge.core.heluo_solar_context import resolve_solar_context
from fatebridge.core.heluo_structure import body_structure, structure_snapshot
from fatebridge.core.heluo_texts import (
    collated_line,
    poem_text_snapshot,
    text_reading_notes_snapshot,
    text_status_snapshot,
)
from fatebridge.core.heluo_yuantang import PURE_HOUR_TO_YAO as PURE_HOUR_TO_YAO
from fatebridge.core.heluo_yuantang import YANG_HOURS as YANG_HOURS
from fatebridge.core.heluo_yuantang import YIN_HOURS as YIN_HOURS
from fatebridge.core.heluo_yuantang import derivation_snapshot as yuantang_snapshot
from fatebridge.core.heluo_yuantang import placement as yuantang_placement
from fatebridge.core.heluo_yuantang import resolve_half_year
from fatebridge.core.heluo_yuantang import source_profile as yuantang_source_profile
from fatebridge.core.numerology_pillars import require_pillar_links
from fatebridge.utils.birth_input import normalize_gender

# ── 八卦（自下而上三爻 bit：1阳 0阴）──
# 洛书数 → 八卦（5 寄中宫，另行处理）
LUOSHU_TRIGRAM: Dict[int, str] = {
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
GAN_NUM: Dict[str, int] = {
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
ZHI_PAIR: Dict[str, List[int]] = {
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
GAN_YUAN: Dict[str, str] = {
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
ZHI_YUAN: Dict[str, str] = {
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
GAN_FAN: Dict[str, str] = {
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
ZHI_FAN: Dict[str, str] = {
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
QUARTER_HG: Dict[str, Dict[str, str]] = {
    "震": {"hg": "震", "fh": "巽"},
    "離": {"hg": "離", "fh": "坎"},
    "兌": {"hg": "兌", "fh": "艮"},
    "坎": {"hg": "坎", "fh": "離"},
}
# 节气(节/气名)→所属中气象限化工卦（繁简兼容）
JIEQI_QUARTER: Dict[str, str] = {
    "春分": "震",
    "清明": "震",
    "穀雨": "震",
    "谷雨": "震",
    "立夏": "震",
    "小滿": "震",
    "小满": "震",
    "芒種": "震",
    "芒种": "震",
    "夏至": "離",
    "小暑": "離",
    "大暑": "離",
    "立秋": "離",
    "處暑": "離",
    "处暑": "離",
    "白露": "離",
    "秋分": "兌",
    "寒露": "兌",
    "霜降": "兌",
    "立冬": "兌",
    "小雪": "兌",
    "大雪": "兌",
    "冬至": "坎",
    "小寒": "坎",
    "大寒": "坎",
    "立春": "坎",
    "雨水": "坎",
    "驚蟄": "坎",
    "惊蛰": "坎",
}
# 无节气信息时(单测)的月支近似回退
MONTH_HG: Dict[str, List[str]] = {
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
MONTH_FH: Dict[str, List[str]] = {
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
NAJIA: Dict[str, List[str]] = {
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
MONTH_GUA: Dict[str, List[str]] = {
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
# 得体：日干→纳甲卦
DAY_TI: Dict[str, str] = {
    "甲": "乾",
    "乙": "坤",
    "丙": "艮",
    "丁": "兌",
    "戊": "坎",
    "己": "離",
    "庚": "震",
    "辛": "巽",
    "壬": "乾",
    "癸": "坤",
}

# 四立 — 土用 window markers.
LI_TERMS = frozenset({"立春", "立夏", "立秋", "立冬"})


def _san_cai(lines: List[int]) -> List[str]:
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


def _flip_line(lines: List[int], pos: int) -> List[int]:
    out = lines[:]
    out[pos - 1] = 0 if out[pos - 1] else 1
    return out


def _swap_trigrams(lines: List[int]) -> List[int]:
    return [lines[3], lines[4], lines[5], lines[0], lines[1], lines[2]]


def transform_houtian(
    xian_name: str, xian_lines: List[int], yuan: int, yang_ling: bool
) -> Dict[str, Any]:
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


def four_pillar_number_totals(four_pillars: Dict[str, str]) -> Dict[str, Any]:
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
    four_pillars: Dict[str, str],
    gender: str,
    hour_zhi: str,
    birth_year: int,
    month_zhi: str,
    month_yang_ling: Optional[bool] = None,
) -> Dict[str, Any]:
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


def hexagram_najia(lines: List[int]) -> List[Dict[str, Any]]:
    """实际六爻纳甲，自初至上；乾坤的甲壬、乙癸借用另列。

    ``NAJIA`` 的旧表顺序为上至初。复卦只用内卦初二三、外卦四五上，
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
    xian: Dict[str, Any], hou: Dict[str, Any], birth_year: int = 0
) -> Dict[str, Any]:
    """大限：先天卦元堂起、自下往上绕行六爻、阳爻9阴爻6年；行完先天接后天。虚岁。"""

    def seg_of(g: Dict[str, Any], start_age: int) -> Dict[str, Any]:
        age = start_age
        segs: List[Dict[str, Any]] = []
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


def solar_term_huagong(prev_jieqi_name: str, tuyong: bool) -> Dict[str, Any]:
    """据真实节气名 + 土用标志，返回 {hg,fh,quarter,tuyong} 化工/反化工候选。"""
    if type(tuyong) is not bool:
        raise ValueError("土用标志须为布尔值。")
    quarter = JIEQI_QUARTER.get(prev_jieqi_name)
    base = (
        QUARTER_HG.get(quarter, {"hg": "", "fh": ""})
        if quarter
        else {"hg": "", "fh": ""}
    )
    hg = [base["hg"]] if base["hg"] else []
    fh = [base["fh"]] if base["fh"] else []
    # NLC PDF35 / NAJDA volume-one image33 explicitly overlaps these clauses:
    # winter solstice -> summer solstice: Li; spring equinox -> summer: Xun.
    # Keep both literal conditions rather than assuming one opposite per quarter.
    if quarter == "震":
        fh.insert(0, "離")
    fanhua_rule_ids = {
        "坎": ["winter_to_summer_li"],
        "震": ["winter_to_summer_li", "spring_xun"],
        "離": ["summer_kan"],
        "兌": ["autumn_gen"],
    }.get(quarter or "", [])[:]
    if tuyong:
        hg += ["坤", "艮"]
        fh += ["乾", "兌"]
        fanhua_rule_ids.append("seasonal_earth_qian_dui")
    return {
        "hg": hg,
        "fh": fh,
        "quarter": quarter,
        "tuyong": tuyong,
        "fanhua_rule_ids": fanhua_rule_ids,
    }


def solar_term(
    year: int,
    month: int,
    day: int,
    timezone_name: str,
    *,
    birth_datetime: Optional[datetime] = None,
) -> Dict[str, Any]:
    """出生当下所处节气 + 土用，经 FateBridge 自有 24 节气引擎计算。

    取最近一个 ≤ 出生绝对瞬间的节气，并以至点划分阴阳令。
    土用采用四立前连续十八日的显式实现约定；原文季月十八日尚待版本校勘。
    省略 birth_datetime 的旧调用仅按零点近似，返回 precision 明示限制。
    """
    anchor = birth_datetime or localize_datetime(
        datetime(year, month, day), timezone_name
    )
    if anchor.tzinfo is None or anchor.utcoffset() is None:
        raise ValueError("节气计算需要带时区的出生时刻。")
    # 比较绝对时刻，避免 DST 跨越时墙钟加减及同 tzinfo 比较的歧义。
    anchor = anchor.astimezone(timezone.utc)
    context = resolve_solar_context(anchor, timezone_name)
    current, previous_solstice, following_li = context["dependencies"]
    prev_name = current["record"]["name"]
    # 土用：未来 18 日内是否有四立(立春/夏/秋/冬)。
    next_li = datetime.fromisoformat(following_li["instant_utc"])
    tuyong = next_li is not None and next_li - timedelta(days=18) <= anchor < next_li
    result = solar_term_huagong(prev_name, tuyong)
    result["term"] = prev_name
    solstice = previous_solstice["record"]["name"]
    result.update(
        {
            "yang_ling": solstice == "冬至",
            "boundary_context": context,
            "anchor_utc": anchor.isoformat(),
            "precision": (
                "birth_instant"
                if birth_datetime is not None
                else "date_midnight_approximation"
            ),
            "tuyong_policy": "18_elapsed_days_before_four_li_v1",
            "tuyong_start_utc": (
                (next_li - timedelta(days=18)).isoformat() if next_li else None
            ),
            "tuyong_end_utc": next_li.isoformat() if next_li else None,
        }
    )
    return result


def judge(
    chart: Dict[str, Any],
    four_pillars: Dict[str, str],
    month_zhi: str,
    hg_override: Optional[Dict[str, Any]] = None,
    *,
    month_assignment_method: MonthAssignmentMethod = DEFAULT_MONTH_ASSIGNMENT,
) -> Dict[str, Any]:
    """命运篇：元气/化工/得势得时得体/葉否/二数/元堂。"""
    year_g = four_pillars["year"][0]
    year_z = four_pillars["year"][1]
    day_g = four_pillars["day"][0]
    tri_set = set(_san_cai(chart["xian"]["lines"]) + _san_cai(chart["hou"]["lines"]))

    def mk(gua: str) -> Dict[str, Any]:
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
    day_stem_mapping = mk(DAY_TI[day_g])
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
        "dangWei": (y_pos % 2 == 1) == y_yang,
        "dangWei_policy": "legacy_alias_for_position_polarity_match; not_source_dangwei",
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
        "deTi_policy": "source_separated_year_nayin_body_relations_v2; complete_deti_present_null; legacy_lookup_in_day_stem_mapping",
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
        "day_stem_mapping": day_stem_mapping,
        "xie": xie,
        "erShu": er_shu,
        "seasonal_numbers": seasonal_number_evidence(
            chart["tian"],
            chart["di"],
            (
                datetime.fromisoformat(hg_override["anchor_utc"])
                if hg_override and hg_override.get("precision") == "birth_instant"
                else None
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
def yao_text(gua_name: str, pos: int) -> Optional[Dict[str, Any]]:
    """本卦元堂(动爻)之爻辞。"""
    g = _tiaowen().get(gua_name)
    if not g or not g.get("yao", {}).get(str(pos)):
        return None
    return collated_line(gua_name, pos, g["yao"][str(pos)])


_YAO_LABEL = ["初", "二", "三", "四", "五", "上"]


def yao_name(lines: List[int], pos: int) -> str:
    yang = lines[pos - 1] == 1
    if pos == 1:
        return f"初{'九' if yang else '六'}"
    if pos == 6:
        return f"上{'九' if yang else '六'}"
    return f"{'九' if yang else '六'}{_YAO_LABEL[pos - 1]}"


def build_snapshot_text(
    chart: Dict[str, Any], jg: Optional[Dict[str, Any]], dy: Optional[Dict[str, Any]]
) -> str:
    if not chart:
        return ""
    lines: List[str] = []
    lines.append("[起命]")
    lines.append(
        f"天数{chart['tian']}→{chart['tianGua']}　地数{chart['di']}→{chart['diGua']}"
    )
    lines.append(
        f"先天卦：{chart['xian']['name']}　元堂 {yao_name(chart['xian']['lines'], chart['xian']['yuan'])}"
    )
    lines.append(
        f"后天卦：{chart['hou']['name']}　元堂 {yao_name(chart['hou']['lines'], chart['hou']['yuan'])}"
    )
    xt = yao_text(chart["xian"]["name"], chart["xian"]["yuan"])
    ht = yao_text(chart["hou"]["name"], chart["hou"]["yuan"])
    for phase, label, text in (("xian", "先天", xt), ("hou", "后天", ht)):
        if text:
            lines += [
                "",
                f"[{label}·{chart[phase]['name']} 元堂爻辞]",
                f"校勘：{text_status_snapshot(text)}；条件分支未自动选取。",
                f"注文：{text['detail']}",
                poem_text_snapshot(text),
                *text_reading_notes_snapshot(text),
            ]
    if jg:
        lines.append("")
        lines.append("[命运篇]")
        lines.append(
            f"先后天合并：天元气 {jg['yuan']['tian']['gua']}{'(有)' if jg['yuan']['tian']['present'] else '(无)'}　地元气 {jg['yuan']['di']['gua']}{'(有)' if jg['yuan']['di']['present'] else '(无)'}"
        )
        hg_present = (
            f"(有:{''.join(jg['huagong']['present'])})"
            if jg["huagong"]["present"]
            else "(无)"
        )
        lines.append(
            f"合并化工 {'/'.join(jg['huagong']['guas'])}{hg_present}　基础命中{'有' if jg['xie'] else '无'}（综合葉否未定）"
        )
        lines.append(
            f"年命纳甲{'有' if jg['deSheng'] else '无'}（按实际六爻含乾坤借用）　月表匹配{'有' if jg['deTime'] else '无'}　日干映射 {jg['day_stem_mapping']['gua']}{'(有)' if jg['day_stem_mapping']['present'] else '(无)'}（得时、得体综合未定）"
        )
        lines.append(
            f"二数（仅对25/30比较，非四时旺衰定论）：天{jg['erShu']['tian']}({jg['erShu']['tianState']}) 地{jg['erShu']['di']}({jg['erShu']['diState']})"
        )
        relation = (
            "未定（缺至点半年）"
            if jg["yuanTang"]["heLi"] is None
            else "同类" if jg["yuanTang"]["heLi"] else "异类"
        )
        lines.append(
            f"元堂：位序阴阳{'匹配' if jg['yuanTang']['position_polarity_match'] else '未匹配'}　先天元堂与应爻阴阳{'相异' if jg['yuanTang']['youYing'] else '相同'}（非十体有援总判）　用爻与所用阴阳令{relation}（非原典当位或综合顺逆时）"
        )
    if dy and dy.get("all"):
        lines.append("")
        lines.append("[大限·岁运]")
        for s in dy["all"]:
            lines.append(
                f"{s['ageStart']}-{s['ageEnd']}岁 {s['gua']} {yao_name(s['lines'], s['pos'])}（{'阳9' if s['yang'] else '阴6'}）"
            )
    if jg and jg.get("najia"):
        lines.extend(["", najia_snapshot(jg["najia"])])
    if jg and jg.get("seasonal_numbers"):
        lines.extend(["", seasonal_snapshot(jg["seasonal_numbers"])])
    if jg and jg.get("deTi"):
        lines.extend(["", body_snapshot(jg["deTi"])])
    if jg and jg.get("qi_phases"):
        lines.extend(["", phase_qi_snapshot(jg["qi_phases"])])
    if jg and jg.get("line_conditions"):
        lines.extend(["", line_snapshot(jg["line_conditions"])])
    if jg and jg.get("month_affinity"):
        lines.extend(
            [
                "",
                "[卦属月与另述窗口]",
                "所用月表方法："
                + jg["month_affinity"]["assignment_method"]
                + "；底本卷首表与卦条共有五处月号差异。",
            ]
        )
        for row in jg["month_affinity"]["phases"]:
            status = (
                f"据影印PDF第{row['source_pdf_page']}页"
                if row["source_pdf_page"] is not None
                else "已核总论未明确所属月，暂保留继承表值"
            )
            lines.append(
                f"{row['gua']}：属{row['assigned_month_number']}月，本月{'匹配' if row['assigned_month_match'] else '不匹配'}（{status}）。"
            )
            for witness in row["source_readings"]:
                label = "卦条" if witness["section"] == "hexagram_intro" else "卷首表"
                reading = (
                    f"{witness['month_number']}月"
                    if witness["month_number"] is not None
                    else "未明确月号"
                )
                lines.append(f"{label}PDF第{witness['source_pdf_page']}页：{reading}。")
            if row["source_months_agree"] is False:
                lines.append("两处月号不同；当前计算按所选方法，未裁定哪处讹误。")
            for window in row["additional_windows"]:
                match = (
                    (
                        "月号匹配，附加条件待核"
                        if window["month_label_match"]
                        else "月号不匹配，附加条件待核"
                    )
                    if window["status"] == "additional_condition_unresolved"
                    else {True: "月号匹配", False: "月号不匹配", None: "边界月待核"}[
                        window["match"]
                    ]
                )
                qualifiers = (
                    "；" + "；".join(window["qualifiers"])
                    if window["qualifiers"]
                    else ""
                )
                lines.append(
                    f"另述「{window['literal']}」：{match}，PDF第{window['source_pdf_page']}页{qualifiers}。"
                )
            if clause := row.get("natal_najia_clause"):
                phase_label = "先天" if row["phase"] == "xian" else "后天"
                factor = clause["najia"]
                najia_text = (
                    f"出生年{factor['year_ganzhi']}的本阶段年命纳甲{'匹配' if factor['present'] else '未匹配'}"
                    if factor is not None
                    else "本阶段年命纳甲未求值"
                )
                lines.append(
                    f"{phase_label}·另列「{clause['literal']}」：月号{'匹配' if clause['month_label_match'] else '不匹配'}，{najia_text}；及字连接范围待核，整条条件未定，PDF第{clause['source_pdf_page']}页。"
                )
            if row["opposed_month_conditions"]:
                lines.append(
                    "此月同时进入原文及时与失时两段，保留冲突，未裁定优先规则。"
                )
        lines.append(
            "以上按四柱月支解释月号；原典月界仍待核定，不据此裁定综合得时或葉否。"
        )
    lines.extend(["", "[所用爻辞与校勘]"])
    for phase, label, text in (("xian", "先天", xt), ("hou", "后天", ht)):
        if text:
            provenance = text["text_provenance"]
            status = (
                f"影印本PDF第{provenance['pdf_page']}页，单次目校，待独立复核"
                if provenance["yaoci_status"] == "source_header_visually_collated"
                else "继承转录，尚未校勘"
            )
            lines.append(
                f"{label}·{chart[phase]['name']}·{yao_name(chart[phase]['lines'], chart[phase]['yuan'])}：{text['yaoci']}（{status}）"
            )
    lines.append(
        "爻辞、注文与诗歌分别标注来源；旧吉凶摘要标签未获底本条件认证，葉与不葉及岁运分支不自动选取。"
    )
    if chart.get("yuantang_derivation"):
        lines.extend(["", yuantang_snapshot(chart["yuantang_derivation"])])
    if jg and jg.get("body_structure"):
        lines.extend(["", structure_snapshot(jg["body_structure"])])
    return "\n".join(lines)
