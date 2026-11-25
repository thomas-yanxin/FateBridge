"""Place Ziwei natal stars by branch before applying transformations."""

from __future__ import annotations

from dataclasses import dataclass

from fatebridge.core.metaphysics.common import sexagenary_index_for
from fatebridge.core.ziwei.ziwei_auxiliary import ZIWEI_LUCUN_BY_STEM
from fatebridge.core.ziwei.ziwei_rulesets import ZiweiRuleProfile
from fatebridge.utils.data import (
    EARTHLY_BRANCHES,
    HEAVENLY_STEMS,
    ZIWEI_BRANCH_SEQUENCE,
)


@dataclass(frozen=True, kw_only=True)
class ZiweiNatalStarPlacement:
    stars_by_branch: dict[str, list[str]]
    ziwei_branch: str
    tianfu_branch: str
    xun_void_source_branches: list[str]
    xun_void_displayed_branches: list[str]


def natal_star_placement(
    *,
    bureau_number: int,
    lunar_month: int,
    lunar_day: int,
    hour_branch: str,
    year_stem: str,
    year_branch: str,
    ming_branch: str,
    shen_branch: str,
    rule_profile: ZiweiRuleProfile,
) -> ZiweiNatalStarPlacement:
    stars_by_branch: dict[str, list[str]] = {
        branch: [] for branch in ZIWEI_BRANCH_SEQUENCE
    }
    hour_index = EARTHLY_BRANCHES.index(hour_branch) + 1
    year_stem_index = HEAVENLY_STEMS.index(year_stem)
    # note (ziwei): Round the lunar day up to a bureau multiple before applying the parity offset.
    rounded_quotient = (lunar_day + bureau_number - 1) // bureau_number
    day_remainder = bureau_number * rounded_quotient - lunar_day
    if day_remainder % 2 == 0:
        ziwei_index = (rounded_quotient + day_remainder - 1) % 12  # Relative to 寅 (0)
    else:
        ziwei_index = (rounded_quotient - day_remainder - 1) % 12

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

    for anchor_index, star_offsets in (
        (ziwei_index, ziwei_group),
        (tianfu_index, tianfu_group),
    ):
        for star_name, branch_offset in star_offsets.items():
            branch = ZIWEI_BRANCH_SEQUENCE[(anchor_index + branch_offset) % 12]
            stars_by_branch[branch].append(star_name)

    # ZIWEI_BRANCH_SEQUENCE indexing: 寅(0), 卯(1), 辰(2), 巳(3), 午(4), 未(5),
    # 申(6), 酉(7), 戌(8), 亥(9), 子(10), 丑(11)。
    # 月系（生月起）：左辅从辰顺、右弼从戌逆。
    # 时系（生时起）：文昌从戌逆、文曲从辰顺。
    auxiliary_star_indices = {
        "左辅": (2 + lunar_month - 1) % 12,
        "右弼": (8 - (lunar_month - 1)) % 12,
        "文昌": (8 - (hour_index - 1)) % 12,
        "文曲": (2 + (hour_index - 1)) % 12,
    }

    for star_name, branch_index in auxiliary_star_indices.items():
        stars_by_branch[ZIWEI_BRANCH_SEQUENCE[branch_index]].append(star_name)

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
    minor_star_branches: dict[str, str] = {
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
    else:
        pass
    for star_name, target_branch in minor_star_branches.items():
        stars_by_branch[target_branch].append(star_name)

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
    guchen_branch, guashu_branch = next(
        branches
        for season_branches, branches in guchen_gushu_table.items()
        if year_branch in season_branches
    )

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

    wenchang_earth_idx, wenqu_earth_idx, zuofu_earth_idx, youbi_earth_idx = (
        EARTHLY_BRANCHES.index(ZIWEI_BRANCH_SEQUENCE[auxiliary_star_indices[star_name]])
        for star_name in ("文昌", "文曲", "左辅", "右弼")
    )

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

    adjective_star_branches: dict[str, str] = {
        # 命身派
        "天伤": EARTHLY_BRANCHES[(ming_branch_idx + 5) % 12],
        "天使": EARTHLY_BRANCHES[(ming_branch_idx + 7) % 12],
        "天才": EARTHLY_BRANCHES[(ming_branch_idx + year_branch_earth_index) % 12],
        "天寿": EARTHLY_BRANCHES[(shen_branch_idx + year_branch_earth_index) % 12],
        # 年支三合派
        "华盖": huagai_by_triad[year_branch],
        "咸池": xianchi_by_triad[year_branch],
        "孤辰": guchen_branch,
        "寡宿": guashu_branch,
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
    for star_name, target_branch in adjective_star_branches.items():
        stars_by_branch[target_branch].append(star_name)

    # The pinned text gives both branches; the software's polarity-based
    # single-branch display is a different convention.
    displayed_xunkong = [xunkong_branch]
    if rule_profile == "quanshu_v2_excerpt":
        displayed_xunkong = [xunkong_yang, xunkong_yin]
        for branch in displayed_xunkong:
            if "旬空" not in stars_by_branch[branch]:
                stars_by_branch[branch].append("旬空")
            else:
                pass
    else:
        pass
    return ZiweiNatalStarPlacement(
        stars_by_branch=stars_by_branch,
        ziwei_branch=ZIWEI_BRANCH_SEQUENCE[ziwei_index],
        tianfu_branch=ZIWEI_BRANCH_SEQUENCE[tianfu_index],
        xun_void_source_branches=[xunkong_yang, xunkong_yin],
        xun_void_displayed_branches=displayed_xunkong,
    )
