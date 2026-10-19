"""Seasonal, rooted strength model; coefficients are explicit engineering policy.

Textual principles: 子平真诠 ch. 5–7, 滴天髓 地支论. No coefficient
is claimed to be a classical constant or a calibrated probability.
"""

from dataclasses import asdict, dataclass, replace
from itertools import combinations
from typing import Any, Dict, Optional, Tuple, TypedDict

from ..utils.data import (
    BRANCH_COMBINATION_ELEMENT,
    BRANCH_CONFLICTS,
    BRANCH_ELEMENTS,
    BRANCH_HIDDEN_STEMS,
    BRANCH_SEASONAL_COMBINATIONS,
    BRANCH_SELF_PUNISHMENTS,
    BRANCH_THREE_PUNISHMENTS,
    BRANCH_TRIPLE_COMBINATIONS,
    BUREAU_ELEMENT,
    DESTRUCTION_CYCLE,
    GENERATION_CYCLE,
    STEM_ELEMENTS,
    TRIPLE_COMBINATION_PEAK,
    Element,
)

POSITIONS = ("year", "month", "day", "hour")
# Descending geometric rank, normalized to one branch budget; no double 本气 count.
SHARES = {1: (1.0,), 2: (2 / 3, 1 / 3), 3: (4 / 7, 2 / 7, 1 / 7)}
PHASE_FACTORS = {"旺": 2.0, "相": 1.5, "休": 1.0, "囚": 0.75, "死": 0.5}
STEM_PAIRS = {
    frozenset(pair): Element(element)
    for pair, element in (
        ("甲己", "土"),
        ("乙庚", "金"),
        ("丙辛", "水"),
        ("丁壬", "木"),
        ("戊癸", "火"),
    )
}
SOURCES = [
    {
        "id": "ditian_zhonghe",
        "title": "滴天髓阐微·中和（财杀重而旺中变弱例）",
        "url": "https://www.shicihui.com/zh-tw/book/ditiansuichanwei/16288",
    },
    {
        "id": "ziping_6",
        "title": "子平真诠·论十干得时不旺失时不弱",
        "url": "https://www.donglishuzhai.net/chapter/3719.html",
    },
    {
        "id": "ziping_7",
        "title": "子平真诠·论刑冲会合解法",
        "url": "https://www.donglishuzhai.net/chapter/3720.html",
    },
    {
        "id": "ziping_5",
        "title": "子平真诠·论十干合而不合",
        "url": "https://www.donglishuzhai.net/chapter/3718.html",
    },
    {
        "id": "ditian_branch",
        "title": "滴天髓·地支论",
        "url": "https://zh.wikisource.org/zh-hant/滴天髓/03",
    },
]


class _Token(TypedDict):
    stem: Optional[str]
    element: Element
    mass: float
    revealed: bool
    origin: str


@dataclass(frozen=True)
class StrengthPolicy:
    """Frozen before reference-case evaluation; no per-chart overrides."""

    branch_budget: float = 2.0
    month_multiplier: float = 2.0
    seasonal_spread: float = 1.0
    floating_stem: float = 0.25
    rooted_stem: float = 1.0
    reveal_multiplier: float = 1.25
    strong_share: float = 0.60
    weak_share: float = 0.40
    clash_winner: float = 0.90
    clash_loser: float = 0.50
    clash_equal: float = 0.75
    punishment: float = 0.90
    binding: float = 0.85
    partial_transfer: float = 0.20
    transformation_transfer: float = 0.80


DEFAULT_POLICY = StrengthPolicy()


def _label(share: float, policy: StrengthPolicy) -> str:
    if share > policy.strong_share:
        return "强"
    if share < policy.weak_share:
        return "弱"
    return "中和"


