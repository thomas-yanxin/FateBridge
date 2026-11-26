"""Finite 月令 selection rules, 十二长生 lookup and a seasonal reference table.

Selection exposes its method, legacy label and declared source scope. It does
not adjudicate every transformation, formation, rescue or school disagreement.
Growth phases and actual hidden-stem roots are separate observations. The
seasonal table is a circulating baseline, not a fully verified critical edition.
"""

from __future__ import annotations

from typing import Any

from fatebridge.core.classical_roots import build_classical_root_profile
from fatebridge.core.classical_seasonal import seasonal_reference_layers
from fatebridge.core.classical_stages import (
    LU_SEATS,
    STAGE_PROFILE_ID,
    YANG_BLADE_SEATS,
    twelve_life_stage,
)
from fatebridge.core.month_use import build_month_use_resolution
from fatebridge.utils.data import (
    BRANCH_HIDDEN_STEMS,
    BRANCH_TRIPLE_COMBINATIONS,
    STEM_ELEMENTS,
    TRIPLE_COMBINATION_PEAK,
    get_shishen,
)

PillarMap = dict[str, tuple[str, str]]

# --------------------------------------------------------------------------- #
# 十二长生 (Twelve Life Stages)
# --------------------------------------------------------------------------- #
# Day-master energy state at each branch. 阳干顺行、阴干逆行 from the 长生 branch.
# A deterministic phase lookup; the stage alone does not establish 通根/旺衰.


def life_stages_for_pillars(pillars: PillarMap) -> dict[str, Any]:
    """Map the day master's 十二长生 state across all four branches."""
    day_stem = pillars["day"][0]
    labels = {"year": "年支", "month": "月支", "day": "日支", "hour": "时支"}
    per_pillar = {
        labels[key]: twelve_life_stage(day_stem, pillars[key][1])
        for key in ("year", "month", "day", "hour")
    }
    day_element = STEM_ELEMENTS[day_stem][0]
    hidden_roots = [
        labels[key]
        for key in ("year", "month", "day", "hour")
        if any(
            STEM_ELEMENTS[stem][0] == day_element
            for stem in BRANCH_HIDDEN_STEMS[pillars[key][1]]
        )
    ]
    return {
        "day_stem": day_stem,
        "life_stage_profile_id": STAGE_PROFILE_ID,
        "per_pillar": per_pillar,
        "hidden_stem_roots": hidden_roots,
        "hidden_stem_root_scope": "仅核对藏干同五行是否存在，不裁定根深、根损或有效力量。",
    }


# --------------------------------------------------------------------------- #
# 月令取格 (Canonical structure from the month branch)
# --------------------------------------------------------------------------- #
# The foundational 子平 pattern: read the month branch's hidden stems
# (本气/中气/余气), see which is 透出 on the other stems, and the ten-god of the
# chosen stem names the 正格. 禄(比肩)/刃(劫财) are handled as the 建禄/月刃 specials.

TEN_GOD_TO_STRUCTURE: dict[str, str] = {
    "正官": "正官格",
    "七杀": "七杀格",
    "正财": "正财格",
    "偏财": "偏财格",
    "正印": "正印格",
    "偏印": "偏印格",
    "食神": "食神格",
    "伤官": "伤官格",
    "比肩": "建禄格",
    "劫财": "月刃格",
}

HIDDEN_ROLES: tuple[str, ...] = ("本气", "中气", "余气")


