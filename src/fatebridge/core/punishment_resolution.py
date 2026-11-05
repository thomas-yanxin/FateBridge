"""Only completed same-run full combinations can provide punishment cover."""

from typing import Any, Mapping, Sequence

POLICY = "completed_combination_unique_pair_resolution_v2"
STRENGTH_METHOD = "season_root_revelation_relations_v12"
CURRENT_STRENGTH_METHODS = frozenset({STRENGTH_METHOD})
SOURCE = {
    "id": "ziping_completed_combination_resolution_primary_v1",
    "author": "沈孝瞻",
    "title": "秘本子平真詮·論刑沖會合解法",
    "edition": "国家图书馆藏本，上海世界图书馆发行",
    "url": "https://upload.wikimedia.org/wikipedia/commons/f/fe/NLC416-11jh010455-35296_%E5%AD%90%E5%B9%B3%E7%9C%9F%E8%A9%AE.pdf",
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
    "scope": "PDF24子卯逢丑、戌或会局可解刑的单端条件；只修正唯一实体子卯对，实际成立的会合须同次可核。重见、非邻接、会合优先次序及冲刑互解另未完成；不认证减损系数、全书符合度或现实结果。",
}


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
