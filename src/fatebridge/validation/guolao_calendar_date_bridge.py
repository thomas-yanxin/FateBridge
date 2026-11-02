"""Published-label checks and conditional historical date-label candidates."""

from __future__ import annotations

from fractions import Fraction as F
from typing import Any

from fatebridge.core.guolao_calendar_date_bridge import (
    COUNTER_BASIS,
    PROFILE,
    SEARCH_POLICY,
    calendar_label_noon_jdn,
    load_calendar_date_bridge,
)


def audit_calendar_date_bridge() -> dict[str, Any]:
    model = load_calendar_date_bridge(PROFILE)
    hko = []
    for row in model.source["hko31_literal_day_labels"]:
        y, m, d = map(int, row["gregorian_date"].split("-"))
        calculated = model.label(y, m, d, calendar="proleptic_gregorian")
        hko.append(
            {
                **row,
                "calculated": calculated,
                "matches": calculated["ganzhi"] == row["printed_ganzhi"],
            }
        )
    usno = []
    for row in model.source["usno5_published_examples"]:
        serial = calendar_label_noon_jdn(*row["date"], calendar=row["calendar"])
        value = F(serial) - F(1, 2) + F(row["ut1_fraction"])
        usno.append(
            {**row, "calculated_jd_exact": str(value), "matches": value == F(row["jd"])}
        )
    return {
        "model_id": "published_ganzhi_and_conditional_source_date_audit_v1",
        "profile_id": PROFILE,
        "source_data_sha256": model.fingerprint,
        "hko31_label_checks": hko,
        "hko_published_anchor_count": 1,
        "hko_remaining30_are_unseen_holdout": False,
        "usno5_published_document_checks": usno,
        "usno_live_api_results_obtained": False,
        "sinica_live_conversion_obtained": False,
        "winter_candidates": [
            model.winter_candidates(source_year=y, search_policy=SEARCH_POLICY)
            for y in (1281, 1599, 1608)
        ],
        "named318_counter_probes": [
            model.source_counter_label(
                F(x),
                source_year=1599,
                search_policy=SEARCH_POLICY,
                counter_basis=COUNTER_BASIS,
            )
            for x in ("42", "130", "130.98875", "131", "318", "318.41265", "319", "407")
        ],
        "ancient_clock_to_modern_epoch_accepted": False,
        "independent_astronomical_winter_observations_used": False,
        "real_world_predictive_efficacy_tested": False,
        "four_axis_perfect_scores_established": False,
    }
