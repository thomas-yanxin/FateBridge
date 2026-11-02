"""Explicit chapter-level variants in the Siku edition of 遁甲演义.

These are source selections, not a ranking of schools or a way to optimize an
auspicious result. Shared sequence positions do not establish semantic aliases.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fatebridge.core.metaphysics.common import ELEMENT_CONTROLS, ELEMENT_GENERATES
from fatebridge.core.qimen_five_jia import describe_five_jia
from fatebridge.core.qimen_gate_relations import describe_gate_relations
from fatebridge.core.qimen_punishment import describe_punishment
from fatebridge.core.qimen_three_deceptions import describe_three_deceptions
from fatebridge.core.qimen_tombs import describe_wonder_tombs

SOURCE = "https://zh.wikisource.org/w/index.php?oldid=625946"
SCAN_SOURCE = "https://ourartnet.com/King_James/Hushulei/047.pdf"
DEFAULT_GOD_PROFILE = "yanyi_text"
DEFAULT_SEASON_PROFILE = "yanyi_vol1_verse"
GOD_PROFILES: dict[str, dict[str, Any]] = {
    "yanyi_text": {
        "title": "卷三正文八神",
        "section": "卷三·天乙直符吉凶神说",
        "scan_pages": [48, 49],
        "sequence": ["值符", "螣蛇", "太阴", "六合", "白虎", "玄武", "九地", "九天"],
    },
    "yanyi_diagrams": {
        "title": "卷四圆图八神",
        "section": "卷四·阴阳二遁圆图",
        "scan_pages": [63, 65, 67, 69],
        "sequence": ["值符", "螣蛇", "太阴", "六合", "勾陈", "朱雀", "九地", "九天"],
    },
}
SEASON_PROFILES: dict[str, dict[str, Any]] = {
    "yanyi_vol1_verse": {
        "title": "卷一烟波钓叟赋九星旺相",
        "section": "卷一·烟波钓叟赋",
        "scan_pages": [7],
        "states_by_relation": {
            "same_element": "相",
            "star_generates_month": "旺",
            "month_generates_star": "废",
            "star_controls_month": "休",
            "month_controls_star": "囚",
        },
    },
    "yanyi_vol3_table": {
        "title": "卷三九星旺相休囚表",
        "section": "卷三·九星旺相休囚表",
        "scan_pages": [38],
        "states_by_relation": {
            "same_element": "旺",
            "star_generates_month": "相",
            "month_generates_star": "废",
            "star_controls_month": "休",
            "month_controls_star": "囚",
        },
    },
    "yanyi_vol3_prose": {
        "title": "卷三九星旺衰正文",
        "section": "卷三·九星所属及旺衰正文",
        "scan_pages": [37, 38],
        "states_by_relation": {
            "same_element": "旺",
            "star_generates_month": "相",
            "month_generates_star": "休",
            "star_controls_month": "死",
            "month_controls_star": "囚",
        },
    },
}


def validate_profiles(god_profile: str, season_profile: str) -> None:
    for name, value, profiles in [
        ("god_profile", god_profile, GOD_PROFILES),
        ("season_profile", season_profile, SEASON_PROFILES),
    ]:
        if not isinstance(value, str) or value not in profiles:
            raise ValueError(f"{name}仅支持：{', '.join(profiles)}")


def star_season_relation(star_element: str, month_element: str) -> str:
    if star_element not in ELEMENT_GENERATES or month_element not in ELEMENT_GENERATES:
        raise ValueError("九星旺衰须使用木火土金水五行")
    if star_element == month_element:
        return "same_element"
    if ELEMENT_GENERATES[star_element] == month_element:
        return "star_generates_month"
    if ELEMENT_GENERATES[month_element] == star_element:
        return "month_generates_star"
    if ELEMENT_CONTROLS[star_element] == month_element:
        return "star_controls_month"
    return "month_controls_star"


def star_season_state(
    star_element: str, month_element: str, profile: str = DEFAULT_SEASON_PROFILE
) -> str:
    validate_profiles(DEFAULT_GOD_PROFILE, profile)
    return str(
        SEASON_PROFILES[profile]["states_by_relation"][
            star_season_relation(star_element, month_element)
        ]
    )


def describe_profiles(god_profile: str, season_profile: str) -> dict[str, Any]:
    validate_profiles(god_profile, season_profile)
    result: dict[str, Any] = {}
    for name, key, profiles in [
        ("god", god_profile, GOD_PROFILES),
        ("season", season_profile, SEASON_PROFILES),
    ]:
        result[name] = {
            "id": key,
            "source": SOURCE,
            "scan_source": SCAN_SOURCE,
            **deepcopy(profiles[key]),
            "selection_policy": "explicit_input_or_fixed_default; never_selected_by_outcome",
        }
    result["god"]["placement"] = "值符从移动值符星宫起，阳顺阴逆；中五先寄坤二"
    result["god"][
        "variant_note"
    ] = "卷三正文列白虎、玄武，所核卷四圆图列勾陈、朱雀；同序位不证明同义，亦不等同六壬十二天将。"
    result["season"][
        "variant_note"
    ] = "卷一赋、卷三表、卷三正文定义有别；本项只按已选章节和实际月支五行计算，不综合为吉凶分数。"
    result["wonder_tomb"] = describe_wonder_tombs()
    result["six_instrument_punishment"] = describe_punishment()
    result["door_palace_relation"] = describe_gate_relations()
    result["three_deceptions"] = describe_three_deceptions()
    result["five_jia"] = describe_five_jia()
    return result


_GOD_ROLES = {
    "值符": "原文称天乙之神，置于事急从其方的军事语境；这里只保留主导、统摄的传统象义。",
    "螣蛇": "原文称虚诈之神，提示混乱、疑虑的传统象义；不据此断言他人欺骗或诊断精神状态。",
    "太阴": "原文称阴佑之神，用于藏兵与避让；可作隐蔽、保留和审慎的传统象义。",
    "六合": "原文称护卫之神，用于防备与抵挡；可作协同、保护的传统象义。",
    "白虎": "原文称凶恶之神，用于军营警戒；可作防备冲突的传统象义，不断现实灾祸。",
    "玄武": "原文称小盗之神，用于防备窥探；可提示核对信息，不据此指认现实盗窃或欺诈。",
    "九地": "原文称坚牢之神，用于屯兵固守；可作稳固、守成的传统象义。",
    "九天": "原文用于扬兵布阵；可作展开、主动的传统象义，不保证现实行动成功。",
}


def god_evidence(god: str) -> dict[str, Any]:
    common: dict[str, Any] = {
        "god": god,
        "source": SOURCE,
        "section": "卷三·天乙直符吉凶神说",
        "scan_pages": [49],
        "layer": "traditional_role_not_outcome",
        "outcome_inferred": False,
    }
    if god not in _GOD_ROLES:
        return {
            **common,
            "interpretation_status": "name_only_not_equated",
            "traditional_role": "本次仅按卷四圆图排出此名称，未将同序位白虎或玄武的卷三解释移植过来。",
            "section": "卷四·阴阳二遁圆图",
            "scan_pages": [63, 65, 67, 69],
        }
    result = {
        **common,
        "interpretation_status": "source_scoped_role",
        "traditional_role": _GOD_ROLES[god],
    }
    if god in {"螣蛇", "白虎", "玄武"}:
        result["source_qualification"] = (
            "原文附有得奇门会合则不忌的条件；此处不凭神名判断该条件已满足。"
        )
        result["qualification_evaluated"] = False
    return result
