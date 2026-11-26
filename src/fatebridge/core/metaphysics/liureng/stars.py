"""Liuren life stages, auxiliary stars, category spirits, emptiness, god yin and relations."""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.common import (
    ELEMENT_CONTROLS,
    ELEMENT_GENERATES,
    GUI_REN_SEQUENCE,
    SEXAGENARY_INDEX,
    branch_element_text,
    kongwang_for_ganzhi,
    liuqin_against_day,
    stem_element_text,
    xun_head_for_ganzhi,
)
from fatebridge.core.metaphysics.ren_calendar import xun_dun_stems
from fatebridge.core.metaphysics.ren_gods import GuirenProfile, noble_start
from fatebridge.utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS

STEM_HOUSES = dict(zip(HEAVENLY_STEMS, "寅辰巳未巳未申戌亥丑"))

GOD_ELEMENTS = dict(
    zip(
        GUI_REN_SEQUENCE,
        "土火火木土木土金土水金水",
    )
)

STAGES = (
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
STAGE_STARTS = dict(zip("甲乙丙丁戊己庚辛壬癸", "亥午寅酉寅酉巳子申卯"))

MONTH_ORDER = "寅卯辰巳午未申酉戌亥子丑"
MONTH_PARTITION = {
    "寅": "春",
    "卯": "春",
    "辰": "季月",
    "巳": "夏",
    "午": "夏",
    "未": "季月",
    "申": "秋",
    "酉": "秋",
    "戌": "季月",
    "亥": "冬",
    "子": "冬",
    "丑": "季月",
}
POWERS = {
    "春": {"木": "旺", "火": "相", "土": "死", "金": "囚", "水": "休"},
    "夏": {"木": "休", "火": "旺", "土": "相", "金": "死", "水": "囚"},
    "秋": {"木": "死", "火": "囚", "土": "休", "金": "旺", "水": "相"},
    "冬": {"木": "相", "火": "死", "土": "囚", "金": "休", "水": "旺"},
    "季月": {"木": "囚", "火": "休", "土": "旺", "金": "相", "水": "死"},
}

HEAVEN_DE = dict(
    zip(
        MONTH_ORDER,
        "丁未 坤申 壬亥 辛戌 乾亥 甲寅 癸丑 艮寅 丙巳 乙辰 巽巳 庚申".split(),
    )
)
MONTH_DE = dict(zip(MONTH_ORDER, ["丙巳", "甲寅", "壬亥", "庚申"] * 3))
DAY_DE = dict(zip("甲乙丙丁戊己庚辛壬癸", "寅申巳亥巳寅申巳亥巳"))
BRANCH_DE = dict(zip(EARTHLY_BRANCHES, "巳午未申酉戌亥子丑寅卯辰"))
DAY_HORSE = dict(zip(EARTHLY_BRANCHES, "寅亥申巳寅亥申巳寅亥申巳"))
HEAVEN_HORSE = dict(zip(MONTH_ORDER, "午申戌子寅辰午申戌子寅辰"))
MONTH_TAI_SHEN = dict(zip(MONTH_ORDER, "子午丑未寅申卯酉辰戌巳亥"))
TAOHUA_BY_BRANCH = dict(zip(EARTHLY_BRANCHES, "酉午卯子酉午卯子酉午卯子"))
JIESHA_BY_BRANCH = dict(zip(EARTHLY_BRANCHES, "巳寅亥申巳寅亥申巳寅亥申"))
HUAGAI_BY_BRANCH = dict(zip(EARTHLY_BRANCHES, "辰丑戌未辰丑戌未辰丑戌未"))
YANGREN_BY_STEM = dict(zip("甲乙丙丁戊己庚辛壬癸", "卯辰午未午未酉戌子丑"))

LIUQIN_CATEGORY = {
    "父母": "文书/印绶/长辈",
    "兄弟": "比劫/同辈/分争",
    "子孙": "福德/解忧/晚辈",
    "妻财": "财禄/妻妾/物用",
    "官鬼": "官禄/鬼贼/公事",
}

PAIRS = {
    "liuhe": ("子丑", "寅亥", "卯戌", "辰酉", "巳申", "午未"),
    "liupo": ("午卯", "辰丑", "酉子", "戌未", "亥寅", "申巳"),
    "liuhai": ("酉戌", "申亥", "未子", "午丑", "巳寅", "辰卯"),
    "liuchong": ("子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥"),
}
XING = dict(zip("子卯寅巳申丑戌未辰午酉亥", "卯子巳申寅戌未丑辰午酉亥"))

DAY_PLACEMENT_RULES = (
    ("D01", "俯就", "干加枝受生", "stem_over_branch", "branch_generates_stem"),
    ("D02", "归福", "枝加干生干", "branch_over_stem", "branch_generates_stem"),
    ("D03", "脱我", "枝加干受生", "branch_over_stem", "stem_generates_branch"),
    ("D04", "历虚", "干加枝生枝", "stem_over_branch", "stem_generates_branch"),
    ("D05", "欺我", "枝加干尅干", "branch_over_stem", "branch_controls_stem"),
    ("D06", "取辱", "干加枝受尅", "stem_over_branch", "branch_controls_stem"),
    ("D07", "招夫", "枝加干受尅", "branch_over_stem", "stem_controls_branch"),
    ("D08", "赘婿", "干加枝尅枝", "stem_over_branch", "stem_controls_branch"),
    ("D09", "壮基", "枝加干比干", "branch_over_stem", "same_element"),
    ("D10", "培本", "干加枝比枝", "stem_over_branch", "same_element"),
    ("D11", "归合", "枝加干合干", "branch_over_stem", "harmony_unadjudicated"),
    ("D12", "求合", "干加枝合枝", "stem_over_branch", "harmony_unadjudicated"),
)


def life_stage_cycle(day_stem: str) -> dict[str, str]:
    if day_stem not in STAGE_STARTS:
        raise ValueError("十二运需要有效日干")
    start = EARTHLY_BRANCHES.index(STAGE_STARTS[day_stem])
    direction = 1 if day_stem in "甲丙戊庚壬" else -1
    return {
        branch: STAGES[((i - start) * direction) % 12]
        for i, branch in enumerate(EARTHLY_BRANCHES)
    }


def build_life_stages(day_stem: str, sky_by_earth: dict[str, str]) -> dict[str, Any]:
    cycle = life_stage_cycle(day_stem)
    branches = set(EARTHLY_BRANCHES)
    if set(sky_by_earth) != branches or set(sky_by_earth.values()) != branches:
        raise ValueError("十二运需要完整且不重复的天地盘")
    offsets = {
        (EARTHLY_BRANCHES.index(sky) - EARTHLY_BRANCHES.index(earth)) % 12
        for earth, sky in sky_by_earth.items()
    }
    if len(offsets) != 1:
        raise ValueError("天地盘须按同一支序顺布")
    by_stage = {stage: branch for branch, stage in cycle.items()}
    earth_by_sky = {sky: earth for earth, sky in sky_by_earth.items()}
    placements = []
    for name, sky, required_earth in (
        ("墓乘长生", by_stage["墓"], by_stage["长生"]),
        ("长生乘墓", by_stage["长生"], by_stage["墓"]),
    ):
        earth = earth_by_sky[sky]
        placements.append(
            {
                "name": name,
                "sky_branch": sky,
                "earth_branch": earth,
                "required_earth_branch": required_earth,
                "sky_stage": cycle[sky],
                "earth_stage": cycle[earth],
                "matched": earth == required_earth,
            }
        )
    return {
        "ruleset_id": "tanyuan_ten_stem_life_stages_v1",
        "source_title": "大六壬探原·论墓（长生沐浴等附）",
        "day_stem": day_stem,
        "direction": "顺" if day_stem in "甲丙戊庚壬" else "逆",
        "changsheng_branch": by_stage["长生"],
        "linguan_branch": by_stage["临官"],
        "tomb_branch": by_stage["墓"],
        "tai_branch": by_stage["胎"],
        "stage_by_branch": cycle,
        "placements": placements,
    }


def build_auxiliary_stars(
    *,
    day_ganzhi: str,
    month_branch: str,
    sky_by_earth: dict[str, str],
    god_by_sky: dict[str, str],
    lessons: list[dict[str, Any]],
    transmissions: list[str],
) -> dict[str, Any]:
    if len(day_ganzhi) != 2:
        raise ValueError("德禄马需要有效日干支")
    if day_ganzhi not in SEXAGENARY_INDEX:
        raise ValueError("德禄马需要有效日干支")
    if month_branch not in MONTH_ORDER or len(month_branch) != 1:
        raise ValueError("德禄马需要有效月建")
    stages = build_life_stages(day_ganzhi[0], sky_by_earth)
    branches = set(EARTHLY_BRANCHES)
    if set(god_by_sky) != branches or set(god_by_sky.values()) != set(GUI_REN_SEQUENCE):
        raise ValueError("德禄马需要完整且不重复的天将对应")
    if (
        len(lessons) != 4
        or [l.get("index") for l in lessons] != [1, 2, 3, 4]
        or any(l.get("upper_branch") not in branches for l in lessons)
    ):
        raise ValueError("德禄马需要四课上神")
    if len(transmissions) != 3 or any(t not in branches for t in transmissions):
        raise ValueError("德禄马需要完整三传")
    stem, day_branch = day_ganzhi[0], day_ganzhi[1]
    earth_by_sky = {sky: earth for earth, sky in sky_by_earth.items()}
    dun = xun_dun_stems(day_ganzhi)
    ding_branch = next((b for b, s in dun.items() if s == "丁"), None)

    star_specs: list[tuple[str, str, str, str]] = [
        ("heaven_de", "天德", "month_building", HEAVEN_DE[month_branch]),
        ("month_de", "月德", "month_building", MONTH_DE[month_branch]),
        ("day_de", "日德", "day_stem", DAY_DE[stem]),
        ("branch_de", "日支德", "day_branch", BRANCH_DE[day_branch]),
        ("day_lu", "日禄", "day_stem", stages["linguan_branch"]),
        ("day_horse", "驿马", "day_branch", DAY_HORSE[day_branch]),
        ("heaven_horse", "天马", "month_building", HEAVEN_HORSE[month_branch]),
        ("stem_tai", "日干胎神", "day_stem", stages["tai_branch"]),
        ("month_tai", "月胎神", "month_building", MONTH_TAI_SHEN[month_branch]),
        ("taohua", "桃花", "day_branch", TAOHUA_BY_BRANCH[day_branch]),
        ("jiesha", "劫煞", "day_branch", JIESHA_BY_BRANCH[day_branch]),
        ("yangren", "羊刃", "day_stem", YANGREN_BY_STEM[stem]),
        ("huagai", "华盖", "day_branch", HUAGAI_BY_BRANCH[day_branch]),
    ]
    if ding_branch is not None:
        star_specs.append(("ding_shen", "旬丁", "day_xun", f"丁{ding_branch}"))

    stars = []
    stars_by_branch: dict[str, list[str]] = {b: [] for b in EARTHLY_BRANCHES}
    for star_id, name, category, token in star_specs:
        branch = token[-1]
        earth = earth_by_sky[branch]
        stars_by_branch[branch].append(name)
        stars.append(
            {
                "id": star_id,
                "name": name,
                "category": category,
                "source_token": token,
                "branch": branch,
                "earth_branch": earth,
                "god": god_by_sky[branch],
                "dun_stem": dun.get(branch),
                "ganzhi": f"{dun[branch]}{branch}" if branch in dun else None,
                "xun_kong": branch not in dun,
                "seated_kong": earth not in dun,
                "day_stem_life_stage": stages["stage_by_branch"][branch],
                "lesson_indices": [
                    l["index"] for l in lessons if l["upper_branch"] == branch
                ],
                "transmission_positions": [
                    label
                    for label, value in zip(
                        ("initial", "middle", "final"), transmissions
                    )
                    if value == branch
                ],
                "on_day_stem": lessons[0]["upper_branch"] == branch,
                "on_day_branch": lessons[2]["upper_branch"] == branch,
            }
        )

    day_element = stem_element_text(stem)
    transmission_spirits = []
    for pos, branch in zip(("initial", "middle", "final"), transmissions):
        liuqin = liuqin_against_day(day_element, branch_element_text(branch))
        transmission_spirits.append(
            {
                "position": pos,
                "branch": branch,
                "liuqin": liuqin,
                "category_meaning": LIUQIN_CATEGORY.get(liuqin, liuqin),
                "god": god_by_sky[branch],
                "dun_stem": dun.get(branch),
                "xun_kong": branch not in dun,
                "stars": stars_by_branch[branch],
            }
        )

    return {
        "ruleset_id": "tanyuan_auxiliary_stars_v2",
        "source_title": "大六壬探原·德禄马及胎神神煞",
        "day_ganzhi": day_ganzhi,
        "month_building_branch": month_branch,
        "nominal_month": MONTH_ORDER.index(month_branch) + 1,
        "stars": stars,
        "tai_shen": {
            "day_stem_tai_branch": stages["tai_branch"],
            "day_stem_tai_earth": earth_by_sky[stages["tai_branch"]],
            "day_stem_tai_god": god_by_sky[stages["tai_branch"]],
            "month_tai_branch": MONTH_TAI_SHEN[month_branch],
            "month_tai_earth": earth_by_sky[MONTH_TAI_SHEN[month_branch]],
            "month_tai_god": god_by_sky[MONTH_TAI_SHEN[month_branch]],
        },
        "transmission_category_spirits": transmission_spirits,
        "complete_classical_conformance": False,
    }


def emptiness_evidence(
    *,
    day_ganzhi: str,
    year_branch: str,
    month_branch: str,
    month_general_branch: str,
    hour_branch: str,
    sky_by_earth: dict[str, str],
) -> dict[str, Any]:
    if day_ganzhi not in SEXAGENARY_INDEX:
        raise ValueError("六壬空亡依据需要有效日干支")
    branches = set(EARTHLY_BRANCHES)
    if (
        any(
            v not in branches
            for v in (year_branch, month_branch, month_general_branch, hour_branch)
        )
        or set(sky_by_earth) != branches
        or set(sky_by_earth.values()) != branches
    ):
        raise ValueError("六壬空亡依据需要有效年月时支、月将和完整天地盘")
    offsets = {
        (EARTHLY_BRANCHES.index(sky) - EARTHLY_BRANCHES.index(earth)) % 12
        for earth, sky in sky_by_earth.items()
    }
    expected_offset = (
        EARTHLY_BRANCHES.index(month_general_branch)
        - EARTHLY_BRANCHES.index(hour_branch)
    ) % 12
    if offsets != {expected_offset}:
        raise ValueError("六壬空亡依据的天地盘与月将加时不一致")
    empty = kongwang_for_ganzhi(day_ganzhi)[:2]
    house = STEM_HOUSES[day_ganzhi[0]]
    roles = (
        ("太岁", year_branch),
        ("月建", month_branch),
        ("月将", month_general_branch),
    )
    evidence = dict(
        ruleset_id="liuren_tanyuan_empty_scope_v3",
        source_title="大六壬探原·卷下论空亡",
        day_ganzhi=day_ganzhi,
        xun_head=xun_head_for_ganzhi(day_ganzhi),
        empty_branches=list(empty),
        day_stem_house=house,
        year_branch=year_branch,
        month_building_branch=month_branch,
        month_general_branch=month_general_branch,
        hour_branch=hour_branch,
        hour_branch_xun_kong=hour_branch in empty,
        role_conditions=[
            dict(
                role=name,
                branch=branch,
                branch_xun_kong=branch in empty,
                xunkong_exception_applies=branch in empty,
            )
            for name, branch in roles
        ],
        rows=[
            dict(
                earth_branch=earth,
                sky_branch=sky_by_earth[earth],
                sky_xun_kong=sky_by_earth[earth] in empty,
                earth_xun_kong=earth in empty,
                earth_is_day_stem_house=earth == house,
                earth_stem_house_exception=earth in empty and earth == house,
                sky_authority_roles=[
                    name for name, branch in roles if branch == sky_by_earth[earth]
                ],
                sky_authority_xunkong_exception=sky_by_earth[earth] in empty
                and any(branch == sky_by_earth[earth] for _, branch in roles),
                effective_empty=None,
            )
            for earth in EARTHLY_BRANCHES
        ],
        seasonal_true_half_empty_status="not_adjudicated",
        filling_clashing_status="role_exceptions_only",
        comprehensive_judgement=None,
        complete_classical_conformance=False,
    )
    apply_year_fate_emptiness(evidence, natal=None, annual=None)
    return evidence


def apply_year_fate_emptiness(
    evidence: dict[str, Any], *, natal: str | None, annual: str | None
) -> None:
    placements = {"natal": natal, "annual": annual}
    complete = natal is not None and annual is not None
    evidence["year_fate_earth_branches"] = placements
    evidence["nianming_status"] = (
        "calculated"
        if complete
        else (
            "partial"
            if natal is not None or annual is not None
            else "inputs_not_available"
        )
    )
    for row in evidence["rows"]:
        roles = [
            role for role, branch in placements.items() if branch == row["earth_branch"]
        ]
        exempt = row["earth_xun_kong"] and bool(roles)
        row.update(
            earth_year_fate_roles=roles,
            earth_year_fate_xunkong_exception=(
                exempt if exempt or not row["earth_xun_kong"] or complete else None
            ),
            earth_xunkong_after_seat_and_year_fate=(
                False
                if not row["earth_xun_kong"]
                or row["earth_stem_house_exception"]
                or exempt
                else True if complete else None
            ),
        )


def role_presence(
    in_lesson: bool,
    in_transmission: bool,
    in_natal: bool | None,
    in_annual: bool | None,
) -> bool | None:
    facts = [in_lesson, in_transmission, in_natal, in_annual]
    if any(v is True for v in facts):
        return True
    return None if any(v is None for v in facts) else False


def god_yin_spirits(
    *,
    day_ganzhi: str,
    month_branch: str,
    is_diurnal: bool,
    guiren_profile: GuirenProfile,
    sky_by_earth: dict[str, str],
    god_by_sky: dict[str, str],
    lesson_uppers: list[str],
    transmission_branches: list[str],
    year_fate_uppers: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    branches = set(EARTHLY_BRANCHES)
    if day_ganzhi not in SEXAGENARY_INDEX or month_branch not in branches:
        raise ValueError("类神阴神需要有效占日与月建")
    if type(is_diurnal) is not bool:
        raise ValueError("类神阴神需要已声明的昼夜策略")
    if set(sky_by_earth) != branches or set(sky_by_earth.values()) != branches:
        raise ValueError("类神阴神需要完整的一一对应天地盘")
    if set(god_by_sky) != branches or set(god_by_sky.values()) != set(GUI_REN_SEQUENCE):
        raise ValueError("类神阴神需要完整且不重复的十二天将")
    if (
        len(lesson_uppers) != 4
        or len(transmission_branches) != 3
        or any(v not in branches for v in lesson_uppers + transmission_branches)
    ):
        raise ValueError("类神阴神需要同课四课与三传")
    upper_roles = year_fate_uppers or {"natal": None, "annual": None}
    if set(upper_roles) != {"natal", "annual"} or any(
        v is not None and v not in branches for v in upper_roles.values()
    ):
        raise ValueError("年命上神须明确提供，缺项保留未知")
    noble = noble_start(day_ganzhi[0], is_diurnal, guiren_profile)
    other_noble = noble_start(day_ganzhi[0], not is_diurnal, guiren_profile)
    if god_by_sky[noble] != "贵人":
        raise ValueError("阴神所用贵人表与本课实际天将盘不一致")
    by_god = {god: sky for sky, god in god_by_sky.items()}
    earth_by_sky = {sky: earth for earth, sky in sky_by_earth.items()}
    empty = kongwang_for_ganzhi(day_ganzhi)[:2]
    powers = POWERS[MONTH_PARTITION[month_branch]]
    positions = ("initial", "middle", "final")
    rows = []
    for god in GUI_REN_SEQUENCE:
        riding = by_god[god]
        yin = other_noble if god == "贵人" else sky_by_earth[riding]
        lesson_indices = [i for i, upper in enumerate(lesson_uppers, 1) if upper == yin]
        trans_positions = [
            p for p, upper in zip(positions, transmission_branches) if upper == yin
        ]
        natal = None if upper_roles["natal"] is None else yin == upper_roles["natal"]
        annual = None if upper_roles["annual"] is None else yin == upper_roles["annual"]
        power = powers[branch_element_text(yin)]
        rows.append(
            dict(
                god=god,
                riding_branch=riding,
                riding_earth_branch=earth_by_sky[riding],
                yin_branch=yin,
                yin_earth_branch=earth_by_sky[yin],
                derivation=(
                    "opposite_noble_start"
                    if god == "贵人"
                    else "upper_of_riding_branch"
                ),
                lesson_indices=lesson_indices,
                transmission_positions=trans_positions,
                in_natal_upper=natal,
                in_annual_upper=annual,
                appears_in_roles=role_presence(
                    bool(lesson_indices), bool(trans_positions), natal, annual
                ),
                yin_branch_xun_kong=yin in empty,
                nominal_seasonal_power=power,
                nominal_wang_xiang=power in ("旺", "相"),
            )
        )
    return dict(
        ruleset_id="tanyuan_category_spirit_yin_v1",
        source_title="大六壬探原·论阴神〔类神之阴〕",
        day_ganzhi=day_ganzhi,
        month_branch=month_branch,
        is_diurnal=is_diurnal,
        guiren_profile=guiren_profile,
        sky_by_earth=dict(sky_by_earth),
        god_by_sky=dict(god_by_sky),
        lesson_uppers=list(lesson_uppers),
        transmission_branches=list(transmission_branches),
        year_fate_uppers=dict(upper_roles),
        seasonal_profile="declared_seasonal_month_branches_v1",
        rows=rows,
        complete_classical_conformance=False,
    )


def add_year_fate_membership(board: dict[str, Any], year_fate: dict[str, Any]) -> None:
    previous = board["god_yin"]
    inputs = {
        key: previous[key]
        for key in (
            "day_ganzhi",
            "month_branch",
            "is_diurnal",
            "guiren_profile",
            "sky_by_earth",
            "god_by_sky",
            "lesson_uppers",
            "transmission_branches",
        )
    }
    inputs["year_fate_uppers"] = {
        role: year_fate[role]["sky_branch"] for role in ("natal", "annual")
    }
    board["god_yin"] = god_yin_spirits(**inputs)


def seasonal_metadata() -> dict[str, Any]:
    return dict(
        ruleset_id="tanyuan_seasonal_month_conditions_v1",
        source_title="大六壬探原·论旺相死囚休",
        month_partition_profile="declared_seasonal_month_branches_v1",
        effective_empty_classification=None,
        effective_true_half_adjudicated=False,
        complete_classical_conformance=False,
    )


def empty_condition(power: str, xun_kong: bool) -> str | None:
    if power not in ("旺", "相", "休", "囚", "死") or type(xun_kong) is not bool:
        raise ValueError("本空季节条件需要有效五态与布尔本空")
    return ("半空条件" if power in ("旺", "相") else "真空条件") if xun_kong else None


def seasonal_evidence(
    *,
    day_ganzhi: str,
    month_branch: str,
    sky_by_earth: dict[str, str],
    god_by_sky: dict[str, str],
) -> dict[str, Any]:
    if (
        not isinstance(day_ganzhi, str)
        or day_ganzhi not in SEXAGENARY_INDEX
        or not isinstance(month_branch, str)
        or month_branch not in MONTH_PARTITION
    ):
        raise ValueError("六壬季节条件需要有效日干支与月建支")
    branches = set(EARTHLY_BRANCHES)
    if (
        not isinstance(sky_by_earth, dict)
        or set(sky_by_earth) != branches
        or set(sky_by_earth.values()) != branches
    ):
        raise ValueError("六壬季节条件需要完整天地盘")
    if (
        len(
            {
                (EARTHLY_BRANCHES.index(s) - EARTHLY_BRANCHES.index(e)) % 12
                for e, s in sky_by_earth.items()
            }
        )
        != 1
    ):
        raise ValueError("六壬季节条件的天地盘须一致转动")
    if (
        not isinstance(god_by_sky, dict)
        or set(god_by_sky) != branches
        or set(god_by_sky.values()) != set(GOD_ELEMENTS)
    ):
        raise ValueError("六壬季节条件需要完整十二天将")
    partition = MONTH_PARTITION[month_branch]
    powers = POWERS[partition]
    empty = list(kongwang_for_ganzhi(day_ganzhi)[:2])
    rows = []
    for earth in EARTHLY_BRANCHES:
        sky = sky_by_earth[earth]
        god = god_by_sky[sky]
        sky_phase = branch_element_text(sky)
        earth_phase = branch_element_text(earth)
        god_phase = GOD_ELEMENTS[god]
        power = powers[sky_phase]
        rows.append(
            dict(
                earth_branch=earth,
                sky_branch=sky,
                sky_element=sky_phase,
                sky_seasonal_power=power,
                god=god,
                god_element=god_phase,
                god_seasonal_power=powers[god_phase],
                earth_element=earth_phase,
                earth_seasonal_power=powers[earth_phase],
                sky_xun_kong=sky in empty,
                sky_empty_seasonal_condition=empty_condition(power, sky in empty),
                effective_empty_class=None,
            )
        )
    metadata = seasonal_metadata()
    day_stem_phase = stem_element_text(day_ganzhi[0])
    day_stem_power = powers[day_stem_phase]
    return dict(
        **metadata,
        day_ganzhi=day_ganzhi,
        month_branch=month_branch,
        season_partition=partition,
        day_stem_element=day_stem_phase,
        day_stem_seasonal_power=day_stem_power,
        rows=rows,
    )


def nominal_seasonal_metadata() -> dict[str, Any]:
    return dict(
        method_id="tanyuan_nominal_trine_seasonal_component_v1",
        month_partition_profile="declared_seasonal_month_branches_v1",
        full_named_course_adjudicated=False,
        transformation_confirmed=None,
    )


def nominal_seasonal_evidence(
    month_branch: str, nominal_element: str
) -> dict[str, Any]:
    if month_branch not in MONTH_PARTITION or nominal_element not in (
        "木",
        "火",
        "金",
        "水",
    ):
        raise ValueError("名义三合局体季态需要明确月建支和五行")
    components = {"旺": "得势", "相": "将来", "休": "既往", "囚": "失时", "死": "失时"}
    season = MONTH_PARTITION[month_branch]
    power = POWERS[season][nominal_element]
    return dict(
        **nominal_seasonal_metadata(),
        month_branch=month_branch,
        season_partition=season,
        nominal_element=nominal_element,
        nominal_power=power,
        course_component=components[power],
    )


def branch_pair_facts(left: str, right: str) -> dict[str, Any]:
    if left not in EARTHLY_BRANCHES or right not in EARTHLY_BRANCHES:
        raise ValueError("六壬支位关系需要单个有效地支")
    pair = frozenset((left, right))
    facts: dict[str, Any] = {}
    if left == right:
        facts["same_branch"] = True
    for k, pairs in PAIRS.items():
        if any(pair == frozenset(p) for p in pairs):
            facts[k] = True
    if XING[left] == right:
        facts["left_xing_right"] = True
    if XING[right] == left:
        facts["right_xing_left"] = True
    if pair == frozenset("寅亥"):
        facts["harmony_annotation"] = "破合"
    elif pair == frozenset("巳申"):
        facts["harmony_annotation"] = "刑合"
    return facts


def branch_relations(
    *,
    day_ganzhi: str,
    year_branch: str,
    month_branch: str,
    hour_branch: str,
    month_general_branch: str,
    sky_by_earth: dict[str, str],
    lessons: list[dict[str, Any]],
    transmissions: list[str],
) -> dict[str, Any]:
    if day_ganzhi not in SEXAGENARY_INDEX:
        raise ValueError("六壬支位关系需要有效日干支")
    branches = set(EARTHLY_BRANCHES)
    if any(
        v not in branches
        for v in (year_branch, month_branch, hour_branch, month_general_branch)
    ):
        raise ValueError("六壬支位关系需要有效年月时支与月将")
    if set(sky_by_earth) != branches or set(sky_by_earth.values()) != branches:
        raise ValueError("六壬支位关系需要完整天地盘")
    offsets = {
        (EARTHLY_BRANCHES.index(s) - EARTHLY_BRANCHES.index(e)) % 12
        for e, s in sky_by_earth.items()
    }
    if offsets != {
        (
            EARTHLY_BRANCHES.index(month_general_branch)
            - EARTHLY_BRANCHES.index(hour_branch)
        )
        % 12
    }:
        raise ValueError("六壬支位关系天地盘与月将加时不一致")
    house = STEM_HOUSES[day_ganzhi[0]]
    lower = [house, sky_by_earth[house], day_ganzhi[1], sky_by_earth[day_ganzhi[1]]]
    if len(lessons) != 4 or any(
        l.get("index") != i
        or l.get("lower_branch") != b
        or l.get("upper_branch") != sky_by_earth[b]
        for i, (l, b) in enumerate(zip(lessons, lower), 1)
    ):
        raise ValueError("六壬支位关系四课与日干寄宫及天地盘不一致")
    if len(transmissions) != 3 or any(v not in branches for v in transmissions):
        raise ValueError("六壬支位关系需要完整三传")
    rows = []

    def add(
        identifier: str, left_role: str, right_role: str, left: str, right: str
    ) -> None:
        rows.append(
            dict(
                id=identifier,
                left_role=left_role,
                right_role=right_role,
                left_branch=left,
                right_branch=right,
                facts=branch_pair_facts(left, right),
            )
        )

    for earth in EARTHLY_BRANCHES:
        add(f"seat.{earth}", "天盘支", "地盘支", sky_by_earth[earth], earth)
    for i, lesson in enumerate(lessons, 1):
        add(
            f"lesson.{i}",
            f"第{i}课上神",
            "日干寄宫支" if i == 1 else f"第{i}课下支",
            lesson["upper_branch"],
            lesson["lower_branch"],
        )
    for name, a, b in (
        ("initial_middle", 0, 1),
        ("middle_final", 1, 2),
        ("initial_final", 0, 2),
    ):
        add(
            f"transmission.{name}",
            ("初传", "中传", "末传")[a],
            ("初传", "中传", "末传")[b],
            transmissions[a],
            transmissions[b],
        )
    targets = [
        (f"lesson.{i}", f"第{i}课上神", l["upper_branch"])
        for i, l in enumerate(lessons, 1)
    ] + [
        (f"transmission.{p}", label, b)
        for p, label, b in zip(
            ("initial", "middle", "final"), ("初传", "中传", "末传"), transmissions
        )
    ]
    calendar_branches = dict(
        year=year_branch, month=month_branch, day=day_ganzhi[1], hour=hour_branch
    )
    for (role, ref), label in zip(
        calendar_branches.items(), ("年支", "月支", "日支", "时支")
    ):
        for identifier, target_label, target in targets:
            add(f"contact.{role}.{identifier}", target_label, label, target, ref)
    return dict(
        ruleset_id="tanyuan_branch_relations_v1",
        source_title="大六壬探原·论合、破、害、刑、冲",
        day_ganzhi=day_ganzhi,
        calendar_branches=calendar_branches,
        month_general_branch=month_general_branch,
        sky_by_earth=dict(sky_by_earth),
        lesson_branches=[
            dict(
                index=i, lower_branch=l["lower_branch"], upper_branch=l["upper_branch"]
            )
            for i, l in enumerate(lessons, 1)
        ],
        transmission_branches=dict(zip(("initial", "middle", "final"), transmissions)),
        rows=rows,
        comprehensive_judgement=None,
        complete_classical_conformance=False,
    )


def placement_metadata() -> dict[str, Any]:
    return dict(
        ruleset_id="tanyuan_day_placements_v2",
        source_title="大六壬探原·论日干日枝、课体纲要",
        evaluations=[
            dict(
                id=i,
                name=n,
                condition=c,
                placement=p,
                relation=r,
                definition_adjudicated=r != "harmony_unadjudicated",
                **({"relation_matches": None} if r == "harmony_unadjudicated" else {}),
            )
            for i, n, c, p, r in DAY_PLACEMENT_RULES
        ],
        evaluated_count=10,
        unresolved_count=2,
        unresolved_ids=["D11", "D12"],
        comprehensive_judgement=None,
        complete_classical_conformance=False,
    )


def day_placement_patterns(
    day_ganzhi: str, sky_by_earth: dict[str, str]
) -> dict[str, Any]:
    if not isinstance(day_ganzhi, str) or day_ganzhi not in SEXAGENARY_INDEX:
        raise ValueError("干支加临条件需要有效占日干支")
    branches = set(EARTHLY_BRANCHES)
    if (
        not isinstance(sky_by_earth, dict)
        or set(sky_by_earth) != branches
        or set(sky_by_earth.values()) != branches
        or len(
            {
                (EARTHLY_BRANCHES.index(s) - EARTHLY_BRANCHES.index(e)) % 12
                for e, s in sky_by_earth.items()
            }
        )
        != 1
    ):
        raise ValueError("干支加临条件需要完整顺布天地盘")
    stem, branch = day_ganzhi[0], day_ganzhi[1]
    house = STEM_HOUSES[stem]
    stem_phase, branch_phase = stem_element_text(stem), branch_element_text(branch)
    placements = dict(
        stem_over_branch=sky_by_earth[branch] == house,
        branch_over_stem=sky_by_earth[house] == branch,
    )
    relations = dict(
        branch_generates_stem=ELEMENT_GENERATES[branch_phase] == stem_phase,
        stem_generates_branch=ELEMENT_GENERATES[stem_phase] == branch_phase,
        branch_controls_stem=ELEMENT_CONTROLS[branch_phase] == stem_phase,
        stem_controls_branch=ELEMENT_CONTROLS[stem_phase] == branch_phase,
        same_element=stem_phase == branch_phase,
    )
    result = placement_metadata()
    for row in result["evaluations"]:
        row["placement_matches"] = placements[row["placement"]]
        if row["definition_adjudicated"]:
            row["relation_matches"] = relations[row["relation"]]
        row["matched"] = row["placement_matches"] and row["relation_matches"]
    result.update(
        day_ganzhi=day_ganzhi,
        day_stem_house=house,
        day_stem_element=stem_phase,
        day_branch_element=branch_phase,
        sky_by_earth=dict(sky_by_earth),
        placements=placements,
        element_relations=relations,
        matched_ids=[r["id"] for r in result["evaluations"] if r["matched"] is True],
    )
    return result


def cross_harmony_metadata() -> dict[str, Any]:
    return dict(
        ruleset_id="daquan_siku_bifa21_cross_harmony_v1",
        name="交车合",
        source_title="六壬大全·毕法赋第二十一法",
        definition="日干与支上神作六合，地支与干上神作六合；干支同宫五日排除",
        excluded_days=["甲寅", "庚申", "丁未", "己未", "癸丑"],
        comprehensive_judgement=None,
        complete_classical_conformance=False,
    )


def cross_harmony(day_ganzhi: str, sky_by_earth: dict[str, str]) -> dict[str, Any]:
    if not isinstance(day_ganzhi, str) or day_ganzhi not in SEXAGENARY_INDEX:
        raise ValueError("交车合条件需要有效占日干支")
    branches = set(EARTHLY_BRANCHES)
    if (
        not isinstance(sky_by_earth, dict)
        or set(sky_by_earth) != branches
        or set(sky_by_earth.values()) != branches
        or len(
            {
                (EARTHLY_BRANCHES.index(s) - EARTHLY_BRANCHES.index(e)) % 12
                for e, s in sky_by_earth.items()
            }
        )
        != 1
    ):
        raise ValueError("交车合条件需要完整顺布天地盘")
    house, branch = STEM_HOUSES[day_ganzhi[0]], day_ganzhi[1]
    stem_upper, branch_upper = sky_by_earth[house], sky_by_earth[branch]
    pairs = [
        dict(
            id=ident,
            left_role=left_role,
            right_role=right_role,
            left_branch=left,
            right_branch=right,
            liuhe=branch_pair_facts(left, right).get("liuhe", False),
        )
        for ident, left_role, right_role, left, right in (
            ("stem_upper_to_day_branch", "干上神", "日支", stem_upper, branch),
            ("branch_upper_to_stem_house", "支上神", "日干寄宫支", branch_upper, house),
        )
    ]
    both = all(row["liuhe"] for row in pairs)
    distinct = house != branch
    return dict(
        **cross_harmony_metadata(),
        day_ganzhi=day_ganzhi,
        day_stem_house=house,
        day_branch=branch,
        stem_upper=stem_upper,
        branch_upper=branch_upper,
        sky_by_earth=dict(sky_by_earth),
        cross_pairs=pairs,
        distinct_anchors=distinct,
        both_cross_pairs=both,
        matched=distinct and both,
        exclusion_reason=None if distinct else "干支同宫（八专五日）",
    )
