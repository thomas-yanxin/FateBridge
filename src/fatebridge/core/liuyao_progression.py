"""Chapter 29's conditional progression, separate from a structural branch pair."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any

from .liuyao_month_break import day_value_exception, month_opposition_applies
from .liuyao_relations import (
    COMBINES,
    ELEMENTS,
    branch_facts,
    element_relation,
    xunkong,
)

PROFILE: dict[str, Any] = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-progression-v8.json")
    .read_text(encoding="utf-8")
)


def both(a: bool | None, b: bool | None) -> bool | None:
    return False if False in (a, b) else (None if None in (a, b) else True)


def either(a: bool | None, b: bool | None) -> bool | None:
    return True if True in (a, b) else (None if None in (a, b) else False)


def changed_calendar_strength(
    branch: str,
    month: str,
    day_ganzhi: str,
    monthly: dict[str, Any],
    stages: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Only calendar actors reach the changed line; never import base-line roots."""
    day, element = day_ganzhi[1], ELEMENTS[branch]
    daily = element_relation(ELEMENTS[day], element)
    support = (
        monthly["monthly_supported"]
        or COMBINES[month] == branch
        or daily in ("生爻", "比和")
        or COMBINES[day] == branch
        or stages[element].get(day) in ("长生", "帝旺")
    )
    facts = branch_facts(branch, month, day, xunkong(day_ganzhi))
    harm = (
        month_opposition_applies(branch, month, day)
        or (
            element_relation(ELEMENTS[month], element) == "克爻"
            and not day_value_exception(branch, month, day)
        )
        or daily == "克爻"
    )
    supported = None if support and harm else bool(support)
    return {
        "status": (
            "contested_calendar_conditions"
            if supported is None
            else "calendar_supported" if supported else "unassisted_seasonal_weak"
        ),
        "is_supported": supported,
        "is_weak": None if supported is None else not supported,
        "scope": "只取日月旺相生扶与已列反制；原卦其他爻不向变爻立根。空破另列待填，不断变爻最终效力。",
    }


def build_progress_conditions(
    *,
    line: dict[str, Any],
    condition: dict[str, Any],
    strength: dict[str, Any],
    month: str,
    day_ganzhi: str,
    changed_monthly: dict[str, Any],
    stages: dict[str, dict[str, str]],
    event_horizon: str | None,
) -> dict[str, Any]:
    old = line["branch"]
    new = line["changed_branch"]
    pairs = dict(PROFILE["advance_pairs"])
    if not line["change"] or not (pairs.get(old) == new or pairs.get(new) == old):
        raise ValueError("Progression requires an actual moving original/changed pair")
    pair = "进神" if pairs.get(old) == new else "退神"
    original_supported = strength["is_supported"]
    original_weak = strength["is_weak"]
    original_basis = "same_run_classical_assessment"
    # Explicit seasonal-only branch for an unassisted line. This does not
    # change the global assessment or silence a weak moving line's action.
    if (
        original_supported is None
        and not strength["supports"]
        and not strength["pending_supports"]
        and not condition["monthly_strength"]["monthly_supported"]
    ):
        original_supported, original_weak = False, True
        original_basis = "unassisted_seasonal_branch_only"
    transformed = changed_calendar_strength(
        new, month, day_ganzhi, changed_monthly, stages
    )
    new_supported, new_weak = transformed["is_supported"], transformed["is_weak"]
    both_supported = both(original_supported, new_supported)
    both_weak = both(original_weak, new_weak)
    one_weak = either(original_weak, new_weak)
    one_supported = either(original_supported, new_supported)
    facts = [
        branch_facts(b, month, day_ganzhi[1], xunkong(day_ganzhi)) for b in (old, new)
    ]
    raw_empty = any(f["is_xunkong"] or f["is_month_clash"] for f in facts)
    empty = any(
        f["is_xunkong"] or month_opposition_applies(b, month, day_ganzhi[1])
        for b, f in zip((old, new), facts)
    )
    near = None if event_horizon is None else event_horizon == "near"
    # The first retreat clause has two routes: both旺相 OR actual 日月动扶.
    has_root = (
        original_supported
        if strength["supports"]
        else (None if strength["pending_supports"] else False)
    )
    supported_near = both(either(both_supported, has_root), near)
    values = (
        [both_supported, both_weak, one_weak, empty]
        if pair == "进神"
        else [supported_near, both_weak, one_supported, empty]
    )
    specs = PROFILE["clauses"][:4] if pair == "进神" else PROFILE["clauses"][4:8]
    source_url = PROFILE["source"]["url"] + "#page=123"
    clauses = [
        {
            "rule_id": spec["id"],
            "condition": spec["quote"],
            "matched": value,
            "status": (
                "unresolved" if value is None else "matched" if value else "not_matched"
            ),
            "source_url": source_url,
            **({"raw_matched": raw_empty} if index == 3 else {}),
        }
        for index, (spec, value) in enumerate(zip(specs, values))
    ]
    now: bool | None = None
    if empty:
        state = (
            "advance_waits_for_void_break_relief"
            if pair == "进神"
            else "retreat_waits_for_void_break_relief"
        )
    elif pair == "进神":
        if both_supported is True:
            state, now = "advance_supported_now", True
        elif one_weak is True:
            state = "advance_waits_for_strength"
        else:
            state = "requires_strength_resolution"
    elif supported_near is True:
        state, now = "retreat_held_for_near_event", False
    elif both_weak is True:
        state, now = "retreat_weak_now", True
    elif one_supported is True:
        state = (
            "requires_event_horizon"
            if event_horizon is None
            else "retreat_waits_for_weakness"
        )
    else:
        state = "requires_strength_resolution"
    return {
        "structural_pair": pair,
        "original_branch": old,
        "changed_branch": new,
        "original_month_strength": condition["monthly_strength"]["category"],
        "changed_month_strength": changed_monthly["category"],
        "has_void_or_month_break": raw_empty,
        "has_current_void_or_month_obstruction": empty,
        "event_horizon": event_horizon,
        "state": state,
        "condition_now": now,
        "original_supported": original_supported,
        "original_weak": original_weak,
        "original_strength_basis": original_basis,
        "original_strength_source_path": f"liuyao_evidence.conditional_analysis.classical_assessment.lines.{line['position'] - 1}.strength",
        "changed_calendar_strength": transformed,
        "clauses": clauses,
        "ruleset_id": PROFILE["ruleset_id"],
        "ruleset_version": PROFILE["ruleset_version"],
        "adjudication": "progression_conditions_only",
        "source_url": source_url,
        "source_sha256": PROFILE["source"]["sha256"],
        "textual_issues": deepcopy(PROFILE["textual_issues"]),
        "scope": "四法可同时匹配，空破优先保留待填；condition_now只表示已列进退条件，不是向外生克效力或事件成败。未给近事久远则不从天数推断。季节无扶与全局无用不同。",
    }
