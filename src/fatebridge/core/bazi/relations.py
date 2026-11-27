"""Unified BaZi stem/branch relation engine for natal, cross-chart, and timing layers."""

from __future__ import annotations

from itertools import combinations
from typing import Any, Literal, Mapping

from fatebridge.utils.data import (
    BRANCH_CLASH_PAIRS,
    BRANCH_COMBINATIONS,
    BRANCH_CONFLICTS,
    BRANCH_ELEMENTS,
    BRANCH_HARM_PAIRS,
    BRANCH_HARMONY_PAIRS,
    BRANCH_HARMS,
    BRANCH_HIDDEN_STEMS,
    BRANCH_PUNISHMENT_TARGETS,
    BRANCH_SEASONAL_COMBINATIONS,
    BRANCH_SELF_PUNISHMENTS,
    BRANCH_THREE_PUNISHMENTS,
    BRANCH_TRIPLE_COMBINATIONS,
    DESTRUCTION_CYCLE,
    EARTHLY_BRANCHES,
    GENERATION_CYCLE,
    STEM_COMBINATIONS,
    STEM_ELEMENTS,
    STEM_FOUR_CLASHES,
    TRIPLE_COMBINATION_PEAK,
    Element,
)

Pillars = Mapping[str, tuple[str, str]]
ORDER = ("year", "month", "day", "hour")
TripleMembership = Literal["complete", "peak_pair", "arch_pair", "insufficient"]

# 地支六破 (Six Breaks)
BRANCH_BREAK_PAIRS: tuple[tuple[str, str], ...] = (
    ("子", "酉"),
    ("午", "卯"),
    ("寅", "亥"),
    ("辰", "丑"),
    ("巳", "申"),
    ("戌", "未"),
)
BRANCH_BREAKS: dict[str, str] = {
    left: right for a, b in BRANCH_BREAK_PAIRS for left, right in ((a, b), (b, a))
}

# 通禄暗合 / 通合 (Hidden-Stem Secret Harmonies)
BRANCH_HIDDEN_COMBINATIONS: dict[frozenset[str], str] = {
    frozenset({"寅", "丑"}): "甲己合土/丙辛合水/戊癸合火（通禄暗合）",
    frozenset({"午", "亥"}): "丁壬合木/甲己合土（通禄暗合）",
    frozenset({"卯", "申"}): "乙庚合金（通禄暗合）",
    frozenset({"子", "巳"}): "戊癸合火（通禄暗合）",
}

_STEM_COMBINATION_ELEMENT: dict[frozenset[str], str] = {
    frozenset((a, b)): elem for a, b, elem in STEM_COMBINATIONS
}
_STEM_CLASH_SET: set[frozenset[str]] = {frozenset(pair) for pair in STEM_FOUR_CLASHES}

# 拱禄拱贵十组 (《三命通会·拱禄拱贵》)
_ARCH_LU_GUI_TABLE: dict[tuple[str, str, str], tuple[str, str]] = {
    ("癸", "亥", "丑"): ("拱禄", "子"),
    ("癸", "丑", "亥"): ("拱禄", "子"),
    ("丁", "巳", "未"): ("拱禄", "午"),
    ("己", "未", "巳"): ("拱禄", "午"),
    ("戊", "辰", "午"): ("拱禄", "巳"),
    ("甲", "申", "戌"): ("拱贵", "酉"),
    ("乙", "未", "酉"): ("拱贵", "申"),
    ("甲", "寅", "子"): ("拱贵", "丑"),
    ("戊", "申", "午"): ("拱贵", "未"),
    ("辛", "丑", "卯"): ("拱贵", "寅"),
}

# 旺神双见拱会 / 半三会 (同方位两支)
_DIRECTIONAL_ARCH_PAIRS: dict[frozenset[str], tuple[str, str, str]] = {
    frozenset((group[0], group[2])): (group, bureau, group[1])
    for group, bureau in BRANCH_SEASONAL_COMBINATIONS.items()
}


def classify_triple_members(
    group: str, branches: set[str] | list[str]
) -> TripleMembership:
    """Classify 3-branch group membership: complete / peak_pair (半合) / arch_pair (拱合)."""
    present = set(group).intersection(branches)
    if len(present) == 3:
        return "complete"
    if len(present) == 2:
        return "peak_pair" if TRIPLE_COMBINATION_PEAK[group] in present else "arch_pair"
    return "insufficient"