def _evaluate(
    pillars: Dict[str, Tuple[str, str]], phases: Dict[str, str], policy: StrengthPolicy
) -> Dict[str, Any]:
    """Score physical positions once; interactions alter those same root budgets."""
    # Stable pillar order, independent of dictionary insertion order.
    names = [name for name in POSITIONS if name in pillars]
    branches = {name: pillars[name][1] for name in names}
    day_element = STEM_ELEMENTS[pillars["day"][0]][0]
    parent = next(e for e, child in GENERATION_CYCLE.items() if child == day_element)
    factors = {
        e: 1 + (PHASE_FACTORS[phases[e.value]] - 1) * policy.seasonal_spread
        for e in Element
    }
    visible = {stem for stem, _ in pillars.values()}
    # Each token has one identity; revelation activates but never duplicates a root.
    tokens: Dict[str, list[_Token]] = {
        name: [
            {
                "stem": stem,
                "element": STEM_ELEMENTS[stem][0],
                "mass": policy.branch_budget
                * share
                * (policy.month_multiplier if name == "month" else 1),
                "revealed": stem in visible,
                "origin": "hidden_stem",
            }
            for stem, share in zip(
                BRANCH_HIDDEN_STEMS[branch], SHARES[len(BRANCH_HIDDEN_STEMS[branch])]
            )
        ]
        for name, branch in branches.items()
    }
    events: list[Dict[str, Any]] = []
    clashed: set[str] = set()
    claimed: set[str] = set()
    # Combination candidates are based on actual position sets, not just branch labels.
    candidates: list[Tuple[str, Tuple[str, ...], Element]] = []
    for kind, groups in (
        ("三会", BRANCH_SEASONAL_COMBINATIONS),
        ("三合", BRANCH_TRIPLE_COMBINATIONS),
    ):
        for group, bureau in groups.items():
            for group_names in combinations(names, 3):
                if {branches[name] for name in group_names} == set(group):
                    candidates.append((kind, group_names, BUREAU_ELEMENT[bureau]))
    for pair in combinations(names, 2):
        target = BRANCH_COMBINATION_ELEMENT.get(frozenset(branches[n] for n in pair))
        if target is not None and abs(names.index(pair[0]) - names.index(pair[1])) == 1:
            candidates.append(("六合", pair, target))
    # A 六合 contained in a full bureau is not a competing claim or a second bonus.
    full_members = [set(c[1]) for c in candidates if len(c[1]) == 3]
    candidates = [
        c
        for c in candidates
        if len(c[1]) == 3 or not any(set(c[1]) <= full for full in full_members)
    ]
    # A unique adjacent 六合 or complete 三合 may resolve an external clash. If both
    # ends have incompatible claims, keep the clash and mark all those claims uncertain.
    memberships = {name: [c for c in candidates if name in c[1]] for name in names}
    protected: set[str] = set()
    for kind, members, target in candidates:
        incompatible = any(
            any(set(other[1]) != set(members) for other in memberships[n])
            for n in members
        )
        if not incompatible:
            protected.update(members)
    for left, right in combinations(names, 2):
        if BRANCH_CONFLICTS[branches[left]] != branches[right]:
            continue
        resolved = (left in protected) != (right in protected)
        if resolved:
            events.append(
                {
                    "kind": "六冲",
                    "positions": [left, right],
                    "status": "resolved_by_combination",
                    "source_id": "ziping_7",
                }
            )
            continue
        # Both exposed to incompatible relations: no arbitrary choice of a winning 合.
        clashed.update((left, right))
        e1, e2 = BRANCH_ELEMENTS[branches[left]][0], BRANCH_ELEMENTS[branches[right]][0]
        # Remaining root resources include the month budget. Seasonal factors are
        # applied in the final ledger, not a second time to decide who survives.
        powers = []
        for element in (e1, e2):
            powers.append(
                sum(
                    t["mass"]
                    for ts in tokens.values()
                    for t in ts
                    if t["element"] == element
                )
            )
        if e1 == e2 or abs(powers[0] - powers[1]) < 1e-9:
            multipliers = (policy.clash_equal, policy.clash_equal)
        else:
            multipliers = (
                (policy.clash_winner, policy.clash_loser)
                if powers[0] > powers[1]
                else (policy.clash_loser, policy.clash_winner)
            )
        # Non-stacking across repeat clashes: retain the strongest damage per position.
        events.append(
            {
                "kind": "六冲",
                "positions": [left, right],
                "status": "active",
                "root_multipliers": dict(zip((left, right), multipliers)),
                "source_id": "ditian_branch",
            }
        )
    losses = {name: 1.0 for name in names}
    for event in events:
        for name, multiplier in event.get("root_multipliers", {}).items():
            losses[name] = min(losses[name], multiplier)
    for kind, members, target in candidates:
        overlapping = any(name in claimed for name in members)
        contested = any(
            any(set(other[1]) != set(members) for other in memberships[n])
            for n in members
        )
        if overlapping or contested or any(n in clashed for n in members):
            events.append(
                {
                    "kind": kind,
                    "positions": list(members),
                    "target": target.value,
                    "status": "contested_or_clashed",
                    "source_id": "ziping_7",
                }
            )
            continue
        claimed.update(members)
        season_supports = phases[target.value] == "旺"
        revealed = any(STEM_ELEMENTS[stem][0] == target for stem in visible)
        transformed = season_supports and revealed
        # Conservation of branch budget: no additive free energy, original residue retained.
        if transformed:
            for name in members:
                transferred = 0.0
                for token in tokens[name]:
                    if token["element"] != target:
                        part = token["mass"] * policy.transformation_transfer
                        token["mass"] -= part
                        transferred += part
                tokens[name].append(
                    {
                        "stem": None,
                        "element": target,
                        "mass": transferred,
                        "revealed": False,
                        "origin": "conditioned_transformation",
                    }
                )
        else:
            for name in members:
                losses[name] = min(losses[name], policy.binding)
        events.append(
            {
                "kind": kind,
                "positions": list(members),
                "target": target.value,
                "status": "conditioned_transformation" if transformed else "binding",
                "season_supports": season_supports,
                "target_revealed": revealed,
                "source_id": "ziping_7",
            }
        )
    # 半合 is 成势, never a full transformation. Shared peaks stay disputed,
    # rather than selecting one partner solely by iteration order.
    half_candidates: list[Tuple[Tuple[str, str], Element]] = []
    for group, bureau in BRANCH_TRIPLE_COMBINATIONS.items():
        peak = TRIPLE_COMBINATION_PEAK[group]
        for pair in combinations(names, 2):
            bs = {branches[n] for n in pair}
            if len(bs) != 2 or peak not in bs or not bs < set(group):
                continue
            if not any(n in claimed or n in clashed for n in pair):
                half_candidates.append((pair, BUREAU_ELEMENT[bureau]))
    for pair, target in half_candidates:
        if any(set(pair) & set(other) for other, _ in half_candidates if other != pair):
            events.append(
                {
                    "kind": "半合",
                    "positions": list(pair),
                    "target": target.value,
                    "status": "contested",
                    "source_id": "ziping_7",
                }
            )
            continue
        claimed.update(pair)
        for name in pair:
            amount = 0.0
            for token in tokens[name]:
                if token["element"] != target:
                    part = token["mass"] * policy.partial_transfer
                    token["mass"] -= part
                    amount += part
            tokens[name].append(
                {
                    "stem": None,
                    "element": target,
                    "mass": amount,
                    "revealed": False,
                    "origin": "partial_tendency",
                }
            )
        events.append(
            {
                "kind": "半合",
                "positions": list(pair),
                "target": target.value,
                "status": "partial_tendency",
                "source_id": "ziping_7",
            }
        )
    for punishment_group in BRANCH_THREE_PUNISHMENTS:
        punished = [n for n in names if branches[n] in punishment_group]
        if set(branches[n] for n in punished) != set(punishment_group):
            continue  # 寅巳/丑戌 two-branch fragments are not full 三刑 in this policy.
        if all(n in protected for n in punished):
            events.append(
                {
                    "kind": "刑",
                    "positions": punished,
                    "status": "resolved_by_combination",
                    "source_id": "ziping_7",
                }
            )
            continue
        for name in punished:
            losses[name] = min(losses[name], policy.punishment)
        events.append(
            {
                "kind": "刑",
                "positions": punished,
                "status": "active",
                "source_id": "ziping_7",
            }
        )
    for branch in sorted(BRANCH_SELF_PUNISHMENTS):
        punished = [n for n in names if branches[n] == branch]
        if len(punished) > 1:
            for name in punished:
                losses[name] = min(losses[name], policy.punishment)
            events.append(
                {
                    "kind": "自刑",
                    "positions": punished,
                    "status": "active",
                    "source_id": "ziping_7",
                }
            )
    for name in names:
        for token in tokens[name]:
            token["mass"] *= losses[name]
    effective = {e: 0.0 for e in Element}
    roots = []
    combination_contributions = []
    root_mass = {
        e: sum(t["mass"] for ts in tokens.values() for t in ts if t["element"] == e)
        for e in Element
    }
    for name in names:
        for token in tokens[name]:
            energy = (
                token["mass"]
                * factors[token["element"]]
                * (policy.reveal_multiplier if token["revealed"] else 1)
            )
            effective[token["element"]] += energy
            if token["stem"] is None and token["mass"]:
                combination_contributions.append(
                    {
                        "pillar": name,
                        "element": token["element"].value,
                        "origin": token["origin"],
                        "energy": round(energy, 6),
                    }
                )
            if (
                token["element"] == day_element
                and token["mass"]
                and token["stem"] is not None
            ):
                roots.append(
                    {
                        "pillar": name,
                        "branch": branches[name],
                        "stem": token["stem"],
                        "remaining_mass": round(token["mass"], 6),
                        "energy": round(energy, 6),
                    }
                )
    stems_evidence: list[Dict[str, Any]] = []
    # Day stem is the target, not an extra vote supporting itself.
    for name in names:
        stem = pillars[name][0]
        element = STEM_ELEMENTS[stem][0]
        if name == "day":
            continue
        activation = policy.floating_stem + (
            policy.rooted_stem - policy.floating_stem
        ) * min(1.0, root_mass[element])
        energy = activation * factors[element]
        effective[element] += energy
        stems_evidence.append(
            {
                "pillar": name,
                "stem": stem,
                "root_mass": round(root_mass[element], 6),
                "energy": round(energy, 6),
            }
        )
    # 天干合绊: adjacent, unique partners, no erasure of 日主 or inference of 化气格.
    stem_links = [
        (a, b)
        for a, b in zip(names, names[1:])
        if frozenset((pillars[a][0], pillars[b][0])) in STEM_PAIRS
    ]
    for a, b in stem_links:
        contested = (
            sum(a in pair for pair in stem_links) > 1
            or sum(b in pair for pair in stem_links) > 1
        )
        if contested or "day" in (a, b):
            events.append(
                {
                    "kind": "天干合",
                    "positions": [a, b],
                    "status": "day_master_or_contested_review",
                    "source_id": "ziping_5",
                }
            )
            continue
        for item in stems_evidence:
            if item["pillar"] in (a, b):
                element = STEM_ELEMENTS[item["stem"]][0]
                reduction = item["energy"] * (1 - policy.binding)
                effective[element] -= reduction
                item["energy"] = round(item["energy"] - reduction, 6)
        events.append(
            {
                "kind": "天干合",
                "positions": [a, b],
                "status": "binding",
                "source_id": "ziping_5",
            }
        )
    support = effective[day_element] + effective[parent]
    weaken = sum(effective[e] for e in Element if e not in {day_element, parent})
    share = support / (support + weaken) if support + weaken else 0.5
    vigorous_roots = [
        name
        for name in names
        if BRANCH_ELEMENTS[branches[name]][0] == day_element
        and tokens[name][0]["mass"]
        >= policy.branch_budget
        * (policy.month_multiplier if name == "month" else 1)
        * SHARES[len(BRANCH_HIDDEN_STEMS[branches[name]])][0]
        * policy.clash_equal
    ]
    numerical_label = _label(share, policy)
    structural_rule = (
        numerical_label == "中和"
        and share > 0.5
        and phases[day_element.value] == "旺"
        and "month" in vigorous_roots
        and len(vigorous_roots) >= 2
    )
    controller = next(
        e for e, controlled in DESTRUCTION_CYCLE.items() if controlled == day_element
    )
    wealth = DESTRUCTION_CYCLE[day_element]
    visible_others = [STEM_ELEMENTS[pillars[n][0]][0] for n in names if n != "day"]
    rooted_controllers = sum(
        e == controller and root_mass[e] >= 1 for e in visible_others
    )
    rooted_wealth = any(e == wealth and root_mass[e] >= 1 for e in visible_others)
    support_visible = sum(e in {day_element, parent} for e in visible_others)
    # 得令不能掩盖有根财生官杀连续透干；得地得势也不能被单一季相否定。
    wealth_officer_chain = (
        len(visible_others) == 3
        and rooted_controllers >= 2
        and rooted_wealth
        and support_visible == 0
        and len(vigorous_roots) <= 1
    )
    rooted_support_front = (
        len(vigorous_roots) >= 2 and len(visible_others) == 3 and support_visible == 3
    )
    if wealth_officer_chain:
        final_label, decision = (
            "弱",
            "rooted_wealth_officer_front_without_visible_support",
        )
    elif structural_rule:
        final_label, decision = "强", "in_command_multiple_vigorous_roots"
    elif rooted_support_front:
        final_label, decision = "强", "multiple_vigorous_roots_and_visible_support"
    else:
        final_label, decision = numerical_label, "weighted_balance"
    return {
        "structural_decision": {
            "rule": decision,
            "vigorous_roots": vigorous_roots,
            "numerical_label": numerical_label,
            "source_id": "ditian_zhonghe" if wealth_officer_chain else "ziping_6",
            "rooted_controller_stems": rooted_controllers,
            "rooted_wealth_visible": rooted_wealth,
            "support_visible_stems": support_visible,
        },
        "branch_budgets": {
            name: {
                "initial": policy.branch_budget
                * (policy.month_multiplier if name == "month" else 1),
                "remaining": sum(t["mass"] for t in tokens[name]),
            }
            for name in names
        },
        "support_strength": support,
        "weaken_strength": weaken,
        "support_share": share,
        "strength_level": final_label,
        "roots": roots,
        "combination_contributions": combination_contributions,
        "revealed_stems": stems_evidence,
        "relations": events,
        "effective_elements": {e.value: round(v, 6) for e, v in effective.items()},
    }