def _select_structure_god(
    candidates: list[dict[str, Any]], day_stem: str, pillars: PillarMap
) -> dict[str, Any]:
    """Pick which month-branch hidden stem defines the 格 (the tunable rule).

    Qualify the actual lu/yang-blade seat before choosing a 比劫 god. For
    miscellaneous qi, retain revealed meeting support before the historical
    revealed-rank fallback. Selection is not a formation adjudication.
    """
    primary = candidates[0]
    month_branch = pillars["month"][1]
    if month_branch == LU_SEATS[day_stem]:
        lu_god = next(c for c in candidates if c["ten_god"] == "比肩")
        return {**lu_god, "is_special": True, "selection_rule": "qualified_lu_seat"}
    if month_branch == YANG_BLADE_SEATS.get(day_stem):
        blade_god = next(c for c in candidates if c["ten_god"] == "劫财")
        return {
            **blade_god,
            "is_special": True,
            "selection_rule": "qualified_yang_blade_seat",
        }

    transparent = [
        c
        for c in candidates
        if c["transparent"] and c["ten_god"] not in ("比肩", "劫财")
    ]
    # 《子平真诠》正官章（核对藏本 PDF65–66）：财、印可辅官，
    # 不因印透就一律改取印格。这只是下列有限条件的取格候选，非成格判定。
    other_gods = {
        get_shishen(day_stem, pillars[p][0]) for p in ("year", "month", "hour")
    }
    if (
        primary["ten_god"] == "正官"
        and month_branch not in "辰戌丑未"
        and transparent
        and all(
            c["ten_god"] in ("正官", "正财", "偏财", "正印", "偏印")
            for c in transparent
        )
        and not other_gods.intersection({"伤官", "食神", "七杀"})
        and not any(
            set(group).issubset({b for _, b in pillars.values()})
            for group in BRANCH_TRIPLE_COMBINATIONS
            if month_branch in group
        )
    ):
        return {
            **primary,
            "is_special": False,
            "selection_rule": "officer_with_wealth_seal_support",
        }
    # 杂气透干会支: preserve a revealed candidate supported by an actual
    # full/peak-containing half triad. This does not certify 合化 or 成格.
    meeting_supported = []
    branches = {branch for _, branch in pillars.values()}
    if month_branch in "辰戌丑未":
        for candidate in transparent:
            element = STEM_ELEMENTS[candidate["stem"]][0].value
            for group, bureau in BRANCH_TRIPLE_COMBINATIONS.items():
                present = set(group) & branches
                if (
                    month_branch in group
                    and bureau.startswith(element)
                    and len(present) >= 2
                    and TRIPLE_COMBINATION_PEAK[group] in present
                ):
                    meeting_supported.append(candidate)
                    break
    chosen = (
        meeting_supported[0]
        if len(meeting_supported) == 1
        else transparent[0] if transparent else primary
    )
    return {
        **chosen,
        "is_special": False,
        "selection_rule": (
            "misc_revealed_meeting_support"
            if len(meeting_supported) == 1
            else "revealed_rank" if transparent else "primary_fallback"
        ),
    }


def determine_monthly_structure(pillars: PillarMap, day_stem: str) -> dict[str, Any]:
    """Determine the canonical 月令正格 from the month branch.

    Returns the recognised 格 plus the factual derivation basis. Pure data —
    the agent interprets what the structure means.
    """
    month_branch = pillars["month"][1]
    hidden = BRANCH_HIDDEN_STEMS[month_branch]

    # 透干 = a month hidden stem appearing on year/month/hour stems
    # (the day stem itself is 我, never the 格神).
    transparent_stems = {pillars[p][0] for p in ("year", "month", "hour")}

    candidates: list[dict[str, Any]] = []
    for rank, hidden_stem in enumerate(hidden):
        candidates.append(
            {
                "stem": hidden_stem,
                "ten_god": get_shishen(day_stem, hidden_stem),
                "role": HIDDEN_ROLES[rank] if rank < len(HIDDEN_ROLES) else "余气",
                "transparent": hidden_stem in transparent_stems,
            }
        )

    god = _select_structure_god(candidates, day_stem, pillars)
    label = TEN_GOD_TO_STRUCTURE.get(god["ten_god"], f"{god['ten_god']}格")
    if not god["is_special"] and god["ten_god"] in ("比肩", "劫财"):
        label = "比劫待取格"

    legacy_label = label
    use_resolution = build_month_use_resolution(
        pillars, god["stem"], candidates[0]["stem"]
    )
    miscellaneous = use_resolution["policy_scope"] == "miscellaneous_qi_source"
    if miscellaneous:
        label = "杂气月令取用候选" if use_resolution["witnesses"] else "杂气月令待取用"
        god = {
            **god,
            "reference_scope": "旧单锚历史参考，不代表本次完整取用见证或最终格局。",
        }
    transparency = "透干" if god["transparent"] else "未透（本气取格）"
    if god["is_special"]:
        basis = (
            f"月令{month_branch}经实际禄刃位置核对，取{label}；不以本气比劫推定资格。"
        )
    else:
        basis = (
            f"月令{month_branch}藏{god['stem']}（{god['role']}），"
            f"对日主{day_stem}为{god['ten_god']}，{transparency}，取{label}。"
        )

    if miscellaneous:
        observed = (
            "；".join(w["label"] for w in use_resolution["witnesses"])
            or "暂无已建模透干/完整会支见证"
        )
        basis = f"月令{month_branch}：{observed}；资格并存，不裁成格、合化或全局喜忌。"

    return {
        "method_id": "month_command_qualified_officer_v3",
        "use_resolution": use_resolution,
        "legacy_selection_label": legacy_label,
        "month_branch": month_branch,
        "label": label,
        "structure_god": god,
        "is_special": god["is_special"],
        "hidden_stems": candidates,
        "original_structure": {
            "stem": candidates[0]["stem"],
            "ten_god": candidates[0]["ten_god"],
            "scope": "月令本气关系，不自动等于最终取格或成格",
        },
        "seat_qualification": {
            "lu_seat": LU_SEATS[day_stem],
            "yang_blade_seat": YANG_BLADE_SEATS.get(day_stem),
            "is_lu": month_branch == LU_SEATS[day_stem],
            "is_yang_blade": month_branch == YANG_BLADE_SEATS.get(day_stem),
        },
        "selection_rule": god["selection_rule"],
        "selection_source": {
            "profile_id": "ziping_zhenquan_month_command_text_v1",
            "locator": "论用神变化 PDF31–32；论正官 PDF65–66",
            "scope": "有限规则形式化；透干会支、兼格、成败救应未完整裁定",
        },
        "selection_scope": "杂气取用以use_resolution全部见证为准；structure_god和legacy_selection_label只保旧单锚参考。其余月保既有有限方法。见证不认证成格。",
        "basis": basis,
    }


