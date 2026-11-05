"""Seasonal, rooted strength model; coefficients are explicit engineering policy.

Textual principles: 子平真诠 ch. 5–7, 滴天髓 地支论. No coefficient
is claimed to be a classical constant or a calibrated probability.
"""

from dataclasses import asdict, dataclass, replace
from itertools import combinations
from typing import Any, Dict, Optional, Tuple, TypedDict

from fatebridge.core.clash_comparison import build_clash_comparison
from fatebridge.core.classical_roots import SOURCE as ROOT_SOURCE
from fatebridge.core.classical_roots import classify_classical_root
from fatebridge.core.complete_bureaus import MEMBERSHIP_POLICY
from fatebridge.core.complete_bureaus import SOURCE as COMPLETE_BUREAU_SOURCE
from fatebridge.core.formation_affiliations import SOURCE as AFFILIATION_SOURCE
from fatebridge.core.formation_affiliations import partition_affiliations
from fatebridge.core.punishment_resolution import POLICY as PUNISHMENT_POLICY
from fatebridge.core.punishment_resolution import SINGLE_PAIR_SOURCE
from fatebridge.core.punishment_resolution import SOURCE as PUNISHMENT_SOURCE
from fatebridge.core.punishment_resolution import (
    completed_combination_positions,
    punishment_is_resolved,
)
from fatebridge.core.stem_effects import evaluate_stem_effects
from fatebridge.core.stem_order_review import build_stem_order_review
from fatebridge.core.storage_movement import SOURCE as STORAGE_SOURCE
from fatebridge.core.storage_movement import storage_movement_effect
from fatebridge.core.strength_thresholds import exact_threshold_decision

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
STRENGTH_METHOD_ID = "season_root_revelation_relations_v12"
STRUCTURAL_PRIORITY_METHOD_ID = "source_root_capacity_priority_v3"
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
SOURCES: list[dict[str, Any]] = [
    {
        "id": "ditian_ordered_four_branch_passage_v1",
        "title": "任注滴天髓闡微·通關（1947年李雨田校訂本PDF199）",
        "url": "https://upload.wikimedia.org/wikipedia/commons/d/db/SSID-11335994_%E6%BB%B4%E5%A4%A9%E9%AB%93%E9%97%A1%E5%BE%AE.pdf",
        "source_sha256": "d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803",
        "pdf_pages": [199],
        "scope": "仅在四支依次财生官杀、官杀生印、印生身，天干年杀月印、时比劫归禄旺且无竞争会合时采用。不得推广到任意见印、隔支或残缺通关。",
    },
    {
        "id": "ditian_rooted_body_before_season_proxy_v1",
        "title": "任注滴天髓闡微·官殺、地支、月令的重根与印比条件",
        "url": "https://upload.wikimedia.org/wikipedia/commons/d/db/SSID-11335994_%E6%BB%B4%E5%A4%A9%E9%AB%93%E9%97%A1%E5%BE%AE.pdf",
        "source_sha256": "d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803",
        "pdf_pages": [91, 172, 173, 203, 205],
        "scope": "多处合格实际根配合有根印比，以及两处本气强根，不再要求三干全部印比；资格仍沿用既有未舍入根预算和保留门槛。不是有根即强或全书定理。",
    },
    {
        "id": "ditian_winter_rootless_wood_v1",
        "title": "任注滴天髓闡微·假化（1947年李雨田校訂本PDF386）",
        "url": "https://upload.wikimedia.org/wikipedia/commons/d/db/SSID-11335994_%E6%BB%B4%E5%A4%A9%E9%AB%93%E9%97%A1%E5%BE%AE.pdf",
        "source_sha256": "d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803",
        "pdf_pages": [386],
        "scope": "冬水当令而木无任何实际同五行藏根时，不将旺印相加为日主强。此有限规则不裁定化气格或从格。",
    },
    {
        "id": "sanming_seasonal_phases",
        "title": "三命通會·論五行旺相休囚死並寄生十二宫",
        "url": "https://www.shidianguji.com/zh/book/SK1610/chapter/1kf5v6ol1tqg5",
        "scope": "季相名称的生克对应：克当令者囚、当令所克者死；数值系数仍是工程约定。电子转录不等同书影校勘。",
    },
    {
        "id": "ditian_complete_same_element_bureau_capacity_v1",
        "title": "任注滴天髓闡微·眾寡（1947年李雨田校訂本PDF268）",
        "url": "https://upload.wikimedia.org/wikipedia/commons/d/db/SSID-11335994_%E6%BB%B4%E5%A4%A9%E9%AB%93%E9%97%A1%E5%BE%AE.pdf",
        "edition": "上海大東書局，1947年4月初版",
        "pdf_pages": [268],
        "scope": "完整同類會局及合格重根的結構規則；條件是工程編碼，不是完全成化或全書定理。",
    },
    dict(COMPLETE_BUREAU_SOURCE),
    dict(AFFILIATION_SOURCE),
    dict(PUNISHMENT_SOURCE),
    dict(SINGLE_PAIR_SOURCE),
    dict(STORAGE_SOURCE),
    dict(ROOT_SOURCE),
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


class _QualifiedRoot(TypedDict):
    pillar: str
    branch: str
    kind: str
    matching_hidden_stems: list[str]
    source_weight_class: str
    qualification_basis: str
    initial_hidden_mass: float
    remaining_hidden_mass: float
    retention_fraction: Optional[float]
    minimum_retention_policy: float
    qualified_for_structural_rule: bool
    source_ref: str
    scope: str


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
    pillars: Dict[str, Tuple[str, str]],
    phases: Dict[str, str],
    policy: StrengthPolicy,
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
    initial_day_root_mass = {
        name: sum(t["mass"] for t in tokens[name] if t["element"] == day_element)
        for name in names
    }
    initial_hidden_mass = {
        (name, t["stem"]): t["mass"] for name in names for t in tokens[name]
    }
    events: list[Dict[str, Any]] = []
    element_losses = {name: {e: 1.0 for e in Element} for name in names}

    def apply_storage_effect(effect: Dict[str, Any]) -> None:
        for root in effect["root_effects"]:
            name, element = root["pillar"], Element(root["element"])
            element_losses[name][element] = min(
                element_losses[name][element], root["event_retention_multiplier"]
            )

    clashed: set[str] = set()
    claimed: set[str] = set()
    # Combination candidates are based on actual position sets, not just branch labels.
    candidates: list[Tuple[str, Tuple[str, ...], Element]] = []
    for kind, groups in (
        ("三会", BRANCH_SEASONAL_COMBINATIONS),
        ("三合", BRANCH_TRIPLE_COMBINATIONS),
    ):
        for group, bureau in groups.items():
            # Repeated members of the SAME complete bureau are one formation,
            # not competing choices of physical triples. Consume every actual
            # position once, including duplicate 旺支; never invent a fifth token.
            members = tuple(name for name in names if branches[name] in group)
            if {branches[name] for name in members} == set(group):
                candidates.append((kind, members, BUREAU_ELEMENT[bureau]))
    for pair in combinations(names, 2):
        target = BRANCH_COMBINATION_ELEMENT.get(frozenset(branches[n] for n in pair))
        if target is not None and abs(names.index(pair[0]) - names.index(pair[1])) == 1:
            candidates.append(("六合", pair, target))
    # A 六合 contained in a full bureau is not a competing claim or a second bonus.
    full_members = [set(c[1]) for c in candidates if len(c[1]) >= 3]
    candidates = [
        c
        for c in candidates
        if len(c[1]) >= 3 or not any(set(c[1]) <= full for full in full_members)
    ]
    candidates, affiliations = partition_affiliations(candidates, branches)
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
    # Prespecified source profile: whole four-column wealth -> officer ->
    # seal -> body branch path, matching visible officer -> seal -> body,
    # with time LU/prosperity and no competing complete/paired formation.
    branch_elements = [BRANCH_ELEMENTS[branches[n]][0] for n in names]
    ordered_passage = (
        names == list(POSITIONS)
        and not candidates
        and all(
            GENERATION_CYCLE[a] == b
            for a, b in zip(branch_elements, branch_elements[1:])
        )
        and branch_elements[2] == parent
        and branch_elements[3] == day_element
        and STEM_ELEMENTS[pillars["year"][0]][0]
        == next(
            e
            for e, controlled in DESTRUCTION_CYCLE.items()
            if controlled == day_element
        )
        and STEM_ELEMENTS[pillars["month"][0]][0] == parent
        and STEM_ELEMENTS[pillars["hour"][0]][0] == day_element
        and classify_classical_root(pillars["day"][0], branches["hour"])["kind"]
        in {"lu_root", "yang_blade_root", "prosperity_root"}
    )
    for left, right in combinations(names, 2):
        if BRANCH_CONFLICTS[branches[left]] != branches[right]:
            continue
        if ordered_passage and names.index(right) - names.index(left) >= 2:
            events.append(
                {
                    "kind": "六冲",
                    "positions": [left, right],
                    "status": "resolved_by_ordered_generation_path",
                    "source_id": "ditian_ordered_four_branch_passage_v1",
                    "intermediary_positions": names[
                        names.index(left) + 1 : names.index(right)
                    ],
                }
            )
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
        storage = storage_movement_effect(
            branches, (left, right), "六冲", pillars["day"][0], policy.clash_equal
        )
        if storage is not None:
            apply_storage_effect(storage)
            events.append(
                {
                    "kind": "六冲",
                    "positions": [left, right],
                    "status": "active",
                    "clash_mode": "storage_earth_movement",
                    "storage_effect": storage,
                    "source_id": STORAGE_SOURCE["id"],
                }
            )
            continue
        e1, e2 = BRANCH_ELEMENTS[branches[left]][0], BRANCH_ELEMENTS[branches[right]][0]
        # Compare initial physical hidden budgets, before interaction losses.
        # The month multiplier is included; seasonal energy and stem activation
        # are applied later and do not participate in this adopted proxy.
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
                "power_comparison": {
                    "powers": [
                        {
                            "element": element.value,
                            "raw_budget": power,
                            "contributors": [
                                {
                                    "pillar": name,
                                    "branch": branches[name],
                                    "stem": t["stem"],
                                    "initial_budget": t["mass"],
                                }
                                for name in names
                                for t in tokens[name]
                                if t["element"] == element
                            ],
                        }
                        for element, power in zip((e1, e2), powers)
                    ]
                },
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
                **(
                    {
                        "membership_policy": MEMBERSHIP_POLICY,
                        "membership_source_id": COMPLETE_BUREAU_SOURCE["id"],
                    }
                    if len(members) > 3
                    else {}
                ),
            }
        )
    # Affiliated outside pairs neither claim seats nor alter their root budgets.
    events.extend(affiliations)
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
    # Initial candidate protection is needed to decide clashes above. By this
    # later stage candidates may have failed; only completed combinations can
    # then resolve a punishment. Half tendencies do not expand that criterion.
    punishment_cover = completed_combination_positions(events)
    for punishment_group in BRANCH_THREE_PUNISHMENTS:
        punished = [n for n in names if branches[n] in punishment_group]
        if set(branches[n] for n in punished) != set(punishment_group):
            continue  # 寅巳/丑戌 two-branch fragments are not full 三刑 in this policy.
        if punishment_is_resolved(punished, branches, punishment_cover):
            events.append(
                {
                    "kind": "刑",
                    "positions": punished,
                    "status": "resolved_by_combination",
                    "source_id": "ziping_7",
                }
            )
            continue
        storage = storage_movement_effect(
            branches, punished, "刑", pillars["day"][0], policy.punishment
        )
        if storage is None:
            for name in punished:
                losses[name] = min(losses[name], policy.punishment)
        else:
            apply_storage_effect(storage)
        events.append(
            {
                "kind": "刑",
                "positions": punished,
                "status": "active",
                "source_id": (
                    STORAGE_SOURCE["id"] if storage is not None else "ziping_7"
                ),
                **({"storage_effect": storage} if storage is not None else {}),
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
            token["mass"] *= min(losses[name], element_losses[name][token["element"]])
    # Expose the actual combined loss and remaining physical token, so a
    # per-event soil exemption cannot be read as immunity to other relations.
    for event in events:
        for root in event.get("storage_effect", {}).get("root_effects", []):
            name, element = root["pillar"], Element(root["element"])
            root["combined_loss_multiplier"] = min(
                losses[name], element_losses[name][element]
            )
            root["remaining_hidden_mass"] = round(
                sum(t["mass"] for t in tokens[name] if t["stem"] == root["stem"]), 6
            )
    effective = {e: 0.0 for e in Element}
    roots = []
    hidden_stem_ledger = []
    combination_contributions = []
    root_mass = {
        e: sum(
            t["mass"]
            for ts in tokens.values()
            for t in ts
            if t["element"] == e and t["stem"] is not None
        )
        for e in Element
    }
    non_root_mass = {
        e: sum(
            t["mass"]
            for ts in tokens.values()
            for t in ts
            if t["element"] == e and t["stem"] is None
        )
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
            if token["stem"] is not None:
                initial = initial_hidden_mass[(name, token["stem"])]
                hidden_stem_ledger.append(
                    {
                        "pillar": name,
                        "branch": branches[name],
                        "stem": token["stem"],
                        "element": token["element"].value,
                        "initial_mass": initial,
                        "remaining_mass": token["mass"],
                        "retention_fraction": (
                            token["mass"] / initial if initial else None
                        ),
                        "combined_relation_loss_factor": min(
                            losses[name], element_losses[name][token["element"]]
                        ),
                        "engineering_energy": energy,
                        "quantity_kind": "post_interaction_hidden_stem_budget",
                    }
                )
            if token["stem"] is None and token["mass"]:
                combination_contributions.append(
                    {
                        "pillar": name,
                        "element": token["element"].value,
                        "origin": token["origin"],
                        "mass": token["mass"],
                        "energy": round(energy, 6),
                        "energy_unrounded": energy,
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
    stem_effects = evaluate_stem_effects(
        pillars,
        factors,
        hidden_stem_ledger,
        non_root_mass,
        floating_stem=policy.floating_stem,
        rooted_stem=policy.rooted_stem,
        binding=policy.binding,
    )
    stems_evidence = stem_effects["revealed_stems"]
    events.extend(
        {
            "kind": event["kind"],
            "positions": event["positions"],
            "status": event["status"],
            "source_id": "ziping_5",
        }
        for event in stem_effects["relations"]
    )
    for element in Element:
        effective[element] += stem_effects["energies"][element.value]
    support = effective[day_element] + effective[parent]
    weaken = sum(effective[e] for e in Element if e not in {day_element, parent})
    share = support / (support + weaken) if support + weaken else 0.5
    root_qualifications: list[_QualifiedRoot] = []
    for name in names:
        classification = classify_classical_root(pillars["day"][0], branches[name])
        initial = initial_day_root_mass[name]
        # Synthetic transformation/tendency tokens are not hidden-stem roots.
        remaining = sum(
            t["mass"]
            for t in tokens[name]
            if t["stem"] is not None and t["element"] == day_element
        )
        principal = BRANCH_ELEMENTS[branches[name]][0] == day_element
        heavy = classification["source_weight_class"] == "heavy"
        eligible_kind = principal or heavy
        qualified = (
            eligible_kind and initial > 0 and remaining >= initial * policy.clash_equal
        )
        root_qualifications.append(
            {
                "pillar": name,
                "branch": branches[name],
                "kind": classification["kind"],
                "matching_hidden_stems": classification["matching_hidden_stems"],
                "source_weight_class": classification["source_weight_class"],
                "qualification_basis": (
                    "source_heavy_root"
                    if heavy
                    else "principal_element_root" if principal else "not_anchored_kind"
                ),
                "initial_hidden_mass": initial,
                "remaining_hidden_mass": remaining,
                "retention_fraction": remaining / initial if initial else None,
                "minimum_retention_policy": policy.clash_equal,
                "qualified_for_structural_rule": qualified,
                "source_ref": ROOT_SOURCE["id"],
                "scope": "本气与所选原典重根类型分别核对；实际藏干根保留比例达到工程门槛才计入结构规则。不是独立原典强弱裁定。",
            }
        )
    vigorous_roots = [
        r["pillar"] for r in root_qualifications if r["qualified_for_structural_rule"]
    ]
    float_numerical_label = _label(share, policy)
    threshold_arithmetic = exact_threshold_decision(
        pillars, phases, PHASE_FACTORS, asdict(policy), events, float_numerical_label
    )
    numerical_label = threshold_arithmetic["numerical_label"]
    # The independently evaluated root rule is not gated by the weighted
    # proxy that it can override. Its roots, season and load guard remain
    # explicit; no coefficient is fitted to a reference chart.
    structural_rule = (
        phases[day_element.value] == "旺"
        and "month" in vigorous_roots
        and len(vigorous_roots) >= 2
    )
    controller = next(
        e for e, controlled in DESTRUCTION_CYCLE.items() if controlled == day_element
    )
    wealth = DESTRUCTION_CYCLE[day_element]
    visible_others = (
        [Element(r["effective_element"]) for r in stem_effects["ledger"]]
        if stem_effects is not None
        else [STEM_ELEMENTS[pillars[n][0]][0] for n in names if n != "day"]
    )
    rooted_controllers = sum(
        e == controller and root_mass[e] >= 1 for e in visible_others
    )
    rooted_wealth = any(e == wealth and root_mass[e] >= 1 for e in visible_others)
    root_comparison = threshold_arithmetic["physical_root_unit_comparison"]
    unit_flags = root_comparison["at_least_unit"]
    float_controllers, float_wealth = rooted_controllers, rooted_wealth
    rooted_controllers = sum(
        e == controller and unit_flags[e.value] for e in visible_others
    )
    rooted_wealth = any(e == wealth and unit_flags[e.value] for e in visible_others)
    root_comparison.update(
        float_at_least_unit={e.value: root_mass[e] >= 1 for e in Element},
        float_rooted_controller_stems=float_controllers,
        float_rooted_wealth_visible=float_wealth,
        rooted_controller_stems=rooted_controllers,
        rooted_wealth_visible=rooted_wealth,
    )
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
        len(vigorous_roots) >= 2
        and len(visible_others) == 3
        and any(e in {day_element, parent} and root_mass[e] > 0 for e in visible_others)
    )
    complete_support_bureau = len(vigorous_roots) >= 2 and any(
        event.get("kind") in {"三合", "三会"}
        and event.get("target") == day_element.value
        and event.get("target_revealed")
        and event.get("status") in {"binding", "conditioned_transformation"}
        for event in events
    )
    principal_roots = [
        r["pillar"]
        for r in root_qualifications
        if r["qualified_for_structural_rule"]
        and BRANCH_ELEMENTS[r["branch"]][0] == day_element
    ]
    winter_floating_wood = (
        day_element == Element.WOOD
        and branches["month"] in {"亥", "子"}
        and not any(r["matching_hidden_stems"] for r in root_qualifications)
    )
    if winter_floating_wood:
        final_label, decision = "弱", "winter_rootless_wood_cannot_receive_water"
    elif ordered_passage:
        final_label, decision = "强", "aligned_four_branch_generation_and_time_lu"
    elif wealth_officer_chain:
        final_label, decision = (
            "弱",
            "rooted_wealth_officer_front_without_visible_support",
        )
    elif complete_support_bureau:
        final_label, decision = (
            "强",
            "complete_same_element_bureau_with_surviving_vigorous_roots",
        )
    elif structural_rule:
        final_label, decision = "强", "in_command_multiple_vigorous_roots"
    elif len(principal_roots) >= 2:
        final_label, decision = "强", "multiple_surviving_principal_body_roots"
    elif rooted_support_front:
        final_label, decision = (
            "强",
            "multiple_vigorous_roots_and_rooted_visible_support",
        )
    else:
        final_label, decision = numerical_label, "weighted_balance"
    return {
        "punishment_resolution_policy": PUNISHMENT_POLICY,
        "threshold_arithmetic": threshold_arithmetic,
        "structural_decision": {
            "method_id": STRUCTURAL_PRIORITY_METHOD_ID,
            "rule": decision,
            "vigorous_roots": vigorous_roots,
            "numerical_label": numerical_label,
            "source_id": (
                "ditian_winter_rootless_wood_v1"
                if winter_floating_wood
                else (
                    "ditian_ordered_four_branch_passage_v1"
                    if ordered_passage
                    else (
                        "ditian_rooted_body_before_season_proxy_v1"
                        if decision
                        in {
                            "multiple_surviving_principal_body_roots",
                            "multiple_vigorous_roots_and_rooted_visible_support",
                        }
                        else (
                            "ditian_complete_same_element_bureau_capacity_v1"
                            if decision
                            == "complete_same_element_bureau_with_surviving_vigorous_roots"
                            else (
                                "ditian_zhonghe" if wealth_officer_chain else "ziping_6"
                            )
                        )
                    )
                )
            ),
            "rooted_controller_stems": rooted_controllers,
            "rooted_wealth_visible": rooted_wealth,
            "support_visible_stems": support_visible,
            "root_qualification_method": "source_category_surviving_root_v1",
            "source_premises": {
                "ordered_branch_elements": [e.value for e in branch_elements],
                "uncontested_full_generation_path": ordered_passage,
                "surviving_principal_root_positions": principal_roots,
                "winter_rootless_wood": winter_floating_wood,
            },
        },
        "root_qualifications": root_qualifications,
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
        "hidden_stem_ledger": hidden_stem_ledger,
        "combination_contributions": combination_contributions,
        "revealed_stems": stems_evidence,
        "stem_effects": stem_effects,
        "relations": events,
        "effective_elements": {e.value: round(v, 6) for e, v in effective.items()},
        "effective_elements_unrounded": {e.value: v for e, v in effective.items()},
    }


def evaluate_strength_policy(
    pillars: Dict[str, Tuple[str, str]],
    phases: Dict[str, str],
    policy: StrengthPolicy,
) -> Dict[str, Any]:
    """Evaluate a supplied policy with the sole adopted arithmetic."""
    return _evaluate(pillars, phases, policy)


def assess_strength(
    pillars: Dict[str, Tuple[str, str]], phases: Dict[str, str]
) -> Dict[str, Any]:
    # Binding acts on unrounded energy and preserves original stem identities.
    result = evaluate_strength_policy(pillars, phases, DEFAULT_POLICY)
    result["clash_comparison"] = build_clash_comparison(
        pillars, result["relations"], SOURCES
    )
    stem_receipt = result.pop("stem_effects")
    result["stem_energy_accounting"] = {
        "method_id": "unrounded_non_day_stem_budget_v1",
        "arithmetic_policy": "round_only_for_display",
        "conversion_policy": "not_applied",
        "ledger": stem_receipt["ledger"],
        "source_order_review": build_stem_order_review(
            {name: pillars[name][0] for name in POSITIONS},
            result["relations"],
            STEM_PAIRS,
        ),
        "quantity_kind": "non_day_stem_budget_weighted_energy",
        "scope": "非日干原字预算各1；合绊乘于未取整的激活与季相能量，最后展示时取整。局部五合成化候选未获原典验收，未启用；不是日主化气格、原典完整强弱或现实概率。",
    }
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
            alternative = evaluate_strength_policy(
                pillars,
                phases,
                replace(DEFAULT_POLICY, **{field: value * scale}),
            )
            variants.append(
                {
                    "parameter": field,
                    "scale": scale,
                    "strength": alternative["strength_level"],
                    "numerical_strength": alternative["threshold_arithmetic"][
                        "numerical_label"
                    ],
                    "support_share": round(alternative["support_share"], 6),
                }
            )
    labels = sorted({result["strength_level"], *(v["strength"] for v in variants)})
    numerical_labels = sorted(
        {
            result["threshold_arithmetic"]["numerical_label"],
            *(v["numerical_strength"] for v in variants),
        }
    )
    special_review = result["threshold_arithmetic"]["requires_special_structure_review"]
    result.update(
        {
            "method_id": STRENGTH_METHOD_ID,
            "root_effect_policy": STORAGE_SOURCE["id"],
            "complete_bureau_membership_policy": MEMBERSHIP_POLICY,
            "root_activation_policy": "remaining_physical_hidden_stems_only_v1",
            "status": "boundary_sensitive" if len(labels) > 1 else "rule_based",
            "parameters": asdict(DEFAULT_POLICY),
            "seasonal_factors": dict(PHASE_FACTORS),
            "seasonal_phases": dict(phases),
            "support_weaken_ratio": (
                result["support_strength"] / result["weaken_strength"]
                if result["weaken_strength"]
                else None
            ),
            "sensitivity": {
                "candidate_strengths": labels,
                "numerical_candidate_strengths": numerical_labels,
                "variants": variants,
            },
            "ordinary_fuyi_requires_review": set(numerical_labels)
            != {result["strength_level"]},
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
                "同一完整会合局的重复支按实体位置各处理一次；不把同局重见误判为两个竞争局。不同局及半合仍分别审查。",
                "合化或半合生成的趋势预算可参与有效能量，不冒充实际藏干通根或激活有根天干；真实根量与合成贡献分别记录。",
                "刑害有门派分歧；三刑取全组、子卯取成对，自刑轻减，六害不机械减根。",
                "四墓土刑冲按所选原典区别冲动与冲克，土根不统一减损，不增造开库能量；水根减损幅度仍为工程约定。",
                "旺衰极端或参数敏感时停止自动扶抑取用，另行核对从格及专旺。",
                "结构三档不替代数值扶抑前提；两者不同或数值敏感时，普通扶抑喜忌继续待判。",
            ],
        }
    )
    return result
