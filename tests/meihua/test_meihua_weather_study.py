"""Synthetic evaluator cases cannot masquerade as real-world Meihua evidence."""

import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal

import pytest

from fatebridge.validation.meihua_weather_study import (
    RainObservation,
    audit_locked_weather_pilot,
    evaluate_weather_cohort,
    parse_hko_rainfall,
    rain_without_clear_label,
)

HEADER = (
    "日總雨量(毫米) - 天文台\n"
    "Daily Total Rainfall (mm) at the Hong Kong Observatory\n"
    "年/Year,月/Month,日/Day,數值/Value,數據完整性/data Completeness\n"
)
LEGEND = (
    "\n*** 沒有數據/unavailable\n# 數據不完整/data incomplete\n"
    "微量表示少於 0.05 毫米/Trace means rainfall less than 0.05 mm\n"
    "C 數據完整/data Complete\n"
)


def source(rows, *, legend=LEGEND):
    return (HEADER + "\n".join(rows) + "\n" + legend).encode("utf-8-sig")


def parse(rows, **options):
    return parse_hko_rainfall(
        source(rows, **options), start=date(2025, 1, 1), end=date(2026, 1, 1)
    )


def test_trace_is_an_interval_and_incomplete_is_not_zero():
    observations = parse(
        ["2025,1,1,Trace,C", "2025,1,2,12.0,#", "2025,1,3,***,C", "2025,1,4,0.1,C"]
    )
    trace = observations[date(2025, 1, 1)]
    assert trace.rainfall_mm is None and trace.upper_exclusive_mm == Decimal("0.05")
    assert trace.occurred(Decimal("0.1")) is False
    assert trace.occurred(Decimal("0.05")) is False
    assert trace.occurred(Decimal("0.01")) is None
    assert observations[date(2025, 1, 2)].occurred(Decimal("0.1")) is None
    assert observations[date(2025, 1, 3)].occurred(Decimal("0.1")) is None
    assert observations[date(2025, 1, 4)].occurred(Decimal("0.1")) is True


def test_trace_without_source_bound_remains_unknown():
    observations = parse(["2025,1,1,Trace,C"], legend="C data Complete\n")
    assert observations[date(2025, 1, 1)].occurred(Decimal("0.1")) is None


def test_unavailable_invalid_date_outside_locked_year_cannot_drop_cohort_days():
    observations = parse(["1900,2,29,***,", "2025,1,1,0,C"])
    assert list(observations) == [date(2025, 1, 1)]
    with pytest.raises(ValueError, match="day is out of range"):
        parse(["2025,2,29,***,", "2025,1,1,0,C"])


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-0.1", "unknown", ""])
def test_bad_values_fail_instead_of_becoming_dry(value):
    with pytest.raises(ValueError, match="rainfall"):
        parse([f"2025,1,1,{value},C"])


def test_wrong_station_bad_rows_and_duplicates_fail():
    for raw in [
        source(["2025,1,1,1.0,C"]).replace(b"Hong Kong Observatory", b"King's Park"),
        source(["2025,1,1,1.0"]),
        source(["2025,1,1,1.0,C", "2025,1,1,0.0,C"]),
        source(["2025,1,1,1.0,C", "unexpected data row"]),
    ]:
        with pytest.raises(ValueError):
            parse_hko_rainfall(raw, start=date(2025, 1, 1), end=date(2026, 1, 1))


