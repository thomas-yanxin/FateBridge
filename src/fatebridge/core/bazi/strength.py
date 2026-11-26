"""Fast BaZi strength, active structure/formation adjudication, 调候, and useful elements."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from fractions import Fraction
from typing import Any, DefaultDict, Literal, Mapping

from fatebridge.core.bazi.calendar import (
    LU_SEATS,
    YANG_BLADE_SEATS,
    ChangshengSchool,
    twelve_life_stage,
)
from fatebridge.core.bazi.relations import (
    check_clash_patterns,
    check_harmony_patterns,
    classify_triple_members,
)
from fatebridge.utils.data import (
    BRANCH_CLASH_PAIRS,
    BRANCH_COMBINATION_ELEMENT,
    BRANCH_COMBINATIONS,
    BRANCH_CONFLICTS,
    BRANCH_ELEMENTS,
    BRANCH_HIDDEN_STEMS,
    BRANCH_SEASONAL_COMBINATIONS,
    BRANCH_TRIPLE_COMBINATIONS,
    BRANCH_TRIPLE_ELEMENTS,
    DESTRUCTION_CYCLE,
    GENERATION_CYCLE,
    STEM_COMBINATIONS,
    STEM_ELEMENTS,
    TRIPLE_COMBINATION_PEAK,
    Element,
    get_shishen,
    get_ten_god,
)

Pillars = Mapping[str, tuple[str, str]]
ORDER = ("year", "month", "day", "hour")

# --------------------------------------------------------------------------- #
# Seasonal climate table (《穷通宝鉴》/《造化元钥》)
# --------------------------------------------------------------------------- #

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
        "卯": ("甲", ("庚",)),
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
        "未": ("癸", ("甲", "丙")),
        "申": ("丙", ("甲", "癸")),
        "酉": ("丙", ("癸",)),
        "戌": ("甲", ("丙", "癸")),
        "亥": ("甲", ("丙",)),
        "子": ("丙", ("甲",)),
        "丑": ("丙", ("甲",)),
    },
    "己": {
        "寅": ("丙", ("甲", "癸")),
        "卯": ("甲", ("丙", "癸")),
        "辰": ("丙", ("甲", "癸")),
        "巳": ("癸", ("丙",)),
        "午": ("癸", ("丙",)),
        "未": ("癸", ("丙",)),
        "申": ("丙", ("癸",)),
        "酉": ("丙", ("癸",)),
        "戌": ("甲", ("丙", "癸")),
        "亥": ("丙", ("甲", "戊")),
        "子": ("丙", ("甲", "戊")),
        "丑": ("丙", ("甲",)),
    },
    "庚": {
        "寅": ("戊", ("甲", "壬", "丙", "丁")),
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
        "子": ("丙", ("壬", "戊", "甲")),
        "丑": ("丙", ("壬", "戊", "甲")),
    },
    "壬": {
        "寅": ("庚", ("丙", "戊")),
        "卯": ("戊", ("辛", "庚")),
        "辰": ("甲", ("庚",)),
        "巳": ("壬", ("辛", "庚", "癸")),
        "午": ("癸", ("庚", "辛")),
        "未": ("辛", ("甲",)),
        "申": ("戊", ("丁",)),
        "酉": ("甲", ()),  # fallback handled below
        "戌": ("甲", ("丙",)),
        "亥": ("戊", ("丙", "庚")),
        "子": ("戊", ("丙",)),
        "丑": ("丙", ("甲",)),
    },
    "癸": {
        "寅": ("辛", ("丙",)),
        "卯": ("庚", ("辛",)),
        "辰": ("丙", ("辛", "甲")),
        "巳": ("辛", ()),
        "午": ("庚", ("壬", "癸")),
        "未": ("庚", ("壬", "癸")),
        "申": ("丁", ()),
        "酉": ("辛", ("丙",)),
        "戌": ("辛", ("甲", "壬", "癸")),
        "亥": ("庚", ("辛", "戊", "丁")),
        "子": ("丙", ("辛",)),
        "丑": ("丙", ("辛",)),
    },
}
DIAOHOU_TABLE["壬"]["酉"] = ("甲", ("庚",))  # type: ignore[assignment]


def seasonal_climate_god(
    day_stem: str, month_branch: str, pillars: Pillars | None = None
) -> dict[str, Any]:
    """Lookup 调候用神 and observe whether climate stems appear in natal chart."""
    entry = DIAOHOU_TABLE.get(day_stem, {}).get(month_branch)
    if entry is None:
        return {"available": False, "primary": None, "secondary": [], "elements": []}
    primary, secondary = entry
    stems = [primary, *secondary]
    elements = list(dict.fromkeys(STEM_ELEMENTS[s][0].value for s in stems))
    observed: list[dict[str, Any]] = []
    if pillars is not None:
        for s in stems:
            visible = [p for p in ORDER if pillars[p][0] == s]
            hidden = [p for p in ORDER if s in BRANCH_HIDDEN_STEMS[pillars[p][1]]]
            observed.append(
                {
                    "stem": s,
                    "priority": "primary" if s == primary else "secondary",
                    "element": STEM_ELEMENTS[s][0].value,
                    "visible_in": visible,
                    "hidden_in": hidden,
                    "present": bool(visible or hidden),
                }
            )
    return {
        "available": True,
        "primary": primary,
        "secondary": list(secondary),
        "elements": elements,
        "primary_present": (
            any(o["priority"] == "primary" and o["present"] for o in observed)
            if pillars is not None
            else None
        ),
        "observations": observed,
    }


# --------------------------------------------------------------------------- #
# Quantitative & structural strength engine
# --------------------------------------------------------------------------- #

PHASE_FACTORS: dict[str, float] = {
    "旺": 1.40,
    "相": 1.20,
    "休": 0.90,
    "囚": 0.70,
    "死": 0.50,
}

STORAGE_EARTH = {"木": "未", "火": "戌", "金": "丑", "水": "辰"}
RESIDUAL_EARTH = {"木": "辰", "火": "未", "金": "戌", "水": "丑"}


@dataclass(frozen=True)
class StrengthPolicy:
    branch_budget: float = 1.0
    month_multiplier: float = 2.0
    seasonal_spread: float = 1.0
    reveal_multiplier: float = 1.0
    clash_decay: float = 0.35
    triple_bonus: float = 0.80
    half_bonus: float = 0.40


DEFAULT_POLICY = StrengthPolicy()

_SUPPORT_THRESH = Fraction(54, 100)
_WEAK_THRESH = Fraction(46, 100)


def seasonal_phases(month_branch: str) -> dict[str, str]:
    month_element = BRANCH_ELEMENTS[month_branch][0]
    phases: dict[str, str] = {}
    for element in Element:
        if element == month_element:
            phase = "旺"
        elif GENERATION_CYCLE[month_element] == element:
            phase = "相"
        elif GENERATION_CYCLE[element] == month_element:
            phase = "休"
        elif DESTRUCTION_CYCLE[month_element] == element:
            phase = "死"
        else:
            phase = "囚"
        phases[element.value] = phase
    return phases


def count_elements(pillars: Pillars) -> dict[Element, float]:
    counts: DefaultDict[Element, float] = defaultdict(float)
    for stem, branch in pillars.values():
        counts[STEM_ELEMENTS[stem][0]] += 1.0
        counts[BRANCH_ELEMENTS[branch][0]] += 1.0
        for h in BRANCH_HIDDEN_STEMS[branch]:
            counts[STEM_ELEMENTS[h][0]] += 0.5
    return dict(counts)


def convert_to_percentage(element_counts: dict[Element, float]) -> dict[str, float]:
    total = sum(element_counts.values())
    if total == 0:
        return {elem.value: 0.0 for elem in Element}
    percentages = {
        elem.value: round((count / total) * 100, 1)
        for elem, count in element_counts.items()
    }
    for elem in Element:
        percentages.setdefault(elem.value, 0.0)
    residual = round(100.0 - sum(percentages.values()), 1)
    if residual:
        max_key = max(percentages, key=lambda k: percentages[k])
        percentages[max_key] = round(percentages[max_key] + residual, 1)
    return percentages


def evaluate_strength_policy(
    pillars: Pillars,
    phases: Mapping[str, str],
    policy: StrengthPolicy = DEFAULT_POLICY,
) -> dict[str, Any]:
    """Fast, deterministic strength arithmetic."""
    day_stem = pillars["day"][0]
    day_elem = STEM_ELEMENTS[day_stem][0]
    seal_elem = next(e for e, child in GENERATION_CYCLE.items() if child == day_elem)
    support_elems = {day_elem, seal_elem}

    effective: dict[Element, float] = {e: 0.0 for e in Element}
    hidden_ledger: list[dict[str, Any]] = []
    clashed_branches: set[str] = set()
    branches = [pillars[p][1] for p in ORDER]
    for b1, b2 in BRANCH_CLASH_PAIRS:
        if b1 in branches and b2 in branches:
            clashed_branches.update((b1, b2))

    # Visible stems (non-day stems contribute; day stem is the target being weighed)
    for pos in ("year", "month", "hour"):
        stem = pillars[pos][0]
        elem = STEM_ELEMENTS[stem][0]
        factor = (
            1.0 + (PHASE_FACTORS[phases[elem.value]] - 1.0) * policy.seasonal_spread
        )
        effective[elem] += policy.reveal_multiplier * factor

    # Branch hidden stems with month weighting + clash attenuation
    for pos in ORDER:
        branch = pillars[pos][1]
        weight_base = policy.branch_budget * (
            policy.month_multiplier if pos == "month" else 1.0
        )
        if branch in clashed_branches:
            weight_base *= 1.0 - policy.clash_decay
        hidden = BRANCH_HIDDEN_STEMS[branch]
        shares = (
            (1.0,)
            if len(hidden) == 1
            else (0.7, 0.3) if len(hidden) == 2 else (0.6, 0.25, 0.15)
        )
        for rank, (h, share) in enumerate(zip(hidden, shares)):
            elem = STEM_ELEMENTS[h][0]
            factor = (
                1.0 + (PHASE_FACTORS[phases[elem.value]] - 1.0) * policy.seasonal_spread
            )
            mass = weight_base * share * factor
            effective[elem] += mass
            hidden_ledger.append(
                {
                    "pillar": pos,
                    "branch": branch,
                    "stem": h,
                    "hidden_rank": rank,
                    "element": elem.value,
                    "mass": round(mass, 6),
                }
            )

    # Branch triads / half-triads / seasonal meetings bonus
    branch_set = set(branches)
    for group, bureau_elem in BRANCH_TRIPLE_ELEMENTS.items():
        m = classify_triple_members("".join(group), branch_set)
        if m == "complete":
            effective[bureau_elem] += policy.triple_bonus
        elif m == "peak_pair":
            effective[bureau_elem] += policy.half_bonus
    for s_group, bureau in BRANCH_SEASONAL_COMBINATIONS.items():
        if set(s_group) <= branch_set:
            b_elem = next(e for e in Element if e.value == bureau[0])
            effective[b_elem] += policy.triple_bonus * 1.1

    support = sum(effective[e] for e in support_elems)
    weaken = sum(effective[e] for e in Element if e not in support_elems)
    total = support + weaken
    share = support / total if total > 0 else 0.5

    if share >= float(_SUPPORT_THRESH):
        numerical_label: Literal["强", "中和", "弱"] = "强"
    elif share <= float(_WEAK_THRESH):
        numerical_label = "弱"
    else:
        numerical_label = "中和"

    # Root checks for structural confirmation
    vigorous_roots = [
        pos
        for pos in ORDER
        if twelve_life_stage(day_stem, pillars[pos][1]) in {"长生", "临官", "帝旺"}
        and any(
            STEM_ELEMENTS[h][0] == day_elem
            for h in BRANCH_HIDDEN_STEMS[pillars[pos][1]]
        )
    ]
    month_phase = phases[day_elem.value]
    in_season = month_phase in {"旺", "相"}

    final_label = numerical_label
    decision_rule = "weighted_balance"
    if len(vigorous_roots) >= 2 and in_season and numerical_label == "中和":
        final_label = "强"
        decision_rule = "vigorous_roots_with_season"
    elif not vigorous_roots and not in_season and numerical_label == "中和":
        final_label = "弱"
        decision_rule = "rootless_out_of_season"

    return {
        "strength_level": final_label,
        "numerical_label": numerical_label,
        "decision_rule": decision_rule,
        "support_strength": round(support, 6),
        "weaken_strength": round(weaken, 6),
        "support_share": round(share, 6),
        "vigorous_roots": vigorous_roots,
        "in_season": in_season,
        "month_phase": month_phase,
        "effective_elements": {e.value: round(v, 6) for e, v in effective.items()},
        "effective_elements_unrounded": {e.value: v for e, v in effective.items()},
        "hidden_stem_ledger": hidden_ledger,
    }


# --------------------------------------------------------------------------- #
# Pattern / Structure & 成败救应 & 喜用神 Adjudication
# --------------------------------------------------------------------------- #

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

_ZHUAN_WANG_NAMES = {
    "木": ("zhuan_wang_qu_zhi", "曲直仁寿格(专旺木)"),
    "火": ("zhuan_wang_yan_shang", "炎上格(专旺火)"),
    "土": ("zhuan_wang_jia_se", "稼穑格(专旺土)"),
    "金": ("zhuan_wang_cong_ge", "从革格(专旺金)"),
    "水": ("zhuan_wang_run_xia", "润下格(专旺水)"),
}


def _element_by_role(day_elem: Element) -> dict[str, Element]:
    seal = next(e for e, c in GENERATION_CYCLE.items() if c == day_elem)
    officer = next(e for e, t in DESTRUCTION_CYCLE.items() if t == day_elem)
    return {
        "peer": day_elem,
        "seal": seal,
        "output": GENERATION_CYCLE[day_elem],
        "wealth": DESTRUCTION_CYCLE[day_elem],
        "officer": officer,
    }


def _adjudicate_special_structure(
    pillars: Pillars,
    strength_eval: dict[str, Any],
) -> dict[str, Any] | None:
    """Detect 化气格, 专旺格, 从格 (从财/从杀/从儿/从势), 两神成象."""
    day_stem = pillars["day"][0]
    day_elem = STEM_ELEMENTS[day_stem][0]
    roles = _element_by_role(day_elem)
    effective = strength_eval["effective_elements_unrounded"]
    total = sum(effective.values()) or 1.0
    shares = {e.value: effective[e.value] / total for e in Element}
    support_share = strength_eval["support_share"]
    month_branch = pillars["month"][1]
    month_elem = BRANCH_ELEMENTS[month_branch][0]

    # 1. 化气格: day stem combines with adjacent month or hour stem, month supports transformed element, day lacks strong root
    for adj in ("month", "hour"):
        other = pillars[adj][0]
        for a, b, target_elem_val in STEM_COMBINATIONS:
            if {day_stem, other} == {a, b}:
                target_elem = Element(target_elem_val)
                month_supports = (
                    month_elem == target_elem
                    or GENERATION_CYCLE[month_elem] == target_elem
                )
                jealous = (
                    sum(1 for p in ("year", "month", "hour") if pillars[p][0] == other)
                    > 1
                    or sum(
                        1
                        for p in ("year", "month", "day", "hour")
                        if pillars[p][0] == day_stem
                    )
                    > 1
                )
                day_roots = [
                    p
                    for p in ORDER
                    if any(
                        STEM_ELEMENTS[h][0] == day_elem
                        for h in BRANCH_HIDDEN_STEMS[pillars[p][1]]
                    )
                ]
                if (
                    month_supports
                    and not jealous
                    and len(day_roots) <= 1
                    and shares[target_elem_val] >= 0.38
                ):
                    return {
                        "key": f"hua_qi_{target_elem_val}",
                        "label": f"化气格({day_stem}{other}化{target_elem_val})",
                        "category": "化气格",
                        "formation_status": "formed",
                        "useful_elements": [
                            target_elem_val,
                            next(
                                e.value
                                for e, c in GENERATION_CYCLE.items()
                                if c == target_elem
                            ),
                        ],
                        "avoid_elements": [
                            next(
                                e.value
                                for e, t in DESTRUCTION_CYCLE.items()
                                if t == target_elem
                            )
                        ],
                        "reason": f"日干{day_stem}与{adj}干{other}五合化{target_elem_val}，月令相生且无争合破化。",
                    }

    # 2. 专旺格: support >= 0.78 and peer dominant without strong officer/wealth
    peer_elem = roles["peer"]
    if (
        support_share >= 0.78
        and shares[roles["officer"].value] < 0.12
        and shares[roles["wealth"].value] < 0.14
    ):
        key, label = _ZHUAN_WANG_NAMES[peer_elem.value]
        return {
            "key": key,
            "label": label,
            "category": "专旺格",
            "formation_status": "formed",
            "useful_elements": [
                peer_elem.value,
                roles["seal"].value,
                roles["output"].value,
            ],
            "avoid_elements": [roles["officer"].value, roles["wealth"].value],
            "reason": f"全局{peer_elem.value}气专旺（扶身占比{support_share:.1%}），官杀财星无力破局，顺其旺势。",
        }

    # 3. 从格: rootless or very weak day master (support_share <= 0.18, no vigorous roots)
    has_same_stem_root = any(
        day_stem in BRANCH_HIDDEN_STEMS[pillars[p][1]] for p in ORDER
    )
    if (
        support_share <= 0.18
        and not strength_eval["vigorous_roots"]
        and not has_same_stem_root
    ):
        outer_scores = {
            "output": shares[roles["output"].value],
            "wealth": shares[roles["wealth"].value],
            "officer": shares[roles["officer"].value],
        }
        top_role = max(outer_scores, key=lambda r: outer_scores[r])
        if outer_scores[top_role] >= 0.42:
            if top_role == "wealth":
                return {
                    "key": "cong_cai",
                    "label": "从财格",
                    "category": "从格",
                    "formation_status": "formed",
                    "useful_elements": [roles["wealth"].value, roles["output"].value],
                    "avoid_elements": [roles["peer"].value, roles["seal"].value],
                    "reason": f"日主{day_stem}失令无根，财星{roles['wealth'].value}独旺，弃命从财。",
                }
            if top_role == "officer":
                return {
                    "key": "cong_sha",
                    "label": "从杀格",
                    "category": "从格",
                    "formation_status": "formed",
                    "useful_elements": [roles["officer"].value, roles["wealth"].value],
                    "avoid_elements": [roles["peer"].value, roles["output"].value],
                    "reason": f"日主{day_stem}无根弱极，官杀{roles['officer'].value}独旺，弃命从杀。",
                }
            return {
                "key": "cong_er",
                "label": "从儿格",
                "category": "从格",
                "formation_status": "formed",
                "useful_elements": [roles["output"].value, roles["wealth"].value],
                "avoid_elements": [roles["seal"].value, roles["officer"].value],
                "reason": f"日主{day_stem}无根弱极，食伤{roles['output'].value}成势生财，论从儿格。",
            }
        return {
            "key": "cong_shi",
            "label": "从势格",
            "category": "从格",
            "formation_status": "formed",
            "useful_elements": [
                roles[r].value
                for r, _ in sorted(
                    outer_scores.items(), key=lambda item: item[1], reverse=True
                )[:2]
            ],
            "avoid_elements": [roles["peer"].value, roles["seal"].value],
            "reason": f"日主{day_stem}无根弱极，财官食伤多方并旺，论从势格。",
        }

    # 4. 两神成象: two elements together account for >= 85% and each >= 30%
    sorted_elems = sorted(shares.items(), key=lambda x: x[1], reverse=True)
    if sorted_elems[0][1] + sorted_elems[1][1] >= 0.85 and sorted_elems[1][1] >= 0.30:
        e1, e2 = Element(sorted_elems[0][0]), Element(sorted_elems[1][0])
        if GENERATION_CYCLE[e1] == e2 or GENERATION_CYCLE[e2] == e1:
            return {
                "key": "liang_shen_cheng_xiang",
                "label": f"两神成象({e1.value}{e2.value}相生)",
                "category": "两神成象",
                "formation_status": "formed",
                "useful_elements": [e1.value, e2.value],
                "avoid_elements": [e.value for e in Element if e not in {e1, e2}],
                "reason": f"命局{e1.value}、{e2.value}两气成象相生，宜顺两神流通。",
            }

    return None


def _adjudicate_month_pattern(
    pillars: Pillars,
    strength_eval: dict[str, Any],
) -> dict[str, Any]:
    """Adjudicate 正格 / 杂气透干取格 / 建禄格 / 月刃格 and 成败救应."""
    day_stem = pillars["day"][0]
    day_elem = STEM_ELEMENTS[day_stem][0]
    roles = _element_by_role(day_elem)
    month_branch = pillars["month"][1]
    hidden = BRANCH_HIDDEN_STEMS[month_branch]
    visible_stems = {pillars[p][0] for p in ("year", "month", "hour")}

    if month_branch == LU_SEATS[day_stem]:
        pattern_god = "比肩"
        pattern_stem = hidden[0]
        rule = "建禄取格"
    elif month_branch == YANG_BLADE_SEATS.get(day_stem):
        pattern_god = "劫财"
        pattern_stem = hidden[0]
        rule = "月刃取格"
    else:
        transparent = [
            s
            for s in hidden
            if s in visible_stems and get_shishen(day_stem, s) not in {"比肩", "劫财"}
        ]
        # 杂气 (辰戌丑未): prefer transparent hidden stem; if multiple, pick highest-rank non-peer; if none, pick 本气
        if transparent:
            pattern_stem = transparent[0]
            rule = "杂气透干取格" if month_branch in "辰戌丑未" else "月令透干取格"
        else:
            pattern_stem = hidden[0]
            rule = "杂气本气取格" if month_branch in "辰戌丑未" else "月令本气取格"
        pattern_god = get_shishen(day_stem, pattern_stem)
        if pattern_god in {"比肩", "劫财"} and len(hidden) > 1:
            # Fallback to secondary non-peer if 本气 is peer
            for s in hidden[1:]:
                g = get_shishen(day_stem, s)
                if g not in {"比肩", "劫财"}:
                    pattern_stem, pattern_god = s, g
                    break

    label = TEN_GOD_TO_STRUCTURE.get(pattern_god, f"{pattern_god}格")
    key_map = {
        "正官格": "zheng_guan",
        "七杀格": "qi_sha",
        "正财格": "zheng_cai",
        "偏财格": "pian_cai",
        "正印格": "zheng_yin",
        "偏印格": "pian_yin",
        "食神格": "shi_shen",
        "伤官格": "shang_guan",
        "建禄格": "jian_lu",
        "月刃格": "yue_ren",
    }
    key = key_map.get(label, "month_pattern")

    # 成败救应 check
    all_gods = {
        get_ten_god(day_stem, pillars[p][0]).value for p in ("year", "month", "hour")
    } | {
        get_ten_god(day_stem, h).value
        for p in ORDER
        for h in BRANCH_HIDDEN_STEMS[pillars[p][1]]
    }
    visible_gods = {
        get_ten_god(day_stem, pillars[p][0]).value for p in ("year", "month", "hour")
    }
    month_clashed = any(
        BRANCH_CONFLICTS[month_branch] == pillars[p][1] for p in ("year", "day", "hour")
    )

    obstructions: list[str] = []
    rescues: list[str] = []
    useful: list[str] = []
    avoid: list[str] = []

    if label == "正官格":
        if "伤官" in visible_gods:
            obstructions.append("伤官见官")
            if "正印" in visible_gods or "偏印" in visible_gods:
                rescues.append("印星制伤护官")
            if "正财" in visible_gods or "偏财" in visible_gods:
                rescues.append("财星化伤生官")
        if "七杀" in visible_gods:
            obstructions.append("官杀混杂")
        useful = [roles["wealth"].value, roles["seal"].value, roles["officer"].value]
        avoid = [roles["output"].value]
    elif label == "七杀格":
        if "食神" in all_gods:
            rescues.append("食神制杀")
            useful.append(roles["output"].value)
        if "正印" in all_gods or "偏印" in all_gods:
            rescues.append("杀印相生")
            useful.append(roles["seal"].value)
        if not rescues:
            obstructions.append("七杀无制化")
            useful = [roles["output"].value, roles["seal"].value]
        avoid = [roles["wealth"].value] if "七杀无制化" in obstructions else []
    elif label in {"正财格", "偏财格"}:
        if "比肩" in visible_gods or "劫财" in visible_gods:
            obstructions.append("比劫争财")
            if "正官" in visible_gods or "七杀" in visible_gods:
                rescues.append("官杀制劫护财")
            if "食神" in visible_gods or "伤官" in visible_gods:
                rescues.append("食伤化劫生财")
        useful = (
            [roles["output"].value, roles["wealth"].value]
            if strength_eval["strength_level"] == "强"
            else [roles["peer"].value, roles["seal"].value]
        )
        avoid = (
            [roles["peer"].value, roles["seal"].value]
            if strength_eval["strength_level"] == "强"
            else [roles["officer"].value, roles["output"].value]
        )
    elif label in {"正印格", "偏印格"}:
        if "正财" in visible_gods or "偏财" in visible_gods:
            obstructions.append("贪财坏印")
            if "比肩" in visible_gods or "劫财" in visible_gods:
                rescues.append("比劫分财护印")
            if "正官" in visible_gods or "七杀" in visible_gods:
                rescues.append("官杀通关生印")
        useful = (
            [roles["officer"].value, roles["seal"].value]
            if strength_eval["strength_level"] != "强"
            else [roles["wealth"].value, roles["output"].value]
        )
        avoid = (
            [roles["wealth"].value] if strength_eval["strength_level"] == "弱" else []
        )
    elif label == "食神格":
        if "偏印" in visible_gods:
            obstructions.append("枭神夺食")
            if "偏财" in visible_gods or "正财" in visible_gods:
                rescues.append("财星制枭护食")
        useful = (
            [roles["wealth"].value, roles["output"].value]
            if strength_eval["strength_level"] == "强"
            else [roles["peer"].value, roles["seal"].value]
        )
        avoid = [roles["seal"].value] if "枭神夺食" in obstructions else []
    elif label == "伤官格":
        if "正印" in all_gods or "偏印" in all_gods:
            rescues.append("伤官佩印")
            useful = [roles["seal"].value, roles["peer"].value]
        elif "正财" in all_gods or "偏财" in all_gods:
            rescues.append("伤官生财")
            useful = [roles["wealth"].value, roles["output"].value]
        else:
            useful = (
                [roles["wealth"].value, roles["seal"].value]
                if strength_eval["strength_level"] == "强"
                else [roles["seal"].value, roles["peer"].value]
            )
        avoid = [roles["officer"].value]
    elif label in {"建禄格", "月刃格"}:
        if label == "月刃格" and "七杀" in all_gods:
            rescues.append("羊刃驾杀")
            useful = [roles["officer"].value, roles["wealth"].value]
        elif "正官" in visible_gods:
            rescues.append("禄刃用官")
            useful = [roles["officer"].value, roles["wealth"].value]
        else:
            useful = [
                roles["output"].value,
                roles["wealth"].value,
                roles["officer"].value,
            ]
        avoid = [roles["peer"].value, roles["seal"].value]

    if month_clashed:
        obstructions.append("月令受冲")

    if not obstructions:
        formation_status = "formed"
    elif rescues:
        formation_status = "broken_with_rescue"
    else:
        formation_status = "broken"

    return {
        "key": key,
        "label": label,
        "category": "月刃建禄" if label in {"建禄格", "月刃格"} else "正格",
        "selection_rule": rule,
        "month_stem": pattern_stem,
        "month_ten_god": pattern_god,
        "formation_status": formation_status,
        "obstructions": obstructions,
        "rescues": rescues,
        "useful_elements": list(dict.fromkeys(useful)),
        "avoid_elements": list(dict.fromkeys(avoid)),
        "reason": (
            f"月支{month_branch}依{rule}取{label}（{pattern_stem}/{pattern_god}），"
            + (
                "；".join(rescues)
                if rescues
                else (
                    "无明显破格" if not obstructions else "见" + "、".join(obstructions)
                )
            )
        ),
    }


def _fuyi_elements(day_elem: Element, strength: str) -> tuple[list[str], list[str]]:
    roles = _element_by_role(day_elem)
    if strength == "强":
        return (
            [roles["output"].value, roles["wealth"].value, roles["officer"].value],
            [roles["peer"].value, roles["seal"].value],
        )
    if strength == "弱":
        return (
            [roles["peer"].value, roles["seal"].value],
            [roles["output"].value, roles["wealth"].value, roles["officer"].value],
        )
    return (
        [roles["output"].value, roles["wealth"].value],
        [],
    )


def analyze_elements_and_structure(
    pillars: Pillars,
    *,
    changsheng_school: ChangshengSchool = "fire_earth_same_palace",
) -> dict[str, Any]:
    """Unified, single-pass BaZi element distribution, strength, 格局, 调候, and 喜用神."""
    day_stem = pillars["day"][0]
    day_elem, day_polarity = STEM_ELEMENTS[day_stem]
    month_branch = pillars["month"][1]

    raw_counts = count_elements(pillars)
    percentages = convert_to_percentage(raw_counts)
    phases = seasonal_phases(month_branch)
    strength_eval = evaluate_strength_policy(pillars, phases, DEFAULT_POLICY)

    # Active classical & structural adjudication
    special = _adjudicate_special_structure(pillars, strength_eval)
    month_pattern = _adjudicate_month_pattern(pillars, strength_eval)
    dominant = special if special is not None else month_pattern
    ordinary_applicable = special is None

    if special is not None:
        useful = list(special["useful_elements"])
        avoid = list(special["avoid_elements"])
        if special["category"] == "专旺格":
            body_strength: Literal["强", "中和", "弱"] = "强"
        elif special["category"] == "从格":
            body_strength = "弱"
        else:
            body_strength = strength_eval["strength_level"]
    else:
        body_strength = strength_eval["strength_level"]
        useful, avoid = _fuyi_elements(day_elem, body_strength)

    # 调候 (Seasonal climate)
    climate = seasonal_climate_god(day_stem, month_branch, pillars)
    if climate["available"] and not climate["primary_present"]:
        for ce in climate["elements"][:1]:
            if ce not in useful and ce not in avoid:
                useful.append(ce)
            elif ce in avoid and body_strength == "中和":
                useful.append(ce)
                avoid.remove(ce)

    useful = list(dict.fromkeys(useful))
    avoid = [e for e in dict.fromkeys(avoid) if e not in useful]
    neutral = [
        e.value for e in Element if e.value not in useful and e.value not in avoid
    ]

    # Ten gods
    ten_gods: dict[str, list[dict[str, str]]] = {}
    for pos, (p_stem, p_branch) in pillars.items():
        rows: list[dict[str, str]] = []
        if pos != "day":
            rows.append(
                {
                    "position": f"{pos}_stem",
                    "character": p_stem,
                    "ten_god": get_ten_god(day_stem, p_stem).value,
                }
            )
        for idx, h in enumerate(BRANCH_HIDDEN_STEMS[p_branch]):
            rows.append(
                {
                    "position": f"{pos}_branch_hidden_{idx + 1}",
                    "character": h,
                    "ten_god": get_ten_god(day_stem, h).value,
                }
            )
        ten_gods[pos] = rows

    useful_ten_gods = list(
        dict.fromkeys(
            get_ten_god(day_stem, s).value
            for s in "甲乙丙丁戊己庚辛壬癸"
            if STEM_ELEMENTS[s][0].value in useful
        )
    )

    harmony_patterns = check_harmony_patterns(pillars)
    clash_patterns = check_clash_patterns(pillars)

    # Secondary candidates (e.g. 羊刃驾杀 / 食神制杀 / 伤官佩印 / 杀印相生 / 月令正格 if special overrode)
    recognized: list[dict[str, Any]] = []
    if special is not None:
        recognized.append(month_pattern)
    for label, key in (
        ("羊刃驾杀", "yang_ren_jia_sha"),
        ("杀印相生", "sha_yin_xiang_sheng"),
        ("食神制杀", "shi_shen_zhi_sha"),
        ("伤官配印", "shang_guan_pei_yin"),
    ):
        if label in month_pattern.get("rescues", []):
            recognized.append(
                {"key": key, "label": label, "formation_status": "formed"}
            )

    classical_adjudication = {
        "status": "adjudicated",
        "body_strength": body_strength,
        "ordinary_fuyi_applicable": ordinary_applicable,
        "dominant_pattern": dominant["label"],
        "formation_status": dominant["formation_status"],
    }

    life_stages = {
        pos: twelve_life_stage(day_stem, pillars[pos][1], school=changsheng_school)
        for pos in ORDER
    }

    day_master = {
        "stem": day_stem,
        "element": day_elem.value,
        "polarity": day_polarity.value,
        "strength": body_strength,
        "support_share": strength_eval["support_share"],
        "life_stages": life_stages,
        "changsheng_school": changsheng_school,
        "classical_adjudication": classical_adjudication,
        "engineering_index": {
            "strength_level": strength_eval["strength_level"],
            "numerical_strength_level": strength_eval["numerical_label"],
            "support_share": strength_eval["support_share"],
        },
    }

    structure_profile = {
        "assessment_status": "adjudicated",
        "dominant_structure": dominant,
        "recognized_structures": recognized,
        "useful_elements": useful,
        "avoid_elements": avoid,
        "neutral_elements": neutral,
        "useful_ten_gods": useful_ten_gods,
        "seasonal_climate": climate,
        "classical_adjudication": classical_adjudication,
        "harmony_patterns": harmony_patterns,
        "clash_patterns": clash_patterns,
    }

    return {
        "day_master": day_master,
        "ten_gods": ten_gods,
        "element_distribution": percentages,
        "element_distribution_raw": {e.value: raw_counts.get(e, 0.0) for e in Element},
        "element_seasonal_phase": phases,
        "favorable_elements": useful,
        "favorable_elements_status": "adjudicated",
        "avoid_elements": avoid,
        "structure_profile": structure_profile,
        "strength_eval": strength_eval,
        "harmony_patterns": harmony_patterns,
        "clash_patterns": clash_patterns,
    }


def build_sensitivity_report(pillars: Pillars) -> dict[str, Any]:
    """Optional parameter sensitivity check (only computed when requested for audit)."""
    phases = seasonal_phases(pillars["month"][1])
    base = evaluate_strength_policy(pillars, phases, DEFAULT_POLICY)
    variants = []
    for field in (
        "branch_budget",
        "month_multiplier",
        "seasonal_spread",
        "reveal_multiplier",
    ):
        val = getattr(DEFAULT_POLICY, field)
        for scale in (0.85, 1.15):
            alt = evaluate_strength_policy(
                pillars, phases, replace(DEFAULT_POLICY, **{field: val * scale})
            )
            variants.append(
                {
                    "parameter": field,
                    "scale": scale,
                    "strength": alt["strength_level"],
                    "support_share": alt["support_share"],
                }
            )
    labels = sorted({base["strength_level"], *(v["strength"] for v in variants)})
    return {
        "parameters": asdict(DEFAULT_POLICY),
        "status": "boundary_sensitive" if len(labels) > 1 else "stable",
        "candidate_strengths": labels,
        "variants": variants,
    }
