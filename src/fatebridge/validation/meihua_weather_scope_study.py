"""Audit the fixed1.7.0 retrospective daily-rain study, preserving negative results."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from .meihua_weather_policy_v2 import full_cohort_assessment
from .meihua_weather_policy_v3 import scope_aware_weather_label
from .meihua_weather_study import evaluate_weather_cohort, parse_hko_rainfall


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_scope_weather_study(directory: Path) -> dict[str, Any]:
    """Recheck all saved labels before a fixed complete-cohort outcome join."""
    directory = directory.resolve()
    for manifest_name, base in [
        ("generation-lock.json", directory),
        ("engine-source-sha256.json", directory / "engine"),
    ]:
        document = json.loads((directory / manifest_name).read_text())
        files = (
            document["files"] if manifest_name == "generation-lock.json" else document
        )
        for name, digest in files.items():
            path = (base / name).resolve()
            if not path.is_relative_to(base) or _sha(path) != digest:
                raise ValueError("Locked study source or protocol changed")
    package = Path(__file__).resolve().parents[1]
    source = json.loads((directory / "engine-source-sha256.json").read_text())
    for name in [
        "validation/meihua_weather_policy_v3.py",
        "validation/meihua_weather_scope_study.py",
        "validation/meihua_weather_study.py",
        "validation/meihua_weather_policy_v2.py",
        "core/meihua_weather_time_scope.py",
    ]:
        if _sha(package / name) != source["src/fatebridge/" + name]:
            raise ValueError(
                "Evaluator implementation differs from the locked study source"
            )
    plan = json.loads((directory / "plan.json").read_text())
    if (
        plan["study_id"] != "meihua-weather1.7.0-scope-policy-v3-HKO"
        or plan["target"]["threshold_mm"] != "0.1"
        or plan["primary_scenario"] != "calendar_season_supplied"
        or plan["baseline_policy"] != ["always_rain", "always_dry"]
    ):
        raise ValueError(
            "The pinned target, primary scenario and baseline comparison must remain fixed"
        )
    expected_sizes = {
        "primary_2026_ytd_through_last_complete_month": 273,
        "retrospective_2024": 366,
        "retrospective_2025": 365,
    }
    if {k: len(v) for k, v in plan["cohorts"].items()} != expected_sizes:
        raise ValueError("Every locked cohort date must be retained")
    seal = json.loads((directory / "generated/forecast-seal.json").read_text())
    for name, digest in seal["files"].items():
        path = (directory / "generated" / name).resolve()
        if not path.is_relative_to(directory / "generated") or _sha(path) != digest:
            raise ValueError("Sealed forecasts or evidence changed")
    predictions = json.loads((directory / "generated/forecasts.json").read_text())
    indexed = {(r["cohort"], r["scenario"], r["date"]): r for r in predictions}
    expected = {
        (cohort, scenario, day)
        for cohort, days in plan["cohorts"].items()
        for scenario in plan["scenario_order"]
        for day in days
    }
    if (
        len(predictions) != 2008
        or len(indexed) != len(predictions)
        or set(indexed) != expected
    ):
        raise ValueError("All date/scenario records are required exactly once")
    seen = set()
    activity: dict[str, Counter[str]] = {s: Counter() for s in plan["scenario_order"]}
    dayparts = {s: 0 for s in plan["scenario_order"]}
    with (directory / "generated/evidence.jsonl").open() as handle:
        for line in handle:
            row = json.loads(line)
            key = (row["cohort"], row["scenario"], row["date"])
            if (
                key not in indexed
                or key in seen
                or hashlib.sha256(line.rstrip("\n").encode()).hexdigest()
                != indexed[key]["evidence_sha256"]
            ):
                raise ValueError("Evidence records must match every sealed forecast")
            seen.add(key)
            decision = scope_aware_weather_label(
                row["weather"],
                expected_profile_sha256=plan["profile_canonical_sha256"],
                expected_control_profile_sha256=plan[
                    "control_profile_canonical_sha256"
                ],
            )
            if (
                decision != row["decision"]
                or decision["label"] != indexed[key]["label"]
            ):
                raise ValueError(
                    "Saved forecast does not match its complete source trace"
                )
            for trace in row["weather"]["rule_trace"]:
                if trace["status"] == "matched":
                    activity[key[1]][trace["rule_id"]] += 1
            dayparts[key[1]] += row["weather"]["time_scope_comparison"][
                "has_explicit_daypart_readings"
            ]
    if seen != expected:
        raise ValueError("Evidence omitted a locked date or scenario")
    calendar = json.loads((directory / "generated/calendar-check.json").read_text())
    if (
        not calendar["passed"]
        or calendar["unique_issue_dates"] != 1004
        or calendar["mismatches"]
    ):
        raise ValueError("Locked study calendar checks are incomplete")
    metadata = json.loads((directory / "observation-sources.json").read_text())
    csv_path = directory / metadata["rainfall"]["file"]
    if (
        not csv_path.resolve().is_relative_to(directory)
        or _sha(csv_path) != metadata["rainfall"]["sha256"]
    ):
        raise ValueError("The selected official outcome file changed")
    observations = parse_hko_rainfall(
        csv_path.read_bytes(), start=date(2024, 1, 1), end=date(2026, 10, 1)
    )
    reports: dict[str, dict[str, Any]] = {}
    for cohort, days in plan["cohorts"].items():
        reports[cohort] = {}
        for scenario in plan["scenario_order"]:
            selected = [indexed[(cohort, scenario, day)] for day in days]
            result = evaluate_weather_cohort(
                days, selected, observations, threshold=Decimal("0.1")
            )
            primary = full_cohort_assessment(result, expected_cohort_days=len(days))
            monthly = []
            for month in sorted({s[:7] for s in days}):
                subset = [s for s in days if s.startswith(month)]
                month_result = evaluate_weather_cohort(
                    subset,
                    [indexed[(cohort, scenario, day)] for day in subset],
                    observations,
                    threshold=Decimal("0.1"),
                )
                monthly.append({"month": month, "evaluation": month_result})
            reports[cohort][scenario] = {
                "evaluation": result,
                "full_cohort_primary_endpoint": primary,
                "monthly": monthly,
            }
    primary_result = reports[plan["primary_cohort"]][plan["primary_scenario"]]
    unique = sorted({day for days in plan["cohorts"].values() for day in days})
    observed = sum(
        observations.get(date.fromisoformat(day)) is not None
        and observations[date.fromisoformat(day)].occurred(Decimal("0.1")) is not None
        for day in unique
    )
    report: dict[str, Any] = {
        "study_id": plan["study_id"],
        "execution_integrity": "passed",
        "forecast_record_count": 2008,
        "unique_target_dates": len(unique),
        "known_observation_target_dates": observed,
        "scenario_replications_are_not_independent_observations": True,
        "primary_cohort": plan["primary_cohort"],
        "primary_scenario": plan["primary_scenario"],
        "primary_endpoint": primary_result["full_cohort_primary_endpoint"],
        "reports": reports,
        "source_rule_activity_by_scenario": {
            s: dict(sorted(c.items())) for s, c in activity.items()
        },
        "explicit_daypart_casts_by_scenario": dayparts,
        "calendar_check": calendar,
        "observation_source": metadata["rainfall"],
        "protocol_sha256": _sha(directory / "plan.json"),
        "forecast_seal_sha256": _sha(directory / "generated/forecast-seal.json"),
        "source_manifest_sha256": _sha(directory / "engine-source-sha256.json"),
        "interpretation_policy": "qualified_scope_aware_daily_rain_clear_v3@1.0.0",
        "weather_profile": "meihua_weather_v1@1.7.0",
        "target_window_and_clear_proxy_are_research_assumptions": True,
        "retrospective_not_blinded_or_prospective": True,
        "actual_model_runs": 0,
        "new_prospective_observations": 0,
        "real_world_predictive_efficacy_established": False,
        "authority_certified": False,
    }
    return report