def test_all_days_abstentions_unknowns_and_equal_baselines_are_retained():
    days = [f"2025-01-0{i}" for i in range(1, 7)]
    observations = parse(
        [
            "2025,1,1,1,C",
            "2025,1,2,0,C",
            "2025,1,3,0,C",
            "2025,1,4,1,C",
            "2025,1,5,1,C",
            "2025,1,6,1,#",
        ]
    )
    forecasts = [
        {"date": day, "label": label}
        for day, label in zip(days, ["rain", "dry", "rain", "dry", "abstain", "rain"])
    ]
    report = evaluate_weather_cohort(days, forecasts, observations)
    assert report["cohort_days"] == 6
    assert report["evaluable_days"] == 4 and report["correct"] == 2
    assert report["accuracy_on_evaluable_days"] == 0.5
    assert (
        report["declared_abstentions"] == 1 and report["unknown_observation_days"] == 1
    )
    assert report["full_cohort_correct_credit_fraction"] == 2 / 6
    assert set(report["confusion_matrix"].values()) == {1}
    baselines = report["fixed_baselines"]
    assert baselines["same_evaluable_dates"]["always_dry_accuracy"] == 0.5
    assert baselines["all_observed_dates"]["always_rain_accuracy"] == 3 / 5
    assert not report["beats_both_baselines_on_same_evaluable_days"]
    assert report["rows"][-1]["raw_value"] == "1"
    assert report["rows"][-1]["occurred"] is None
    assert report["independent_subject_count"] is None
    assert not report["real_world_predictive_efficacy_established"]


def test_missing_predictions_and_observations_cannot_disappear():
    report = evaluate_weather_cohort(
        ["2025-01-01", "2025-01-02"], [], parse(["2025,1,1,0,C"])
    )
    assert report["missing_forecasts"] == 2 and report["unknown_observation_days"] == 1
    assert report["accuracy_on_evaluable_days"] is None
    assert report["beats_both_baselines_on_same_evaluable_days"] is None
    assert len(report["rows"]) == 2


def test_invalid_and_repeated_forecasts_are_rejected():
    for forecasts in [
        [{"date": "2025-01-02", "label": "dry"}],
        [{"date": "2025-01-01", "label": "unknown"}],
        [{"date": "2025-01-01", "label": "dry"}] * 2,
    ]:
        with pytest.raises(ValueError):
            evaluate_weather_cohort(["2025-01-01"], forecasts, {})
    with pytest.raises(ValueError, match="cohort key"):
        evaluate_weather_cohort(
            ["2025-01-01"],
            [],
            {
                date(2025, 1, 1): RainObservation(
                    date(2025, 1, 2), "0", "C", "complete_numeric", Decimal("0")
                )
            },
        )


