"""The full named policy matrix, including unassigned source midnights."""

from __future__ import annotations

from collections import Counter
from itertools import product
from typing import Any

from fatebridge.core.guolao_daily_solar import POLICIES
from fatebridge.core.guolao_midnight_anchors import RATE_POLICIES
from fatebridge.core.guolao_solar_fold import PROFILES as FOLD_PROFILES
from fatebridge.core.guolao_solar_fold import TABLE_PROFILES
from fatebridge.core.guolao_source_solar_day import (
    PROFILE,
    SIDE_POLICY,
    load_named_source_solar_day,
)


def audit_named_source_solar_day() -> dict[str, Any]:
    matrix = []
    for rate, daily, fold, table in product(
        RATE_POLICIES, POLICIES, FOLD_PROFILES, TABLE_PROFILES
    ):
        model = load_named_source_solar_day(
            PROFILE,
            anchor_rate_policy=rate,
            daily_policy=daily,
            fold_profile=fold,
            table_profile=table,
            side_policy=SIDE_POLICY,
            basis="dadu_source_table",
        )
        rows = [model.day(n) for n in range(366)]
        matrix.append(
            {
                **model.audit(),
                "all366_day_statuses": [
                    {
                        "index": q["source_day_index"],
                        "status": q["status"],
                        "selected_side": q["solar_side_reconstruction"][
                            "selected_side"
                        ],
                        "folded_argument_exact": q["folded_sunrise_argument"],
                        "source_sunrise_fraction_exact": q[
                            "usable_source_sunrise_fraction_exact"
                        ],
                    }
                    for q in rows
                ],
                "status_counts": dict(Counter(q["status"] for q in rows)),
                "all_partial_records": [q for q in rows if q["status"] != "calculated"],
                "coverage_count_used_as_accuracy_score": False,
            }
        )
    return {
        "model_id": PROFILE,
        "all24_policy_configurations": matrix,
        "source_midnight_cases_retained": 24 * 366,
        "best_configuration_selected_using_coverage_or_matching": False,
        "origin_or_side_reconstruction_accepted_as_full_original": False,
        "physical_sunrise_or_real_world_prediction_validated": False,
        "four_axis_perfect_scores_established": False,
    }
