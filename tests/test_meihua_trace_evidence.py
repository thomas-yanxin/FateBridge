"""Synthetic source-integrity failures must never turn unknown traces into dry days."""

import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from fatebridge.validation import meihua_weather_prospective as prospective
from fatebridge.validation.meihua_weather_study import (
    evaluate_weather_cohort,
    parse_hko_rainfall,
)
from tests.test_meihua_weather_prospective import AFTER, BEFORE, run, sample

REFERENCE = json.loads(
    (
        Path(__file__).parent / "fixtures/meihua-trace-evidence-v1/reference.json"
    ).read_bytes()
)


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda row: row["id"])
def test_independent_trace_evidence_reference(case):
    def parse():
        return parse_hko_rainfall(
            case["csv"].encode("utf-8-sig"),
            start=date(2025, 1, 1),
            end=date(2026, 1, 1),
        )

    if case["expected_error"]:
        with pytest.raises(ValueError):
            parse()
        return
    observation = parse()[date(2025, 1, 1)]
    assert observation.status == case["expected_status"]
    assert (
        observation.occurred(Decimal(REFERENCE["threshold_mm"]))
        is case["expected_occurred"]
    )
    assert observation.rainfall_mm is None
    assert observation.upper_exclusive_mm == (
        Decimal("0.05") if case["expected_status"] == "complete_trace" else None
    )


@pytest.mark.parametrize(
    "case",
    [
        row
        for row in REFERENCE["cases"]
        if not row["expected_error"] and row["expected_occurred"] is None
    ],
    ids=lambda row: row["id"],
)
def test_unadjudicated_bound_cannot_earn_correct_dry_credit(case):
    observations = parse_hko_rainfall(
        case["csv"].encode("utf-8-sig"),
        start=date(2025, 1, 1),
        end=date(2026, 1, 1),
    )
    result = evaluate_weather_cohort(
        ["2025-01-01", "2025-01-02"],
        [
            {"date": "2025-01-01", "label": "dry"},
            {"date": "2025-01-02", "label": "abstain"},
        ],
        observations,
    )
    assert result["known_observation_days"] == 0
    assert result["unknown_observation_days"] == 2
    assert result["evaluable_days"] == result["correct"] == 0
    assert result["full_cohort_correct_credit_fraction"] == 0
    assert result["accuracy_on_evaluable_days"] is None
    assert result["declared_abstentions"] == 1
    assert len(result["rows"]) == 2


@pytest.mark.parametrize(
    "definition",
    [
        "Trace means rainfall less than 0.05 mm0",
        "Trace means rainfall less than 0.05 mm is not the current definition",
        "微量表示少於 5 毫米/Trace means rainfall less than 0.05 mm",
        "Trace means rainfall less than 0.05 mm\nTrace means rainfall less than 5 mm",
    ],
)
def test_original_prospective_synthetic_ingestion_keeps_uncertain_trace(
    definition, monkeypatch
):
    monkeypatch.setattr(prospective, "_now_utc", lambda: BEFORE)
    args = sample()
    text = args["observation_bytes"].decode("utf-8-sig")
    original = "微量表示少於 0.05 毫米/Trace means rainfall less than 0.05 mm"
    assert original in text
    raw = text.replace(original, definition).encode("utf-8-sig")
    args["observation_bytes"] = raw
    args["source_receipt"]["body_sha256"] = hashlib.sha256(raw).hexdigest()
    result = run(AFTER, **args)
    report = result["outcome_report"]
    assert result["status"] == "synthetic_mechanical_replay"
    assert result["ledger"]["label_counts"] == {"rain": 70, "dry": 141, "abstain": 154}
    assert result["ingested_outcome_rows"] == 5
    assert report["known_observation_days"] == 2
    assert report["unknown_observation_days"] == 363
    assert report["rows"][2]["observation_status"] == "trace_unadjudicated"
    assert report["rows"][2]["occurred"] is None
    assert report["rows"][2]["correct"] is None
    assert len(report["rows"]) == 365
    assert not result["real_world_predictive_efficacy_established"]
    assert not result["authority_certified"]
