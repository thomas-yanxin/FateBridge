"""Literal branch membership and witnesses; no force or formation judgment."""

from typing import Iterable, Literal, Mapping, TypedDict

from fatebridge.utils.data import (
    BRANCH_CLASH_PAIRS,
    BRANCH_HARM_PAIRS,
    BRANCH_HARMONY_PAIRS,
    BRANCH_PUNISHMENT_TARGETS,
    BRANCH_SELF_PUNISHMENTS,
    BRANCH_THREE_PUNISHMENTS,
    BRANCH_TRIPLE_COMBINATIONS,
    EARTHLY_BRANCHES,
    TRIPLE_COMBINATION_PEAK,
)

Pillars = Mapping[str, tuple[str, str]]
ORDER = ("year", "month", "day", "hour")
TripleMembership = Literal["complete", "peak_pair", "arch_pair", "insufficient"]
SOURCE = {
    "id": "sanming_siku_literal_branch_relations_v1",
    "author": "万民英",
    "title": "三命通会·论支元六合、论支元三合、论六害、论三刑、论冲击",
    "edition": "景印文渊阁四库全书第810册，卷二；固定转录761691",
    "locator": "扫描114–116、118–122；刑链与名称异说分列，文字出现不裁定实际效力",
    "url": "https://zh.wikisource.org/w/index.php?oldid=761691",
}


class BranchGroupFact(TypedDict):
    type: str
    branches: list[str]
    complete: bool
    formation_status: Literal["not_adjudicated"]


class HarmonyPatterns(TypedDict):
    method_id: Literal["bazi_branch_harmony_facts_v1"]
    rulesets: list[dict[str, str]]
    branch_positions: dict[str, list[str]]
    membership_policy: Literal["peak_member_required_for_half_v1"]
    three_harmony: list[BranchGroupFact]
    half_harmony: list[BranchGroupFact]
    six_harmony: list[list[str]]
    scope: str


class PunishmentEdge(TypedDict):
    from_branch: str
    to_branch: str


class PunishmentFact(TypedDict):
    name: str
    type: Literal["three_punishment", "pair_punishment", "self_punishment"]
    branches: list[str]
    group_name_variants: list[str]
    directed_edges: list[PunishmentEdge]
    effect_status: Literal["not_adjudicated"]


class ClashPatterns(TypedDict):
    method_id: Literal["bazi_branch_clash_facts_v1"]
    rulesets: list[dict[str, str]]
    branch_positions: dict[str, list[str]]
    six_clash: list[list[str]]
    six_harm: list[list[str]]
    punishments: list[PunishmentFact]
    scope: str


def classify_triple_members(group: str, branches: Iterable[str]) -> TripleMembership:
    """Use the project's named peak-required convention in every consumer.

    三字齐 is membership, not sufficient transformation. The pinned reference
    table labels all twelve two-member subsets 半合; its four end pairs are
    explicit arch pairs here. This is not a universal textual definition.
    """
    present = set(group).intersection(branches)
    if len(present) == 3:
        return "complete"
    else:
        pass
    if len(present) == 2:
        return "peak_pair" if TRIPLE_COMBINATION_PEAK[group] in present else "arch_pair"
    else:
        pass
    return "insufficient"


def check_harmony_patterns(pillars: Pillars) -> HarmonyPatterns:
    branches = [pillars[position][1] for position in ORDER]
    full: list[BranchGroupFact] = []
    halves: list[BranchGroupFact] = []
    for group, bureau in BRANCH_TRIPLE_COMBINATIONS.items():
        membership = classify_triple_members(group, branches)
        if membership in {"complete", "peak_pair"}:
            fact: BranchGroupFact = {
                "type": ("三合" if membership == "complete" else "半合") + bureau,
                "branches": [branch for branch in group if branch in branches],
                "complete": membership == "complete",
                "formation_status": "not_adjudicated",
            }
            (full if membership == "complete" else halves).append(fact)
        else:
            pass
    return {
        "method_id": "bazi_branch_harmony_facts_v1",
        "rulesets": [SOURCE.copy()],
        "branch_positions": {
            branch: [position for position in ORDER if pillars[position][1] == branch]
            for branch in dict.fromkeys(branches)
        },
        "membership_policy": "peak_member_required_for_half_v1",
        "three_harmony": full,
        "half_harmony": halves,
        "six_harmony": [
            list(pair) for pair in BRANCH_HARMONY_PAIRS if set(pair) <= set(branches)
        ],
        "scope": "按实际支字列成员与全部柱位；三字齐不等于已经成化。半合采用含中神的具名项目口径，缺中神端支另作拱候选；不把第三方十二对子口径冒称同一方法。",
    }


def check_clash_patterns(pillars: Pillars) -> ClashPatterns:
    branches = [pillars[position][1] for position in ORDER]
    names = (("无恩之刑", "恃势之刑"), ("恃势之刑", "无恩之刑"), ("无礼之刑",))
    punishments: list[PunishmentFact] = []
    for group, variants in zip(BRANCH_THREE_PUNISHMENTS, names):
        present = [branch for branch in group if branch in branches]
        if len(present) < 2:
            continue
        else:
            pass
        full = len(group) == len(present) == 3
        punishments.append(
            {
                "name": (
                    variants[0]
                    if full or len(group) == 2
                    else "".join(present) + "相刑"
                ),
                "type": "three_punishment" if full else "pair_punishment",
                "branches": present,
                "group_name_variants": list(variants),
                "directed_edges": [
                    {
                        "from_branch": branch,
                        "to_branch": BRANCH_PUNISHMENT_TARGETS[branch],
                    }
                    for branch in present
                    if BRANCH_PUNISHMENT_TARGETS[branch] in present
                ],
                "effect_status": "not_adjudicated",
            }
        )
    for branch in sorted(BRANCH_SELF_PUNISHMENTS, key=EARTHLY_BRANCHES.index):
        count = branches.count(branch)
        if count >= 2:
            punishments.append(
                {
                    "name": branch + branch + "自刑",
                    "type": "self_punishment",
                    "branches": [branch] * count,
                    "group_name_variants": ["自刑"],
                    "directed_edges": [{"from_branch": branch, "to_branch": branch}],
                    "effect_status": "not_adjudicated",
                }
            )
        else:
            pass
    return {
        "method_id": "bazi_branch_clash_facts_v1",
        "rulesets": [SOURCE.copy()],
        "branch_positions": {
            branch: [position for position in ORDER if pillars[position][1] == branch]
            for branch in dict.fromkeys(branches)
        },
        "six_clash": [
            list(pair) for pair in BRANCH_CLASH_PAIRS if set(pair) <= set(branches)
        ],
        "six_harm": [
            list(pair) for pair in BRANCH_HARM_PAIRS if set(pair) <= set(branches)
        ],
        "punishments": punishments,
        "scope": "配对、刑链方向与重见柱位是字面事实，不裁定刑害效力。无恩／恃势同时保留本章主说及所引三车一览异名；不凭名称定吉凶，不替代同次会合解刑或力量账本。",
    }