def element_relation(left: Element, right: Element) -> str:
    if left == right:
        return "same_element"
    if GENERATION_CYCLE[left] == right:
        return "generates"
    if GENERATION_CYCLE[right] == left:
        return "generated_by"
    if DESTRUCTION_CYCLE[left] == right:
        return "controls"
    return "controlled_by"


def pair_relations(
    left: str,
    right: str,
    pillars: Pillars,
    *,
    include_directional_punishments: bool = True,
) -> list[dict[str, Any]]:
    """Return all stem and branch pair relations between two labeled pillars."""
    a, b = pillars[left], pillars[right]
    s1, b1 = a
    s2, b2 = b
    kinds: list[tuple[str, str, dict[str, Any]]] = []

    if frozenset((s1, s2)) in _STEM_COMBINATION_ELEMENT:
        kinds.append(
            (
                "stem",
                "天干五合",
                {"candidate_element": _STEM_COMBINATION_ELEMENT[frozenset((s1, s2))]},
            )
        )
    if frozenset((s1, s2)) in _STEM_CLASH_SET:
        kinds.append(("stem", "天干四冲", {}))

    if BRANCH_COMBINATIONS.get(b1) == b2:
        kinds.append(("branch", "六合", {}))
    if BRANCH_CONFLICTS.get(b1) == b2:
        kinds.append(("branch", "六冲", {}))
    if BRANCH_HARMS.get(b1) == b2:
        kinds.append(("branch", "六害", {}))
    if BRANCH_BREAKS.get(b1) == b2:
        kinds.append(("branch", "六破", {}))
    if b1 != b2 and frozenset((b1, b2)) in BRANCH_HIDDEN_COMBINATIONS:
        kinds.append(
            (
                "branch",
                "暗合",
                {"detail": BRANCH_HIDDEN_COMBINATIONS[frozenset((b1, b2))]},
            )
        )
    if b1 == b2 and b1 in BRANCH_SELF_PUNISHMENTS:
        kinds.append(("branch", "自刑", {}))
    if {b1, b2} == {"子", "卯"}:
        kinds.append(("branch", "子卯刑", {}))
    if include_directional_punishments and b1 != b2:
        for group in BRANCH_THREE_PUNISHMENTS:
            if len(group) == 3 and {b1, b2} <= set(group):
                kinds.append(
                    ("branch", "三刑(半)", {"group": "".join(group), "complete": False})
                )
                break
    if s1 == s2 and b1 == b2:
        kinds.append(("pillar", "伏吟", {}))
    elif (
        DESTRUCTION_CYCLE[STEM_ELEMENTS[s1][0]] == STEM_ELEMENTS[s2][0]
        or DESTRUCTION_CYCLE[STEM_ELEMENTS[s2][0]] == STEM_ELEMENTS[s1][0]
    ) and BRANCH_CONFLICTS.get(b1) == b2:
        if STEM_ELEMENTS[s1][1] == STEM_ELEMENTS[s2][1]:
            kinds.append(("pillar", "天克地冲", {}))

    dist = (
        abs(ORDER.index(left) - ORDER.index(right))
        if left in ORDER and right in ORDER
        else None
    )
    return [
        {
            "kind": kind,
            "level": level,
            "positions": [left, right],
            "characters": (
                [s1 + b1, s2 + b2]
                if level == "pillar"
                else [
                    s1 if level == "stem" else b1,
                    s2 if level == "stem" else b2,
                ]
            ),
            "distance": dist,
            "effect_status": "relation_only",
            **extra,
        }
        for level, kind, extra in kinds
    ]


