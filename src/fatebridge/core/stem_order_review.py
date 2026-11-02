"""Source-local month/hour geometry, separate from adopted stem budgets."""

from copy import deepcopy
from typing import Any, Collection, Mapping, Sequence

SOURCE = {
    "id": "ziping_stem_order_month_hour_v1",
    "title": "秘本子平真诠·论生克先后分吉凶",
    "author": "沈孝瞻",
    "edition": "国家图书馆藏本 NLC416-11jh010455-35296，上海世界图书馆发行",
    "url": "https://upload.wikimedia.org/wikipedia/commons/f/fe/NLC416-11jh010455-35296_%E5%AD%90%E5%B9%B3%E7%9C%9F%E8%A9%AE.pdf",
    "source_sha256": "71402a780b0351b54edf121a51bc4a4a4ce5896496c35b954563ee06f1a6f620",
    "pdf_pages": [47, 48],
    "printed_pages": [38, 39],
    "support_scope": "原页年甲月癸日丙时戊亦论戊癸无隔而合。同章许类推；其余五合字对只列候选类推，未逐类独立校验。不认证其他格局、合绊量、成化或全章算法。",
    "independent_expert_review": "not_completed",
}


def build_stem_order_review(
    stems: Mapping[str, str],
    relations: Sequence[Mapping[str, Any]] | None,
    pair_keys: Collection[frozenset[str]],
) -> dict[str, Any]:
    """Observe glyphs and actual supplied events without changing any budget."""
    candidates = []
    if frozenset((stems["month"], stems["hour"])) in pair_keys:
        refs = (
            [
                f"assessment.relations:{i}"
                for i, event in enumerate(relations)
                if event.get("kind") == "天干合"
                and set(event.get("positions", [])) == {"month", "hour"}
            ]
            if relations is not None
            else None
        )
        candidates.append(
            {
                "positions": ["month", "hour"],
                "stems": [stems["month"], stems["hour"]],
                "four_column_distance": 2,
                "intervening_positions": ["day"],
                "intervening_stem": stems["day"],
                "source_geometry": "adjacent_in_non_day_order",
                "other_matching_stem_positions": [
                    name
                    for name in ("year", "day")
                    if any(
                        frozenset((stems[name], stems[target])) in pair_keys
                        for target in ("month", "hour")
                    )
                ],
                "recorded_relation_refs": refs,
                "effective_combination": "not_adjudicated",
            }
        )
    return {
        "method_id": "ziping_month_hour_source_review_v1",
        "source": deepcopy(SOURCE),
        "current_numeric_policy": "four_column_adjacent_binding_v6",
        "relations_status": "supplied" if relations is not None else "not_supplied",
        "candidates": candidates,
        "unrecorded_source_candidate_count": (
            sum(not row["recorded_relation_refs"] for row in candidates)
            if relations is not None
            else None
        ),
        "candidate_numeric_policy_adopted": False,
        "effective_combination": "not_adjudicated",
        "calculation_effect": "none",
        "scope": "所选原典的月时非日干邻接候选与同次事件表分别核对；未记录不等于原典判不合。日干或别干的同字匹配只列待审，不认证争合或合去。默认天干预算、根气、旺衰、司令与通关保持；原典全章先后效力及现实应期未据此算出。",
    }


def stem_order_review_snapshot_line(review: Mapping[str, Any]) -> str | None:
    """Render only the supplied factual receipt, never calculate another chart."""
    candidates = review.get("candidates")
    if not candidates:
        return None
    row = candidates[0]
    refs = row.get("recorded_relation_refs")
    status = "事件未供" if refs is None else "事件已记录" if refs else "事件未记录"
    return (
        f"原典先后复核：月时{''.join(row['stems'])}为所选原典候选，{status}；"
        "未改变默认合绊预算，合效、成化与通关仍待审。"
    )
