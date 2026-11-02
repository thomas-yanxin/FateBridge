"""Coherent interpretation evidence for the actual numeric root candidates.

These are conditional mechanical readings, not a physical uncertainty envelope.
Unchanged personality recipients still depend on both sides' fixing donors.
"""

from copy import deepcopy
from math import isfinite
from typing import Any

from fatebridge.core.human_design_depth import cross_identifier
from fatebridge.core.human_design_joint import JointSnapshotCache, joint_changes
from fatebridge.core.human_design_mechanics import bodygraph
from fatebridge.utils.json_digest import digest

METHOD = "human_design_root_endpoint_interpretations_v1"
SCOPE = "每个端点固定同一人格激活，使用该端点全部13项设计激活，独立核对双侧26项固定机制、桥接完整门集、回路拓扑和角色依据。calculation_path与basis均相对于该候选盘（人格来自外层原盘，设计由同索引evaluations重建），不指所选主盘；before/after分别指较早/较晚TT。固定记录SHA绑定完整26项含reading记录，可由原始位置纯重建；不是签名或原生真实性证明。不把固定机制核验当完整384线线义验收，不拼接端点，不认证物理误差、连续稳定或预测。"
FAMILY_SCOPE = "每次比较固定外层原盘的同一人格激活，逐盘核对双侧26项固定机制、桥接完整门集、回路拓扑和角色依据。before为所选主盘、after为当前数值候选盘，不按时刻重排；实际TT、时序关系与设计来源见comparison_basis。所选设计来自外层activations.design，当前候选设计由当前family索引的native_positions重建，不是同索引端点evaluations。calculation_path与basis相对于各自候选盘。固定记录SHA绑定完整26项含reading记录，可由原始位置纯重建；不是签名或原生真实性证明。不把固定机制核验当完整384线线义验收，不拼接候选，不认证物理误差、连续稳定或预测。"


def family_comparison_basis(
    epochs: tuple[float, float] | None, family_index: int | None
) -> dict[str, Any]:
    if (
        type(epochs) is not tuple
        or len(epochs) != 2
        or any(type(tt) is not float or not isfinite(tt) for tt in epochs)
        or type(family_index) is not int
        or family_index < 0
    ):
        raise ValueError("Invalid selected-to-candidate comparison context")
    selected, candidate = epochs
    return {
        "order": "selected_then_candidate",
        "personality_path": "activations.personality",
        "before": {
            "candidate_index": 0,
            "role": "selected",
            "jd_tt": selected,
            "design_path": "activations.design",
        },
        "after": {
            "candidate_index": 1,
            "role": "candidate",
            "jd_tt": candidate,
            "design_path": (
                "design_solver.numerical_precision.local_root_family."
                f"candidates[{family_index}].native_positions"
            ),
        },
        "candidate_time_relation": (
            "earlier"
            if candidate < selected
            else "later" if candidate > selected else "same"
        ),
        "calculation_paths_relative_to_each_candidate": True,
    }


def candidate_chart(personality: list[dict], design: list[dict]) -> dict[str, Any]:
    """Keep incomplete/unsupported profile candidates explicit, never repair them."""
    suns = [
        next(a for a in rows if a["body"] == "Sun") for rows in (personality, design)
    ]
    profile = f"{suns[0]['line']}/{suns[1]['line']}"
    angle = (
        "juxtaposition"
        if profile == "4/1"
        else "right" if suns[0]["line"] <= 4 else "left"
    )
    gates = [
        next(a["gate"] for a in rows if a["body"] == body)
        for rows in (personality, design)
        for body in ("Sun", "Earth")
    ]
    return {
        "activations": {"personality": personality, "design": design},
        "bodygraph": bodygraph(
            (a["gate"] for a in personality), (a["gate"] for a in design)
        ),
        "profile": profile,
        "incarnation_cross": {
            "gates": gates,
            "order": [
                "personality_sun",
                "personality_earth",
                "design_sun",
                "design_earth",
            ],
            "angle": angle,
            **cross_identifier(gates[0], angle),
        },
    }


def root_interpretations(
    personality: list[dict],
    designs: list[list[dict]],
    *,
    comparison_epochs: tuple[float, float] | None = None,
    family_candidate_index: int | None = None,
) -> dict[str, Any]:
    comparison = None
    if comparison_epochs is not None or family_candidate_index is not None:
        if len(designs) != 2:
            raise ValueError("Selected-to-candidate comparison requires two charts")
        comparison = family_comparison_basis(comparison_epochs, family_candidate_index)
    cache = JointSnapshotCache()
    snapshots = [
        cache.snapshot(candidate_chart(personality, design)) for design in designs
    ]
    candidates = []
    for snapshot in snapshots:
        depth = snapshot["depth_evidence"]
        candidates.append(
            {
                "line_fixings_sha256": digest(depth["line_fixings"]),
                "fixing_state_columns": ["side", "body", "status", "fixing_state"],
                "fixing_states": [
                    [row[k] for k in ("side", "body", "status", "fixing_state")]
                    for row in depth["line_fixings"]
                ],
                **{
                    k: deepcopy(depth[k])
                    for k in (
                        "fixing_summary",
                        "fixing_policy",
                        "channel_identifiers",
                        "source_url",
                        "source_pdf_sha256",
                        "fixing_rule_source",
                        "node_fixing_exclusion_source",
                    )
                },
                **{
                    k: deepcopy(snapshot[k])
                    for k in (
                        "definition_bridging",
                        "circuitry",
                        "profile_evidence",
                    )
                },
            }
        )
    changes = joint_changes(snapshots[0], snapshots[-1])
    changed = [k for k in candidates[0] if candidates[0][k] != candidates[-1][k]]
    records = changes["line_fixing_changes"]
    summary = {
        "changed_fields": changed,
        "line_fixing_record_change_count": len(records),
        "line_fixing_state_change_count": sum(
            r["fixing_state_changed"] for r in records
        ),
        "personality_fixing_record_change_count": sum(
            r["side"] == "personality" for r in records
        ),
        **{
            k: changes[k]
            for k in (
                "definition_bridging_changed",
                "minimum_bridge_count_changed",
                "minimum_bridge_sets_changed",
            )
        },
        "circuitry_changed": "circuitry" in changed,
        "profile_evidence_changed": "profile_evidence" in changed,
        "complete_line_meanings_accepted": False,
    }
    return {
        "method_id": METHOD,
        "candidates": candidates,
        "line_fixing_changes": deepcopy(records),
        "summary": summary,
        "scope": FAMILY_SCOPE if comparison is not None else SCOPE,
        **({"comparison_basis": comparison} if comparison is not None else {}),
    }


def root_interpretation_reading(proof: dict[str, Any]) -> str:
    summary = proof["summary"]
    text = (
        "端点解释逐盘核对双侧26项固定机制："
        f"{summary['line_fixing_record_change_count']}项完整依据记录有差异，"
        f"其中{summary['line_fixing_state_change_count']}项触发状态改变，"
        f"{summary['personality_fixing_record_change_count']}项位于人格侧。"
    )
    if summary["definition_bridging_changed"]:
        text += "假设桥接的完整门集或结构有差异，不能只比较方案数量。"
    if summary["circuitry_changed"]:
        text += "回路／整合拓扑证据有差异。"
    if summary["profile_evidence_changed"]:
        text += "角色结构依据有差异，未支持的组合保留未完成状态。"
    return (
        text + "这是候选计算的条件解释；固定极性不代表吉凶，完整384线原典线义仍未验收。"
    )
