"""Conditional joint support for shared, explicitly named reconstructions.

This joins already computed alternatives. It does not choose a historical rule,
equate two people's unknown halves, or calculate a mansion from a new formula.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

MODELS = (
    "adjacent_month_short_day_assignment",
    "repeat_regular_month_first_day_assignment",
)
METHOD = "shared_hinoo_reconstruction_support_v1"


def _leaves(context: dict[str, Any]) -> list[dict[str, Any]]:
    return [leaf for leaf in context.get("calendar_candidates") or [context]]


def _precedence(context: dict[str, Any]) -> dict[str, Any] | None:
    assignment = context["profile_calculation"].get("short_month_assignment")
    value = assignment.get("leap_short_month_precedence") if assignment else None
    return {**value} if value is not None else None


def _identity(context: dict[str, Any]) -> dict[str, Any] | None:
    signatures: list[dict[str, Any]] = []
    for leaf in _leaves(context):
        profile = leaf["profile_calculation"]
        signature = {
            "calendar_profile": leaf["calendar_profile"],
            "mansion_method_id": leaf["mansion_method_id"],
            "source_bundle_sha256": profile.get("source_bundle_sha256"),
            "calendar_system": leaf["calendar_system"],
            "calendar_backend": leaf["calendar_backend"],
            "calendar_timezone": leaf["calendar_timezone"],
        }
        if not signature["source_bundle_sha256"]:
            return None
        signatures.append(signature)
    return signatures[0] if all(s == signatures[0] for s in signatures) else None


def _names(context: dict[str, Any]) -> set[str]:
    name = context["natal_su27"]
    return {name} if name else set(context.get("candidate_su27s", []))


def _states(context: dict[str, Any], model: str) -> tuple[list[dict[str, Any]], bool]:
    states: list[dict[str, Any]] = []
    covered = True
    for leaf in _leaves(context):
        selected = leaf.get("calendar_day_part")
        profile = leaf["profile_calculation"]
        assignment = profile.get("short_month_assignment")
        precedence = _precedence(leaf)
        alternatives: list[tuple[str | None, str, str]] = []
        if precedence:
            records = precedence["reconstruction_calculations"]
            if len(records) != len(MODELS) or {r["id"] for r in records} != set(MODELS):
                covered = False
                continue
            record = next(r for r in records if r["id"] == model)
            for half, key in (
                ("first_half", "first_half_calculation"),
                ("second_half", "second_half_calculation"),
            ):
                calculation = record[key]
                if calculation["source_bundle_sha256"] != profile.get(
                    "source_bundle_sha256"
                ):
                    covered = False
                    continue
                if selected is None or selected == half:
                    alternatives.append((half, calculation["direct_mansion"], model))
        elif assignment:
            for slot in assignment["slots"]:
                if selected is None or selected == slot["day_part"]:
                    for name in slot["candidate_mansions"]:
                        alternatives.append((slot["day_part"], name, slot["origin"]))
        else:
            # A non-discriminating day is compatible with either rule model.
            # Missing predecessor evidence is caught by the coverage flag below.
            alternatives.extend(
                (selected, name, "profile_result_model_independent")
                for name in sorted(_names(leaf))
            )
        actual = _names(leaf)
        if not {name for _, name, _ in alternatives}.issubset(actual):
            covered = False
        for state_half, name, origin in alternatives:
            if name in actual:
                state = {
                    "calendar_date": leaf["calendar_date"],
                    "calendar_day_part": state_half,
                    "natal_su27": name,
                    "assignment_origin": origin,
                }
                if state not in states:
                    states.append(state)
        covered = (
            covered and profile["candidate_set_complete_under_declared_reconstructions"]
        )
    return states, covered and not context.get("out_of_range_calendar_dates")


def add_shared_reconstruction_support(
    first: dict[str, Any], second: dict[str, Any], analysis: dict[str, Any]
) -> dict[str, Any]:
    """Preserve the marginal envelope and expose a separate shared-model join."""
    if not any(_precedence(leaf) for c in (first, second) for leaf in _leaves(c)):
        return analysis
    result = deepcopy(analysis)
    identity = _identity(first)
    shared: dict[str, Any] = {
        "method_id": METHOD,
        "status": "not_shared",
        "model_ids": list(MODELS),
        "model_identity": identity,
        "assumption": "仅在双方共同采用同一套已声明现代重建的条件下连接；不证明古代各时期规则统一，也不裁定原典优先次序。",
        "person_half_days_independent": True,
        "source_priority_established": False,
        "historical_uniformity_established": False,
        "unconstrained_row_count": len(analysis["rows"]),
        "supported_row_count": None,
        "unsupported_row_count": None,
        "support_coverage_complete": False,
    }
    result["shared_reconstruction_analysis"] = shared
    if identity is None or identity != _identity(second):
        shared["reason"] = "profile_algorithm_source_or_calendar_identity_not_shared"
        return result
    supports: dict[tuple[str, str], list[dict[str, Any]]] = {}
    complete = analysis["candidate_set_complete_within_profile"]
    marginal_coverage: list[set[tuple[str, str]]] = [set(), set()]
    for model in MODELS:
        left, left_complete = _states(first, model)
        right, right_complete = _states(second, model)
        complete = complete and left_complete and right_complete
        for index, states in enumerate((left, right)):
            marginal_coverage[index].update(
                (s["calendar_date"], s["natal_su27"]) for s in states
            )
        for a in left:
            for b in right:
                key = (a["natal_su27"], b["natal_su27"])
                support = {"reconstruction_id": model, "person1": a, "person2": b}
                if support not in supports.setdefault(key, []):
                    supports[key].append(support)
    for index, context in enumerate((first, second)):
        expected = {
            (leaf["calendar_date"], name)
            for leaf in _leaves(context)
            for name in _names(leaf)
        }
        complete = complete and marginal_coverage[index] == expected
    shared["support_coverage_complete"] = complete
    if result["status"] == "not_needed":
        shared["status"] = "not_needed" if complete else "incomplete"
        shared["resolved_support"] = [s for values in supports.values() for s in values]
        shared["reason"] = "resolved_mansions_do_not_establish_a_reconstruction_model"
        return result
    annotated = []
    for row in result["rows"]:
        key = (row["person1_su27"], row["person2_su27"])
        row["joint_support"] = deepcopy(supports.get(key, []))
        row["shared_reconstruction_ids"] = list(
            dict.fromkeys(s["reconstruction_id"] for s in row["joint_support"])
        )
        row["joint_support_status"] = (
            "supported"
            if row["joint_support"]
            else (
                "unsupported_within_enumerated_shared_models"
                if complete
                else "not_determined"
            )
        )
        annotated.append(row)
    result["unconstrained_rows"] = deepcopy(annotated)
    if not complete:
        shared["status"] = "incomplete"
        shared["reason"] = (
            "missing_context_or_incomplete_model_branch_coverage_no_rows_pruned"
        )
        result["candidate_set_complete_within_profile"] = False
        return result
    result["rows"] = [r for r in annotated if r["joint_support"]]
    for row in result["rows"]:
        # These are projections of actual joint supports, not independent lists
        # to be combined again. The full records above retain the dependency.
        for label in ("person1", "person2"):
            row[label + "_calendar_dates"] = list(
                dict.fromkeys(s[label]["calendar_date"] for s in row["joint_support"])
            )
    shared["status"] = "applied"
    shared["supported_row_count"] = len(result["rows"])
    shared["unsupported_row_count"] = len(annotated) - len(result["rows"])
    shared["reason"] = (
        "union_of_same_model_cartesian_products_not_cartesian_product_of_marginal_unions"
    )
    result["scope"] = (
        "rows仅列双方共同采用同一套已声明现代重建时有支持的条件组合；"
        "完整无约束外包络保留在unconstrained_rows。无共同模型支持不等于原典禁止或历史不可能。"
        "日期及半日分别未知，完整支持记录不得再次独立交叉。未裁定主宿、模型或确定相性。"
    )
    return result
