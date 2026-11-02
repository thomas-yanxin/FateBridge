"""Posthoc reference comparisons for the unchanged1.7.0 weather study."""

from __future__ import annotations

import hashlib
import html
import json
import re
from calendar import month_name
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from .meihua_weather_references import (
    HKT,
    climatology_reference,
    monthly_climatology_profile,
    persistence_reference,
)
from .meihua_weather_study import evaluate_weather_cohort, parse_hko_rainfall


def official_normal_rain_days(raw: str) -> list[str]:
    """Select only the actual0.1mm column of the frozen HKO table2."""
    tables = re.findall(r"<table\b[^>]*>(.*?)</table>", raw, re.I | re.S)
    selected = [t for t in tables if all(s in t for s in ["0.1 mm", "25 mm", "50 mm"])]
    if len(selected) != 1:
        raise ValueError("The declared HKO rainfall-day normals table is ambiguous")
    values = {}
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", selected[0], re.I | re.S):
        cells = [
            html.unescape(re.sub(r"<[^>]*>", "", cell)).strip()
            for cell in re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.I | re.S)
        ]
        if cells and cells[0] in list(month_name)[1:]:
            if len(cells) != 6 or cells[0] in values:
                raise ValueError("Repeated or incomplete HKO normals month")
            value = Decimal(cells[3])
            if not value.is_finite() or not 0 <= value <= 31:
                raise ValueError("Invalid HKO monthly mean rain-day count")
            values[cells[0]] = format(value, ".2f")
    if set(values) != set(list(month_name)[1:]):
        raise ValueError("All twelve official normals months are required")
    return [values[month_name[m]] for m in range(1, 13)]


def audit_weather_reference_study(directory: Path) -> dict[str, Any]:
    """Keep original labels and endpoint, with conditional baselines disclosed."""
    base = directory.resolve()
    lock = json.loads((base / "reference-lock.json").read_text())
    for group, folder in [
        ("study_files", base),
        ("implementation_files", Path(__file__).resolve().parent),
    ]:
        for name, digest in lock[group].items():
            path = (folder / name).resolve()
            if (
                not path.is_relative_to(folder)
                or hashlib.sha256(path.read_bytes()).hexdigest() != digest
            ):
                raise ValueError("Locked reference source or protocol changed")
    return _evaluate_reference_material(base)


