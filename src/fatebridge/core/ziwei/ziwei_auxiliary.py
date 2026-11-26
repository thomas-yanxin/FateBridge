"""Named natal cycles, chart masters and explicitly scoped flowing stars."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal, TypedDict

from typing_extensions import NotRequired

from fatebridge.core.ziwei.ziwei_rulesets import (
    IZTRO_SOURCE,
    NAJ_MING_SOURCE,
    QUANSHU_SOURCE,
)
from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS

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
    # The selected text explicitly says male forward/female reverse for
    # 长生; 博士 uses year polarity and gender. Do not conflate the two.
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
        "changsheng_source": (
            NAJ_MING_SOURCE if rule_profile == "quanshu_v2_excerpt" else IZTRO_SOURCE
        ),
        "boshi_start": bs_start,
        "boshi_direction": (
            ("顺行" if yang_gender_forward else "逆行") if known else None
        ),
        "boshi_rule": "lucun_start_year_polarity_and_gender",
        "boshi_source": NAJ_MING_SOURCE,
        "label_scope": "symbolic_cycle_names_only",
        "naming_note": "明刊博士蜚廉对应今飞廉，与年支蜚廉分层；原页大耗、官府不作旧转录天耗、宫府",
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
    rule_profile: str,
) -> dict[str, Any]:
    def record(star: str, basis: str, branch: str) -> dict[str, Any]:
        palace = next(
            p for p in palaces if any(s["name"] == star for s in p["stars_detail"])
        )
        ambiguous = (
            basis == "natal_year_branch"
            and branch in {"子", "午"}
            and rule_profile == "quanshu_v2_excerpt"
        )
        return {
            "star": star,
            "selection_basis": basis,
            "basis_branch": branch,
            "natal_palace_name": palace["name"],
            "natal_branch": palace["ganzhi"][1],
            "source": (
                IZTRO_SOURCE
                if ambiguous or rule_profile != "quanshu_v2_excerpt"
                else QUANSHU_SOURCE
            ),
            "source_status": (
                "software_fallback_ambiguous_fire_ling_text"
                if ambiguous
                else "selected_rule"
            ),
        }

    return {
        "life": record(LIFE_MASTER[ming_branch], "ming_palace_branch", ming_branch),
        "body": record(BODY_MASTER[year_branch], "natal_year_branch", year_branch),
    }


# iztro 2.5.8, src/star/location.ts. Stem columns follow 甲 through 癸.
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
    source: str
    system_id: NotRequired[str]
    natal_stars_relocated: Literal[False]


def flowing_horoscope_stars(
    scope_palaces: Sequence[Mapping[str, str]],
    *,
    scope: ZiweiFlowingScope,
    stem: str,
    pillar_branch: str,
) -> list[FlowingStarPlacement]:
    """Project the pinned placements for the layer's supplied stem and branch."""
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

    by_branch = {palace["branch"]: palace for palace in scope_palaces}
    result: list[FlowingStarPlacement] = []
    for star, branch, rule_id in placements:
        palace = by_branch[branch]
        record: FlowingStarPlacement = {
            "star": star,
            "scope": scope,
            "branch": branch,
            "scope_palace_name": palace["scope_palace_name"],
            "natal_palace_name": palace["natal_palace_name"],
            "rule_id": rule_id,
            "source": IZTRO_SOURCE,
            "natal_stars_relocated": False,
        }
        if rule_id.endswith("_branch"):
            record["basis_branch"] = pillar_branch
        else:
            record["stem"] = stem
        if rule_id == "annual_lucun_yang_tuo":
            record["source"] = QUANSHU_SOURCE
        else:
            record["system_id"] = "iztro_2_5_8_horoscope"
        result.append(record)
    return result