def group_relations(pillars: Pillars) -> list[dict[str, Any]]:
    """Return 三合, 半合, 拱合, 三会, 拱会, 三刑 across a set of labeled pillars."""
    groups: list[dict[str, Any]] = []
    branches = [b for _, b in pillars.values()]
    branch_set = set(branches)

    for group, bureau in BRANCH_TRIPLE_COMBINATIONS.items():
        membership = classify_triple_members(group, branch_set)
        if membership == "complete":
            groups.append(
                {
                    "kind": "三合",
                    "branches": list(group),
                    "positions": [n for n, (_, b) in pillars.items() if b in group],
                    "bureau": bureau,
                    "effect_status": "relation_only",
                }
            )
        elif membership == "peak_pair":
            groups.append(
                {
                    "kind": "半合",
                    "branches": [b for b in group if b in branch_set],
                    "positions": [n for n, (_, b) in pillars.items() if b in group],
                    "bureau": bureau,
                    "effect_status": "relation_only",
                }
            )
        elif membership == "arch_pair":
            groups.append(
                {
                    "kind": "拱合",
                    "branches": [b for b in group if b in branch_set],
                    "positions": [n for n, (_, b) in pillars.items() if b in group],
                    "arched": TRIPLE_COMBINATION_PEAK[group],
                    "bureau": bureau,
                    "effect_status": "relation_only",
                }
            )

    for group, bureau in BRANCH_SEASONAL_COMBINATIONS.items():
        present = [b for b in group if b in branch_set]
        if len(present) == 3:
            groups.append(
                {
                    "kind": "三会",
                    "branches": list(group),
                    "positions": [n for n, (_, b) in pillars.items() if b in group],
                    "bureau": bureau,
                    "effect_status": "relation_only",
                }
            )
        elif set(present) == {group[0], group[2]}:
            groups.append(
                {
                    "kind": "拱会",
                    "branches": present,
                    "positions": [n for n, (_, b) in pillars.items() if b in present],
                    "arched": group[1],
                    "bureau": bureau,
                    "effect_status": "relation_only",
                }
            )

    for punish_group in BRANCH_THREE_PUNISHMENTS:
        if len(punish_group) == 3 and set(punish_group) <= branch_set:
            groups.append(
                {
                    "kind": "三刑",
                    "branches": list(punish_group),
                    "positions": [
                        n for n, (_, b) in pillars.items() if b in punish_group
                    ],
                    "bureau": None,
                    "effect_status": "relation_only",
                }
            )

    return groups


def check_harmony_patterns(pillars: Pillars) -> dict[str, Any]:
    """Structured natal harmony facts (三合/半合/拱合/三会/六合/暗合)."""
    active_order = tuple(pos for pos in ORDER if pos in pillars)
    branches = [pillars[pos][1] for pos in active_order]
    branch_set = set(branches)
    three_harmony: list[dict[str, Any]] = []
    half_harmony: list[dict[str, Any]] = []
    arch_harmony: list[dict[str, Any]] = []
    for group, bureau in BRANCH_TRIPLE_COMBINATIONS.items():
        membership = classify_triple_members(group, branch_set)
        if membership == "complete":
            three_harmony.append(
                {
                    "type": "三合" + bureau,
                    "branches": list(group),
                    "complete": True,
                }
            )
        elif membership == "peak_pair":
            half_harmony.append(
                {
                    "type": "半合" + bureau,
                    "branches": [b for b in group if b in branch_set],
                    "complete": False,
                }
            )
        elif membership == "arch_pair":
            arch_harmony.append(
                {
                    "type": "拱" + bureau,
                    "branches": [b for b in group if b in branch_set],
                    "arched": TRIPLE_COMBINATION_PEAK[group],
                }
            )

    seasonal = [
        {"type": "三会" + bureau, "branches": list(group), "complete": True}
        for group, bureau in BRANCH_SEASONAL_COMBINATIONS.items()
        if set(group) <= branch_set
    ]
    hidden_harmonies = [
        {
            "branches": [b1, b2],
            "positions": [p1, p2],
            "detail": BRANCH_HIDDEN_COMBINATIONS[frozenset((b1, b2))],
        }
        for p1, p2 in combinations(active_order, 2)
        for b1, b2 in ((pillars[p1][1], pillars[p2][1]),)
        if b1 != b2 and frozenset((b1, b2)) in BRANCH_HIDDEN_COMBINATIONS
    ]
    return {
        "branch_positions": {
            b: [p for p in active_order if pillars[p][1] == b]
            for b in dict.fromkeys(branches)
        },
        "three_harmony": three_harmony,
        "half_harmony": half_harmony,
        "arch_harmony": arch_harmony,
        "seasonal_meeting": seasonal,
        "six_harmony": [
            list(pair) for pair in BRANCH_HARMONY_PAIRS if set(pair) <= branch_set
        ],
        "hidden_harmony": hidden_harmonies,
    }


