"""
Zi Wei Dou Shu (紫微斗数) chart, horoscope, and rules for the FateBridge
metaphysics package.

Pure relocation from the package facade: the ZIWEI_* tables, sihua ordering,
五行局 resolution, and the public ``build_ziwei_chart`` / ``build_ziwei_horoscope``
/ ``build_ziwei_rules``. Shared primitives come from ``.common``; star
brightness/mutagen tables from ``..ziwei_tables``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, cast

from fatebridge.utils.birth_input import normalize_gender

from ...utils.data import (
    EARTHLY_BRANCHES,
    HEAVENLY_STEMS,
    ZIWEI_BRANCH_SEQUENCE,
    get_nayin,
)
from ..ziwei_tables import lookup_star_brightness, split_star_mutagen
from .common import MetaphysicsSeed, require_lunar_month_day, sexagenary_index_for

_WUXING_JU_NUMBER_BY_ELEMENT: Dict[str, int] = {
    "水": 2,
    "木": 3,
    "金": 4,
    "土": 5,
    "火": 6,
}


_WUXING_JU_LABEL_BY_NUMBER: Dict[int, str] = {
    2: "水二局",
    3: "木三局",
    4: "金四局",
    5: "土五局",
    6: "火六局",
}


def _resolve_wuxing_ju(ming_stem: str, ming_branch: str) -> Dict[str, Any]:
    """由命宫干支的纳音推出五行局 (起大限岁数)。"""
    nayin = get_nayin(ming_stem, ming_branch)
    element = nayin[-1] if nayin and nayin != "未知纳音" else "木"
    if element not in _WUXING_JU_NUMBER_BY_ELEMENT:
        element = "木"  # 无法识别时退回 木三局 保守默认
    number = _WUXING_JU_NUMBER_BY_ELEMENT[element]
    return {
        "number": number,
        "element": element,
        "label": _WUXING_JU_LABEL_BY_NUMBER[number],
        "nayin": nayin,
    }


ZIWEI_PALACE_SEQUENCE = [
    "命宫",
    "父母宫",
    "福德宫",
    "田宅宫",
    "官禄宫",
    "仆役宫",
    "迁移宫",
    "疾厄宫",
    "财帛宫",
    "子女宫",
    "夫妻宫",
    "兄弟宫",
]


ZIWEI_SIHUA_RULES = {
    "甲": {"化禄": "廉贞", "化权": "破军", "化科": "武曲", "化忌": "太阳"},
    "乙": {"化禄": "天机", "化权": "天梁", "化科": "紫微", "化忌": "太阴"},
    "丙": {"化禄": "天同", "化权": "天机", "化科": "文昌", "化忌": "廉贞"},
    "丁": {"化禄": "太阴", "化权": "天同", "化科": "天机", "化忌": "巨门"},
    "戊": {"化禄": "贪狼", "化权": "太阴", "化科": "右弼", "化忌": "天机"},
    "己": {"化禄": "武曲", "化权": "贪狼", "化科": "天梁", "化忌": "文曲"},
    "庚": {"化禄": "太阳", "化权": "武曲", "化科": "太阴", "化忌": "天同"},
    "辛": {"化禄": "巨门", "化权": "太阳", "化科": "文曲", "化忌": "文昌"},
    "壬": {"化禄": "天梁", "化权": "紫微", "化科": "左辅", "化忌": "武曲"},
    "癸": {"化禄": "破军", "化权": "巨门", "化科": "太阴", "化忌": "贪狼"},
}


SIHUA_DISPLAY_ORDER = {
    "化忌": 0,
    "化权": 1,
    "化科": 2,
    "化禄": 3,
}


class OrderedSihuaKey(str):
    """String subclass that keeps Zi Wei sihua labels in traditional order."""

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, str):
            return NotImplemented
        return (
            SIHUA_DISPLAY_ORDER.get(str(self), 99),
            str(self),
        ) < (
            SIHUA_DISPLAY_ORDER.get(str(other), 99),
            str(other),
        )


def ordered_sihua_mapping(mapping: Dict[str, str]) -> Dict[OrderedSihuaKey, str]:
    return {OrderedSihuaKey(label): star for label, star in mapping.items()}


def _branch_from_hour(hour_branch: str) -> int:
    return EARTHLY_BRANCHES.index(hour_branch) + 1


def _lunar_year_ganzhi(lunar_year: int) -> Tuple[str, str]:
    """紫微斗数年干支：以农历年（正月初一为界）推，不用八字的立春换年。

    命盘的五虎遁宫干、四化、年支系辅煞（天马/火铃/红鸾天喜/孤辰寡宿等）
    都随这个年干支走。立春～正月初一之间出生者，立春年比正月初一年多一位，
    若误用八字年柱（立春界）会让整张星盘平移一宫。
    """
    return (
        HEAVENLY_STEMS[(lunar_year - 4) % len(HEAVENLY_STEMS)],
        EARTHLY_BRANCHES[(lunar_year - 4) % len(EARTHLY_BRANCHES)],
    )


def _apply_sihua_to_palaces(
    palaces: List[Dict[str, Any]],
    year_stem: str,
) -> Dict[str, str]:
    sihua = ZIWEI_SIHUA_RULES[year_stem]
    transformed = {}
    for change_name, star_name in sihua.items():
        for palace in palaces:
            if star_name in palace["stars"]:
                palace["stars"] = [
                    f"{star}{change_name}" if star == star_name else star
                    for star in palace["stars"]
                ]
                transformed[change_name] = f"{star_name}入{palace['name']}"
                break
        else:
            transformed[change_name] = star_name
    # ordered_sihua_mapping keeps OrderedSihuaKey (a str subclass) keys for their
    # custom ordering; at runtime they are plain str keys, satisfying Dict[str, str].
    return cast(Dict[str, str], ordered_sihua_mapping(sihua))


def build_ziwei_chart(seed: MetaphysicsSeed, gender: str) -> Dict[str, Any]:
    lunar, lunar_month, lunar_day = require_lunar_month_day(seed, "紫微斗数")

    # 紫微斗数闰月处理：以十五日为界，十五日及以前作当月算，十六日及以后作下月算
    if lunar.get("is_leap_month"):
        if lunar_day >= 16:
            lunar_month = (lunar_month % 12) + 1
    hour_branch = seed.pillars["hour"][1]
    hour_index = _branch_from_hour(hour_branch)
    # 年干支按农历年（正月初一为界）取，而非八字立春年柱——见 _lunar_year_ganzhi。
    lunar_year = lunar.get("year")
    if lunar_year is None:
        raise ValueError("紫微斗数需要完整农历年月日，无法起盘：农历年缺失")
    year_stem, year_branch = _lunar_year_ganzhi(int(lunar_year))

    ming_index = (lunar_month - hour_index) % 12
    shen_index = (lunar_month + hour_index - 2) % 12
    ming_branch = ZIWEI_BRANCH_SEQUENCE[ming_index]
    shen_branch = ZIWEI_BRANCH_SEQUENCE[shen_index]

    # 宫干按「五虎遁」规则从年干推出：
    #   甲己之年 → 寅宫起丙寅，乙庚 → 戊寅，丙辛 → 庚寅，丁壬 → 壬寅，戊癸 → 甲寅。
    # ZIWEI_BRANCH_SEQUENCE 以 寅=0 为起点顺数到丑=11，因此某宫位在序列中的位置
    # 就是它相对于寅的偏移量，可直接叠加到寅宫干基。
    year_stem_index = HEAVENLY_STEMS.index(year_stem)
    yin_stem_base = (year_stem_index * 2 + 2) % len(HEAVENLY_STEMS)
    palace_stems = [
        HEAVENLY_STEMS[
            (yin_stem_base + (ming_index + offset) % 12) % len(HEAVENLY_STEMS)
        ]
        for offset in range(12)
    ]
    palace_branches = (
        ZIWEI_BRANCH_SEQUENCE[ming_index:] + ZIWEI_BRANCH_SEQUENCE[:ming_index]
    )
    palace_names = ZIWEI_PALACE_SEQUENCE[:]
    # 五行局 (起大限岁数) — 由命宫 (palaces[0]) 干支的纳音决定
    # Note: palace_stems[0] and palace_branches[0] are Ming Gong stems/branches
    wuxing_ju = _resolve_wuxing_ju(palace_stems[0], palace_branches[0])
    start_age = wuxing_ju["number"]

    # 大限方向: 阳男阴女顺行 / 阴男阳女逆行
    is_yang_year = HEAVENLY_STEMS.index(year_stem) % 2 == 0
    canonical_gender = normalize_gender(gender)
    daxian_forward = (canonical_gender == "男" and is_yang_year) or (
        canonical_gender == "女" and not is_yang_year
    )

    daxian_direction_label = "顺行" if daxian_forward else "逆行"

    # --- Standard Zi Wei Star Placement ---
    # 1. Resolve Zi Wei star position based on Wu Xing Ju and Lunar Day
    ju_num = wuxing_ju["number"]
    # Formula: find X such that ju_num * X >= lunar_day, Y = ju_num * X - lunar_day
    x = (lunar_day + ju_num - 1) // ju_num
    y = ju_num * x - lunar_day
    if y % 2 == 0:
        ziwei_index = (x + y - 1) % 12  # Relative to 寅 (0)
    else:
        ziwei_index = (x - y - 1) % 12

    # 2. Derive Tian Fu star position (mirrored from Zi Wei)
    tianfu_index = (12 - ziwei_index) % 12

    # 3. Place stars
    # Zi Wei group (Counter-clockwise relative to Zi Wei)
    ziwei_group = {
        "紫微": 0,
        "天机": -1,
        "太阳": -3,
        "武曲": -4,
        "天同": -5,
        "廉贞": -8,
    }
    # Tian Fu group (Clockwise relative to Tian Fu)
    tianfu_group = {
        "天府": 0,
        "太阴": 1,
        "贪狼": 2,
        "巨门": 3,
        "天相": 4,
        "天梁": 5,
        "七杀": 6,
        "破军": 10,
    }

    palaces: List[Dict[str, Any]] = []
    for index, palace_name in enumerate(palace_names):
        # 命宫永远是第一个大限，其余按顺/逆方向沿宫位排列；
        # 宫名序列已按地支递增方向排布（命→父母→福德→...→兄弟）。
        if daxian_forward:
            period_index = index  # 阳男/阴女：命→父母→福德→...
        else:
            period_index = (-index) % 12  # 阴男/阳女：命→兄弟→夫妻→...
        period_start = start_age + period_index * 10
        palace: Dict[str, Any] = {
            "name": palace_name,
            "ganzhi": f"{palace_stems[index]}{palace_branches[index]}",
            "daxian": f"{period_start}~{period_start + 9}",
            "daxian_period": period_index + 1,
            "stars": [],
        }
        palaces.append(palace)

    # Place Zi Wei group
    for star, offset in ziwei_group.items():
        idx = (ziwei_index + offset) % 12
        # Current palaces list is ordered by ZIWEI_PALACE_SEQUENCE starting from Ming Gong
        # But we need to find the palace that matches the earthly branch index (idx)
        for p in palaces:
            if p["ganzhi"][1] == ZIWEI_BRANCH_SEQUENCE[idx]:
                p["stars"].append(star)
                break

    # Place Tian Fu group
    for star, offset in tianfu_group.items():
        idx = (tianfu_index + offset) % 12
        for p in palaces:
            if p["ganzhi"][1] == ZIWEI_BRANCH_SEQUENCE[idx]:
                p["stars"].append(star)
                break

    # 4. Place Auxiliary Stars (Fixed Rules)
    # ZIWEI_BRANCH_SEQUENCE indexing: 寅(0), 卯(1), 辰(2), 巳(3), 午(4), 未(5),
    # 申(6), 酉(7), 戌(8), 亥(9), 子(10), 丑(11)。
    # 月系（生月起）：左辅从辰顺、右弼从戌逆。
    # 时系（生时起）：文昌从戌逆、文曲从辰顺。
    aux_locators = {
        "左辅": (2 + lunar_month - 1) % 12,
        "右弼": (8 - (lunar_month - 1)) % 12,
        "文昌": (8 - (hour_index - 1)) % 12,
        "文曲": (2 + (hour_index - 1)) % 12,
    }

    for star, idx in aux_locators.items():
        for p in palaces:
            if p["ganzhi"][1] == ZIWEI_BRANCH_SEQUENCE[idx]:
                p["stars"].append(star)
                break

    # --- 年干 / 年支 / 生时 派生的辅煞星 ---
    # year_stem / year_branch 已在上方按农历年（正月初一）统一确定。
    year_branch_earth_index = EARTHLY_BRANCHES.index(year_branch)
    hour_earth_index = EARTHLY_BRANCHES.index(hour_branch)

    lucun_by_year_stem = {
        "甲": "寅",
        "乙": "卯",
        "丙": "巳",
        "丁": "午",
        "戊": "巳",
        "己": "午",
        "庚": "申",
        "辛": "酉",
        "壬": "亥",
        "癸": "子",
    }
    tiankui_by_year_stem = {
        "甲": "丑",
        "戊": "丑",
        "庚": "丑",
        "乙": "子",
        "己": "子",
        "丙": "亥",
        "丁": "亥",
        "辛": "午",
        "壬": "卯",
        "癸": "卯",
    }
    tianyue_by_year_stem = {
        "甲": "未",
        "戊": "未",
        "庚": "未",
        "乙": "申",
        "己": "申",
        "丙": "酉",
        "丁": "酉",
        "辛": "寅",
        "壬": "巳",
        "癸": "巳",
    }
    # 年支三合局定马 / 火铃起点
    tianma_by_year_branch = {
        "寅": "申",
        "午": "申",
        "戌": "申",
        "申": "寅",
        "子": "寅",
        "辰": "寅",
        "巳": "亥",
        "酉": "亥",
        "丑": "亥",
        "亥": "巳",
        "卯": "巳",
        "未": "巳",
    }
    huoxing_start_by_year_branch = {
        "寅": "丑",
        "午": "丑",
        "戌": "丑",
        "申": "寅",
        "子": "寅",
        "辰": "寅",
        "巳": "卯",
        "酉": "卯",
        "丑": "卯",
        "亥": "酉",
        "卯": "酉",
        "未": "酉",
    }
    lingxing_start_by_year_branch = {
        "寅": "卯",
        "午": "卯",
        "戌": "卯",
        "申": "戌",
        "子": "戌",
        "辰": "戌",
        "巳": "戌",
        "酉": "戌",
        "丑": "戌",
        "亥": "戌",
        "卯": "戌",
        "未": "戌",
    }

    def _branch_by_offset(start_branch: str, offset: int) -> str:
        return EARTHLY_BRANCHES[(EARTHLY_BRANCHES.index(start_branch) + offset) % 12]

    lucun_branch = lucun_by_year_stem[year_stem]
    minor_star_branches: Dict[str, str] = {
        "禄存": lucun_branch,
        "擎羊": _branch_by_offset(lucun_branch, 1),  # 禄存前一位
        "陀罗": _branch_by_offset(lucun_branch, -1),  # 禄存后一位
        "天魁": tiankui_by_year_stem[year_stem],
        "天钺": tianyue_by_year_stem[year_stem],
        "天马": tianma_by_year_branch[year_branch],
        "火星": _branch_by_offset(
            huoxing_start_by_year_branch[year_branch], hour_earth_index
        ),
        "铃星": _branch_by_offset(
            lingxing_start_by_year_branch[year_branch], hour_earth_index
        ),
        # 地空 / 地劫：生时起亥逆 / 顺
        "地空": EARTHLY_BRANCHES[(11 - hour_earth_index) % 12],
        "地劫": EARTHLY_BRANCHES[(11 + hour_earth_index) % 12],
        # 红鸾 / 天喜：年支起卯逆 / 对冲
        "红鸾": EARTHLY_BRANCHES[(3 - year_branch_earth_index) % 12],
        "天喜": EARTHLY_BRANCHES[(9 - year_branch_earth_index) % 12],
    }
    for star, target_branch in minor_star_branches.items():
        for p in palaces:
            if p["ganzhi"][1] == target_branch:
                p["stars"].append(star)
                break

    # --- 杂星 (adjective stars) ---
    # 年支三合派
    huagai_by_triad = {
        "寅": "戌",
        "午": "戌",
        "戌": "戌",
        "申": "辰",
        "子": "辰",
        "辰": "辰",
        "巳": "丑",
        "酉": "丑",
        "丑": "丑",
        "亥": "未",
        "卯": "未",
        "未": "未",
    }
    xianchi_by_triad = {
        "寅": "卯",
        "午": "卯",
        "戌": "卯",
        "申": "酉",
        "子": "酉",
        "辰": "酉",
        "巳": "午",
        "酉": "午",
        "丑": "午",
        "亥": "子",
        "卯": "子",
        "未": "子",
    }
    # 孤辰/寡宿 按年支"方局"
    guchen_gushu_table = {
        frozenset({"寅", "卯", "辰"}): ("巳", "丑"),
        frozenset({"巳", "午", "未"}): ("申", "辰"),
        frozenset({"申", "酉", "戌"}): ("亥", "未"),
        frozenset({"亥", "子", "丑"}): ("寅", "戌"),
    }
    guchen_branch = None
    guashu_branch = None
    for members, (gu, gua) in guchen_gushu_table.items():
        if year_branch in members:
            guchen_branch, guashu_branch = gu, gua
            break

    # 破碎 按年支
    posui_by_year_branch = {
        "子": "巳",
        "午": "巳",
        "卯": "巳",
        "酉": "巳",
        "寅": "酉",
        "申": "酉",
        "巳": "酉",
        "亥": "酉",
        "辰": "丑",
        "戌": "丑",
        "丑": "丑",
        "未": "丑",
    }
    # 蜚廉 按年支（固定表）
    feilian_by_year_branch = {
        "子": "申",
        "丑": "酉",
        "寅": "戌",
        "卯": "巳",
        "辰": "午",
        "巳": "未",
        "午": "寅",
        "未": "卯",
        "申": "辰",
        "酉": "亥",
        "戌": "子",
        "亥": "丑",
    }

    # 年干系 查表
    tianguan_by_year_stem = {
        "甲": "未",
        "乙": "辰",
        "丙": "巳",
        "丁": "寅",
        "戊": "卯",
        "己": "酉",
        "庚": "亥",
        "辛": "酉",
        "壬": "戌",
        "癸": "午",
    }
    tianfu_by_year_stem = {
        "甲": "酉",
        "乙": "申",
        "丙": "子",
        "丁": "亥",
        "戊": "卯",
        "己": "寅",
        "庚": "午",
        "辛": "巳",
        "壬": "午",
        "癸": "巳",
    }
    tianchu_by_year_stem = {
        "甲": "巳",
        "乙": "午",
        "丙": "子",
        "丁": "巳",
        "戊": "午",
        "己": "申",
        "庚": "寅",
        "辛": "午",
        "壬": "酉",
        "癸": "亥",
    }

    # 月系（按生月, 1-12）: 天月 / 天刑 / 天姚 / 天巫 / 解神 / 阴煞
    tianyue_month_table = [
        "戌",
        "巳",
        "辰",
        "寅",
        "未",
        "卯",
        "亥",
        "未",
        "寅",
        "午",
        "戌",
        "寅",
    ]
    tianxing_start_idx = 9  # 酉起正月顺
    tianyao_start_idx = 1  # 丑起正月顺
    tianwu_cycle = ["巳", "申", "寅", "亥"]  # 4-day cycle
    jieshen_pair_table = [
        "申",
        "申",
        "戌",
        "戌",
        "子",
        "子",
        "寅",
        "寅",
        "辰",
        "辰",
        "午",
        "午",
    ]
    yinsha_six_cycle = ["寅", "子", "戌", "申", "午", "辰"]

    # 时系: 封诰 / 台辅
    fenggao_start_idx = 2  # 寅起子时顺
    taifu_start_idx = 6  # 午起子时顺

    # 命宫/身宫 + 年支: 天才 / 天寿
    ming_branch_idx = EARTHLY_BRANCHES.index(ming_branch)
    shen_branch_idx = EARTHLY_BRANCHES.index(shen_branch)

    # 文昌/文曲地支位置（复用前面 aux_locators 公式，转成地支索引）
    wenchang_earth_idx = (10 - hour_earth_index) % 12
    wenqu_earth_idx = (4 + hour_earth_index) % 12
    # 左辅/右弼地支位置（月系）
    zuofu_earth_idx = (4 + lunar_month - 1) % 12  # 辰(4)起正月顺
    youbi_earth_idx = (10 - (lunar_month - 1)) % 12  # 戌(10)起正月逆

    # 旬空: 年支所在旬空亡，阳干取阳支、阴干取阴支
    #   甲子旬 → 戌亥, 甲戌旬 → 申酉, 甲申旬 → 午未,
    #   甲午旬 → 辰巳, 甲辰旬 → 寅卯, 甲寅旬 → 子丑。
    #   第一支为阳(戌/申/午/辰/寅/子)，第二支为阴(亥/酉/未/巳/卯/丑)。
    year_pillar_text = f"{year_stem}{year_branch}"
    year_cycle_index = sexagenary_index_for(year_pillar_text)
    xunkong_pairs = [
        ("戌", "亥"),
        ("申", "酉"),
        ("午", "未"),
        ("辰", "巳"),
        ("寅", "卯"),
        ("子", "丑"),
    ]
    xun_group = year_cycle_index // 10  # 0..5
    xunkong_yang, xunkong_yin = xunkong_pairs[xun_group]
    is_yang_stem = HEAVENLY_STEMS.index(year_stem) % 2 == 0
    xunkong_branch = xunkong_yang if is_yang_stem else xunkong_yin

    adjective_star_branches: Dict[str, str] = {
        # 命身派
        "天伤": EARTHLY_BRANCHES[(ming_branch_idx + 5) % 12],
        "天使": EARTHLY_BRANCHES[(ming_branch_idx + 7) % 12],
        "天才": EARTHLY_BRANCHES[(ming_branch_idx + year_branch_earth_index) % 12],
        "天寿": EARTHLY_BRANCHES[(shen_branch_idx + year_branch_earth_index) % 12],
        # 年支三合派
        "华盖": huagai_by_triad[year_branch],
        "咸池": xianchi_by_triad[year_branch],
        "孤辰": guchen_branch or year_branch,
        "寡宿": guashu_branch or year_branch,
        "破碎": posui_by_year_branch[year_branch],
        "蜚廉": feilian_by_year_branch[year_branch],
        # 年支派
        "龙池": EARTHLY_BRANCHES[(4 + year_branch_earth_index) % 12],
        "凤阁": EARTHLY_BRANCHES[(10 - year_branch_earth_index) % 12],
        "年解": EARTHLY_BRANCHES[(10 - year_branch_earth_index) % 12],  # 与凤阁同位
        "天哭": EARTHLY_BRANCHES[(6 - year_branch_earth_index) % 12],
        "天虚": EARTHLY_BRANCHES[(6 + year_branch_earth_index) % 12],
        "天德": EARTHLY_BRANCHES[(9 + year_branch_earth_index) % 12],
        "月德": EARTHLY_BRANCHES[(5 + year_branch_earth_index) % 12],
        # 年干查表派
        "天官": tianguan_by_year_stem[year_stem],
        "天福": tianfu_by_year_stem[year_stem],
        "天厨": tianchu_by_year_stem[year_stem],
        # 月系
        "天月": tianyue_month_table[(lunar_month - 1) % 12],
        "天刑": EARTHLY_BRANCHES[(tianxing_start_idx + lunar_month - 1) % 12],
        "天姚": EARTHLY_BRANCHES[(tianyao_start_idx + lunar_month - 1) % 12],
        "天巫": tianwu_cycle[(lunar_month - 1) % 4],
        "解神": jieshen_pair_table[(lunar_month - 1) % 12],
        "阴煞": yinsha_six_cycle[(lunar_month - 1) % 6],
        # 时系
        "封诰": EARTHLY_BRANCHES[(fenggao_start_idx + hour_earth_index) % 12],
        "台辅": EARTHLY_BRANCHES[(taifu_start_idx + hour_earth_index) % 12],
        # 月日复合派 (三台/八座 沿左辅/右弼; 恩光/天贵 沿文昌/文曲)
        "三台": EARTHLY_BRANCHES[(zuofu_earth_idx + lunar_day - 1) % 12],
        "八座": EARTHLY_BRANCHES[(youbi_earth_idx - (lunar_day - 1)) % 12],
        "恩光": EARTHLY_BRANCHES[(wenchang_earth_idx + lunar_day - 2) % 12],
        "天贵": EARTHLY_BRANCHES[(wenqu_earth_idx + lunar_day - 2) % 12],
        # 旬空
        "旬空": xunkong_branch,
    }
    for star, target_branch in adjective_star_branches.items():
        for p in palaces:
            if p["ganzhi"][1] == target_branch:
                p["stars"].append(star)
                break

    sihua = _apply_sihua_to_palaces(palaces, year_stem)
    for palace in palaces:
        palace["stars"] = sorted(dict.fromkeys(palace["stars"]))

    # Attach brightness and parsed mutagen to each star label.
    # `palace["stars"]` displays a list[str] of mutagen-suffixed labels;
    # `stars_detail` mirrors it 1:1 with structured data.
    for palace in palaces:
        palace_branch = palace["ganzhi"][1]
        detail: List[Dict[str, Any]] = []
        for label in palace["stars"]:
            base_name, mutagen = split_star_mutagen(label)
            detail.append(
                {
                    "name": base_name,
                    "label": label,
                    "brightness": lookup_star_brightness(base_name, palace_branch),
                    "mutagen": mutagen,
                }
            )
        palace["stars_detail"] = detail

    ming_palace = next(palace for palace in palaces if palace["name"] == "命宫")
    shen_palace = next(
        (palace for palace in palaces if palace["ganzhi"][1] == shen_branch),
        ming_palace,
    )
    return {
        "time_algorithm": "真太阳时" if seed.applied_true_solar else "直接时间",
        "year_stem": year_stem,
        "lunar_date": {
            "year": int(lunar["year"]),
            "month": int(lunar["month"]),
            "day": int(lunar["day"]),
            "is_leap_month": bool(lunar.get("is_leap_month")),
        },
        "hour_branch": hour_branch,
        "calendar_rules": {
            "year_boundary": "农历正月初一",
            "late_zi": "晚子时本命农历日期算当天",
            "leap_month": "闰月十五日及以前算当月，之后算下月",
        },
        "ming_gong": {
            "name": "命宫",
            "branch": ming_branch,
            "ganzhi": ming_palace["ganzhi"],
        },
        "shen_gong": {
            "name": "身宫",
            "branch": shen_branch,
            "ganzhi": shen_palace["ganzhi"],
        },
        "wuxing_ju": wuxing_ju,
        "daxian_direction": daxian_direction_label,
        "sihua": sihua,
        "palaces": palaces,
    }


_XIAOXIAN_START_BY_YEAR_BRANCH = {
    "寅": "辰",
    "午": "辰",
    "戌": "辰",
    "申": "戌",
    "子": "戌",
    "辰": "戌",
    "巳": "未",
    "酉": "未",
    "丑": "未",
    "亥": "丑",
    "卯": "丑",
    "未": "丑",
}


def _palace_by_branch(palaces: List[Dict[str, Any]], branch: str) -> Dict[str, Any]:
    palace = next((p for p in palaces if p["ganzhi"][1] == branch), None)
    if palace is None:
        raise ValueError(f"未找到地支为 {branch!r} 的宫位")
    return palace


def _palace_for_nominal_age(
    palaces: List[Dict[str, Any]], nominal_age: int
) -> Dict[str, Any]:
    for palace in palaces:
        lo, hi = (int(x) for x in palace["daxian"].split("~"))
        if lo <= nominal_age <= hi:
            return palace
    # Before the first decade, use the six childhood palaces rather than
    # accidentally returning the last (oldest) decade.
    childhood = ("命宫", "财帛宫", "疾厄宫", "夫妻宫", "福德宫", "官禄宫")
    first_age = min(int(p["daxian"].split("~")[0]) for p in palaces)
    if 1 <= nominal_age < first_age:
        return next(p for p in palaces if p["name"] == childhood[nominal_age - 1])
    raise ValueError("目标虚岁超出紫微大限支持范围")


def _xiaoxian_branch(year_branch: str, nominal_age: int, gender: str) -> str:
    start = _XIAOXIAN_START_BY_YEAR_BRANCH[year_branch]
    start_idx = ZIWEI_BRANCH_SEQUENCE.index(start)
    offset = (nominal_age - 1) % 12
    forward = normalize_gender(gender) == "男"
    idx = (start_idx + offset) % 12 if forward else (start_idx - offset) % 12
    return ZIWEI_BRANCH_SEQUENCE[idx]


def _horoscope_scope(scope: str, palace: Dict[str, Any], stem: str) -> Dict[str, Any]:
    branch = palace["ganzhi"][1]
    return {
        "scope": scope,
        "palace_name": palace["name"],
        # The index names the natal palace occupied by this scope's Ming
        # activity index. It is not a rotated scope-specific functional palace.
        "scope_palace_role": "ming_palace_activity_index",
        "natal_palace_name": palace["name"],
        "branch": branch,
        "branch_index": ZIWEI_BRANCH_SEQUENCE.index(branch),
        "palace_ganzhi": palace["ganzhi"],
        "stem": stem,
        "mutagen": dict(ZIWEI_SIHUA_RULES[stem]),
    }


def _link_mutagen_to_natal_stars(
    scope: Dict[str, Any], palaces: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Join the computed transformations to computed natal star placements.

    No scope palace rotation or career interpretation is performed here. Keep
    the natal transformation separately so it cannot be mistaken for the new
    transformation of this scope.
    """
    links = []
    for transformation, star_name in scope["mutagen"].items():
        matches = [
            (palace, star)
            for palace in palaces
            for star in palace["stars_detail"]
            if star["name"] == star_name
        ]
        if not matches:
            links.append(
                {
                    "transformation": transformation,
                    "star": star_name,
                    "status": "not_located_in_natal_chart",
                }
            )
        for palace, star in matches:
            links.append(
                {
                    "transformation": transformation,
                    "star": star_name,
                    "status": "matched",
                    "natal_palace_name": palace["name"],
                    "natal_palace_ganzhi": palace["ganzhi"],
                    "natal_branch": palace["ganzhi"][1],
                    "natal_star_label": star["label"],
                    "natal_star_brightness": star["brightness"],
                    "natal_mutagen": star["mutagen"],
                }
            )
    return links


