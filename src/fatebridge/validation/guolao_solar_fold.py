"""Directed source-fold boundary probes, keeping uncovered table arguments."""

from __future__ import annotations

from fractions import Fraction as F
from typing import Any

from fatebridge.core.guolao_solar_fold import (
    PROFILES,
    TABLE_PROFILES,
    load_source_fold,
)


def audit_source_solar_fold() -> dict[str, Any]:
    profiles = {}
    for profile in PROFILES:
        model = load_source_fold(profile)
        epsilon = F(1, 100000000)
        probes = (
            F(),
            F(1),
            F(91),
            F("91.31"),
            F("91.3125"),
            model.threshold - epsilon,
            model.threshold,
            model.threshold + epsilon,
            model.half_year - epsilon,
            model.half_year,
            model.half_year + epsilon,
            2 * model.half_year - epsilon,
            2 * model.half_year,
        )
        records = []
        for table in TABLE_PROFILES:
            for side in ("inside", "outside"):
                for value in probes:
                    records.append(
                        model.sunrise(
                            value,
                            origin_reference="explicit_arithmetic_boundary_probe_not_a_real_date",
                            table_profile=table,
                            solar_side=side,
                            basis="dadu_source_table",
                        )
                    )
        profiles[profile] = {
            "fold_audit": model.audit(),
            "all_directed_probes": records,
        }
    return {
        "model_id": "named_source_solar_fold_boundary_audit_v1",
        "profiles": profiles,
        "boundary_probes_are_independent_astronomical_observations": False,
        "best_profile_selected_by_table_coverage_or_continuity": False,
        "Qizheng_witness_used_to_emend_Gujin_text": False,
        "full_original_sunrise_calendar_chain_accepted": False,
        "real_world_predictive_efficacy_tested": False,
        "four_axis_perfect_scores_established": False,
    }
