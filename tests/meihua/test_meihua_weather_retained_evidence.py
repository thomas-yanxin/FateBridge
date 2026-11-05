"""Retain negative outcomes from issued vectors without regenerating forecasts."""

import gzip
import json
from pathlib import Path

DATA = Path(__file__).parents[1] / "data/meihua/weather_evidence"


def test_original_full_cohort_negative_result_follows_issued_labels_and_observations():
    study = json.loads((DATA / "study_identity.json").read_bytes())
    forecasts = json.loads((DATA / "issued_forecasts2008.json").read_bytes())
    source = json.loads(
        gzip.decompress((DATA / "observed_source_rows13057.json.gz").read_bytes())
    )
    observations = {row["date"]: row["expected_rain_ge0_1_mm"] for row in source}
    assert len(source) == 13057
    assert len(forecasts) == study["forecast_record_count"] == 2008
    assert (
        len({row["date"] for row in forecasts}) == study["unique_target_dates"] == 1004
    )
    rows = [
        row
        for row in forecasts
        if row["cohort"] == study["primary_cohort"]
        and row["scenario"] == study["primary_scenario"]
    ]
    assert len(rows) == len({row["date"] for row in rows}) == 273
    assert all(observations[row["date"]] is not None for row in rows)
    correct = sum(
        row["label"] == ("rain" if observations[row["date"]] else "dry") for row in rows
    )
    dry = sum(not observations[row["date"]] for row in rows)
    assert correct == study["primary_endpoint"]["correct_credit"] == 29
    assert dry == study["primary_endpoint"]["better_constant_baseline_credit"] == 158
    assert correct - dry == -129
    assert not study["primary_endpoint"]["passes_full_cohort_baselines"]
    assert not study["real_world_predictive_efficacy_established"]
    assert not study["authority_certified"]
