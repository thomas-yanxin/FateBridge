"""Dated meteorological references, separate from casts and historic availability.

These are modern comparison methods. They do not supply a classical weather
forecast or infer prolonged clear/rain. A dated observation is not evidence that
its final value had been published when a retrospective forecast was issued.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from fatebridge.core.meihua_clock_iso import parse_meihua_clock_label

from .meihua_weather_study import RainObservation

HKT = ZoneInfo("Asia/Hong_Kong")
TRAINING_START = date(1991, 1, 1)
TRAINING_END = date(2021, 1, 1)


def _aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("Reference timestamps require an explicit timezone")
    return value


def daily_window_end(day: date) -> datetime:
    if type(day) is not date:
        raise ValueError("Reference observation requires a civil date")
    return datetime.combine(day + timedelta(days=1), time(), HKT)


def daily_value_availability(
    day: date, issued_at: datetime, published_at: datetime | None = None
) -> dict[str, Any]:
    """Check completion and declared publication separately; never fill a time."""
    issue = _aware(issued_at)
    end = daily_window_end(day)
    reasons = []
    if end > issue:
        reasons.append("observation_window_not_complete_at_issue")
    if published_at is None:
        reasons.append("historical_value_publication_time_unknown")
    else:
        publication = _aware(published_at)
        if publication < end:
            raise ValueError(
                "A complete daily total cannot be published before its end"
            )
        if publication > issue:
            reasons.append("value_published_after_issue")
    return {
        "input_date": day.isoformat(),
        "observation_window_end": end.isoformat(),
        "issued_at": issue.isoformat(),
        "declared_value_published_at": (
            published_at.isoformat() if published_at is not None else None
        ),
        "window_complete_at_issue": end <= issue,
        "available_under_declared_times": not reasons,
        "reason_codes": reasons,
        "publication_provenance_authenticated": False,
    }


def _target(target_day: date, issued_at: datetime) -> None:
    if type(target_day) is not date or daily_window_end(target_day) - timedelta(
        days=1
    ) <= _aware(issued_at):
        raise ValueError("Reference issue must precede the target civil day")


def _observed(
    observations: Mapping[date, RainObservation], day: date, threshold: Decimal
) -> bool | None:
    value = observations.get(day)
    if value is not None and value.day != day:
        raise ValueError("Reference observation date differs from its dictionary key")
    return value.occurred(threshold) if value is not None else None


def persistence_reference(
    target_day: date,
    issued_at: datetime,
    observations: Mapping[date, RainObservation],
    *,
    threshold: Decimal = Decimal("0.1"),
    publication_times: Mapping[date, datetime] | None = None,
) -> dict[str, Any]:
    """Persist the last completed local day, not an unfinished issue-day total."""
    _target(target_day, issued_at)
    if not threshold.is_finite() or threshold <= 0:
        raise ValueError("Reference rain threshold must be finite and positive")
    day = issued_at.astimezone(HKT).date() - timedelta(days=1)
    availability = daily_value_availability(
        day, issued_at, (publication_times or {}).get(day)
    )
    actual = _observed(observations, day, threshold)
    label = None if actual is None else "rain" if actual else "dry"
    usable = availability["available_under_declared_times"] and label is not None
    return {
        "reference_id": "last_completed_civil_day_hkt_v1",
        "target_date": target_day.isoformat(),
        "input_day_lag_from_target": (target_day - day).days,
        "conditional_historical_label": label,
        "label_under_declared_availability": label if usable else None,
        "input_observation_known": actual is not None,
        "availability": availability,
        "source_provenance_authenticated": False,
        "classical_rule_or_engine_forecast": False,
    }


def monthly_climatology_profile(
    observations: Mapping[date, RainObservation],
    *,
    threshold: Decimal = Decimal("0.1"),
    publication_times: Mapping[date, datetime] | None = None,
) -> dict[str, Any]:
    """Fixed1991..2020 daily rain frequencies, retaining every training date."""
    if not threshold.is_finite() or threshold <= 0:
        raise ValueError("Reference rain threshold must be finite and positive")
    months: dict[int, dict[str, Any]] = {
        m: {
            "month": m,
            "expected_days": 0,
            "known_observation_days": 0,
            "rain_days": 0,
            "unknown_publication_days": 0,
            "last_observation_window_end": None,
            "latest_declared_publication": None,
        }
        for m in range(1, 13)
    }
    day = TRAINING_START
    while day < TRAINING_END:
        row = months[day.month]
        row["expected_days"] += 1
        value = _observed(observations, day, threshold)
        row["known_observation_days"] += value is not None
        row["rain_days"] += value is True
        end = daily_window_end(day)
        row["last_observation_window_end"] = end.isoformat()
        publication = (publication_times or {}).get(day)
        if publication is None:
            row["unknown_publication_days"] += 1
        else:
            publication = _aware(publication)
            if publication < end:
                raise ValueError("Training daily total published before its window end")
            previous = row["latest_declared_publication"]
            if previous is None or publication > parse_meihua_clock_label(previous):
                row["latest_declared_publication"] = publication.isoformat()
        day += timedelta(days=1)
    for row in months.values():
        n, known, rain = (
            row["expected_days"],
            row["known_observation_days"],
            row["rain_days"],
        )
        row["conditional_historical_label"] = (
            None if known != n or 2 * rain == n else "rain" if 2 * rain > n else "dry"
        )
        row["mean_rain_days_per_year"] = (
            str(Decimal(rain) / Decimal(30)) if known == n else None
        )
    return {
        "reference_id": "monthly_1991_2020_majority_hkt_v1",
        "training_start": TRAINING_START.isoformat(),
        "training_end_exclusive": TRAINING_END.isoformat(),
        "training_days": (TRAINING_END - TRAINING_START).days,
        "threshold_mm": str(threshold),
        "months": list(months.values()),
        "tie_or_any_unknown_training_observation": "unresolved_not_dropped",
        "source_provenance_authenticated": False,
        "empirical_reference_is_not_a_cast_probability": True,
    }


def climatology_reference(
    target_day: date, issued_at: datetime, profile: dict[str, Any]
) -> dict[str, Any]:
    """Apply a fixed profile without treating unknown vintage times as known."""
    _target(target_day, issued_at)
    if (
        profile["reference_id"] != "monthly_1991_2020_majority_hkt_v1"
        or profile["training_start"] != TRAINING_START.isoformat()
        or profile["training_end_exclusive"] != TRAINING_END.isoformat()
        or profile["training_days"] != (TRAINING_END - TRAINING_START).days
        or [r["month"] for r in profile["months"]] != list(range(1, 13))
    ):
        raise ValueError("Reference training profile differs from the fixed protocol")
    row = profile["months"][target_day.month - 1]
    expected = sum(monthrange(y, target_day.month)[1] for y in range(1991, 2021))
    fields = [
        "expected_days",
        "known_observation_days",
        "rain_days",
        "unknown_publication_days",
    ]
    if any(type(row[name]) is not int for name in fields):
        raise ValueError("Reference counts must be explicit integers")
    n, known, rain, unknown = (row[name] for name in fields)
    if n != expected or not 0 <= rain <= known <= n or not 0 <= unknown <= n:
        raise ValueError("Reference profile dropped dates or contains invalid counts")
    label = None if known != n or 2 * rain == n else "rain" if 2 * rain > n else "dry"
    if row["conditional_historical_label"] != label:
        raise ValueError("Reference label differs from the fixed majority rule")
    end = _aware(parse_meihua_clock_label(row["last_observation_window_end"]))
    expected_end = daily_window_end(
        date(2020, target_day.month, monthrange(2020, target_day.month)[1])
    )
    if end != expected_end:
        raise ValueError(
            "Reference final training window differs from the fixed period"
        )
    if end > issued_at:
        raise ValueError("Training observation window ends after forecast issue")
    latest = row["latest_declared_publication"]
    if (latest is None) != (unknown == n):
        raise ValueError("Reference publication count and latest timestamp disagree")
    if (
        latest is not None
        and unknown == 0
        and _aware(parse_meihua_clock_label(latest)) < end
    ):
        raise ValueError(
            "Complete training publication precedes the final input window"
        )
    reasons = []
    if row["known_observation_days"] != row["expected_days"]:
        reasons.append("training_observation_unknown")
    if row["unknown_publication_days"]:
        reasons.append("historical_training_publication_times_unknown")
    if latest is not None and _aware(parse_meihua_clock_label(latest)) > issued_at:
        reasons.append("training_value_published_after_issue")
    if label is None:
        reasons.append("reference_category_unresolved")
    return {
        "reference_id": profile["reference_id"],
        "target_date": target_day.isoformat(),
        "issued_at": issued_at.isoformat(),
        "training_month": row["month"],
        "conditional_historical_label": label,
        "label_under_declared_availability": label if not reasons else None,
        "reason_codes": reasons,
        "source_provenance_authenticated": False,
        "classical_rule_or_engine_forecast": False,
    }
