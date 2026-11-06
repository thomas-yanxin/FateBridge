"""Audit finite refinement trees and their same-run projected states.

This checks a mathematical trace, not the truth of a state's astronomical TT.
"""

from __future__ import annotations

import math
from typing import Any

from fatebridge.core.human_design_transition import (
    BRACKET_SECONDS,
    DEPENDENCY_ORDER,
    MAX_ADDITIONAL_EVALUATIONS,
    changed_dependencies,
    dependency_projection,
    refinement_summary,
)
from fatebridge.core.public_output import same_public_value as _same_value


def verify_transition_trace(
    report: dict[str, Any],
    variants: list[dict[str, Any]],
    sampling: dict[str, Any],
    nominal_tt: float,
    radius_seconds: int,
    grid_step_seconds: int,
) -> dict[str, Any]:
    try:
        if set(report) != {
            "summary",
            "dependency_order",
            "states",
            "initial_samples",
            "roots",
            "nodes",
        }:
            raise ValueError("unexpected_trace_fields")
        if report["dependency_order"] != [list(x) for x in DEPENDENCY_ORDER]:
            raise ValueError("dependency_order_mismatch")
        states = report["states"]
        if not isinstance(states, list) or not states:
            raise ValueError("missing_states")
        for state in states:
            if not isinstance(state, list) or len(state) != len(DEPENDENCY_ORDER):
                raise ValueError("invalid_state")
            for (side, body), values in zip(DEPENDENCY_ORDER, state):
                if not isinstance(values, list) or len(values) != 4:
                    raise ValueError("invalid_dependency")
                if any(
                    type(v) is not int or not 1 <= v <= limit
                    for v, limit in zip(values[:2], (64, 6))
                ):
                    raise ValueError("invalid_gate_line")
                tone = values[2]
                if body in {"Sun", "NorthNode"}:
                    if type(tone) is not int or not 1 <= tone <= 6:
                        raise ValueError("invalid_tone")
                elif tone is not None:
                    raise ValueError("extra_tone_dependency")
                color = values[3]
                if side == "personality" and body in {"Sun", "NorthNode"}:
                    if type(color) is not int or not 1 <= color <= 6:
                        raise ValueError("invalid_personality_color")
                elif color is not None:
                    raise ValueError("extra_color_dependency")
        state_set = {tuple(tuple(row) for row in value) for value in states}
        if len(state_set) != len(states) or state_set != {
            dependency_projection(row["value"]["activations"]) for row in variants
        }:
            raise ValueError("states_not_equal_same_run_variants")

        def state_id(value: Any) -> int:
            if type(value) is not int or not 0 <= value < len(states):
                raise ValueError("invalid_state_id")
            return value

        def epoch(value: Any) -> float:
            if type(value) not in {int, float} or not math.isfinite(value):
                raise ValueError("invalid_tt")
            return float(value)

        seeds = report["initial_samples"]
        if not isinstance(seeds, list) or len(seeds) < 2:
            raise ValueError("missing_initial_samples")
        for row in seeds:
            if not isinstance(row, list) or len(row) != 2:
                raise ValueError("invalid_initial_sample")
            epoch(row[0])
            state_id(row[1])
        times = [float(row[0]) for row in seeds]
        if any(a >= b for a, b in zip(times, times[1:])):
            raise ValueError("initial_samples_not_ordered")
        grid = [
            nominal_tt + offset / 86400
            for offset in range(-radius_seconds, radius_seconds + 1, grid_step_seconds)
        ]
        if times[0] != grid[0] or times[-1] != grid[-1] or not set(grid) <= set(times):
            raise ValueError("initial_grid_missing_or_outside_interval")
        expected_roots = [
            (lo, hi, left, right)
            for (lo, left), (hi, right) in zip(seeds, seeds[1:])
            if changed_dependencies(states[left], states[right]) >= 2
        ]
        roots, nodes = report["roots"], report["nodes"]
        if (
            not isinstance(roots, list)
            or not isinstance(nodes, list)
            or len(roots) != len(expected_roots)
        ):
            raise ValueError("candidate_root_coverage_mismatch")
        next_index = splits = unresolved = 0
        visited_states = {state_id(row[1]) for row in seeds}
        midpoint_times: set[float] = set()

        def walk(index: Any, lo: float, hi: float, left: int, right: int) -> None:
            nonlocal next_index, splits, unresolved
            if (
                type(index) is not int
                or index != next_index
                or not 0 <= index < len(nodes)
            ):
                raise ValueError("invalid_or_reused_tree_node")
            next_index += 1
            node = nodes[index]
            base = {
                "start_tt": lo,
                "end_tt": hi,
                "left_state": left,
                "right_state": right,
            }
            if any(not _same_value(node.get(k), value) for k, value in base.items()):
                raise ValueError("tree_boundary_or_state_mismatch")
            midpoint = lo + (hi - lo) / 2
            multiple = changed_dependencies(states[left], states[right]) >= 2
            if not multiple:
                expected = {
                    **base,
                    "outcome": "at_most_one_changed_dependency_observed",
                }
            elif (hi - lo) * 86400 <= BRACKET_SECONDS or midpoint in (lo, hi):
                unresolved += 1
                expected = {**base, "outcome": "unseparated_at_TT_resolution"}
            elif splits >= MAX_ADDITIONAL_EVALUATIONS:
                unresolved += 1
                expected = {**base, "outcome": "evaluation_budget_exhausted"}
            else:
                middle = state_id(node["midpoint_state"])
                children = node["children"]
                if not isinstance(children, list) or len(children) != 2:
                    raise ValueError("missing_partition_children")
                if midpoint in midpoint_times or midpoint in times:
                    raise ValueError("reused_midpoint_evaluation")
                midpoint_times.add(midpoint)
                visited_states.add(middle)
                splits += 1
                expected = {
                    **base,
                    "outcome": "split",
                    "midpoint_tt": midpoint,
                    "midpoint_state": middle,
                    "children": children,
                }
                if not _same_value(node, expected):
                    raise ValueError("split_trace_mismatch")
                walk(children[0], lo, midpoint, left, middle)
                walk(children[1], midpoint, hi, middle, right)
                return
            if not _same_value(node, expected):
                raise ValueError("terminal_trace_mismatch")

        for index, args in zip(roots, expected_roots):
            walk(index, *args)
        if next_index != len(nodes) or visited_states != set(range(len(states))):
            raise ValueError("unreachable_trace_or_state")
        expected_summary = refinement_summary(
            len(seeds), splits, len(roots), len(states), unresolved
        )
        if not _same_value(report["summary"], expected_summary):
            raise ValueError("refinement_summary_mismatch")
        if (
            type(sampling["total_evaluation_count"]) is not int
            or sampling["total_evaluation_count"] != len(seeds) + splits
            or type(sampling["grid_sample_count"]) is not int
            or sampling["grid_sample_count"] != len(grid)
            or type(sampling["additional_evaluation_count"]) is not int
            or sampling["additional_evaluation_count"]
            != len(seeds) + splits - len(grid)
        ):
            raise ValueError("evaluation_counts_mismatch")
    except (
        KeyError,
        TypeError,
        ValueError,
        IndexError,
        AttributeError,
        OverflowError,
    ) as error:
        return {"status": "rejected", "errors": [str(error)]}
    return {
        "status": "verified_local_refinement_trace",
        "errors": [],
        "astronomical_witness_certified": False,
        "scope": "仅核对有限取样树、计数及同次联合投影集合；不认证TT天文坐标、未观测事件排除或连续区间穷尽。",
    }