def build_ziwei_horoscope(
    *,
    chart: Dict[str, Any],
    gender: str,
    target_seed: MetaphysicsSeed,
) -> Dict[str, Any]:
    """Six scopes using lunar-year ages and the natal-month/hour Dou Jun.

    Scope ``branch`` is the actual natal palace, not the calendar branch of
    the target date. Month/day/hour stems still determine their own 四化.
    This follows iztro 2.5.8 normal year/age/horoscope boundaries; late-zi
    natal dates keep FateBridge's existing current-day convention.
    """
    palaces = chart["palaces"]
    target_lunar, target_month, target_day = require_lunar_month_day(
        target_seed, "紫微斗数运限"
    )
    natal_lunar = chart["lunar_date"]
    nominal_age = int(target_lunar["year"]) - int(natal_lunar["year"]) + 1
    if nominal_age < 1:
        raise ValueError("目标农历年早于出生农历年")
    natal_year_branch = _lunar_year_ganzhi(int(natal_lunar["year"]))[1]
    target_year_stem, target_year_branch = _lunar_year_ganzhi(int(target_lunar["year"]))

    daxian_palace = _palace_for_nominal_age(palaces, nominal_age)
    daxian = _horoscope_scope("大限", daxian_palace, daxian_palace["ganzhi"][0])

    xiao_palace = _palace_by_branch(
        palaces, _xiaoxian_branch(natal_year_branch, nominal_age, gender)
    )
    # 小限 四化 follows the 宫干 of the 小限 palace (iztro convention), not the 流年 stem.
    xiaoxian = _horoscope_scope("小限", xiao_palace, xiao_palace["ganzhi"][0])

    natal_month = int(natal_lunar["month"]) + int(
        natal_lunar["is_leap_month"] and int(natal_lunar["day"]) > 15
    )
    target_month += int(target_lunar.get("is_leap_month", False) and target_day > 15)
    # Reverse from the year's palace to birth month, then forward to birth
    # hour; the result is 正月斗君. Count the target month/day/hour from it.
    month_index = (
        ZIWEI_BRANCH_SEQUENCE.index(target_year_branch)
        - natal_month
        + EARTHLY_BRANCHES.index(chart["hour_branch"])
        + target_month
    ) % 12
    day_index = (month_index + target_day - 1) % 12
    hour_index = (
        day_index + EARTHLY_BRANCHES.index(target_seed.pillars["hour"][1])
    ) % 12
    month_stem = HEAVENLY_STEMS[
        (HEAVENLY_STEMS.index(target_year_stem) * 2 + 2 + target_month - 1) % 10
    ]
    flowing = [
        _horoscope_scope(
            "流年", _palace_by_branch(palaces, target_year_branch), target_year_stem
        )
    ]
    for scope, index, stem in (
        ("流月", month_index, month_stem),
        ("流日", day_index, target_seed.pillars["day"][0]),
        ("流时", hour_index, target_seed.pillars["hour"][0]),
    ):
        flowing.append(
            _horoscope_scope(
                scope, _palace_by_branch(palaces, ZIWEI_BRANCH_SEQUENCE[index]), stem
            )
        )

    scopes = [daxian, xiaoxian, *flowing]
    for scope_record in scopes:
        scope_record["mutagen_natal_links"] = _link_mutagen_to_natal_stars(
            scope_record, palaces
        )

    return {
        "engine": "fatebridge-offline",
        "nominal_age": nominal_age,
        "calendar_rules": chart["calendar_rules"],
        "interpretation_scope": {
            "contract_version": "natal_scope_linkage_v1",
            "scope_palace_meaning": "运限命宫活动索引所临的本命宫",
            "transformation_meaning": "本层四化标记连接本命星所在宫，不是本层旋宫的功能宫",
            "full_scope_palaces_supported": False,
            "limitations": ["未提供完整运限十二宫旋宫表", "未据此判定职业事件或吉凶"],
        },
        "scopes": scopes,
    }


def build_ziwei_rules(year_stem: Optional[str] = None) -> Dict[str, Any]:
    catalogue = {
        "palace_sequence": ZIWEI_PALACE_SEQUENCE,
        "ming_gong_method": "寅宫起正月，顺数生月，逆数生时。",
        "shen_gong_method": "寅宫起正月，顺数生月，再顺数生时。",
        "sihua_by_year_stem": ZIWEI_SIHUA_RULES,
    }
    focused = None
    if year_stem:
        focused = {
            "year_stem": year_stem,
            "sihua": ordered_sihua_mapping(ZIWEI_SIHUA_RULES[year_stem]),
        }
    return {
        "requested_year_stem": year_stem,
        "rule_catalogue": catalogue,
        "focused_rules": focused,
    }
