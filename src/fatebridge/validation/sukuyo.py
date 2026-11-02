"""Run-bound Sukuyo quotations with mandatory interpretation context.

Validating an isolated favorable clause is insufficient on a conflicted day.
This checker requires complete context groups, but never certifies free-text
semantic fidelity. A human or separate semantic review must examine the prose.
"""

from __future__ import annotations

from typing import Any, Literal

from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims

Focus = Literal["compatibility", "day", "activity", "clothing", "astronomy"]


def required_quote_paths(focus: Focus) -> tuple[str, ...]:
    if focus == "compatibility":
        return (
            "status",
            "su27_basis",
            "person1",
            "person2",
            "person1_to_person2",
            "person2_to_person1",
            "candidate_relation_analysis",
            "pair",
            "interpretation_contract",
            "rulesets",
        )
    common = (
        "sukuyo.calendar",
        "sukuyo.day_mansion",
        "sukuyo.conjunction_doctrine",
        "sukuyo.palace_reference",
        "rulesets",
    )
    if focus in {"day", "activity", "clothing"}:
        return (
            *common,
            "sukuyo.calendar_day",
            "sukuyo.weekday",
            "sukuyo.nature",
            "sukuyo.personal_day",
            "sukuyo.six_palace_reference",
            "sukuyo.taibai_direction_reference",
            "sukuyo.activity_assessment",
            "sukuyo.lower_mansion_day",
            "sukuyo.lower_methods",
            "sukuyo.directional_travel",
            "sukuyo.special_day_evidence",
            "sukuyo.candidate_days",
            *(("sukuyo.clothing_reference",) if focus == "clothing" else ()),
        )
    if focus == "astronomy":
        return (*common, "astronomy", "params")
    raise ValueError("未知宿曜取证主题")


def verify_sukuyo_context_claims(
    payload: dict[str, Any],
    claims: list[CalculationClaim],
    *,
    focus: Focus,
) -> dict[str, Any]:
    required = list(required_quote_paths(focus))
    day = payload.get("sukuyo") or {}
    if (
        focus != "compatibility"
        and (
            day.get("clothing_reference") is not None
            or any(
                row.get("clothing_reference") is not None
                for row in day.get("candidate_days") or []
            )
        )
        and "sukuyo.clothing_reference" not in required
    ):
        required.append("sukuyo.clothing_reference")
    report = verify_calculation_claims(payload, claims)
    errors = list(report["errors"])
    tool = (payload.get("run_metadata") or {}).get("tool_name")
    expected = "sukuyo_compatibility" if focus == "compatibility" else "suzhan"
    if tool != expected:
        errors.append({"code": "wrong_sukuyo_tool", "expected": expected})
    paths = [c.path for c in claims]
    if len(paths) != len(set(paths)):
        errors.append({"code": "duplicate_quote_path"})
    for path in required:
        if path not in paths:
            errors.append({"code": "missing_interpretation_context", "path": path})
    return {
        "method_id": "same_run_sukuyo_context_quotes_v4",
        "status": "rejected" if errors else "verified_context_complete_quotes",
        "focus": focus,
        "required_paths": list(required),
        "checked_claim_count": len(claims),
        "errors": errors,
        "semantic_review_required": True,
        "authority_certified": False,
        "scope": "核验同run完整结果及必要上下文，防止只摘宜条、遗漏相反方向或隐藏闰月/昼夜条件；不认证自由文本语义、原典成立或现实效力。可信原始回执及语义盲评仍须另行核验。",
    }