# Input and implementation bytes must be verified by the caller first.
def _evaluate_reference_material(base: Path) -> dict[str, Any]:
    plan = json.loads((base / "plan.json").read_text())
    if (
        plan["id"] != "meihua_weather_reference_baseline_supplement_v1"
        or plan["study_kind"]
        != "posthoc_reference_baseline_supplement_not_preregistered_not_new_prediction_test"
        or plan["climatology_training"] != ["1991-01-01", "2021-01-01"]
        or plan["threshold_mm"] != "0.1"
    ):
        raise ValueError("Reference supplement protocol differs from the fixed scope")
    for name, digest in plan["parent_files_sha256"].items():
        path = (base / "parent" / name).resolve()
        if (
            not path.is_relative_to(base / "parent")
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise ValueError("Original study material changed")
    parent = json.loads((base / "parent/plan.json").read_text())
    expected = {
        "primary_2026_ytd_through_last_complete_month": (date(2026, 1, 1), 273),
        "retrospective_2024": (date(2024, 1, 1), 366),
        "retrospective_2025": (date(2025, 1, 1), 365),
    }
    if set(parent["cohorts"]) != set(expected) or parent["scenario_order"] != [
        "calendar_season_supplied",
        "season_not_supplied",
    ]:
        raise ValueError("Original cohorts and scenarios must remain unchanged")
    for key, (start, n) in expected.items():
        if parent["cohorts"][key] != [
            (start + timedelta(days=i)).isoformat() for i in range(n)
        ]:
            raise ValueError("Every original locked date is required")
    forecasts_raw = (base / "parent/forecasts.json").read_bytes()
    seal = json.loads((base / "parent/forecast-seal.json").read_text())
    if hashlib.sha256(forecasts_raw).hexdigest() != seal["files"]["forecasts.json"]:
        raise ValueError("Original forecast seal no longer matches")
    forecasts = json.loads(forecasts_raw)
    indexed = {(r["cohort"], r["scenario"], r["date"]): r for r in forecasts}
    keys = {
        (key, scenario, day)
        for key, days in parent["cohorts"].items()
        for scenario in parent["scenario_order"]
        for day in days
    }
    if len(forecasts) != 2008 or len(indexed) != 2008 or set(indexed) != keys:
        raise ValueError("Every original date/scenario forecast is required once")
    rainfall_raw = (base / "sources/daily_HKO_RF_ALL.csv").read_bytes()
    if hashlib.sha256(rainfall_raw).hexdigest() != plan["raw_rainfall_sha256"]:
        raise ValueError("Original observation source changed")
    observations = parse_hko_rainfall(
        rainfall_raw, start=date(1991, 1, 1), end=date(2026, 10, 1)
    )
    profile = monthly_climatology_profile(observations)
    official = official_normal_rain_days(
        (base / "sources/HKO-normals-1991-2020.html").read_text()
    )
    if official != plan["official_monthly_mean_rain_days_ge0_1_mm"]:
        raise ValueError("The frozen official norms transcription changed")
    normal_checks = []
    for row, published in zip(profile["months"], official, strict=True):
        value = row["mean_rain_days_per_year"]
        rounded = str(Decimal(value).quantize(Decimal("0.01"))) if value else None
        normal_checks.append(
            {
                "month": row["month"],
                "raw_daily_complete_days": row["known_observation_days"],
                "expected_training_days": row["expected_days"],
                "raw_daily_rain_days": row["rain_days"],
                "computed_mean_rounded2decimals": rounded,
                "official_mean_rain_days": published,
                "matches_published_precision": rounded == published,
            }
        )
    unique = sorted({day for days in parent["cohorts"].values() for day in days})
    references = {}
    for text_day in unique:
        day = date.fromisoformat(text_day)
        issue = datetime.combine(day - timedelta(days=1), time(12), HKT)
        references[text_day] = {
            "persistence": persistence_reference(day, issue, observations),
            "monthly_climatology": climatology_reference(day, issue, profile),
        }
    original = json.loads((base / "parent/evaluation.json").read_text())
    reports: dict[str, Any] = {}
    for key, days in parent["cohorts"].items():
        baseline_reports = {}
        for method in ["persistence", "monthly_climatology"]:
            labels = [
                {
                    "date": day,
                    "label": references[day][method]["conditional_historical_label"]
                    or "abstain",
                }
                for day in days
            ]
            baseline_reports[method] = {
                "conditional_historical_evaluation": evaluate_weather_cohort(
                    days, labels, observations
                ),
                "usable_under_declared_publication_times": sum(
                    references[day][method]["label_under_declared_availability"]
                    is not None
                    for day in days
                ),
                "operational_vintage_efficacy_established": False,
            }
        scenario_reports = {}
        for scenario in parent["scenario_order"]:
            chosen = [indexed[(key, scenario, day)] for day in days]
            weather = evaluate_weather_cohort(days, chosen, observations)
            if weather != original["reports"][key][scenario]["evaluation"]:
                raise ValueError("Original forecast evaluation must reproduce exactly")
            categorical = [r["date"] for r in chosen if r["label"] != "abstain"]
            same_dates = {}
            for method in baseline_reports:
                same_dates[method] = (
                    evaluate_weather_cohort(
                        categorical,
                        [
                            {
                                "date": day,
                                "label": references[day][method][
                                    "conditional_historical_label"
                                ]
                                or "abstain",
                            }
                            for day in categorical
                        ],
                        observations,
                    )
                    if categorical
                    else None
                )
            scenario_reports[scenario] = {
                "original_weather_evaluation": weather,
                "same_weather_categorical_dates_conditional_references": same_dates,
                "operational_superiority_gate": None,
                "gate_reason": "Historic value-publication times unknown; conditional references are not proven available at issue. Supplement is posthoc, not a new preregistered gate.",
            }
        reports[key] = {
            "conditional_references": baseline_reports,
            "scenarios": scenario_reports,
        }
    return {
        "id": plan["id"],
        "execution_integrity": "passed",
        "study_kind": plan["study_kind"],
        "weather_profile": "meihua_weather_v1@1.7.0",
        "original_forecast_records_retained": 2008,
        "unique_target_dates": 1004,
        "new_meihua_forecasts": 0,
        "old_primary_endpoint": original["primary_endpoint"],
        "monthly_climatology_profile": profile,
        "official_normals_checks": normal_checks,
        "all12_official_normals_match_published_precision": all(
            r["matches_published_precision"] for r in normal_checks
        ),
        "reference_records": references,
        "reports": reports,
        "original_primary_replaced": False,
        "input_publication_times_known": False,
        "rainfall_target_does_not_validate_ancient_clear_sky": True,
        "conditional_references_not_classical_forecasts": True,
        "posthoc_or_categorical_subset_cannot_certify_skill": True,
        "actual_model_runs": 0,
        "new_prospective_observations": 0,
        "real_world_predictive_efficacy_established": False,
        "authority_certified": False,
    }