def check_clash_patterns(pillars: Pillars) -> dict[str, Any]:
    """Structured natal clash/harm/break/punishment facts."""
    active_order = tuple(pos for pos in ORDER if pos in pillars)
    branches = [pillars[pos][1] for pos in active_order]
    branch_set = set(branches)
    names = (("无恩之刑", "恃势之刑"), ("恃势之刑", "无恩之刑"), ("无礼之刑",))
    punishments: list[dict[str, Any]] = []
    for group, variants in zip(BRANCH_THREE_PUNISHMENTS, names):
        present = [b for b in group if b in branch_set]
        if len(present) < 2:
            continue
        full = len(group) == len(present) == 3
        row: dict[str, Any] = {
            "name": (
                variants[0] if full or len(group) == 2 else "".join(present) + "相刑"
            ),
            "type": "three_punishment" if full else "pair_punishment",
            "branches": present,
            "directed_edges": [
                {"from_branch": b, "to_branch": BRANCH_PUNISHMENT_TARGETS[b]}
                for b in present
                if BRANCH_PUNISHMENT_TARGETS[b] in present
            ],
        }
        if group == ("子", "卯"):
            zi_count = branches.count("子")
            mao_count = branches.count("卯")
            if zi_count != mao_count:
                row["ratio_note"] = (
                    f"{'一子二卯' if zi_count == 1 and mao_count >= 2 else '二子一卯' if zi_count >= 2 and mao_count == 1 else f'{zi_count}子{mao_count}卯'}（子卯相刑并见多支）"
                )
        punishments.append(row)

    for b in sorted(BRANCH_SELF_PUNISHMENTS, key=EARTHLY_BRANCHES.index):
        count = branches.count(b)
        if count >= 2:
            punishments.append(
                {
                    "name": b + b + "自刑",
                    "type": "self_punishment",
                    "branches": [b] * count,
                    "directed_edges": [{"from_branch": b, "to_branch": b}],
                }
            )

    return {
        "branch_positions": {
            b: [p for p in active_order if pillars[p][1] == b]
            for b in dict.fromkeys(branches)
        },
        "six_clash": [
            list(pair) for pair in BRANCH_CLASH_PAIRS if set(pair) <= branch_set
        ],
        "six_harm": [
            list(pair) for pair in BRANCH_HARM_PAIRS if set(pair) <= branch_set
        ],
        "six_break": [
            list(pair) for pair in BRANCH_BREAK_PAIRS if set(pair) <= branch_set
        ],
        "punishments": punishments,
    }


def check_stem_patterns(pillars: Pillars) -> dict[str, Any]:
    """Check stem 5-combinations, 4-clashes, and adjacent pairings."""
    active_order = tuple(pos for pos in ORDER if pos in pillars)
    stems = {pos: pillars[pos][0] for pos in active_order}
    combinations_found = []
    clashes_found = []
    for p1, p2 in combinations(active_order, 2):
        s1, s2 = stems[p1], stems[p2]
        key = frozenset((s1, s2))
        if key in _STEM_COMBINATION_ELEMENT:
            combinations_found.append(
                {
                    "positions": [p1, p2],
                    "stems": [s1, s2],
                    "candidate_element": _STEM_COMBINATION_ELEMENT[key],
                    "adjacent": abs(ORDER.index(p1) - ORDER.index(p2)) == 1,
                }
            )
        if key in _STEM_CLASH_SET:
            clashes_found.append(
                {
                    "positions": [p1, p2],
                    "stems": [s1, s2],
                    "adjacent": abs(ORDER.index(p1) - ORDER.index(p2)) == 1,
                }
            )
    return {
        "stem_combinations": combinations_found,
        "stem_clashes": clashes_found,
    }


def check_pillar_patterns(pillars: Pillars) -> dict[str, Any]:
    """Per-pillar stem vs principal/hidden branch element relations."""
    active_order = tuple(pos for pos in ORDER if pos in pillars)
    rows = []
    for pos in active_order:
        stem, branch = pillars[pos]
        elem = STEM_ELEMENTS[stem][0]
        principal = BRANCH_ELEMENTS[branch][0]
        rows.append(
            {
                "pillar": pos,
                "stem": stem,
                "branch": branch,
                "stem_element": elem.value,
                "principal_branch_element": principal.value,
                "principal_relation": element_relation(elem, principal),
                "hidden_relations": [
                    {
                        "stem": h,
                        "hidden_rank": rank,
                        "element": STEM_ELEMENTS[h][0].value,
                        "relation": element_relation(elem, STEM_ELEMENTS[h][0]),
                    }
                    for rank, h in enumerate(BRANCH_HIDDEN_STEMS[branch])
                ],
            }
        )
    return {"pillars": rows}


