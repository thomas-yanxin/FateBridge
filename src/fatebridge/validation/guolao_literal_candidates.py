"""Internal coverage of the predeclared literal-candidate policy, not accuracy."""

from __future__ import annotations

from fractions import Fraction as F
from typing import Any

from fatebridge.core.guolao_historical import shoushi_winter_cycle
from fatebridge.core.guolao_literal_candidates import POLICY, literal_candidate_year


def audit_literal_candidate_grid(start: int, stop: int) -> dict[str, Any]:
    if any(type(v) is not int for v in (start, stop)) or not 0 <= start < stop <= 400:
        raise ValueError("诊断范围须为0至400内的非空整数区间，前含后不含")
    rows = []
    for elapsed in range(start, stop):
        result = literal_candidate_year(shoushi_winter_cycle(elapsed).zhongji_days)
        choices = result["conjunction_choice_sets"]
        varying = [c["lunation_index"] for c in choices if len(c["candidates"]) > 1]
        spreads = []
        for c in choices:
            offsets = [
                candidate["research_conjunction_offset_from_winter_days_exact"]
                for candidate in c["candidates"]
            ]
            known = [F(o) for o in offsets if o is not None]
            if len(known) > 1:
                spreads.append(
                    {
                        "lunation_index": c["lunation_index"],
                        "time_spread_days_exact": str(max(known) - min(known)),
                        "missing_time_count": len(offsets) - len(known),
                    }
                )
        rows.append(
            {
                "elapsed_years": elapsed,
                "strict_year_complete": result["strict_calendar"][
                    "complete_named_year_assigned"
                ],
                "strict_reason": result["strict_calendar"]["reason"],
                "declared_branch_count": result["declared_branch_count"],
                "enumerated_branch_count": result["enumerated_branch_count"],
                "varying_lunation_indices": varying,
                "conditional_time_spreads": spreads,
                "conditional_civil_facts_identical": result[
                    "complete_civil_facts_identical_under_candidate_policy"
                ],
                "unresolved_fields": result["unresolved_fields"],
                "status": result["status"],
            }
        )
    return {
        "model_id": "guolao_literal_candidate_coverage_audit_v1",
        "policy_id": POLICY,
        "elapsed_year_range": [start, stop],
        "year_count": len(rows),
        "strict_complete_year_count": sum(r["strict_year_complete"] for r in rows),
        "conditional_civil_consensus_count": sum(
            r["conditional_civil_facts_identical"] for r in rows
        ),
        "rows": rows,
        "internal_coverage_only": True,
        "strict_partial_years_reclassified_as_historically_resolved": False,
        "historical_reference_facts_added": 0,
        "real_world_prediction_subjects": 0,
        "historical_accuracy_validated": False,
        "real_world_prediction_validated": False,
    }
