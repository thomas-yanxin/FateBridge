"""Refine observed multiple dependency changes without claiming a time oracle.

The initial finite grid/station samples remain essential: this cannot detect an
unobserved reversal or prove that any leaf interval contains just one event.
"""

from __future__ import annotations

from typing import Any, Callable

METHOD_ID = "human_design_observed_joint_transition_refinement_v2"
BRACKET_SECONDS = 0.0002
MAX_ADDITIONAL_EVALUATIONS = 4096
DIRECT_BODIES = (
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
    "NorthNode",
)
DEPENDENCY_ORDER = tuple(
    (side, body) for side in ("personality", "design") for body in DIRECT_BODIES
)
SCOPE = "仅细化初始有限样本已观察到两个或更多独立门线／Variable Tone／人格Color依赖变化的区间，并保存共同取值。日地及节点对点不重复计事件，同一源星体的Color和Tone也不拆成两个依赖；未分开区间保留，不认证连续稳定、未采到的转向或天文真实性。"


def dependency_projection(activations: dict[str, Any]) -> tuple[tuple[Any, ...], ...]:
    """Exactly the independent inputs to a coherent gate/line/Tone snapshot."""
    bodies = {
        side: {a["body"]: a for a in activations[side]}
        for side in ("personality", "design")
    }
    return tuple(
        (
            bodies[side][body]["gate"],
            bodies[side][body]["line"],
            bodies[side][body]["tone"] if body in {"Sun", "NorthNode"} else None,
            (
                bodies[side][body].get("color")
                if side == "personality" and body in {"Sun", "NorthNode"}
                else None
            ),
        )
        for side, body in DEPENDENCY_ORDER
    )


def changed_dependencies(first: Any, second: Any) -> int:
    return sum(a != b for a, b in zip(first, second))


def refinement_summary(
    initial_count: int,
    additional_count: int,
    root_count: int,
    state_count: int,
    unresolved_count: int,
) -> dict[str, Any]:
    return {
        "method_id": METHOD_ID,
        "status": (
            "no_multiple_dependency_change_observed"
            if not root_count
            else (
                "some_multiple_dependency_brackets_unresolved"
                if unresolved_count
                else "observed_multiple_dependency_brackets_refined"
            )
        ),
        "initial_evaluation_count": initial_count,
        "additional_evaluation_count": additional_count,
        "candidate_interval_count": root_count,
        "distinct_dependency_states": state_count,
        "unresolved_multiple_dependency_brackets": unresolved_count,
        "bracket_target_seconds": BRACKET_SECONDS,
        "maximum_additional_evaluations": MAX_ADDITIONAL_EVALUATIONS,
        "continuous_interval_certified": False,
        "scope": SCOPE,
    }


def refine_joint_transitions(
    cache: dict[float, dict[str, Any]],
    at: Callable[[float], dict[str, Any]],
) -> dict[str, Any]:
    """Bisect brackets containing at least two changed independent inputs.

    All evaluated midpoints remain in the caller's chart cache, so subsequent
    variant construction uses the actual complete chart, never a mixed state.
    """
    states: list[tuple[tuple[Any, ...], ...]] = []
    ids: dict[tuple[tuple[Any, ...], ...], int] = {}

    def state(chart: dict[str, Any]) -> int:
        value = dependency_projection(chart["activations"])
        if value not in ids:
            ids[value] = len(states)
            states.append(value)
        return ids[value]

    seeds = [(jd, state(cache[jd])) for jd in sorted(cache)]
    initial_count = len(cache)
    nodes: list[dict[str, Any]] = []
    additional = unresolved = 0

    def refine(lo: float, hi: float, left: int, right: int) -> int:
        nonlocal additional, unresolved
        index = len(nodes)
        node: dict[str, Any] = {
            "start_tt": lo,
            "end_tt": hi,
            "left_state": left,
            "right_state": right,
        }
        nodes.append(node)
        count = changed_dependencies(states[left], states[right])
        mid = lo + (hi - lo) / 2
        if count < 2:
            node["outcome"] = "at_most_one_changed_dependency_observed"
        elif (hi - lo) * 86400 <= BRACKET_SECONDS or mid in (lo, hi):
            node["outcome"] = "unseparated_at_TT_resolution"
            unresolved += 1
        elif additional >= MAX_ADDITIONAL_EVALUATIONS:
            node["outcome"] = "evaluation_budget_exhausted"
            unresolved += 1
        else:
            midpoint = state(at(mid))
            additional += 1
            node.update(outcome="split", midpoint_tt=mid, midpoint_state=midpoint)
            node["children"] = [
                refine(lo, mid, left, midpoint),
                refine(mid, hi, midpoint, right),
            ]
        return index

    roots = [
        refine(lo, hi, left, right)
        for (lo, left), (hi, right) in zip(seeds, seeds[1:])
        if changed_dependencies(states[left], states[right]) >= 2
    ]
    if len(cache) != initial_count + additional:
        raise RuntimeError("联合过渡细查的缓存与实际计算计数不一致")
    return {
        "summary": refinement_summary(
            initial_count, additional, len(roots), len(states), unresolved
        ),
        "dependency_order": [list(pair) for pair in DEPENDENCY_ORDER],
        "states": [[list(row) for row in value] for value in states],
        "initial_samples": [list(row) for row in seeds],
        "roots": roots,
        "nodes": nodes,
    }
