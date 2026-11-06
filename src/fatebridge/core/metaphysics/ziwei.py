"""
Zi Wei Dou Shu (紫微斗数) chart, horoscope, and rules for the FateBridge
metaphysics package.

Deterministic placement, versioned source conventions, natal cycles and scope
identity. Geometry and evidence links stay separate from event interpretations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, cast

from fatebridge.core.ziwei_age import nominal_age_calendar
from fatebridge.core.ziwei_aux_sources import auxiliary_placement_source_evidence
from fatebridge.core.ziwei_auxiliary import (
    ZIWEI_LUCUN_BY_STEM,
    attach_natal_cycles,
    chart_masters,
    flowing_lucun_stars,
)
from fatebridge.core.ziwei_childhood import childhood_limit
from fatebridge.core.ziwei_classical import (
    annual_text_stars,
    annual_three_sha,
    symbolic_properties,
)
from fatebridge.core.ziwei_conditions import structural_condition_evidence
from fatebridge.core.ziwei_cycle_sources import cycle_source_evidence
from fatebridge.core.ziwei_evidence import (
    horoscope_natal_prerequisites,
    natal_reading_view,
    palace_structural_evidence,
    scope_palace_map,
)
from fatebridge.core.ziwei_limit_sources import limit_source_evidence
from fatebridge.core.ziwei_ming_properties import ming_property_evidence
from fatebridge.core.ziwei_rulesets import (
    DEFAULT_ZIWEI_PROFILE,
)
from fatebridge.core.ziwei_rulesets import ZIWEI_SIHUA_RULES as ZIWEI_SIHUA_RULES
from fatebridge.core.ziwei_rulesets import (
    effective_lunar_month,
    sihua_rules_for,
    validate_rule_profile,
    validate_sihua_source,
    ziwei_ruleset_metadata,
)
from fatebridge.core.ziwei_sources import (
    natal_sihua_source_comparison,
    sihua_source_comparison,
    ziwei_day_source_evidence,
    ziwei_prerequisite_source_evidence,
)
from fatebridge.core.ziwei_subperiods import limit_subperiod_evidence
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
    element = nayin[-1] if nayin and nayin != "未知纳音" else ""
    if element not in _WUXING_JU_NUMBER_BY_ELEMENT:
        raise ValueError(f"命宫干支无法确定五行局：{ming_stem}{ming_branch}")
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
    rule_profile: str = DEFAULT_ZIWEI_PROFILE,
    *,
    sihua_source: str = "rule_profile",
) -> Dict[str, str]:
    sihua = sihua_rules_for(ZIWEI_SIHUA_RULES, rule_profile, sihua_source=sihua_source)[
        year_stem
    ]
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


def build_ziwei_chart(
    seed: MetaphysicsSeed,
    gender: str,
    *,
    rule_profile: str = DEFAULT_ZIWEI_PROFILE,
    sihua_source: str = "rule_profile",
) -> Dict[str, Any]:
    validate_rule_profile(rule_profile)
    validate_sihua_source(sihua_source)
    lunar, lunar_month, lunar_day = require_lunar_month_day(seed, "紫微斗数")

    lunar_month = effective_lunar_month(
        lunar_month, lunar_day, bool(lunar.get("is_leap_month")), rule_profile
    )
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
    gender_known = canonical_gender in {"男", "女"}
    daxian_forward = (canonical_gender == "男" and is_yang_year) or (
        canonical_gender == "女" and not is_yang_year
    )

    daxian_direction_label = (
        ("顺行" if daxian_forward else "逆行") if gender_known else "未定（缺少性别）"
    )

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
        # 软件首限命宫，摘录首限邻宫，其余按顺/逆方向排列；
        # 宫名序列已按地支递增方向排布（命→父母→福德→...→兄弟）。
        if daxian_forward:
            period_index = index  # 软件：命→父母→福德→...
        else:
            period_index = (-index) % 12  # 阴男/阳女：命→兄弟→夫妻→...
        if rule_profile == "quanshu_v2_excerpt":
            # 所选安大限诀从命前/后一宫起，首限为父母/兄弟。
            # 命宫仍为本命宫，不能因运限起点改变而搬移星曜。
            period_index = (period_index - 1) % 12
        period_start = start_age + period_index * 10
        palace: Dict[str, Any] = {
            "name": palace_name,
            "ganzhi": f"{palace_stems[index]}{palace_branches[index]}",
            "daxian": f"{period_start}~{period_start + 9}" if gender_known else None,
            "daxian_period": period_index + 1 if gender_known else None,
            "stars": [],
        }
        palaces.append(palace)

    for star, offset in ziwei_group.items():
        idx = (ziwei_index + offset) % 12
        # Current palaces list is ordered by ZIWEI_PALACE_SEQUENCE starting from Ming Gong
        # But we need to find the palace that matches the earthly branch index (idx)
        for p in palaces:
            if p["ganzhi"][1] == ZIWEI_BRANCH_SEQUENCE[idx]:
                p["stars"].append(star)
                break

    for star, offset in tianfu_group.items():
        idx = (tianfu_index + offset) % 12
        for p in palaces:
            if p["ganzhi"][1] == ZIWEI_BRANCH_SEQUENCE[idx]:
                p["stars"].append(star)
                break

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

    lucun_branch = ZIWEI_LUCUN_BY_STEM[year_stem]
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
    if rule_profile == "quanshu_v2_excerpt":
        # 1.3.0 adopts the explicit year-only reading of the selected verse;
        # the software profile retains its independent birth-hour walk.
        minor_star_branches["火星"] = huoxing_start_by_year_branch[year_branch]
        minor_star_branches["铃星"] = lingxing_start_by_year_branch[year_branch]
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
        # The software baseline has a separate 天空, not an alias for 地空.
        # 截路 / 空亡 are the two 截路空亡 branches, separate from 旬空.
        "天空": EARTHLY_BRANCHES[(year_branch_earth_index + 1) % 12],
        "截路": ("申", "午", "辰", "寅", "子")[year_stem_index % 5],
        "空亡": ("酉", "未", "巳", "卯", "丑")[year_stem_index % 5],
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

    # The pinned text gives both branches; the software's polarity-based
    # single-branch display is a different convention.
    displayed_xunkong = [xunkong_branch]
    if rule_profile == "quanshu_v2_excerpt":
        displayed_xunkong = [xunkong_yang, xunkong_yin]
        for p in palaces:
            if p["ganzhi"][1] in displayed_xunkong and "旬空" not in p["stars"]:
                p["stars"].append("旬空")

    sihua = _apply_sihua_to_palaces(
        palaces, year_stem, rule_profile, sihua_source=sihua_source
    )
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
                    "brightness": lookup_star_brightness(
                        base_name, palace_branch, rule_profile=rule_profile
                    ),
                    "mutagen": mutagen,
                }
            )
        palace["stars_detail"] = detail

    cycle_rules = attach_natal_cycles(
        palaces,
        element=wuxing_ju["element"],
        year_stem=year_stem,
        gender=gender,
        rule_profile=rule_profile,
    )
    for palace in palaces:
        palace["structural_evidence"] = palace_structural_evidence(palace, palaces)

    ming_palace = next(palace for palace in palaces if palace["name"] == "命宫")
    shen_palace = next(
        (palace for palace in palaces if palace["ganzhi"][1] == shen_branch),
        ming_palace,
    )
    return {
        "time_algorithm": "真太阳时" if seed.applied_true_solar else "直接时间",
        "reading_view": natal_reading_view(palaces),
        "symbolic_properties": symbolic_properties(palaces),
        "ming_textual_properties": ming_property_evidence(
            palaces, ming_branch=ming_branch, shen_branch=shen_branch
        ),
        "ming_structural_conditions": structural_condition_evidence(
            palaces, ming_branch=ming_branch, year_stem=year_stem
        ),
        "auxiliary_placement_sources": auxiliary_placement_source_evidence(
            palaces,
            lunar_month=int(lunar["month"]),
            lunar_day=lunar_day,
            is_leap=bool(lunar.get("is_leap_month")),
            hour_branch=hour_branch,
            year_branch=year_branch,
            rule_profile=rule_profile,
        ),
        "sihua_source_comparison": natal_sihua_source_comparison(
            palaces,
            year_stem=year_stem,
            selected_sihua=sihua,
            compared_assignments_applied=sihua_source == "naj_ming_v1",
        ),
        "void_systems": {
            "xun": {
                "source_branches": [xunkong_yang, xunkong_yin],
                "displayed_star_branches": displayed_xunkong,
                "display_rule": (
                    "both_branches_as_written"
                    if rule_profile == "quanshu_v2_excerpt"
                    else "software_primary_branch_by_year_polarity"
                ),
                "source": ziwei_ruleset_metadata(
                    rule_profile, sihua_source=sihua_source
                )["classical_source"],
            },
            "source_name_mapping": {
                "天空地劫诀中的天空": "地空",
                "软件另列的天空": "年支顺一位的软件扩展，不是前述古名天空",
                "安天德月德解神诀中的本生年解神": "年解",
                "软件另列的解神": "月系解神，与原文的本生年解神分开",
            },
        },
        "calendar_cycles": cycle_rules,
        "cycle_source_comparison": cycle_source_evidence(
            palaces,
            cycle_rules,
            element=wuxing_ju["element"],
            year_stem=year_stem,
            gender=gender,
            rule_profile=rule_profile,
        ),
        "chart_masters": chart_masters(
            palaces,
            ming_branch=ming_branch,
            year_branch=year_branch,
            rule_profile=rule_profile,
        ),
        "rule_trace": [
            {
                "rule_id": "lunar_month_for_placement",
                "source": (
                    ziwei_ruleset_metadata(rule_profile, sihua_source=sihua_source)[
                        "classical_source"
                    ]
                    if rule_profile == "quanshu_v2_excerpt"
                    else ziwei_ruleset_metadata(
                        rule_profile, sihua_source=sihua_source
                    )["baseline_source"]
                ),
                "inputs": {
                    "month": int(lunar["month"]),
                    "day": lunar_day,
                    "is_leap_month": bool(lunar.get("is_leap_month")),
                },
                "outputs": {"effective_month": lunar_month},
            },
            {
                "rule_id": "ming_shen_month_hour",
                "source": "安身命例；寅起正月、命逆身顺",
                "inputs": {"effective_month": lunar_month, "hour_branch": hour_branch},
                "outputs": {"ming_branch": ming_branch, "shen_branch": shen_branch},
            },
            {
                "rule_id": "wuhu_dun_nayin_ju",
                "source": "起五行寅例与命宫干支纳音",
                "inputs": {
                    "lunar_year": int(lunar["year"]),
                    "year_stem": year_stem,
                    "ming_ganzhi": ming_palace["ganzhi"],
                },
                "outputs": {
                    "nayin": wuxing_ju["nayin"],
                    "ju_number": wuxing_ju["number"],
                    "source_comparison": ziwei_prerequisite_source_evidence(
                        lunar_month=int(lunar["month"]),
                        is_leap=bool(lunar.get("is_leap_month")),
                        effective_month=lunar_month,
                        hour_branch=hour_branch,
                        year_stem=year_stem,
                        shen_branch=shen_branch,
                        palaces=palaces,
                        nayin=wuxing_ju["nayin"],
                        bureau=wuxing_ju["number"],
                    ),
                },
            },
            {
                "rule_id": "ziwei_tianfu_placement",
                "source": "五行局生日安紫微；寅申轴对映安天府",
                "inputs": {"lunar_day": lunar_day, "ju_number": ju_num},
                "outputs": {
                    "ziwei_branch": ZIWEI_BRANCH_SEQUENCE[ziwei_index],
                    "tianfu_branch": ZIWEI_BRANCH_SEQUENCE[tianfu_index],
                    "source_comparison": ziwei_day_source_evidence(
                        bureau=ju_num,
                        lunar_day=lunar_day,
                        actual_branch=ZIWEI_BRANCH_SEQUENCE[ziwei_index],
                    ),
                },
            },
            {
                "rule_id": "daxian_direction",
                "source": (
                    "明刊卷三安大限诀：阳男阴女从父母、阴男阳女从兄弟起"
                    if rule_profile == "quanshu_v2_excerpt"
                    else "软件首限命宫，阳男阴女顺、阴男阳女逆；未知性别不排运"
                ),
                "inputs": {"year_stem": year_stem, "gender": canonical_gender},
                "outputs": {
                    "direction": daxian_direction_label,
                    "initial_palace_name": (
                        next(p["name"] for p in palaces if p["daxian_period"] == 1)
                        if gender_known
                        else None
                    ),
                    "first_age_given_bureau": start_age,
                },
            },
        ],
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
            "leap_month": (
                "闰月全月作下月（全书卷二转录摘录）"
                if rule_profile == "quanshu_v2_excerpt"
                else "闰月十五日及以前算当月，之后算下月"
            ),
            "effective_birth_month": lunar_month,
        },
        "ruleset": ziwei_ruleset_metadata(rule_profile, sihua_source=sihua_source),
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
    first_age = min(int(p["daxian"].split("~")[0]) for p in palaces)
    if 1 <= nominal_age < first_age:
        raise ValueError("按所选五行局起岁，尚未起正式大限；童限不能替代大限取宫")
    raise ValueError("目标虚岁超出紫微大限支持范围")


def _xiaoxian_branch(year_branch: str, nominal_age: int, gender: str) -> str:
    if normalize_gender(gender) not in {"男", "女"}:
        raise ValueError("紫微小限顺逆需要明确性别，不能用未知性别代替女命")
    start = _XIAOXIAN_START_BY_YEAR_BRANCH[year_branch]
    start_idx = ZIWEI_BRANCH_SEQUENCE.index(start)
    offset = (nominal_age - 1) % 12
    forward = normalize_gender(gender) == "男"
    idx = (start_idx + offset) % 12 if forward else (start_idx - offset) % 12
    return ZIWEI_BRANCH_SEQUENCE[idx]


def _horoscope_scope(
    scope: str,
    palace: Dict[str, Any],
    stem: str,
    rule_profile: str,
    *,
    sihua_source: str = "rule_profile",
) -> Dict[str, Any]:
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
        "mutagen": sihua_rules_for(
            ZIWEI_SIHUA_RULES, rule_profile, sihua_source=sihua_source
        )[stem],
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
    birth_seed: Optional[MetaphysicsSeed] = None,
    nominal_age_basis: str = "birth_civil_timezone",
) -> Dict[str, Any]:
    """Six scopes using lunar-year ages and the natal-month/hour Dou Jun.

    Scope ``branch`` is the actual natal palace, not the calendar branch of
    the target date. Month/day/hour stems still determine their own 四化.
    Flowing scopes retain the target clock. Age ordinals use one civil clock
    for both physical endpoints. A chart alone cannot supply its birth instant.
    """
    palaces = chart["palaces"]
    rule_profile = chart.get("ruleset", {}).get("id", DEFAULT_ZIWEI_PROFILE)
    validate_rule_profile(rule_profile)
    sihua_source = chart.get("ruleset", {}).get("sihua_source", "rule_profile")
    validate_sihua_source(sihua_source)
    named_rule = chart.get("ruleset", {}).get("sihua_rule") == "naj_ming_v1"
    named_version = str(chart.get("ruleset", {}).get("version", "")).endswith(
        "+sihua.naj-ming-v1"
    )
    if named_rule != named_version or named_rule != (sihua_source == "naj_ming_v1"):
        raise ValueError("本命四化来源身份不一致，须保留实际所选表的完整规则信息")
    if (
        named_rule
        and dict(chart["sihua"])
        != sihua_rules_for(ZIWEI_SIHUA_RULES, rule_profile, sihua_source=sihua_source)[
            chart["year_stem"]
        ]
    ):
        raise ValueError("本命四化与所选明刊来源不一致，须按实际来源重建命盘")
    if normalize_gender(gender) not in {"男", "女"}:
        raise ValueError("紫微运限的大限、小限顺逆需要明确性别；本命非运限部分仍可计算")
    target_lunar, target_month, target_day = require_lunar_month_day(
        target_seed, "紫微斗数运限"
    )
    if target_lunar.get("year") is None:
        raise ValueError("紫微运限目标农历年缺失")
    natal_lunar = chart["lunar_date"]
    age_calendar = nominal_age_calendar(
        birth_seed=birth_seed,
        target_seed=target_seed,
        birth_placement_year=int(natal_lunar["year"]),
        target_civil_year=int(target_lunar["year"]),
        basis=nominal_age_basis,
    )
    nominal_age = age_calendar["nominal_age"]
    natal_year_branch = _lunar_year_ganzhi(int(natal_lunar["year"]))[1]
    target_year_stem, target_year_branch = _lunar_year_ganzhi(int(target_lunar["year"]))

    first_daxian_age = int(chart["wuxing_ju"]["number"])
    daxian: Dict[str, Any]
    if nominal_age < first_daxian_age:
        # The six literal childhood labels do not establish a substitute
        # formal decade, a decade palace stem, or decade transformations.
        # Retain the scope slot with explicit nulls so absence is observable.
        daxian = {
            "scope": "大限",
            "palace_name": None,
            "scope_palace_role": None,
            "natal_palace_name": None,
            "branch": None,
            "branch_index": None,
            "palace_ganzhi": None,
            "stem": None,
            "mutagen": None,
            "palace_map": [],
            "mutagen_natal_links": [],
            "stem_origin": None,
            "status": "not_started",
            "unavailable_reason": "before_selected_bureau_start_no_childhood_substitution",
        }
    else:
        daxian_palace = _palace_for_nominal_age(palaces, nominal_age)
        daxian = _horoscope_scope(
            "大限",
            daxian_palace,
            daxian_palace["ganzhi"][0],
            rule_profile,
            sihua_source=sihua_source,
        )
        daxian["status"] = "computed"
    daxian["first_age"] = first_daxian_age

    xiao_palace = _palace_by_branch(
        palaces, _xiaoxian_branch(natal_year_branch, nominal_age, gender)
    )
    # 小限 四化 follows the 宫干 of the 小限 palace (iztro convention), not the 流年 stem.
    xiaoxian = _horoscope_scope(
        "小限",
        xiao_palace,
        xiao_palace["ganzhi"][0],
        rule_profile,
        sihua_source=sihua_source,
    )

    natal_month = effective_lunar_month(
        int(natal_lunar["month"]),
        int(natal_lunar["day"]),
        bool(natal_lunar["is_leap_month"]),
        rule_profile,
    )
    target_month = effective_lunar_month(
        target_month,
        target_day,
        bool(target_lunar.get("is_leap_month")),
        # The excerpt concerns natal 身命, not flowing leap months.
        DEFAULT_ZIWEI_PROFILE,
    )
    # Reverse from the year's palace to birth month, then forward to birth
    # hour; the result is 正月斗君. Count the target month/day/hour from it.
    doujun_index = (
        ZIWEI_BRANCH_SEQUENCE.index(target_year_branch)
        - natal_month
        + EARTHLY_BRANCHES.index(chart["hour_branch"])
        + 1
    ) % 12
    month_index = (doujun_index + target_month - 1) % 12
    day_index = (month_index + target_day - 1) % 12
    hour_index = (
        day_index + EARTHLY_BRANCHES.index(target_seed.pillars["hour"][1])
    ) % 12
    month_stem = HEAVENLY_STEMS[
        (HEAVENLY_STEMS.index(target_year_stem) * 2 + 2 + target_month - 1) % 10
    ]
    flowing = [
        _horoscope_scope(
            "流年",
            _palace_by_branch(palaces, target_year_branch),
            target_year_stem,
            rule_profile,
            sihua_source=sihua_source,
        )
    ]
    for scope, index, stem in (
        ("流月", month_index, month_stem),
        ("流日", day_index, target_seed.pillars["day"][0]),
        ("流时", hour_index, target_seed.pillars["hour"][0]),
    ):
        flowing.append(
            _horoscope_scope(
                scope,
                _palace_by_branch(palaces, ZIWEI_BRANCH_SEQUENCE[index]),
                stem,
                rule_profile,
                sihua_source=sihua_source,
            )
        )

    scopes = [daxian, xiaoxian, *flowing]
    stem_origins = (
        "本命所临宫干",
        "本命所临宫干",
        "目标农历年干",
        "目标农历月序五虎遁月干",
        "目标日柱天干",
        "目标时柱天干",
    )
    for scope_record, stem_origin in zip(scopes, stem_origins):
        if scope_record.get("status") == "not_started":
            continue
        scope_record["stem_origin"] = stem_origin
        scope_record["palace_map"] = scope_palace_map(
            scope_record["branch"], palaces, ZIWEI_PALACE_SEQUENCE
        )
        if scope_record["scope"] == "流年":
            scope_record["flowing_stars"] = flowing_lucun_stars(
                scope_record["palace_map"], stem=scope_record["stem"]
            )
            if rule_profile == "quanshu_v2_excerpt":
                scope_record["flowing_stars"].extend(
                    annual_text_stars(
                        scope_record["palace_map"], year_branch=target_year_branch
                    )
                )
                scope_record["annual_three_sha"] = annual_three_sha(target_year_branch)
        scope_record["mutagen_natal_links"] = _link_mutagen_to_natal_stars(
            scope_record, palaces
        )
        roles = {
            p["branch"]: p["scope_palace_name"] for p in scope_record["palace_map"]
        }
        for link in scope_record["mutagen_natal_links"]:
            if link["status"] == "matched":
                link["scope_palace_name"] = roles[link["natal_branch"]]

    table_evidence = sihua_source_comparison(
        sihua_rules_for(ZIWEI_SIHUA_RULES, rule_profile, sihua_source=sihua_source),
        compared_assignments_applied=sihua_source == "naj_ming_v1",
    )
    table_evidence.update(
        scope="natal_table_reused_for_scopes_by_software_convention",
        dynamic_reuse_classically_verified=False,
    )
    return {
        "engine": "fatebridge-offline",
        "natal_prerequisites": horoscope_natal_prerequisites(chart),
        "nominal_age": nominal_age,
        "nominal_age_calendar": age_calendar,
        "sihua_source_comparison": table_evidence,
        "childhood_limit": childhood_limit(chart, nominal_age),
        "ming_limit_subperiods": limit_subperiod_evidence(
            palaces, scopes, nominal_age=nominal_age
        ),
        "calendar_rules": chart["calendar_rules"],
        "ruleset": ziwei_ruleset_metadata(rule_profile, sihua_source=sihua_source),
        "source_comparison": limit_source_evidence(
            chart,
            scopes,
            nominal_age=nominal_age,
            gender=normalize_gender(gender),
            natal_year_branch=natal_year_branch,
            target_year_branch=target_year_branch,
            actual_doujun_branch=ZIWEI_BRANCH_SEQUENCE[doujun_index],
        ),
        "interpretation_scope": {
            "contract_version": "scope_palace_mapping_v3",
            "scope_palace_meaning": "运限命宫活动索引所临的本命宫",
            "transformation_meaning": "本层四化连接本命星位；scope_palace_name 单独标记本层功能宫",
            "scope_palace_map_supported": True,
            "full_scope_palaces_supported": False,
            "limitations": [
                "已提供十二宫功能名映射与部分流曜，范围由所选规则配置与实际字段确定；未提供全部流曜及飞宫体系",
                "本命星位未随旋宫搬移",
                "未起正式大限时该层标记not_started，不取童限宫、不生成大限四化；其他层分别计算",
                "未据此判定职业事件或吉凶",
            ],
        },
        "scopes": scopes,
    }


def build_ziwei_rules(
    year_stem: Optional[str] = None,
    *,
    rule_profile: str = DEFAULT_ZIWEI_PROFILE,
    sihua_source: str = "rule_profile",
) -> Dict[str, Any]:
    rules = sihua_rules_for(ZIWEI_SIHUA_RULES, rule_profile, sihua_source=sihua_source)
    catalogue = {
        "palace_sequence": ZIWEI_PALACE_SEQUENCE,
        "ming_gong_method": "寅宫起正月，顺数生月，逆数生时。",
        "shen_gong_method": "寅宫起正月，顺数生月，再顺数生时。",
        "sihua_by_year_stem": rules,
        "sihua_source_comparison": sihua_source_comparison(
            rules, compared_assignments_applied=sihua_source == "naj_ming_v1"
        ),
        "ruleset": ziwei_ruleset_metadata(rule_profile, sihua_source=sihua_source),
        "cycle_methods": {
            "pre_decade": "所选局数起岁前不取大限宫、不生成大限四化；童限独立",
            "daxian_start": (
                "阳男阴女首限父母、阴男阳女首限兄弟；局数起岁，十年一宫"
                if rule_profile == "quanshu_v2_excerpt"
                else "首限命宫；阳男阴女顺、阴男阳女逆，局数起岁"
            ),
            "fire_bell": (
                "按所列年支二支安星，不推进生时；这是明确选择的年支定点读法"
                if rule_profile == "quanshu_v2_excerpt"
                else "年支起点起子时，火铃双顺至生时；软件约定"
            ),
            "changsheng": (
                "男顺女逆"
                if rule_profile == "quanshu_v2_excerpt"
                else "阳男阴女顺、阴男阳女逆"
            ),
            "boshi": "禄存起博士，阳男阴女顺、阴男阳女逆",
            "annual_lucun_yang_tuo": "目标年干定流禄，前一位流羊、后一位流陀；不搬移本命星",
        },
    }
    focused = None
    if year_stem:
        if year_stem not in rules:
            raise ValueError("紫微四化年干必须为甲乙丙丁戊己庚辛壬癸之一")
        focused = {
            "year_stem": year_stem,
            "sihua": ordered_sihua_mapping(rules[year_stem]),
        }
    return {
        "requested_year_stem": year_stem,
        "rule_catalogue": catalogue,
        "focused_rules": focused,
    }
