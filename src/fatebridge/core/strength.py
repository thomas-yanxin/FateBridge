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
from fatebridge.core.formation_affiliations import (
    LEGACY_POLICY as LEGACY_FORMATION_POLICY,
)
from fatebridge.core.formation_affiliations import POLICY as FORMATION_POLICY
from fatebridge.core.formation_affiliations import SOURCE as AFFILIATION_SOURCE
from fatebridge.core.formation_affiliations import partition_affiliations
from fatebridge.core.punishment_resolution import (
    LEGACY_POLICY as LEGACY_PUNISHMENT_POLICY,
)
from fatebridge.core.punishment_resolution import POLICY as PUNISHMENT_POLICY
from fatebridge.core.punishment_resolution import (
    PREVIOUS_POLICY as PREVIOUS_PUNISHMENT_POLICY,
)
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
STRENGTH_METHOD_ID = "season_root_revelation_relations_v11"
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
    *,
    stem_effect_mode: str = "legacy_v5",
    formation_overlap_policy: str = LEGACY_FORMATION_POLICY,
    punishment_resolution_policy: str = LEGACY_PUNISHMENT_POLICY,
) -> Dict[str, Any]:
    """Score physical positions once; interactions alter those same root budgets."""
    if stem_effect_mode not in {
        "legacy_v5",
        "precise_binding_only_v1",
        "non_day_transformation_v1",
    }:
        raise ValueError("Unknown stem effect mode")
    if formation_overlap_policy not in {LEGACY_FORMATION_POLICY, FORMATION_POLICY}:
        raise ValueError("Unknown formation overlap policy")
    if punishment_resolution_policy not in {
        LEGACY_PUNISHMENT_POLICY,
        PREVIOUS_PUNISHMENT_POLICY,
        PUNISHMENT_POLICY,
    }:
        raise ValueError("Unknown punishment resolution policy")
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
    affiliations: list[Dict[str, Any]] = []
    if formation_overlap_policy == FORMATION_POLICY:
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
    punishment_cover = (
        completed_combination_positions(events)
        if punishment_resolution_policy
        in {PREVIOUS_PUNISHMENT_POLICY, PUNISHMENT_POLICY}
        else protected
    )
    for punishment_group in BRANCH_THREE_PUNISHMENTS:
        punished = [n for n in names if branches[n] in punishment_group]
        if set(branches[n] for n in punished) != set(punishment_group):
            continue  # 寅巳/丑戌 two-branch fragments are not full 三刑 in this policy.
        if punishment_is_resolved(
            punished, branches, punishment_cover, punishment_resolution_policy
        ):
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
    stem_effects: Optional[Dict[str, Any]] = None
    stems_evidence: list[Dict[str, Any]] = []
    if stem_effect_mode != "legacy_v5":
        stem_effects = evaluate_stem_effects(
            pillars,
            phases,
            factors,
            hidden_stem_ledger,
            non_root_mass,
            floating_stem=policy.floating_stem,
            rooted_stem=policy.rooted_stem,
            binding=policy.binding,
            minimum_retention=policy.clash_equal,
            enable_transformation=stem_effect_mode == "non_day_transformation_v1",
        )
        stems_evidence = stem_effects["revealed_stems"]
        if stem_effect_mode == "precise_binding_only_v1":
            # Applied historical binding retains its own source. The rejected
            # 任注 conversion hypothesis must not become public provenance.
            events.extend(
                {
                    "kind": event["kind"],
                    "positions": event["positions"],
                    "status": event["status"],
                    "source_id": "ziping_5",
                }
                for event in stem_effects["relations"]
            )
            for stem_row in stems_evidence:
                stem_row["root_activation_policy"] = (
                    "remaining_physical_hidden_stems_only_v1"
                )
        else:
            events.extend(stem_effects["relations"])
        for element in Element:
            effective[element] += stem_effects["energies"][element.value]
    else:
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
                    "non_root_combination_mass": round(non_root_mass[element], 6),
                    "root_activation_policy": "remaining_physical_hidden_stems_only_v1",
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
    root_qualifications = []
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
    threshold_arithmetic = (
        exact_threshold_decision(
            pillars,
            phases,
            PHASE_FACTORS,
            asdict(policy),
            events,
            float_numerical_label,
        )
        if stem_effect_mode == "precise_binding_only_v1"
        else None
    )
    numerical_label = (
        threshold_arithmetic["numerical_label"]
        if threshold_arithmetic is not None
        else float_numerical_label
    )
    structural_rule = (
        numerical_label == "中和"
        and (
            threshold_arithmetic["support_above_half"]
            if threshold_arithmetic is not None
            else share > 0.5
        )
        and phases[day_element.value] == "旺"
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
    if threshold_arithmetic is not None:
        root_comparison = threshold_arithmetic["physical_root_unit_comparison"]
        unit_flags = root_comparison["at_least_unit"]
        legacy_controllers, legacy_wealth = rooted_controllers, rooted_wealth
        rooted_controllers = sum(
            e == controller and unit_flags[e.value] for e in visible_others
        )
        rooted_wealth = any(e == wealth and unit_flags[e.value] for e in visible_others)
        root_comparison.update(
            legacy_float_at_least_unit={e.value: root_mass[e] >= 1 for e in Element},
            legacy_float_rooted_controller_stems=legacy_controllers,
            legacy_float_rooted_wealth_visible=legacy_wealth,
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
        len(vigorous_roots) >= 2 and len(visible_others) == 3 and support_visible == 3
    )
    complete_support_bureau = len(vigorous_roots) >= 2 and any(
        event.get("kind") in {"三合", "三会"}
        and event.get("target") == day_element.value
        and event.get("target_revealed")
        and event.get("status") in {"binding", "conditioned_transformation"}
        for event in events
    )
    if wealth_officer_chain:
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
    elif rooted_support_front:
        final_label, decision = "强", "multiple_vigorous_roots_and_visible_support"
    else:
        final_label, decision = numerical_label, "weighted_balance"
    return {
        **(
            {"punishment_resolution_policy": punishment_resolution_policy}
            if punishment_resolution_policy
            in {PREVIOUS_PUNISHMENT_POLICY, PUNISHMENT_POLICY}
            else {}
        ),
        **(
            {"threshold_arithmetic": threshold_arithmetic}
            if threshold_arithmetic is not None
            else {}
        ),
        "structural_decision": {
            "rule": decision,
            "vigorous_roots": vigorous_roots,
            "numerical_label": numerical_label,
            "source_id": (
                "ditian_complete_same_element_bureau_capacity_v1"
                if decision
                == "complete_same_element_bureau_with_surviving_vigorous_roots"
                else "ditian_zhonghe" if wealth_officer_chain else "ziping_6"
            ),
            "rooted_controller_stems": rooted_controllers,
            "rooted_wealth_visible": rooted_wealth,
            "support_visible_stems": support_visible,
            "root_qualification_method": "source_category_surviving_root_v1",
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
        **({"stem_effects": stem_effects} if stem_effects is not None else {}),
        "relations": events,
        "effective_elements": {e.value: round(v, 6) for e, v in effective.items()},
        "effective_elements_unrounded": {e.value: v for e, v in effective.items()},
    }


def evaluate_strength_policy(
    pillars: Dict[str, Tuple[str, str]],
    phases: Dict[str, str],
    policy: StrengthPolicy,
) -> Dict[str, Any]:
    """Evaluate a supplied policy with the adopted arithmetic, before presentation.

    Historical experiments deliberately keep _evaluate's legacy default. Public
    assessment and current-policy sensitivity must instead use the same mode.
    """
    return _evaluate(
        pillars,
        phases,
        policy,
        stem_effect_mode="precise_binding_only_v1",
        formation_overlap_policy=FORMATION_POLICY,
        punishment_resolution_policy=PUNISHMENT_POLICY,
    )


def assess_strength(
    pillars: Dict[str, Tuple[str, str]], phases: Dict[str, str]
) -> Dict[str, Any]:
    # The conversion prototype failed its frozen source gate. Adopt only the
    # independently justified arithmetic repair: binding acts on unrounded
    # energy. Original stem identities and the legacy binding policy remain.
    result = evaluate_strength_policy(pillars, phases, DEFAULT_POLICY)
    result["clash_comparison"] = build_clash_comparison(
        pillars, result["relations"], SOURCES
    )
    stem_receipt = result.pop("stem_effects")
    result["stem_energy_accounting"] = {
        "method_id": "unrounded_non_day_stem_budget_v1",
        "arithmetic_policy": "round_only_for_display",
        "conversion_policy": "legacy_binding_only_conversion_prototype_not_adopted",
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
                    "support_share": round(alternative["support_share"], 6),
                }
            )
    labels = sorted({result["strength_level"], *(v["strength"] for v in variants)})
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
                "同一完整会合局的重复支按实体位置各处理一次；不把同局重见误判为两个竞争局。不同局及半合仍分别审查。",
                "合化或半合生成的趋势预算可参与有效能量，不冒充实际藏干通根或激活有根天干；真实根量与合成贡献分别记录。",
                "刑害有门派分歧；三刑取全组、子卯取成对，自刑轻减，六害不机械减根。",
                "四墓土刑冲按所选原典区别冲动与冲克，土根不统一减损，不增造开库能量；水根减损幅度仍为工程约定。",
                "旺衰极端或参数敏感时停止自动扶抑取用，另行核对从格及专旺。",
            ],
        }
    )
    return result