# --------------------------------------------------------------------------- #
# 调候用神 (Seasonal adjustment, after 《穷通宝鉴》/《造化元钥》)
# --------------------------------------------------------------------------- #
# month branch -> (primary, [secondary...]) per day stem. This is the widely
# circulated 调候用神简表. It is school-variant at the margins — treat as the
# mainstream baseline and validate against a preferred lineage source if needed.

DIAOHOU_TABLE: dict[str, dict[str, tuple[str, tuple[str, ...]]]] = {
    "甲": {
        "寅": ("丙", ("癸",)),
        "卯": ("庚", ("丙", "丁", "戊", "己")),
        "辰": ("庚", ("丁", "壬")),
        "巳": ("癸", ("丁", "庚")),
        "午": ("癸", ("丁", "庚")),
        "未": ("癸", ("丁", "庚")),
        "申": ("庚", ("丁", "壬")),
        "酉": ("庚", ("丁", "丙")),
        "戌": ("庚", ("甲", "丁", "壬", "癸")),
        "亥": ("庚", ("丁", "丙", "戊")),
        "子": ("丁", ("庚", "丙")),
        "丑": ("丁", ("庚", "丙")),
    },
    "乙": {
        "寅": ("丙", ("癸",)),
        "卯": ("丙", ("癸",)),
        "辰": ("癸", ("丙", "戊")),
        "巳": ("癸", ()),
        "午": ("癸", ("丙",)),
        "未": ("癸", ("丙",)),
        "申": ("丙", ("癸", "己")),
        "酉": ("癸", ("丙", "丁")),
        "戌": ("癸", ("辛",)),
        "亥": ("丙", ("戊",)),
        "子": ("丙", ()),
        "丑": ("丙", ()),
    },
    "丙": {
        "寅": ("壬", ("庚",)),
        "卯": ("壬", ("己",)),
        "辰": ("壬", ("甲",)),
        "巳": ("壬", ("庚", "癸")),
        "午": ("壬", ("庚",)),
        "未": ("壬", ("庚",)),
        "申": ("壬", ("戊",)),
        "酉": ("壬", ("癸",)),
        "戌": ("甲", ("壬",)),
        "亥": ("甲", ("戊", "庚", "壬")),
        "子": ("壬", ("戊", "己")),
        "丑": ("壬", ("甲",)),
    },
    "丁": {
        "寅": ("甲", ("庚",)),
        "卯": ("庚", ("甲",)),
        "辰": ("甲", ("庚",)),
        "巳": ("甲", ("庚",)),
        "午": ("壬", ("庚", "癸")),
        "未": ("甲", ("壬", "庚")),
        "申": ("甲", ("庚", "丙", "戊")),
        "酉": ("甲", ("庚", "丙", "戊")),
        "戌": ("甲", ("庚", "戊")),
        "亥": ("甲", ("庚",)),
        "子": ("甲", ("庚",)),
        "丑": ("甲", ("庚",)),
    },
    "戊": {
        "寅": ("丙", ("甲", "癸")),
        "卯": ("丙", ("甲", "癸")),
        "辰": ("甲", ("丙", "癸")),
        "巳": ("甲", ("丙", "癸")),
        "午": ("壬", ("甲", "丙")),
        "未": ("癸", ("丙", "甲")),
        "申": ("丙", ("癸", "甲")),
        "酉": ("丙", ("癸",)),
        "戌": ("甲", ("丙", "癸")),
        "亥": ("甲", ("丙",)),
        "子": ("丙", ("甲",)),
        "丑": ("丙", ("甲",)),
    },
    "己": {
        "寅": ("丙", ("庚", "甲")),
        "卯": ("甲", ("癸", "丙")),
        "辰": ("丙", ("癸", "甲")),
        "巳": ("癸", ("丙",)),
        "午": ("癸", ("丙",)),
        "未": ("癸", ("丙",)),
        "申": ("丙", ("癸",)),
        "酉": ("丙", ("癸",)),
        "戌": ("甲", ("丙", "癸")),
        "亥": ("丙", ("甲", "戊")),
        "子": ("丙", ("甲", "戊")),
        "丑": ("丙", ("甲", "戊")),
    },
    "庚": {
        "寅": ("戊", ("甲", "丙", "丁", "壬")),
        "卯": ("丁", ("甲", "庚", "丙")),
        "辰": ("甲", ("丁", "壬", "癸")),
        "巳": ("壬", ("戊", "丙", "丁")),
        "午": ("壬", ("癸",)),
        "未": ("丁", ("甲",)),
        "申": ("丁", ("甲",)),
        "酉": ("丁", ("甲", "丙")),
        "戌": ("甲", ("壬",)),
        "亥": ("丁", ("丙",)),
        "子": ("丁", ("丙", "甲")),
        "丑": ("丙", ("丁", "甲")),
    },
    "辛": {
        "寅": ("己", ("壬", "庚")),
        "卯": ("壬", ("甲",)),
        "辰": ("壬", ("甲",)),
        "巳": ("壬", ("甲", "癸")),
        "午": ("壬", ("己", "癸")),
        "未": ("壬", ("庚", "甲")),
        "申": ("壬", ("甲", "戊")),
        "酉": ("壬", ("甲",)),
        "戌": ("壬", ("甲",)),
        "亥": ("壬", ("丙",)),
        "子": ("丙", ("戊", "壬", "甲")),
        "丑": ("丙", ("壬", "戊", "己")),
    },
    "壬": {
        "寅": ("庚", ("丙", "戊")),
        "卯": ("戊", ("辛", "庚")),
        "辰": ("甲", ("庚",)),
        "巳": ("壬", ("辛", "庚", "癸")),
        "午": ("癸", ("庚", "辛")),
        "未": ("辛", ("甲",)),
        "申": ("戊", ("丁",)),
        "酉": ("甲", ("庚",)),
        "戌": ("甲", ("丙",)),
        "亥": ("戊", ("庚", "丙")),
        "子": ("戊", ("丙",)),
        "丑": ("丙", ("丁", "甲")),
    },
    "癸": {
        "寅": ("辛", ("丙",)),
        "卯": ("庚", ("辛",)),
        "辰": ("丙", ("辛", "甲")),
        "巳": ("辛", ()),
        "午": ("庚", ("壬", "辛", "癸")),
        "未": ("庚", ("辛", "壬", "癸")),
        "申": ("丁", ()),
        "酉": ("辛", ("丙",)),
        "戌": ("辛", ("甲", "壬", "癸")),
        "亥": ("庚", ("辛", "戊", "丁")),
        "子": ("丙", ("辛",)),
        "丑": ("丙", ("丁",)),
    },
}


