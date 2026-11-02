"""Named natal cycles, chart masters and explicitly scoped flowing stars."""

from __future__ import annotations

from typing import Any, Dict, List

from fatebridge.core.ziwei_rulesets import IZTRO_SOURCE, NAJ_MING_SOURCE, QUANSHU_SOURCE
from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS

ZIWEI_LUCUN_BY_STEM = dict(zip(HEAVENLY_STEMS, "寅卯巳午巳午申酉亥子"))
_CHANGSHENG = (
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
_BOSHI = (
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
_CHANGSHENG_START = {"水": "申", "木": "亥", "金": "巳", "土": "申", "火": "寅"}
_LIFE_MASTER = dict(
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
_BODY_MASTER = dict(
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
    palaces: List[Dict[str, Any]],
    *,
    element: str,
    year_stem: str,
    gender: str,
    rule_profile: str,
) -> Dict[str, Any]:
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
    cs_start = _CHANGSHENG_START[element]
    bs_start = ZIWEI_LUCUN_BY_STEM[year_stem]
    for palace in palaces:
        index = EARTHLY_BRANCHES.index(palace["ganzhi"][1])
        cs_offset = index - EARTHLY_BRANCHES.index(cs_start)
        bs_offset = index - EARTHLY_BRANCHES.index(bs_start)
        palace["changsheng12"] = (
            _CHANGSHENG[(cs_offset if cs_forward else -cs_offset) % 12]
            if known
            else (
                _CHANGSHENG[cs_offset % 12]
                if _CHANGSHENG[cs_offset % 12] == _CHANGSHENG[-cs_offset % 12]
                else None
            )
        )
        palace["boshi12"] = (
            _BOSHI[(bs_offset if yang_gender_forward else -bs_offset) % 12]
            if known
            else (
                _BOSHI[bs_offset % 12]
                if _BOSHI[bs_offset % 12] == _BOSHI[-bs_offset % 12]
                else None
            )
        )
    result: Dict[str, Any] = {
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
    palaces: List[Dict[str, Any]],
    *,
    ming_branch: str,
    year_branch: str,
    rule_profile: str,
) -> Dict[str, Any]:
    def record(star: str, basis: str, branch: str) -> Dict[str, Any]:
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
        "life": record(_LIFE_MASTER[ming_branch], "ming_palace_branch", ming_branch),
        "body": record(_BODY_MASTER[year_branch], "natal_year_branch", year_branch),
    }


def flowing_lucun_stars(
    scope_palaces: List[Dict[str, Any]],
    *,
    stem: str,
) -> List[Dict[str, Any]]:
    """流年禄羊陀; natal star locations are never moved or overwritten."""
    index = EARTHLY_BRANCHES.index(ZIWEI_LUCUN_BY_STEM[stem])
    result = []
    for star, offset in (("禄存", 0), ("擎羊", 1), ("陀罗", -1)):
        branch = EARTHLY_BRANCHES[(index + offset) % 12]
        palace = next(p for p in scope_palaces if p["branch"] == branch)
        result.append(
            {
                "star": star,
                "scope": "流年",
                "branch": branch,
                "scope_palace_name": palace["scope_palace_name"],
                "natal_palace_name": palace["natal_palace_name"],
                "rule_id": "annual_lucun_yang_tuo",
                "stem": stem,
                "source": QUANSHU_SOURCE,
                "natal_stars_relocated": False,
            }
        )
    return result