@pytest.mark.parametrize(
    "threshold", [Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity")]
)
def test_invalid_thresholds_fail_even_when_no_outcomes(threshold):
    with pytest.raises(ValueError):
        evaluate_weather_cohort(["2025-01-01"], [], {}, threshold=threshold)


def test_the_frozen_label_adapter_does_not_vote_or_use_pending_rules():
    assert (
        rain_without_clear_label(
            [{"status": "matched", "tags": ["rain"]}] * 10
            + [{"status": "matched", "tags": ["clear"]}]
        )
        == "abstain"
    )
    assert (
        rain_without_clear_label(
            [
                {"status": "matched", "tags": ["rain"]},
                {"status": "pending_context", "tags": ["clear"]},
            ]
        )
        == "rain"
    )
    # Preserve the existing research hypothesis, including its known limitation:
    # a variable-weather symbol does not veto a categorical label in v1.
    assert (
        rain_without_clear_label([{"status": "matched", "tags": ["clear", "variable"]}])
        == "dry"
    )


def test_old_research_policy_cannot_silently_consume_new_control_aware_results():
    with pytest.raises(ValueError, match="frozen pre-control trace"):
        rain_without_clear_label(
            [
                {
                    "status": "matched",
                    "tags": ["rain"],
                    "effective_status": "qualified_by_source_control",
                }
            ]
        )


def _synthetic_pilot(directory):
    def write(name, value):
        (directory / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        )

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    cohort = [
        {
            "date": (date(2025, 1, 1) + timedelta(days=i)).isoformat(),
            "case_id": f"synthetic-{i}",
        }
        for i in range(365)
    ]
    origin = {
        "interpretation_policy": {"id": "rain_without_clear_sign_v1"},
        "target": {
            "positive_threshold_mm": 0.1,
            "source": "https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKO/ALL/daily_HKO_RF_ALL.csv",
        },
        "casting_policy": {},
        "source_manifest_sha256": "a" * 64,
    }
    write("policy-origin-plan.json", origin)
    policy_bytes = json.dumps(
        origin["interpretation_policy"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    plan = {
        **origin,
        "study_id": "synthetic_evaluator_contract_only",
        "study_kind": "retrospective_before_data_retrieval_not_prospective",
        "created_at": "2026-10-22T01:00:00+08:00",
        "policy_origin_plan_sha256": sha(directory / "policy-origin-plan.json"),
        "interpretation_policy_sha256": hashlib.sha256(policy_bytes).hexdigest(),
        "cohort": cohort,
        "baselines": ["always_rain", "always_dry"],
    }
    write("plan.json", plan)
    forecasts = []
    with (directory / "evidence.jsonl").open("w") as file:
        for member in cohort:
            row = {**member, "weather_rule_trace": [], "study_label": "abstain"}
            line = json.dumps(row, sort_keys=True, separators=(",", ":"))
            file.write(line + "\n")
            forecasts.append(
                {
                    **member,
                    "label": "abstain",
                    "generated_at": plan["created_at"],
                    "evidence_sha256": hashlib.sha256(line.encode()).hexdigest(),
                }
            )
    write("forecasts.json", forecasts)
    seal = {
        "sealed_at": "2026-10-22T01:01:00+08:00",
        "files": {p.name: sha(p) for p in directory.iterdir()},
    }
    write("pre-observation-seal.json", seal)
    (directory / "sources").mkdir()
    (directory / "sources/daily_HKO_RF_ALL.csv").write_bytes(
        source(
            [
                f"2025,{(date(2025,1,1)+timedelta(days=i)).month},{(date(2025,1,1)+timedelta(days=i)).day},0,C"
                for i in range(365)
            ]
        )
    )
    write(
        "observation-sources.json",
        {
            "pre_observation_seal_sha256": sha(directory / "pre-observation-seal.json"),
            "csv_retrieval_started_at": "2026-10-22T01:02:00+08:00",
            "sources": [
                {
                    "file": "sources/daily_HKO_RF_ALL.csv",
                    "url": origin["target"]["source"],
                    "sha256": sha(directory / "sources/daily_HKO_RF_ALL.csv"),
                }
            ],
        },
    )


def test_all_abstention_synthetic_audit_does_not_produce_perfect_accuracy(tmp_path):
    _synthetic_pilot(tmp_path)
    report = audit_locked_weather_pilot(tmp_path)
    assert report["declared_abstentions"] == 365
    assert report["known_observation_days"] == 365
    assert report["accuracy_on_evaluable_days"] is None
    assert report["full_cohort_correct_credit_fraction"] == 0
    assert report["prospective_case_count"] == 0
    assert not report["authority_certified"]
    (tmp_path / "sources/daily_HKO_RF_ALL.csv").write_bytes(source(["2025,1,1,1,C"]))
    with pytest.raises(ValueError, match="observation source changed"):
        audit_locked_weather_pilot(tmp_path)


def test_sealed_forecast_tampering_and_resigned_policy_drift_are_rejected(tmp_path):
    _synthetic_pilot(tmp_path)
    path = tmp_path / "forecasts.json"
    forecasts = json.loads(path.read_text())
    forecasts[0]["label"] = "rain"
    path.write_text(json.dumps(forecasts))
    with pytest.raises(ValueError, match="Sealed pre-observation material changed"):
        audit_locked_weather_pilot(tmp_path)
    seal_path = tmp_path / "pre-observation-seal.json"
    seal = json.loads(seal_path.read_text())
    seal["files"]["forecasts.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
    seal_path.write_text(json.dumps(seal))
    with pytest.raises(ValueError, match="fixed interpretation policy disagree"):
        audit_locked_weather_pilot(tmp_path)
