"""Propagate a declared set of literal-table interpretations into civil facts.

The descending-segment alternative is a conservative diagnostic assumption,
not an adjudication of the book's intended lookup. No printed cell is repaired.
"""

from __future__ import annotations

from fractions import Fraction as F
from itertools import product
from math import prod
from typing import Any

from fatebridge.core.guolao_calendar_year import (
    _fixed_qice_year_from_conjunctions,
    gujin_fixed_qice_year,
)
from fatebridge.core.guolao_conjunctions import GUJIN_COMPONENTS, source_conjunction
from fatebridge.core.guolao_cumulative_table import (
    _literal_conjunction_from_components,
    _literal_lunar_from_lookup,
)
from fatebridge.core.guolao_day_rate import _table as _rates
from fatebridge.core.guolao_day_rate import gujin45_day_rate
from fatebridge.core.guolao_intercalation import _fixed_qice_months_from_conjunctions

POLICY = "guolao_literal_adjacent_candidates_v1"
PROFILE = "gujin_literal_candidates_fixed_qice_conditional_civil_facts_research"
MAX_BRANCHES = 4096
CIVIL_FIELDS = (
    "lunation_index",
    "start_source_day_integer",
    "next_start_source_day_integer",
    "length_days",
    "principal_term_indices",
    "principal_terms",
    "sexagenary_start_day",
)


def literal_lunar_candidates(anomaly_days: F) -> dict[str, Any]:
    """Keep ascending brackets and closed descending spans, with no clipping."""
    strict = gujin45_day_rate(anomaly_days)
    data, digest = _rates()
    if digest != strict["source_data_sha256"]:
        raise ValueError("日率在同一计算中改变，不能混用来源")
    indices = (
        [168]
        if strict["whole_limit_index"] == 168
        else sorted(
            set(strict["candidate_limit_indices"])
            | set(strict["conflicting_reversed_interval_indices"])
        )
    )
    candidates = []
    for index in indices or [None]:
        lookup = dict(strict)
        row = data["rows"][index] if index is not None else None
        lookup.update(
            whole_limit_index=index,
            selected_printed_day_rate_days=(
                row["day_rate_days"]
                if row and not row["printed_empty_origin"]
                else None
            ),
            selected_effective_day_rate_days=row["day_rate_days"] if row else None,
            selected_day_rate_source_mark=(
                ("空" if row["printed_empty_origin"] else "numeric") if row else None
            ),
            empty_day_rate_origin_interpreted_as_zero=index == 0,
            next_printed_day_rate_days=(
                data["rows"][index + 1]["day_rate_days"]
                if index is not None and index < 168
                else None
            ),
            source_locator=(
                {
                    "djvu_page": row["djvu_page"],
                    "half": row["half"],
                    "limit_index": index,
                }
                if row
                else None
            ),
            candidate_policy_id=POLICY,
            conditional_candidate=True,
            descending_segment_diagnostic_assumption=(
                index in strict["conflicting_reversed_interval_indices"]
            ),
            source_lookup_adjudicated=False,
        )
        lunar = _literal_lunar_from_lookup(lookup)
        lunar["arithmetic_status"] = lunar["status"]
        lunar["status"] = "conditional_literal_candidate"
        candidates.append(lunar)
    return {
        "policy_id": POLICY,
        "strict_lookup": strict,
        "candidate_limit_indices": indices,
        "candidates": candidates,
        "missing_branch_dropped": False,
        "source_lookup_adjudicated": False,
    }


def literal_conjunction_candidates(
    zhongji_days: F, lunation_index: int
) -> dict[str, Any]:
    old = source_conjunction(zhongji_days, lunation_index, profile_id=GUJIN_COMPONENTS)
    lunar = literal_lunar_candidates(F(old["lunar"]["anomaly_phase_days_exact"]))
    candidates = []
    for row in lunar["candidates"]:
        candidate = _literal_conjunction_from_components(
            zhongji_days, lunation_index, old, row
        )
        candidate.update(
            candidate_policy_id=POLICY,
            conditional_candidate=True,
            source_lookup_adjudicated=False,
        )
        candidates.append(candidate)
    return {
        "lunation_index": lunation_index,
        "strict_lookup": lunar["strict_lookup"],
        "candidate_limit_indices": lunar["candidate_limit_indices"],
        "candidates": candidates,
    }


def _civil_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: row[k] for k in ("month_number", "is_leap_month", *CIVIL_FIELDS)}


