"""Locked weather-study evaluation with source flags and every cohort day kept.

This module does not train a predictor or select an interpretation policy.
Daily values from one station are a time series, not independent subjects.
"""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from fatebridge.core.meihua_clock_iso import parse_meihua_clock_label

_TITLE = "Daily Total Rainfall (mm) at the Hong Kong Observatory"
_HEADER = [
    "年/Year",
    "月/Month",
    "日/Day",
    "數值/Value",
    "數據完整性/data Completeness",
]
_TRACE_LEGEND = "Trace means rainfall less than 0.05 mm"
_TRACE_DEFINITIONS = {
    _TRACE_LEGEND,
    f"微量表示少於 0.05 毫米/{_TRACE_LEGEND}",
}
_LABELS = {"rain", "dry", "abstain"}


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _day(value: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Study dates must be explicit YYYY-MM-DD civil dates")
    return date.fromisoformat(value)


def _aware(value: str) -> datetime:
    parsed = parse_meihua_clock_label(value)
    if parsed.utcoffset() is None:
        raise ValueError("Study record timestamps require an explicit timezone")
    return parsed


def rain_without_clear_label(rule_trace: list[dict[str, Any]]) -> str:
    """Replay the already declared v1 hypothesis; do not silently tune it."""
    if any("effective_status" in row or "control_checks" in row for row in rule_trace):
        raise ValueError(
            "The v1 research policy requires its frozen pre-control trace schema"
        )
    tags = {
        tag for row in rule_trace if row["status"] == "matched" for tag in row["tags"]
    }
    if "rain" in tags and "clear" not in tags:
        return "rain"
    if "clear" in tags and "rain" not in tags:
        return "dry"
    return "abstain"


@dataclass(frozen=True)
class RainObservation:
    day: date
    raw_value: str
    completeness: str
    status: str
    rainfall_mm: Decimal | None = None
    upper_exclusive_mm: Decimal | None = None

    def occurred(self, threshold: Decimal) -> bool | None:
        if not threshold.is_finite() or threshold <= 0:
            raise ValueError("Rain threshold must be finite and positive")
        if self.status == "complete_numeric" and self.rainfall_mm is not None:
            if (
                not self.rainfall_mm.is_finite()
                or self.rainfall_mm < 0
                or self.completeness != "C"
            ):
                raise ValueError(
                    "Complete rainfall requires a finite nonnegative C observation"
                )
            return self.rainfall_mm >= threshold
        if self.status == "complete_trace" and self.upper_exclusive_mm is not None:
            if (
                not self.upper_exclusive_mm.is_finite()
                or self.upper_exclusive_mm <= 0
                or self.completeness != "C"
            ):
                raise ValueError(
                    "Complete trace requires an adjudicated positive C upper bound"
                )
            # A source-bounded trace is not a measured zero. It can determine
            # a negative only when the whole interval is below the threshold.
            if self.upper_exclusive_mm <= threshold:
                return False
        return None


def parse_hko_rainfall(
    raw: bytes, *, start: date, end: date
) -> dict[date, RainObservation]:
    """Read the documented HKO station dataset, end exclusive; fail on duplicates."""
    if start >= end:
        raise ValueError("Observation period must be ordered")
    text = raw.decode("utf-8-sig")
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise ValueError("Malformed rainfall source CSV") from exc
    if len(rows) < 4 or rows[1] != [_TITLE] or rows[2] != _HEADER:
        raise ValueError("Not the declared HKO station rainfall dataset/header")
    data_rows = []
    trace_definitions = []
    footer_started = False
    for number, row in enumerate(rows[3:], start=4):
        if not row or not any(s.strip() for s in row):
            continue
        if not re.fullmatch(r"\d{4}", row[0].strip()):
            if len(row) == 1 and any(
                token in row[0]
                for token in [
                    "unavailable",
                    "data incomplete",
                    "Trace means",
                    "data Complete",
                ]
            ):
                footer_started = True
                if "Trace means" in row[0]:
                    trace_definitions.append(row[0].strip())
                continue
            raise ValueError(f"Unrecognized rainfall source row {number}")
        if footer_started:
            raise ValueError("Rainfall data rows cannot follow the source footer")
        if len(row) != 5:
            raise ValueError(f"Incomplete rainfall source row {number}")
        data_rows.append(row)
    # The documented footer, not an arbitrary substring in the file, supplies
    # this interval. A conflicting or unrecognized definition leaves it unknown.
    trace_adjudicated = bool(trace_definitions) and all(
        definition in _TRACE_DEFINITIONS for definition in trace_definitions
    )
    observations = {}
    for row in data_rows:
        year = int(row[0])
        # The ALL file contains an unavailable 1900-02-29 placeholder. The
        # locked cohort is 2025: unrelated years are outside this parser's
        # validation scope, and an invalid date in a selected year still fails.
        if not start.year <= year <= (end - timedelta(days=1)).year:
            continue
        day = date(year, int(row[1]), int(row[2]))
        if not start <= day < end:
            continue
        if day in observations:
            raise ValueError("Duplicate observation dates cannot be selected by value")
        value, flag = row[3].strip(), row[4].strip()
        amount = None
        upper = None
        if value == "***":
            status = "unavailable"
        elif value.casefold() == "trace":
            if flag == "C" and trace_adjudicated:
                status, upper = "complete_trace", Decimal("0.05")
            else:
                status = "trace_unadjudicated" if flag == "C" else "incomplete"
        else:
            try:
                amount = Decimal(value)
            except InvalidOperation as exc:
                raise ValueError(f"Invalid rainfall value on {day}") from exc
            if not amount.is_finite() or amount < 0:
                raise ValueError(f"Nonfinite or negative rainfall on {day}")
            status = "complete_numeric" if flag == "C" else "incomplete"
        observations[day] = RainObservation(day, value, flag, status, amount, upper)
    return observations


def evaluate_weather_cohort(
    cohort: list[str],
    forecasts: list[dict[str, Any]],
    observations: dict[date, RainObservation],
    *,
    threshold: Decimal = Decimal("0.1"),
) -> dict[str, Any]:
    """Report descriptive counts, coverage and fixed baselines on equal dates."""
    if not threshold.is_finite() or threshold <= 0:
        raise ValueError("Rain threshold must be finite and positive")
    days = [_day(s) for s in cohort]
    if not days or len(set(days)) != len(days) or days != sorted(days):
        raise ValueError("Cohort must retain unique ordered dates")
    predicted = {}
    for row in forecasts:
        day = _day(row["date"])
        if day not in days or day in predicted or row["label"] not in _LABELS:
            raise ValueError("Unregistered, repeated or invalid forecast")
        predicted[day] = row["label"]
    matrix = {
        key: 0
        for key in [
            "true_positive",
            "false_positive",
            "true_negative",
            "false_negative",
        ]
    }
    rows = []
    n_observed = n_evaluable = correct = observed_rain = eligible_rain = 0
    missing_forecasts = abstentions = 0
    for day in days:
        label = predicted.get(day)
        observation = observations.get(day)
        if observation is not None and observation.day != day:
            raise ValueError("Observation date disagrees with its cohort key")
        actual = observation.occurred(threshold) if observation is not None else None
        abstentions += label == "abstain"
        missing_forecasts += label is None
        n_observed += actual is not None
        observed_rain += actual is True
        is_correct = None
        if actual is None:
            status = "observation_unknown"
        elif label is None:
            status = "forecast_missing"
        elif label == "abstain":
            status = "abstained"
        else:
            status = "evaluable"
            n_evaluable += 1
            eligible_rain += actual is True
            positive = label == "rain"
            is_correct = positive == actual
            correct += is_correct
            matrix[
                ("true_" if is_correct else "false_")
                + ("positive" if positive else "negative")
            ] += 1
        rows.append(
            {
                "date": day.isoformat(),
                "label": label,
                "observation_status": observation.status if observation else "absent",
                "raw_value": observation.raw_value if observation else None,
                "completeness": observation.completeness if observation else None,
                "rainfall_mm": (
                    str(observation.rainfall_mm)
                    if observation and observation.rainfall_mm is not None
                    else None
                ),
                "trace_upper_exclusive_mm": (
                    str(observation.upper_exclusive_mm)
                    if observation and observation.upper_exclusive_mm is not None
                    else None
                ),
                "occurred": actual,
                "status": status,
                "correct": is_correct,
            }
        )

    def ratio(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    baselines = {
        "same_evaluable_dates": {
            "count": n_evaluable,
            "always_rain_correct": eligible_rain,
            "always_dry_correct": n_evaluable - eligible_rain,
            "always_rain_accuracy": ratio(eligible_rain, n_evaluable),
            "always_dry_accuracy": ratio(n_evaluable - eligible_rain, n_evaluable),
        },
        "all_observed_dates": {
            "count": n_observed,
            "always_rain_correct": observed_rain,
            "always_dry_correct": n_observed - observed_rain,
            "always_rain_accuracy": ratio(observed_rain, n_observed),
            "always_dry_accuracy": ratio(n_observed - observed_rain, n_observed),
        },
    }
    return {
        "cohort_days": len(days),
        "issued_forecasts": len(predicted),
        "declared_abstentions": abstentions,
        "missing_forecasts": missing_forecasts,
        "known_observation_days": n_observed,
        "unknown_observation_days": len(days) - n_observed,
        "evaluable_days": n_evaluable,
        "correct": correct,
        "accuracy_on_evaluable_days": ratio(correct, n_evaluable),
        "evaluable_fraction_of_full_cohort": n_evaluable / len(days),
        "full_cohort_correct_credit_fraction": correct / len(days),
        "full_cohort_credit_definition": "Correct predictions divided by every declared day; unknowns and abstentions earn no correct credit. This is not accuracy on observed predictions.",
        "confusion_matrix": matrix,
        "fixed_baselines": baselines,
        "beats_both_baselines_on_same_evaluable_days": (
            correct > max(eligible_rain, n_evaluable - eligible_rain)
            if n_evaluable
            else None
        ),
        "statistical_scope": "descriptive_one_station_correlated_time_series_no_independent_Bernoulli_confidence_interval",
        "independent_subject_count": None,
        "real_world_predictive_efficacy_established": False,
        "authority_certified": False,
        "rows": rows,
    }


def audit_locked_weather_pilot(directory: Path) -> dict[str, Any]:
    """Audit the sealed historical ledger and the preserved independent source."""
    directory = directory.resolve()
    evaluator_path = Path(__file__).resolve()
    evaluator_hash = _hash(evaluator_path.read_bytes())
    seal_bytes = (directory / "pre-observation-seal.json").read_bytes()
    seal = json.loads(seal_bytes)
    material = {}
    for name, expected in seal["files"].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory):
            raise ValueError("Sealed study path escapes its directory")
        raw = path.read_bytes()
        if _hash(raw) != expected:
            raise ValueError(f"Sealed pre-observation material changed: {name}")
        material[name] = raw
    plan = json.loads(material["plan.json"])
    if plan["study_kind"] != "retrospective_before_data_retrieval_not_prospective":
        raise ValueError(
            "This v1 audit must not relabel retrospective data as prospective"
        )
    forecasts = json.loads(material["forecasts.json"])
    evidence = material["evidence.jsonl"].decode().splitlines()
    cohort = plan["cohort"]
    expected_days = [
        (date(2025, 1, 1) + timedelta(days=i)).isoformat() for i in range(365)
    ]
    if (
        [row["date"] for row in cohort] != expected_days
        or len(forecasts) != 365
        or len(evidence) != 365
    ):
        raise ValueError("The locked 2025 pilot must retain all 365 ordered days")
    origin = json.loads(material["policy-origin-plan.json"])
    policy = json.dumps(
        plan["interpretation_policy"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    if (
        plan["interpretation_policy"] != origin["interpretation_policy"]
        or _hash(policy) != plan["interpretation_policy_sha256"]
        or _hash(material["policy-origin-plan.json"])
        != plan["policy_origin_plan_sha256"]
    ):
        raise ValueError("The historical pilot must use the already frozen policy")
    if (
        plan["target"] != origin["target"]
        or plan["casting_policy"] != origin["casting_policy"]
        or plan["source_manifest_sha256"] != origin["source_manifest_sha256"]
        or plan["baselines"] != ["always_rain", "always_dry"]
        or plan["interpretation_policy"]["id"] != "rain_without_clear_sign_v1"
        or Decimal(str(plan["target"]["positive_threshold_mm"])) != Decimal("0.1")
    ):
        raise ValueError(
            "The v1 target, casting policy and baselines must remain fixed"
        )
    generated_at = _aware(plan["created_at"])
    if (
        not _aware("2026-01-01T00:00:00+08:00")
        <= generated_at
        <= _aware(seal["sealed_at"])
    ):
        raise ValueError(
            "Historical generation time must follow the full target period"
        )
    for member, forecast, serialized in zip(cohort, forecasts, evidence):
        row = json.loads(serialized)
        if not (
            member["date"] == forecast["date"] == row["date"]
            and member["case_id"] == forecast["case_id"] == row["case_id"]
            and _hash(serialized.encode()) == forecast["evidence_sha256"]
            and _aware(forecast["generated_at"]) == generated_at
            and rain_without_clear_label(row["weather_rule_trace"])
            == forecast["label"]
            == row["study_label"]
        ):
            raise ValueError(
                "Forecast, evidence or the fixed interpretation policy disagree"
            )
    source_metadata_bytes = (directory / "observation-sources.json").read_bytes()
    source_metadata = json.loads(source_metadata_bytes)
    if source_metadata["pre_observation_seal_sha256"] != _hash(
        seal_bytes
    ) or not _aware(seal["sealed_at"]) < _aware(
        source_metadata["csv_retrieval_started_at"]
    ):
        raise ValueError("Forecast lock must precede recorded CSV retrieval")
    sources = {}
    for source in source_metadata["sources"]:
        path = (directory / source["file"]).resolve()
        if not path.is_relative_to(directory):
            raise ValueError("Observation source escapes study directory")
        raw = path.read_bytes()
        if _hash(raw) != source["sha256"]:
            raise ValueError("Preserved independent observation source changed")
        if (
            path.name == "daily_HKO_RF_ALL.csv"
            and source["url"] != plan["target"]["source"]
        ):
            raise ValueError("Observation source must match the fixed target dataset")
        sources[path.name] = raw
    observations = parse_hko_rainfall(
        sources["daily_HKO_RF_ALL.csv"], start=date(2025, 1, 1), end=date(2026, 1, 1)
    )
    report = evaluate_weather_cohort(
        expected_days,
        forecasts,
        observations,
        threshold=Decimal(str(plan["target"]["positive_threshold_mm"])),
    )
    timing_text = re.sub(
        r"\s+",
        " ",
        html.unescape(
            re.sub(
                r"<[^>]*>",
                " ",
                sources.get("tc2024-introduction.html", b"").decode("utf-8"),
            )
        ),
    )
    timing_supported = (
        "Daily rainfall amounts are computed over a 24-hour period ending at midnight Hong Kong Time."
        in timing_text
    )
    if _hash(evaluator_path.read_bytes()) != evaluator_hash:
        raise ValueError("Study evaluator changed during audit")
    return {
        "study_id": plan["study_id"],
        "study_kind": plan["study_kind"],
        "pre_observation_seal_sha256": _hash(seal_bytes),
        "evaluation_implementation_sha256": evaluator_hash,
        "observation_sources_sha256": _hash(source_metadata_bytes),
        "interpretation_policy_sha256": plan["interpretation_policy_sha256"],
        "source_manifest_sha256": plan["source_manifest_sha256"],
        "registration_authenticated": False,
        "prospective_case_count": 0,
        "calendar_day_alignment": {
            "status": (
                "supported_by_cross_document_inference"
                if timing_supported
                else "not_verified"
            ),
            "basis": "HKO 2024 publication defines rainfall days ending at midnight Hong Kong Time; applying this provider convention to the CSV is an explicit cross-document inference.",
        },
        "trace_treatment": "CSV legend states Trace < 0.05 mm; for threshold 0.1 mm a complete trace is negative, with measured numeric amount kept null. Without the legend the trace remains unknown.",
        **report,
    }