def check_pillar_pair_patterns(pillars: Pillars) -> dict[str, Any]:
    """Check all pillar pairs for identity, clash, and stem relation."""
    active_order = tuple(pos for pos in ORDER if pos in pillars)
    pairs = []
    for left, right in combinations(active_order, 2):
        s1, b1 = pillars[left]
        s2, b2 = pillars[right]
        pairs.append(
            {
                "pillars": [left, right],
                "pillar_content": [s1 + b1, s2 + b2],
                "identical": pillars[left] == pillars[right],
                "branch_six_clash": BRANCH_CONFLICTS[b1] == b2,
                "stem_four_clash": frozenset((s1, s2)) in _STEM_CLASH_SET,
                "stem_relation": element_relation(
                    STEM_ELEMENTS[s1][0], STEM_ELEMENTS[s2][0]
                ),
            }
        )
    return {"pairs": pairs}


def check_hidden_patterns(pillars: Pillars) -> dict[str, Any]:
    """Check concealed stem combinations, arch combinations, and 拱禄拱贵."""
    active_order = tuple(pos for pos in ORDER if pos in pillars)
    branches = [pillars[name][1] for name in active_order]
    hidden_stem_combinations = []
    for left, right in combinations(active_order, 2):
        a, b = pillars[left][1], pillars[right][1]
        stem_pairs = []
        for ra, sa in enumerate(BRANCH_HIDDEN_STEMS[a]):
            for rb, sb in enumerate(BRANCH_HIDDEN_STEMS[b]):
                key = frozenset((sa, sb))
                if key in _STEM_COMBINATION_ELEMENT:
                    stem_pairs.append(
                        {
                            "stems": [sa, sb],
                            "hidden_ranks": [ra, rb],
                            "candidate_element": _STEM_COMBINATION_ELEMENT[key],
                        }
                    )
        if stem_pairs:
            hidden_stem_combinations.append(
                {"pillars": [left, right], "branches": [a, b], "stem_pairs": stem_pairs}
            )

    arch_combinations = []
    for group, bureau in BRANCH_TRIPLE_COMBINATIONS.items():
        if classify_triple_members(group, branches) == "arch_pair":
            arched = TRIPLE_COMBINATION_PEAK[group]
            arch_combinations.append(
                {
                    "branches": [b for b in group if b in branches],
                    "arched": arched,
                    "group_kind": "三合",
                    "candidate_element": bureau[0],
                }
            )

    arch_lu_gui = []
    day_s, day_b = pillars["day"]
    if "hour" in pillars:
        hour_s, hour_b = pillars["hour"]
        if day_s == hour_s and (day_s, day_b, hour_b) in _ARCH_LU_GUI_TABLE:
            kind, arched = _ARCH_LU_GUI_TABLE[(day_s, day_b, hour_b)]
            filled = [p for p in active_order if pillars[p][1] == arched]
            arch_lu_gui.append(
                {
                    "kind": kind,
                    "day_pillar": day_s + day_b,
                    "hour_pillar": hour_s + hour_b,
                    "arched": arched,
                    "target_present_at": filled,
                    "status": "excluded_by_filled_target" if filled else "present",
                }
            )

    return {
        "hidden_stem_combinations": hidden_stem_combinations,
        "arch_combinations": arch_combinations,
        "arch_lu_gui": arch_lu_gui,
    }