def assess_strength(
    pillars: Dict[str, Tuple[str, str]], phases: Dict[str, str]
) -> Dict[str, Any]:
    result = _evaluate(pillars, phases, DEFAULT_POLICY)
    # Independent, one-factor +/-15% sensitivity. Not fitting or selecting a winner.
    variants = []
    for field in (
        "branch_budget",
        "month_multiplier",
        "seasonal_spread",
        "reveal_multiplier",
    ):
        value = getattr(DEFAULT_POLICY, field)
        for scale in (0.85, 1.15):
            alternative = _evaluate(
                pillars, phases, replace(DEFAULT_POLICY, **{field: value * scale})
            )
            variants.append(
                {
                    "parameter": field,
                    "scale": scale,
                    "strength": alternative["strength_level"],
                    "support_share": round(alternative["support_share"], 6),
                }
            )
    labels = sorted({result["strength_level"], *(v["strength"] for v in variants)})
    special_review = result["support_share"] < 0.15 or result["support_share"] > 0.85
    result.update(
        {
            "method_id": "season_root_revelation_relations_v2",
            "status": "boundary_sensitive" if len(labels) > 1 else "rule_based",
            "parameters": asdict(DEFAULT_POLICY),
            "seasonal_factors": dict(PHASE_FACTORS),
            "seasonal_phases": dict(phases),
            "support_weaken_ratio": (
                result["support_strength"] / result["weaken_strength"]
                if result["weaken_strength"]
                else None
            ),
            "sensitivity": {"candidate_strengths": labels, "variants": variants},
            "requires_special_structure_review": special_review,
            "month_command": {
                "branch": pillars["month"][1],
                "phase": phases[STEM_ELEMENTS[pillars["day"][0]][0].value],
            },
            "sources": [dict(source) for source in SOURCES],
            "limitations": [
                "数值系数为公开工程参数，古籍只支持规则关系，不提供这些系数或现实预测效度。",
                "月令按月支季相处理，未细分节气后司令天数、湿燥土与寒暖调候。",
                "合化采用化神当令、透化神、无争合及未受冲的保守条件；不认证化气格。",
                "刑害有门派分歧；三刑取全组、子卯取成对，自刑轻减，六害不机械减根。",
                "旺衰极端或参数敏感时停止自动扶抑取用，另行核对从格及专旺。",
            ],
        }
    )
    return result
