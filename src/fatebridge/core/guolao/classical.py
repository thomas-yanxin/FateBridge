"""Classical Guolao rules: 12 palaces, 安命, 命度, 身宫, 洞微大限, 十干化曜, 33神煞, 恩用难仇, and 授时历古度."""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

from fatebridge.core.astro.lunar_mansions import (
    MANSION_LORDS,
    MANSIONS,
    SEVEN_LUMINARIES_ZH,
    SHOUSHI_1281,
    SHOUSHI_EQUATORIAL_1281,
    HistoricalMansions,
)

BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
STEMS = "甲乙丙丁戊己庚辛壬癸"
PALACES = (
    "命",
    "财帛",
    "兄弟",
    "田宅",
    "男女",
    "奴仆",
    "夫妻",
    "疾厄",
    "迁移",
    "官禄",
    "福德",
    "相貌",
)
# Clockwise Dongwei Daxian traversal order & classical year spans (命15 + 11 palaces)
DONGWEI_ORDER: tuple[tuple[str, float], ...] = (
    ("命", 15.0),
    ("相貌", 10.0),
    ("福德", 11.0),
    ("官禄", 15.0),
    ("迁移", 8.0),
    ("疾厄", 7.0),
    ("夫妻", 11.0),
    ("奴仆", 4.5),
    ("男女", 4.5),
    ("田宅", 4.5),
    ("兄弟", 5.0),
    ("财帛", 5.0),
)
PALACE_BRANCHES = [
    "戌",
    "酉",
    "申",
    "未",
    "午",
    "巳",
    "辰",
    "卯",
    "寅",
    "丑",
    "子",
    "亥",
]
PALACE_LORDS = ["火", "金", "水", "月", "日", "水", "金", "火", "木", "土", "土", "木"]
CN = SEVEN_LUMINARIES_ZH

GENERATES = dict(zip("木火土金水", "火土金水木"))
OVERCOMES = dict(zip("木土水火金", "土水火金木"))
RELATION_TO_ROLE = {
    "生我": "恩",
    "我生": "用",
    "克我": "难",
    "我克": "仇",
    "同主": "同",
}

DAY_NOBLES = dict(zip(STEMS, "未申酉亥丑子丑寅卯巳"))
NIGHT_NOBLES = dict(zip(STEMS, "丑子亥酉未申未午巳卯"))
STEM_LU = dict(zip(STEMS, "寅卯巳午巳午申酉亥子"))
STEM_YANG_REN = dict(zip(STEMS, "卯辰午未午未酉戌子丑"))

HUA_YAO_NAMES = (
    "天禄",
    "天暗",
    "天福",
    "天耗",
    "天荫",
    "天贵",
    "天刑",
    "天印",
    "天囚",
    "天权",
)
HUA_YAO_PLANETS = ("火", "孛", "木", "金", "土", "月", "水", "炁", "计", "罗")

# NaYin 5-element cycle (60 JiaZi pairs -> element) for 长生/临官/帝旺
_NAYIN_ELEMENTS_30 = (
    "金",
    "火",
    "木",
    "土",
    "金",
    "火",
    "水",
    "土",
    "木",
    "金",
    "火",
    "水",
    "土",
    "木",
    "金",
    "水",
    "火",
    "土",
    "木",
    "火",
    "土",
    "金",
    "木",
    "水",
    "土",
    "火",
    "木",
    "水",
    "金",
    "木",
)
_CHANGSHENG_START = {"木": "亥", "火": "寅", "土": "申", "金": "巳", "水": "申"}
_GUAGUA_NAJIA = {
    "甲": "亥",
    "壬": "亥",  # 乾纳甲壬
    "乙": "未",
    "癸": "未",  # 坤纳乙癸
    "戊": "子",  # 坎纳戊
    "丙": "寅",  # 艮纳丙
    "庚": "卯",  # 震纳庚
    "辛": "巳",  # 巽纳辛
    "己": "午",  # 离纳己
    "丁": "酉",  # 兑纳丁
}


def _branch_index(branch: str) -> int:
    if len(branch) != 1 or branch not in BRANCHES:
        raise ValueError("须提供单个有效地支")
    return BRANCHES.index(branch)


def relation(target: str, other: str) -> str:
    """Directional 五星生克: other acts on the designated target lord."""
    if target == other:
        return "同主"
    if target not in GENERATES or other not in GENERATES:
        return "未分配"
    if GENERATES[other] == target:
        return "生我"
    if OVERCOMES[other] == target:
        return "克我"
    if GENERATES[target] == other:
        return "我生"
    return "我克"


def en_yong_nan_chou_table(lord: str) -> dict[str, str]:
    """Return {恩, 用, 难, 仇, 同} mapping for a designated lord (命宫主 or 命度主)."""
    if lord not in GENERATES:
        return {}
    en = next(e for e, gen in GENERATES.items() if gen == lord)
    yong = GENERATES[lord]
    nan = next(e for e, ov in OVERCOMES.items() if ov == lord)
    chou = OVERCOMES[lord]
    return {"恩": en, "用": yong, "难": nan, "仇": chou, "同": lord}