def _civil_consensus(branches: list[dict[str, Any]]) -> dict[str, Any]:
    """Intersect facts, retaining absent and differing branches as unresolved."""
    if not branches:
        raise ValueError("空候选集不能充作全体候选一致")
    calendars = [b["calendar"] for b in branches]
    all_complete = all(c["complete_named_year_assigned"] for c in calendars)
    conflicts = []

    def shared(locator: dict[str, Any], field: str, values: list[Any]) -> Any:
        if all(v is not None and v == values[0] for v in values):
            return values[0]
        conflicts.append(
            {
                "locator": locator,
                "field": field,
                "branch_values": [
                    {"branch_id": b["branch_id"], "value": v}
                    for b, v in zip(branches, values, strict=True)
                ],
            }
        )
        return None

    rows = [c["months"] for c in calendars]
    identities = sorted(
        {(r["month_number"], r["is_leap_month"]) for rs in rows for r in rs}
    )
    months = []
    for number, leap in identities:
        locator = {"month_number": number, "is_leap_month": leap}
        matches = [
            [r for r in rs if (r["month_number"], r["is_leap_month"]) == (number, leap)]
            for rs in rows
        ]
        month = dict(locator)
        month["present_in_every_branch"] = all(len(m) == 1 for m in matches)
        for field in CIVIL_FIELDS:
            month[field] = shared(
                locator,
                field,
                [m[0].get(field) if len(m) == 1 else None for m in matches],
            )
        months.append(month)
    facts: dict[str, Any] = {"months": months}
    for field in ("month_count", "total_days"):
        values = [
            c[field] if c["complete_named_year_assigned"] else None for c in calendars
        ]
        facts[field] = shared({"scope": "whole_year"}, field, values)
    next_rows = [
        (
            _civil_row(c["next_regular_first_month"])
            if c["complete_named_year_assigned"]
            else {}
        )
        for c in calendars
    ]
    facts["next_regular_first_month"] = {
        field: shared(
            {"scope": "next_regular_first_month"},
            field,
            [r.get(field) for r in next_rows],
        )
        for field in ("month_number", "is_leap_month", *CIVIL_FIELDS)
    }
    return {
        "shared_civil_facts": facts,
        "unresolved_fields": conflicts,
        "all_branch_years_complete": all_complete,
        "complete_civil_facts_identical_under_candidate_policy": all_complete
        and not conflicts,
        "unique_conjunction_times_claimed": False,
    }


def literal_candidate_year(zhongji_days: F) -> dict[str, Any]:
    """Enumerate every declared branch; keep the strict result separately."""
    strict = gujin_fixed_qice_year(zhongji_days, conjunction_method="literal_table")
    choices = [literal_conjunction_candidates(zhongji_days, i) for i in range(18)]
    count = prod(len(c["candidates"]) for c in choices)
    result: dict[str, Any] = {
        "model_id": "guolao_literal_candidate_civil_consensus_v1",
        "policy_id": POLICY,
        "profile_id": PROFILE,
        "zhongji_days_exact": str(zhongji_days),
        "strict_calendar": strict,
        "conjunction_choice_sets": choices,
        "declared_branch_count": count,
        "enumerated_branch_count": 0,
        "branch_limit": MAX_BRANCHES,
        "branches": [],
        "shared_civil_facts": None,
        "unresolved_fields": [],
        "status": "branch_limit_exceeded_unresolved",
        "complete_civil_facts_identical_under_candidate_policy": False,
        "unique_conjunction_times_claimed": False,
        "source_lookup_adjudicated": False,
        "printed_source_cells_repaired": False,
        "all_possible_historical_interpretations_enumerated": False,
        "complete_historical_calendar_accepted": False,
        "real_world_prediction_validated": False,
        "modern_epoch_calibrated": False,
        "used_in_native_birth_chart": False,
    }
    if count > MAX_BRANCHES:
        return result
    branches = []
    for branch_id, selected in enumerate(product(*(c["candidates"] for c in choices))):

        def conjunction(middle: F, index: int) -> dict[str, Any]:
            if middle != zhongji_days:
                raise ValueError("不能把其他中积的候选用于本分支")
            selected_conjunction: dict[str, Any] = selected[index]
            return selected_conjunction

        base = _fixed_qice_months_from_conjunctions(zhongji_days, PROFILE, conjunction)
        calendar = _fixed_qice_year_from_conjunctions(zhongji_days, base, conjunction)
        branches.append(
            {
                "branch_id": branch_id,
                "selected_limit_indices": [
                    c["lunar_velocity"]["whole_limit_index"] for c in selected
                ],
                "calendar": calendar,
            }
        )
    result.update(_civil_consensus(branches))
    result.update(
        branches=branches,
        enumerated_branch_count=len(branches),
        status=(
            "civil_facts_identical_under_declared_candidates_only"
            if result["complete_civil_facts_identical_under_candidate_policy"]
            else "candidate_civil_facts_partial_or_differing"
        ),
    )
    return result