def seasonal_climate_god(
    day_stem: str, month_branch: str, pillars: PillarMap | None = None
) -> dict[str, Any]:
    """Return table candidates, source layers and optional factual positions."""
    entry: tuple[str, tuple[str, ...]] | None = DIAOHOU_TABLE.get(day_stem, {}).get(
        month_branch
    )
    if entry is None:
        lookup: dict[str, Any] = {"primary": None, "secondary": [], "available": False}
        return seasonal_reference_layers(day_stem, month_branch, lookup, pillars)
    primary, secondary = entry
    return seasonal_reference_layers(
        day_stem,
        month_branch,
        {"primary": primary, "secondary": list(secondary), "available": True},
        pillars,
    )


# --------------------------------------------------------------------------- #
# Snapshot adapter
# --------------------------------------------------------------------------- #


def build_classical_overview(pillars: PillarMap) -> dict[str, Any]:
    """Bundle the three classical facts for the chart payload + snapshot."""
    day_stem = pillars["day"][0]
    month_branch = pillars["month"][1]
    return {
        "monthly_structure": determine_monthly_structure(pillars, day_stem),
        "seasonal_climate": seasonal_climate_god(day_stem, month_branch, pillars),
        "life_stages": life_stages_for_pillars(pillars),
        "root_profile": build_classical_root_profile(pillars),
    }
