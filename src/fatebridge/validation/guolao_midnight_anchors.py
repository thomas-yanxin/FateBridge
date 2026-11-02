"""All named cardinal selectors, without picking the most favorable lane."""

from __future__ import annotations

from typing import Any

from fatebridge.core.guolao_midnight_anchors import (
    PROFILE,
    RATE_POLICIES,
    load_recomputed_midnight,
)


def audit_midnight_anchors() -> dict[str, Any]:
    return {
        "model_id": PROFILE,
        "all_rate_policies": {
            policy: load_recomputed_midnight(PROFILE, rate_policy=policy).audit()
            for policy in RATE_POLICIES
        },
        "best_policy_selected_by_match_or_closure": False,
        "all_source_selector_disagreements_retained": True,
        "full_source_calendar_reconstructed": False,
        "four_axis_perfect_scores_established": False,
        "real_world_predictive_efficacy_tested": False,
    }