def collect_target_branch_relations(
    target_branch: str,
    natal_pillars: Pillars,
    label: str,
    *,
    target_stem: str | None = None,
    target_pillar_label: str | None = None,
) -> list[dict[str, Any]]:
    """Full branch + stem relation scan between one timing branch/pillar and natal 4 pillars."""
    relations: list[dict[str, Any]] = []
    active_order = tuple(p for p in ORDER if p in natal_pillars)
    natal_branches = {natal_pillars[p][1] for p in active_order}
    for pillar_name in active_order:
        p_stem, p_branch = natal_pillars[pillar_name]
        if BRANCH_CONFLICTS.get(target_branch) == p_branch:
            relations.append(
                {
                    "type": "六冲",
                    "with_pillar": pillar_name,
                    "with_branch": p_branch,
                }
            )
        if BRANCH_COMBINATIONS.get(target_branch) == p_branch:
            relations.append(
                {
                    "type": "六合",
                    "with_pillar": pillar_name,
                    "with_branch": p_branch,
                }
            )
        if BRANCH_HARMS.get(target_branch) == p_branch:
            relations.append(
                {
                    "type": "六害",
                    "with_pillar": pillar_name,
                    "with_branch": p_branch,
                }
            )
        if BRANCH_BREAKS.get(target_branch) == p_branch:
            relations.append(
                {
                    "type": "六破",
                    "with_pillar": pillar_name,
                    "with_branch": p_branch,
                }
            )
        if (
            target_branch != p_branch
            and frozenset((target_branch, p_branch)) in BRANCH_HIDDEN_COMBINATIONS
        ):
            relations.append(
                {
                    "type": "暗合",
                    "with_pillar": pillar_name,
                    "with_branch": p_branch,
                }
            )
        if target_branch == p_branch and target_branch in BRANCH_SELF_PUNISHMENTS:
            relations.append(
                {
                    "type": "自刑",
                    "with_pillar": pillar_name,
                    "with_branch": p_branch,
                }
            )
        if {target_branch, p_branch} == {"子", "卯"}:
            relations.append(
                {
                    "type": "子卯刑",
                    "with_pillar": pillar_name,
                    "with_branch": p_branch,
                }
            )
        if target_branch != p_branch:
            for group in BRANCH_THREE_PUNISHMENTS:
                if len(group) == 3 and {target_branch, p_branch} <= set(group):
                    kind = (
                        "三刑"
                        if set(group) <= (natal_branches | {target_branch})
                        else "三刑(半)"
                    )
                    relations.append(
                        {
                            "type": kind,
                            "with_pillar": pillar_name,
                            "with_branch": p_branch,
                            "group": "".join(group),
                        }
                    )
                    break
        if target_stem is not None:
            if target_stem == p_stem and target_branch == p_branch:
                relations.append(
                    {
                        "type": "伏吟",
                        "with_pillar": pillar_name,
                        "with_branch": p_branch,
                        "with_pillar_ganzhi": p_stem + p_branch,
                    }
                )
            elif (
                BRANCH_CONFLICTS.get(target_branch) == p_branch
                and (
                    DESTRUCTION_CYCLE[STEM_ELEMENTS[target_stem][0]]
                    == STEM_ELEMENTS[p_stem][0]
                    or DESTRUCTION_CYCLE[STEM_ELEMENTS[p_stem][0]]
                    == STEM_ELEMENTS[target_stem][0]
                )
                and STEM_ELEMENTS[target_stem][1] == STEM_ELEMENTS[p_stem][1]
            ):
                relations.append(
                    {
                        "type": "天克地冲(反吟)",
                        "with_pillar": pillar_name,
                        "with_branch": p_branch,
                        "with_pillar_ganzhi": p_stem + p_branch,
                    }
                )

    combined_branches = natal_branches | {target_branch}
    for triple_group, bureau in BRANCH_TRIPLE_COMBINATIONS.items():
        if target_branch not in triple_group:
            continue
        membership = classify_triple_members(triple_group, combined_branches)
        if membership == "complete":
            relations.append(
                {
                    "type": "三合",
                    "group": triple_group,
                    "bureau": bureau,
                    "with_pillars": [
                        p for p in active_order if natal_pillars[p][1] in triple_group
                    ],
                }
            )
        elif membership == "peak_pair":
            relations.append(
                {
                    "type": "半合",
                    "group": triple_group,
                    "bureau": bureau,
                    "with_pillars": [
                        p for p in active_order if natal_pillars[p][1] in triple_group
                    ],
                }
            )

    for seasonal_group, bureau in BRANCH_SEASONAL_COMBINATIONS.items():
        if target_branch in seasonal_group and set(seasonal_group) <= combined_branches:
            relations.append(
                {
                    "type": "三会",
                    "group": seasonal_group,
                    "bureau": bureau,
                    "with_pillars": [
                        p for p in active_order if natal_pillars[p][1] in seasonal_group
                    ],
                }
            )

    return relations
