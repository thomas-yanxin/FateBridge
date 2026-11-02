"""Full75 declared interpolation checks; source clock bins remain intervals."""

from __future__ import annotations

from fractions import Fraction as F
from typing import Any

from fatebridge.core.guolao_gnomon_epoch import (
    PROFILE,
    READING_PROFILE,
    SEASONS,
    load_gnomon_epoch,
)


def _audit_profile(profile: str) -> dict[str, Any]:
    model = load_gnomon_epoch(profile)
    rows = [model.triad(v["season"], int(v["case_id"])) for v in model.source["triads"]]
    means = [model.season_mean(season) for season in SEASONS]
    winter1279 = F(means[-1]["mean_source_cycle_day_exact"])
    derived1280 = (winter1279 + F("365.2425")) % 60
    paper1280 = model.source["season_means"][-1]
    return {
        "model_id": "li2013_yuanshi_complete75_three_shadow_audit_v1",
        "profile_id": profile,
        "source_data_sha256": model.fingerprint,
        "source_observations_retained": len(model.observations),
        "all75_declared_triads": rows,
        "matches_within_predeclared_printed_half_unit": sum(
            v["within_published_half_unit"] for v in rows
        ),
        "all_declared_spans_match": all(v["span_matches_published"] for v in rows),
        "five_season_means": means,
        "derived1280_epoch": {
            "winter1279_mean_source_cycle_day_exact": str(winter1279),
            "added_source_year_days_exact": "146097/400",
            "derived_cycle_day_exact": str(derived1280),
            "paper_printed_mean_cycle_day": paper1280["printed_mean_cycle_day"],
            "mean_within_published_half_unit": abs(
                derived1280 - F(paper1280["printed_mean_cycle_day"])
            )
            <= F(1, 20000),
            "fixed_original_qiying_source_cycle_day_exact": "2753/50",
            "derived_minus_original_nominal_minutes_exact": str(
                (derived1280 - F("55.06")) * 1440
            ),
            "paper_modern_minus_original_nominal_minutes_exact": str(
                (F(paper1280["printed_modern_cycle_day"]) - F("55.06")) * 1440
            ),
            "source_55_06_constant_replaced_to_fit": False,
            "paper_modern_value_recomputed_here": False,
        },
        "independent_second_collator_or_unseen_holdout": False,
        "historical_local_apparent_clock_calibrated_to_TT_or_UT1": False,
        "independent_astronomical_accuracy_certified": False,
        "native_birth_chart_or_source_phase_backfilled": False,
        "real_world_predictive_efficacy_tested": False,
        "four_axis_perfect_scores_established": False,
    }


def audit_gnomon_epoch() -> dict[str, Any]:
    literal = _audit_profile(PROFILE)
    literal["declared_postcomparison_NLC_reading"] = _audit_profile(READING_PROFILE)
    literal["original_literal_failure_overwritten_or_hidden"] = False
    literal["paper_row_number_variant_chosen_before_comparison"] = False
    return literal
