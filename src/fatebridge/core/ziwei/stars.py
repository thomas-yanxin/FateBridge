"""Place Ziwei natal stars, twelve-star cycles, chart masters, and flowing stars."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from typing_extensions import NotRequired

from fatebridge.core.metaphysics.common import sexagenary_index_for
from fatebridge.core.ziwei.tables import (
    DEFAULT_ZIWEI_SCHOOL,
    IZTRO_SOURCE,
    QUANSHU_SOURCE,
    ZHONGZHOU_SOURCE,
    ZiweiRuleProfile,
    ZiweiSchool,
)
from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.data import (
    EARTHLY_BRANCHES,
    HEAVENLY_STEMS,
    ZIWEI_BRANCH_SEQUENCE,
)

ZIWEI_LUCUN_BY_STEM = dict(zip(HEAVENLY_STEMS, "寅卯巳午巳午申酉亥子"))
CHANGSHENG = (
    "长生",
    "沐浴",
    "冠带",
    "临官",
    "帝旺",
    "衰",
    "病",
    "死",
    "墓",
    "绝",
    "胎",
    "养",
)
BOSHI = (
    "博士",
    "力士",
    "青龙",
    "小耗",
    "将军",
    "奏书",
    "飞廉",
    "喜神",
    "病符",
    "大耗",
    "伏兵",
    "官府",
)
CHANGSHENG_START = {"水": "申", "木": "亥", "金": "巳", "土": "申", "火": "寅"}
LIFE_MASTER = dict(
    zip(
        EARTHLY_BRANCHES,
        (
            "贪狼",
            "巨门",
            "禄存",
            "文曲",
            "廉贞",
            "武曲",
            "破军",
            "武曲",
            "廉贞",
            "文曲",
            "禄存",
            "巨门",
        ),
    )
)
BODY_MASTER = dict(
    zip(
        EARTHLY_BRANCHES,
        (
            "火星",
            "天相",
            "天梁",
            "天同",
            "文昌",
            "天机",
            "火星",
            "天相",
            "天梁",
            "天同",
            "文昌",
            "天机",
        ),
    )
)

SUIQIAN_DEFAULT = tuple(
    "岁建 晦气 丧门 贯索 官符 小耗 大耗 龙德 白虎 天德 吊客 病符".split()
)
SUIQIAN_ZHONGZHOU = tuple(
    "岁建 晦气 丧门 贯索 官符 小耗 岁破 龙德 白虎 天德 吊客 病符".split()
)
JIANGQIAN = tuple("将星 攀鞍 岁驿 息神 华盖 劫煞 灾煞 天煞 指背 咸池 月煞 亡神".split())


@dataclass(frozen=True, kw_only=True)
class ZiweiNatalStarPlacement:
    stars_by_branch: dict[str, list[str]]
    ziwei_branch: str
    tianfu_branch: str
    xun_void_source_branches: list[str]
    xun_void_displayed_branches: list[str]


def compute_doujun_branch(year_branch: str, lunar_month: int, hour_branch: str) -> str:
    """Compute 斗君 (太岁逆数生月、顺数生时). 子斗 passes year_branch='子'."""
    index = (
        ZIWEI_BRANCH_SEQUENCE.index(year_branch)
        - lunar_month
        + EARTHLY_BRANCHES.index(hour_branch)
        + 1
    ) % 12
    return ZIWEI_BRANCH_SEQUENCE[index]


def compute_zidou_branch(lunar_month: int, hour_branch: str) -> str:
    """Compute natal 子斗 (从子逆数生月、顺数生时)."""
    return compute_doujun_branch("子", lunar_month, hour_branch)


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
    school: ZiweiSchool = DEFAULT_ZIWEI_SCHOOL,
    gender: str = "男",
) -> ZiweiNatalStarPlacement:
    stars_by_branch: dict[str, list[str]] = {
        branch: [] for branch in ZIWEI_BRANCH_SEQUENCE
    }
    hour_index = EARTHLY_BRANCHES.index(hour_branch) + 1
    year_stem_index = HEAVENLY_STEMS.index(year_stem)
    is_yang_stem = year_stem_index % 2 == 0
    canonical_gender = normalize_gender(gender)

    rounded_quotient = (lunar_day + bureau_number - 1) // bureau_number
    day_remainder = bureau_number * rounded_quotient - lunar_day
    if day_remainder % 2 == 0:
        ziwei_index = (rounded_quotient + day_remainder - 1) % 12
    else:
        ziwei_index = (rounded_quotient - day_remainder - 1) % 12
    tianfu_index = (12 - ziwei_index) % 12

    ziwei_group = {
        "紫微": 0,
        "天机": -1,
        "太阳": -3,
        "武曲": -4,
        "天同": -5,
        "廉贞": -8,
    }
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
        "擎羊": _branch_by_offset(lucun_branch, 1),
        "陀罗": _branch_by_offset(lucun_branch, -1),
        "天魁": tiankui_by_year_stem[year_stem],
        "天钺": tianyue_by_year_stem[year_stem],
        "天马": tianma_by_year_branch[year_branch],
        "火星": _branch_by_offset(
            huoxing_start_by_year_branch[year_branch], hour_earth_index
        ),
        "铃星": _branch_by_offset(
            lingxing_start_by_year_branch[year_branch], hour_earth_index
        ),
        "地空": EARTHLY_BRANCHES[(11 - hour_earth_index) % 12],
        "地劫": EARTHLY_BRANCHES[(11 + hour_earth_index) % 12],
        "红鸾": EARTHLY_BRANCHES[(3 - year_branch_earth_index) % 12],
        "天喜": EARTHLY_BRANCHES[(9 - year_branch_earth_index) % 12],
    }
    if rule_profile == "quanshu_v2_excerpt":
        minor_star_branches["火星"] = huoxing_start_by_year_branch[year_branch]
        minor_star_branches["铃星"] = lingxing_start_by_year_branch[year_branch]
    for star_name, target_branch in minor_star_branches.items():
        stars_by_branch[target_branch].append(star_name)

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
    tianwu_cycle = ["巳", "申", "寅", "亥"]

    ming_branch_idx = EARTHLY_BRANCHES.index(ming_branch)
    shen_branch_idx = EARTHLY_BRANCHES.index(shen_branch)
    wenchang_earth_idx, wenqu_earth_idx, zuofu_earth_idx, youbi_earth_idx = (
        EARTHLY_BRANCHES.index(ZIWEI_BRANCH_SEQUENCE[auxiliary_star_indices[star_name]])
        for star_name in ("文昌", "文曲", "左辅", "右弼")
    )

    year_cycle_index = sexagenary_index_for(f"{year_stem}{year_branch}")
    xunkong_pairs = [
        ("戌", "亥"),
        ("申", "酉"),
        ("午", "未"),
        ("辰", "巳"),
        ("寅", "卯"),
        ("子", "丑"),
    ]
    xunkong_yang, xunkong_yin = xunkong_pairs[year_cycle_index // 10]
    xunkong_branch = xunkong_yang if is_yang_stem else xunkong_yin

    jielu_yang = ("申", "午", "辰", "寅", "子")[year_stem_index % 5]
    jielu_yin = ("酉", "未", "巳", "卯", "丑")[year_stem_index % 5]

    adjective_star_branches: dict[str, str] = {
        "天才": EARTHLY_BRANCHES[(ming_branch_idx + year_branch_earth_index) % 12],
        "天寿": EARTHLY_BRANCHES[(shen_branch_idx + year_branch_earth_index) % 12],
        "华盖": huagai_by_triad[year_branch],
        "咸池": xianchi_by_triad[year_branch],
        "孤辰": guchen_branch,
        "寡宿": guashu_branch,
        "破碎": posui_by_year_branch[year_branch],
        "蜚廉": feilian_by_year_branch[year_branch],
        "龙池": EARTHLY_BRANCHES[(4 + year_branch_earth_index) % 12],
        "凤阁": EARTHLY_BRANCHES[(10 - year_branch_earth_index) % 12],
        "年解": EARTHLY_BRANCHES[(10 - year_branch_earth_index) % 12],
        "天哭": EARTHLY_BRANCHES[(6 - year_branch_earth_index) % 12],
        "天虚": EARTHLY_BRANCHES[(6 + year_branch_earth_index) % 12],
        "天德": EARTHLY_BRANCHES[(9 + year_branch_earth_index) % 12],
        "月德": EARTHLY_BRANCHES[(5 + year_branch_earth_index) % 12],
        "天空": EARTHLY_BRANCHES[(year_branch_earth_index + 1) % 12],
        "天官": tianguan_by_year_stem[year_stem],
        "天福": tianfu_by_year_stem[year_stem],
        "天厨": tianchu_by_year_stem[year_stem],
        "天月": tianyue_month_table[(lunar_month - 1) % 12],
        "天刑": EARTHLY_BRANCHES[(9 + lunar_month - 1) % 12],
        "天姚": EARTHLY_BRANCHES[(1 + lunar_month - 1) % 12],
        "天巫": tianwu_cycle[(lunar_month - 1) % 4],
        "解神": jieshen_pair_table[(lunar_month - 1) % 12],
        "阴煞": yinsha_six_cycle[(lunar_month - 1) % 6],
        "封诰": EARTHLY_BRANCHES[(2 + hour_earth_index) % 12],
        "台辅": EARTHLY_BRANCHES[(6 + hour_earth_index) % 12],
        "三台": EARTHLY_BRANCHES[(zuofu_earth_idx + lunar_day - 1) % 12],
        "八座": EARTHLY_BRANCHES[(youbi_earth_idx - (lunar_day - 1)) % 12],
        "恩光": EARTHLY_BRANCHES[(wenchang_earth_idx + lunar_day - 2) % 12],
        "天贵": EARTHLY_BRANCHES[(wenqu_earth_idx + lunar_day - 2) % 12],
        "旬空": xunkong_branch,
    }

    if school == "zhongzhou":
        # 中州派：阴男阳女天伤天使互换；单星截空；加天置大耗、龙德、劫杀
        if canonical_gender in {"男", "女"}:
            yang_male_yin_female = (canonical_gender == "男") == is_yang_stem
            if yang_male_yin_female:
                adjective_star_branches["天伤"] = EARTHLY_BRANCHES[
                    (ming_branch_idx + 5) % 12
                ]
                adjective_star_branches["天使"] = EARTHLY_BRANCHES[
                    (ming_branch_idx + 7) % 12
                ]
            else:
                adjective_star_branches["天伤"] = EARTHLY_BRANCHES[
                    (ming_branch_idx + 7) % 12
                ]
                adjective_star_branches["天使"] = EARTHLY_BRANCHES[
                    (ming_branch_idx + 5) % 12
                ]
        adjective_star_branches["截空"] = jielu_yang if is_yang_stem else jielu_yin
        # 中州派杂曜大耗：年支对冲，阳支顺一位、阴支逆一位
        yang_branch = year_branch_earth_index % 2 == 0
        adjective_star_branches["大耗"] = EARTHLY_BRANCHES[
            (year_branch_earth_index + 6 + (1 if yang_branch else -1)) % 12
        ]
        adjective_star_branches["龙德"] = EARTHLY_BRANCHES[
            (year_branch_earth_index + 7) % 12
        ]
        jiangxing_index = (0, 9, 6, 3)[year_branch_earth_index % 4]
        adjective_star_branches["劫杀"] = EARTHLY_BRANCHES[(jiangxing_index + 5) % 12]
    else:
        adjective_star_branches["天伤"] = EARTHLY_BRANCHES[(ming_branch_idx + 5) % 12]
        adjective_star_branches["天使"] = EARTHLY_BRANCHES[(ming_branch_idx + 7) % 12]
        adjective_star_branches["截路"] = jielu_yang
        adjective_star_branches["空亡"] = jielu_yin

    for star_name, target_branch in adjective_star_branches.items():
        stars_by_branch[target_branch].append(star_name)

    displayed_xunkong = [xunkong_branch]
    if rule_profile == "quanshu_v2_excerpt":
        displayed_xunkong = [xunkong_yang, xunkong_yin]
        for branch in displayed_xunkong:
            if "旬空" not in stars_by_branch[branch]:
                stars_by_branch[branch].append("旬空")
    return ZiweiNatalStarPlacement(
        stars_by_branch=stars_by_branch,
        ziwei_branch=ZIWEI_BRANCH_SEQUENCE[ziwei_index],
        tianfu_branch=ZIWEI_BRANCH_SEQUENCE[tianfu_index],
        xun_void_source_branches=[xunkong_yang, xunkong_yin],
        xun_void_displayed_branches=displayed_xunkong,
    )


_YearBranchBasis = Literal["natal_lunar_year_branch", "target_lunar_year_branch"]


class _YearCyclePosition(TypedDict):
    name: str
    branch: str


class _YearCycle(TypedDict):
    system_id: str
    start_branch: str
    positions: list[_YearCyclePosition]


class YearBranchCycles(TypedDict):
    anchor_basis: _YearBranchBasis
    year_branch: str
    direction: Literal["forward"]
    source: str
    suiqian: _YearCycle
    jiangqian: _YearCycle


def year_branch_cycles(
    year_branch: str,
    *,
    anchor_basis: _YearBranchBasis,
    school: ZiweiSchool = DEFAULT_ZIWEI_SCHOOL,
) -> YearBranchCycles:
    """Compute 岁前12神 and 将前12神 for a resolved lunar year branch."""
    year_index = EARTHLY_BRANCHES.index(year_branch)
    jiangxing_index = (0, 9, 6, 3)[year_index % 4]
    suiqian_labels = SUIQIAN_ZHONGZHOU if school == "zhongzhou" else SUIQIAN_DEFAULT

    def rotate(start: int, labels: tuple[str, ...], system_id: str) -> _YearCycle:
        return {
            "system_id": system_id,
            "start_branch": EARTHLY_BRANCHES[start],
            "positions": [
                {"name": name, "branch": EARTHLY_BRANCHES[(start + offset) % 12]}
                for offset, name in enumerate(labels)
            ],
        }

    return {
        "anchor_basis": anchor_basis,
        "year_branch": year_branch,
        "direction": "forward",
        "source": ZHONGZHOU_SOURCE if school == "zhongzhou" else IZTRO_SOURCE,
        "suiqian": rotate(
            year_index,
            suiqian_labels,
            (
                "zhongzhou_suiqian"
                if school == "zhongzhou"
                else "iztro_2_5_8_suiqian_default"
            ),
        ),
        "jiangqian": rotate(jiangxing_index, JIANGQIAN, "iztro_2_5_8_jiangqian"),
    }


def attach_natal_cycles(
    palaces: list[dict[str, Any]],
    *,
    element: str,
    year_stem: str,
    gender: str,
    rule_profile: str,
) -> dict[str, Any]:
    canonical = normalize_gender(gender)
    known = canonical in {"男", "女"}
    yang = HEAVENLY_STEMS.index(year_stem) % 2 == 0
    yang_gender_forward = (canonical == "男") == yang
    cs_forward = (
        canonical == "男"
        if rule_profile == "quanshu_v2_excerpt"
        else yang_gender_forward
    )
    cs_start = CHANGSHENG_START[element]
    bs_start = ZIWEI_LUCUN_BY_STEM[year_stem]
    for palace in palaces:
        index = EARTHLY_BRANCHES.index(palace["ganzhi"][1])
        cs_offset = index - EARTHLY_BRANCHES.index(cs_start)
        bs_offset = index - EARTHLY_BRANCHES.index(bs_start)
        palace["changsheng12"] = (
            CHANGSHENG[(cs_offset if cs_forward else -cs_offset) % 12]
            if known
            else (
                CHANGSHENG[cs_offset % 12]
                if CHANGSHENG[cs_offset % 12] == CHANGSHENG[-cs_offset % 12]
                else None
            )
        )
        palace["boshi12"] = (
            BOSHI[(bs_offset if yang_gender_forward else -bs_offset) % 12]
            if known
            else (
                BOSHI[bs_offset % 12]
                if BOSHI[bs_offset % 12] == BOSHI[-bs_offset % 12]
                else None
            )
        )
    result: dict[str, Any] = {
        "status": "computed" if known else "partial_missing_gender",
        "changsheng_start": cs_start,
        "changsheng_direction": ("顺行" if cs_forward else "逆行") if known else None,
        "changsheng_rule": (
            "text_male_forward_female_reverse"
            if rule_profile == "quanshu_v2_excerpt"
            else "software_year_polarity_and_gender"
        ),
        "boshi_start": bs_start,
        "boshi_direction": (
            ("顺行" if yang_gender_forward else "逆行") if known else None
        ),
        "boshi_rule": "lucun_start_year_polarity_and_gender",
    }
    if not known:
        result["missing_gender_resolution"] = (
            "retain_only_labels_shared_by_both_directions"
        )
        result["gender_invariant_positions"] = {
            cycle: {p["ganzhi"][1]: p[cycle] for p in palaces if p[cycle] is not None}
            for cycle in ("changsheng12", "boshi12")
        }
    return result


def chart_masters(
    palaces: list[dict[str, Any]],
    *,
    ming_branch: str,
    year_branch: str,
    school: ZiweiSchool = DEFAULT_ZIWEI_SCHOOL,
) -> dict[str, Any]:
    def record(star: str, basis: str, branch: str) -> dict[str, Any]:
        palace = next(
            (p for p in palaces if any(s["name"] == star for s in p["stars_detail"])),
            None,
        )
        return {
            "star": star,
            "selection_basis": basis,
            "basis_branch": branch,
            "natal_palace_name": palace["name"] if palace else None,
            "natal_branch": palace["ganzhi"][1] if palace else None,
        }

    life_basis_branch = year_branch if school == "zhongzhou" else ming_branch
    life_basis_name = (
        "natal_year_branch" if school == "zhongzhou" else "ming_palace_branch"
    )
    return {
        "life": record(
            LIFE_MASTER[life_basis_branch], life_basis_name, life_basis_branch
        ),
        "body": record(BODY_MASTER[year_branch], "natal_year_branch", year_branch),
    }


FLOWING_STEM_TABLE = {
    "天魁": "丑子亥亥丑子丑午卯卯",
    "天钺": "未申酉酉未申未寅巳巳",
    "文昌": "巳午申酉申酉亥子寅卯",
    "文曲": "酉申午巳午巳卯寅子亥",
}

ZiweiFlowingScope = Literal["大限", "流年", "流月", "流日", "流时"]


class FlowingStarPlacement(TypedDict):
    star: str
    scope: ZiweiFlowingScope
    branch: str
    scope_palace_name: str
    natal_palace_name: str
    rule_id: str
    stem: NotRequired[str]
    basis_branch: NotRequired[str]
    system_id: NotRequired[str]


def flowing_horoscope_stars(
    scope_palaces: Sequence[Mapping[str, str]] | Mapping[str, str],
    *,
    scope: ZiweiFlowingScope,
    stem: str,
    pillar_branch: str,
) -> list[dict[str, Any]]:
    """Compute dynamic flowing stars for one horoscope layer."""
    branches = EARTHLY_BRANCHES
    lu = branches.index(ZIWEI_LUCUN_BY_STEM[stem])
    stem_index = HEAVENLY_STEMS.index(stem)
    branch_index = branches.index(pillar_branch)
    annual = scope == "流年"
    lu_rule = "annual_lucun_yang_tuo" if annual else "lu_yang_tuo_by_stem"
    placements = [
        ("禄存", branches[lu], lu_rule),
        ("擎羊", branches[(lu + 1) % 12], lu_rule),
        ("陀罗", branches[(lu - 1) % 12], lu_rule),
        ("天魁", FLOWING_STEM_TABLE["天魁"][stem_index], "kui_yue_by_stem"),
        ("天钺", FLOWING_STEM_TABLE["天钺"][stem_index], "kui_yue_by_stem"),
        ("文昌", FLOWING_STEM_TABLE["文昌"][stem_index], "flowing_chang_qu_by_stem"),
        ("文曲", FLOWING_STEM_TABLE["文曲"][stem_index], "flowing_chang_qu_by_stem"),
        ("天马", "寅亥申巳"[branch_index % 4], "tianma_by_branch"),
        ("红鸾", branches[(3 - branch_index) % 12], "luan_xi_by_branch"),
        ("天喜", branches[(9 - branch_index) % 12], "luan_xi_by_branch"),
    ]
    if annual:
        placements.append(
            ("年解", branches[(10 - branch_index) % 12], "nianjie_by_year_branch")
        )

    if isinstance(scope_palaces, Mapping):
        role_by_branch = scope_palaces
    else:
        role_by_branch = {
            palace["branch"]: palace["scope_palace_name"] for palace in scope_palaces
        }
    return [
        {
            "star": star,
            "branch": branch,
            "scope_palace_name": role_by_branch[branch],
        }
        for star, branch, _rule_id in placements
    ]


def annual_text_stars(
    scope_palaces: Sequence[Mapping[str, str]] | Mapping[str, str],
    *,
    year_branch: str,
) -> list[dict[str, Any]]:
    """Annual virtues and four flying stars (fixing 月德 at 巳 + year_branch)."""
    year_index = EARTHLY_BRANCHES.index(year_branch)
    if isinstance(scope_palaces, Mapping):
        role_by_branch = scope_palaces
    else:
        role_by_branch = {p["branch"]: p["scope_palace_name"] for p in scope_palaces}
    result = []
    for star, offset in (
        ("天德", 9),
        ("月德", 5),
        ("丧门", 2),
        ("吊客", -2),
        ("白虎", 8),
        ("官府", 4),
    ):
        branch = EARTHLY_BRANCHES[(year_index + offset) % 12]
        result.append(
            {
                "star": star,
                "branch": branch,
                "scope_palace_name": role_by_branch[branch],
            }
        )
    return result


def annual_three_sha(year_branch: str) -> dict[str, Any]:
    groups = (
        ("寅午戌", ["亥", "卯", "未"]),
        ("申子辰", ["巳", "酉", "丑"]),
        ("巳酉丑", ["寅", "午", "戌"]),
        ("亥卯未", ["申", "子", "辰"]),
    )
    branches = next(target for group, target in groups if year_branch in group)
    return {
        "rule_id": "annual_flying_three_sha",
        "scope": "流年",
        "year_branch": year_branch,
        "names_as_written": ["奏书", "将军", "直符"],
        "branches": list(branches),
        "source": QUANSHU_SOURCE,
    }