def body_relation_role(lord: str, body_element: str) -> str:
    if body_element not in GENERATES:
        return "未分配"
    return RELATION_TO_ROLE.get(relation(lord, body_element), "未分配")


def hua_yao_for_stem(year_stem: str) -> dict[str, Any]:
    """Compute 十干化曜 for a birth year stem."""
    if year_stem not in STEMS:
        raise ValueError("须提供单个有效年干")
    idx = STEMS.index(year_stem)
    by_transformation = {
        HUA_YAO_NAMES[i]: HUA_YAO_PLANETS[(idx + i) % 10] for i in range(10)
    }
    by_body = {planet: yao for yao, planet in by_transformation.items()}
    return {
        "year_stem": year_stem,
        "by_transformation": by_transformation,
        "by_body": by_body,
    }


def counting_anchor(solar_longitude: float) -> str:
    if not math.isfinite(solar_longitude):
        raise ValueError("太阳黄经须有限")
    longitude = Fraction(solar_longitude) % 360
    if 270 <= longitude < 300:
        return "辰"
    if 90 <= longitude < 105:
        return "寅"
    return "卯"


def life_branch(sun_palace: str, birth_hour: str, anchor: str) -> str:
    """生时加太阳宫，顺数遇指定辰即命宫."""
    sun, hour, stop = map(_branch_index, (sun_palace, birth_hour, anchor))
    return BRANCHES[(sun + stop - hour) % 12]


def palace_branches(life: str) -> dict[str, str]:
    start = _branch_index(life)
    return {
        name: BRANCHES[(start - offset) % 12] for offset, name in enumerate(PALACES)
    }


def small_limit_branch(life: str, birth_year: str, target_year: str) -> str:
    start, birth, target = map(_branch_index, (life, birth_year, target_year))
    return BRANCHES[(start - (target - birth)) % 12]


def month_limit_branch(annual_branch: str, birth_month: int, target_month: int) -> str:
    start = _branch_index(annual_branch)
    for month in (birth_month, target_month):
        if type(month) is not int or not 1 <= month <= 12:
            raise ValueError("月限须显式提供1至12的整数月序")
    return BRANCHES[(start - (target_month - birth_month)) % 12]


def year_god_branches(year_stem: str, year_branch: str) -> dict[str, str]:
    if year_stem not in DAY_NOBLES:
        raise ValueError("须提供单个有效年干")
    _branch_index(year_branch)
    return {
        "天贵": DAY_NOBLES[year_stem],
        "玉贵": NIGHT_NOBLES[year_stem],
        "岁驾": year_branch,
    }


