"""Source-scoped punishment entities and completed same-run combination cover."""

from typing import Any, Mapping, Sequence

from fatebridge.core.source_identity import ZIPING_ZHENQUAN_NLC_SCAN_URL

POLICY = "completed_combination_zi_mao_month_officer_resolution_v4"
STRENGTH_METHOD = "season_root_revelation_relations_v12"
CURRENT_STRENGTH_METHODS = frozenset({STRENGTH_METHOD})
SOURCE = {
    "id": "ziping_completed_combination_resolution_primary_v1",
    "author": "沈孝瞻",
    "title": "秘本子平真詮·論刑沖會合解法",
    "edition": "国家图书馆藏本，上海世界图书馆发行",
    "url": ZIPING_ZHENQUAN_NLC_SCAN_URL,
    "source_sha256": "71402a780b0351b54edf121a51bc4a4a4ce5896496c35b954563ee06f1a6f620",
    "pdf_pages": [23, 24, 25],
    "printed_pages": [14, 15, 16],
    "scope": "所选章区分会合能解与不能解；本规则仅排除同次组合已争议或受冲却仍宣称解刑的内部矛盾。全刑组覆盖是既有模型门槛，不认证原典全部解法、刑冲有效力量、减损系数或现实结果。",
}


SINGLE_PAIR_SOURCE = {
    **SOURCE,
    "id": "ziping_unique_zi_mao_single_end_resolution_primary_v1",
    "pdf_pages": [24, 25],
    "printed_pages": [15, 16],
    "scope": "PDF24子卯逢丑、戌或会局可解刑的单端条件；只修正唯一实体子卯对，实际成立的会合须同次可核。另列一子二卯的实体规则；其余重见、非邻接、会合优先次序及冲刑互解未完成，不认证减损系数、全书符合度或现实结果。",
}

REPEATED_PAIR_SOURCE = {
    **SOURCE,
    "id": "ziping_zi_mao_repeated_entities_primary_v1",
    "pdf_pages": [24, 25],
    "printed_pages": [15, 16],
    "scope": "仅一子二卯：二卯不刑一子；同次实际会合合去一卯后，余下一子一卯仍刑。只按实体位置裁定准入与参与者，不外推一子三卯、反向重见、双重见或其他刑冲，不裁定减损幅度与全局旺衰。",
}
REPETITION_NO_PUNISHMENT = "source_repetition_no_punishment"

MONTH_OFFICER_SOURCE = {
    **SOURCE,
    "id": "ziping_bing_zi_month_officer_alternative_clash_primary_v1",
    "pdf_pages": [25],
    "printed_pages": [16],
    "scope": "仅丙日子月的月令正官条件：唯一子卯酉，子卯未被同次实际会合解刑，卯酉冲实际活动且参与者无另一活动冲或已成会合争用，才以别位卯酉冲免去子卯刑。只裁定该刑准入，不移除实际藏根，不裁定冲力、损益系数、旺衰、成格或现实结果。甲酉例原字卯日冲子的位置未裁；非邻接会合及半会夺合另待校勘。",
}
MONTH_OFFICER_CLASH_RESOLVED = "resolved_by_month_officer_alternative_clash"


def completed_combination_positions(events: Sequence[Mapping[str, Any]]) -> set[str]:
    """Affiliation, half tendencies and disputed candidates do not supply cover."""
    return {
        p
        for event in events
        if event.get("kind") in {"三会", "三合", "六合"}
        and event.get("status") in {"binding", "conditioned_transformation"}
        for p in event["positions"]
    }


def punishment_is_resolved(
    positions: Sequence[str],
    branches: Mapping[str, str],
    cover: set[str],
) -> bool:
    """Only the unique physical 子卯 pair permits one-end cover."""
    return all(p in cover for p in positions) or (
        len(positions) == 2
        and {branches[p] for p in positions} == {"子", "卯"}
        and any(p in cover for p in positions)
    )


def repeated_zi_mao_participants(
    positions: Sequence[str],
    branches: Mapping[str, str],
    cover: set[str],
) -> list[str] | None:
    """The selected text's one子/two卯 entities after actual combination cover.

    None means this source rule does not apply; the caller retains its other
    policies. An empty list means no active punishment in this exact pattern.
    No branch, root or force disappears when a seat leaves this relation.
    """
    if (
        sum(branches[p] == "子" for p in positions) != 1
        or sum(branches[p] == "卯" for p in positions) != 2
    ):
        return None
    remaining = [p for p in positions if p not in cover]
    return (
        remaining
        if len(remaining) == 2 and {branches[p] for p in remaining} == {"子", "卯"}
        else []
    )


def zi_month_officer_clash_alternative(
    positions: Sequence[str],
    branches: Mapping[str, str],
    cover: set[str],
    active_clashes: Sequence[Sequence[str]],
    *,
    day_stem: str,
) -> list[str] | None:
    """Return the actual alternative clash for the source's 丙子月官 profile.

    The selected text does not establish a universal clash/punishment priority.
    Repeated actors, completed combination cover and another active clash are
    outside this source profile and retain the caller's existing policies.
    """
    if (
        day_stem != "丙"
        or branches["month"] != "子"
        or len(positions) != 2
        or "month" not in positions
        or {branches[p] for p in positions} != {"子", "卯"}
        or any(list(branches.values()).count(branch) != 1 for branch in "子卯酉")
    ):
        return None
    actors = {p for p, branch in branches.items() if branch in "子卯酉"}
    if actors & cover:
        return None
    alternatives = [
        pair for pair in active_clashes if {branches[p] for p in pair} == {"卯", "酉"}
    ]
    if len(alternatives) != 1 or any(
        set(pair) & actors and set(pair) != set(alternatives[0])
        for pair in active_clashes
    ):
        return None
    return list(alternatives[0])