def compute_all_33_gods(
    *,
    year_stem: str,
    year_branch: str,
    month_branch: str,
    hour_branch: str,
    is_day: bool,
    sun_branch: str,
    moon_branch: str,
) -> dict[str, str]:
    """Compute all 33 Guolao/Moira Shensha branch positions."""
    si = STEMS.index(year_stem)
    bi = _branch_index(year_branch)
    mi = _branch_index(month_branch)
    hi = _branch_index(hour_branch)

    # Year stem gods
    tian_gui = DAY_NOBLES[year_stem]
    yu_gui = NIGHT_NOBLES[year_stem]
    lu_xun = STEM_LU[year_stem]
    yang_ren = STEM_YANG_REN[year_stem]
    fei_ren = BRANCHES[(_branch_index(yang_ren) + 6) % 12]
    tang_fu = fei_ren
    guo_yin = BRANCHES[(_branch_index(tang_fu) + 1) % 12]
    zi_wei = BRANCHES[(bi + 7) % 12]  # 紫微/龙德

    # Year branch gods
    sui_jia = year_branch
    sui_dian = BRANCHES[(bi + si) % 12]
    tian_xiong = BRANCHES[(bi + 3) % 12]
    di_ci = BRANCHES[(bi + 9) % 12]
    da_hao = BRANCHES[(bi + 6) % 12]
    tian_hao = BRANCHES[(bi + 5) % 12]
    di_hao = BRANCHES[(bi + 6) % 12]
    bing_fu = BRANCHES[(bi - 1) % 12]
    si_fu = BRANCHES[(bi + 5) % 12]
    jian_feng = year_branch
    tian_gou = BRANCHES[(bi + 10) % 12]
    kong_wang = BRANCHES[(bi - si + 10) % 12]

    # Triplicity / Season gods
    sanhe = bi % 4  # 0=申子辰, 1=巳酉丑, 2=寅午戌, 3=亥卯未
    yi_ma = ("寅", "亥", "申", "巳")[sanhe]
    jie_sha = ("巳", "寅", "亥", "申")[sanhe]
    de_sha = ("巳", "丑", "酉", "丑")[
        bi % 4
    ]  # 子午卯酉->巳, 丑未辰戌->丑, 寅申巳亥->酉

    gu_chen = {
        "亥": "寅",
        "子": "寅",
        "丑": "寅",
        "寅": "巳",
        "卯": "巳",
        "辰": "巳",
        "巳": "申",
        "午": "申",
        "未": "申",
        "申": "亥",
        "酉": "亥",
        "戌": "亥",
    }[year_branch]
    gua_su = {
        "亥": "戌",
        "子": "戌",
        "丑": "戌",
        "寅": "丑",
        "卯": "丑",
        "辰": "丑",
        "巳": "辰",
        "午": "辰",
        "未": "辰",
        "申": "未",
        "酉": "未",
        "戌": "未",
    }[year_branch]

    san_xing_map = dict(zip("子丑寅卯辰巳午未申酉戌亥", "卯戌巳子辰申午丑寅酉未亥"))
    liu_hai_map = dict(zip("子丑寅卯辰巳午未申酉戌亥", "未午巳辰卯寅丑子亥戌酉申"))
    fei_lian_map = dict(zip("子丑寅卯辰巳午未申酉戌亥", "申酉戌巳午未寅卯辰亥子丑"))

    # NaYin Changsheng / Linguan / Diwang
    jiazi_idx = (si * 6 - (si - bi) * 5) % 60  # 0..59
    nayin_elem = _NAYIN_ELEMENTS_30[jiazi_idx // 2]
    cs_idx = _branch_index(_CHANGSHENG_START[nayin_elem])
    chang_sheng = BRANCHES[cs_idx]
    lin_guan = BRANCHES[(cs_idx + 3) % 12]
    di_wang = BRANCHES[(cs_idx + 4) % 12]

    # DouShao (月建起戌顺数至生时)
    dou_shao = BRANCHES[(mi + (hi - 10)) % 12]

    # GuaQi (纳甲宫逆数至太阳/太阴，取对应天干之禄)
    najia_idx = _branch_index(_GUAGUA_NAJIA[year_stem])
    lum_idx = _branch_index(sun_branch if is_day else moon_branch)
    steps = (najia_idx - lum_idx) % 12
    gua_stem = STEMS[(si + steps) % 10]
    gua_qi = STEM_LU[gua_stem]

    return {
        "天贵": tian_gui,
        "玉贵": yu_gui,
        "紫微": zi_wei,
        "禄勋": lu_xun,
        "驿马": yi_ma,
        "岁驾": sui_jia,
        "岁殿": sui_dian,
        "斗杓": dou_shao,
        "唐符": tang_fu,
        "国印": guo_yin,
        "卦气": gua_qi,
        "长生": chang_sheng,
        "帝旺": di_wang,
        "临官": lin_guan,
        "阳刃": yang_ren,
        "天雄": tian_xiong,
        "的杀": de_sha,
        "劫杀": jie_sha,
        "飞廉": fei_lian_map[year_branch],
        "剑锋": jian_feng,
        "大耗": da_hao,
        "天耗": tian_hao,
        "地耗": di_hao,
        "死符": si_fu,
        "病符": bing_fu,
        "孤辰": gu_chen,
        "寡宿": gua_su,
        "三刑": san_xing_map[year_branch],
        "六害": liu_hai_map[year_branch],
        "地雌": di_ci,
        "天狗": tian_gou,
        "空亡": kong_wang,
        "飞刃": fei_ren,
    }


def dongwei_daxian(
    *,
    life_branch_str: str,
    sun_degree_in_palace: float,
    birth_year: int,
    target_age: float | None = None,
) -> dict[str, Any]:
    """Compute 洞微大限 (Dongwei 106-year Great Limits) with 3° = 1 year childhood entry."""
    # Childhood limit (童限) ends at 10 + sun_deg / 3.0 years (or 15 nominal if standard span)
    life_years = round(10.0 + sun_degree_in_palace / 3.0, 4)
    life_palace_idx = _branch_index(life_branch_str)
    spans: list[dict[str, Any]] = []
    age_cursor = 0.0
    for offset, (palace_name, default_years) in enumerate(DONGWEI_ORDER):
        duration = life_years if offset == 0 else default_years
        branch = BRANCHES[(life_palace_idx + offset) % 12]
        palace_idx = PALACE_BRANCHES.index(branch)
        lord = PALACE_LORDS[palace_idx]
        start_age = round(age_cursor, 4)
        end_age = round(age_cursor + duration, 4)
        spans.append(
            {
                "palace": palace_name,
                "branch": branch,
                "palace_lord": lord,
                "duration_years": duration,
                "start_age": start_age,
                "end_age": end_age,
                "start_year": round(birth_year + start_age, 2),
                "end_year": round(birth_year + end_age, 2),
            }
        )
        age_cursor += duration
    current = None
    if target_age is not None:
        current = next(
            (s for s in spans if s["start_age"] <= target_age < s["end_age"]),
            spans[-1],
        )
    return {
        "method": "dongwei_daxian_sun_degree_3deg_per_year",
        "childhood_exit_age": life_years,
        "total_years": round(age_cursor, 4),
        "periods": spans,
        **(
            {"current_period": current, "target_age": round(target_age, 4)}
            if target_age is not None
            else {}
        ),
    }
