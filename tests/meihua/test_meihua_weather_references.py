"""Synthetic references cannot borrow an unfinished day or a future vintage."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from fatebridge.validation.meihua_weather_references import (
    HKT,
    TRAINING_END,
    TRAINING_START,
    climatology_reference,
    daily_value_availability,
    daily_window_end,
    monthly_climatology_profile,
    persistence_reference,
)
from fatebridge.validation.meihua_weather_study import RainObservation

ISSUE = datetime(2025, 1, 2, 12, tzinfo=HKT)
TARGET = date(2025, 1, 3)


def observation(day, rainy=False):
    value = Decimal(1 if rainy else 0)
    return RainObservation(day, str(value), "C", "complete_numeric", value)


@pytest.fixture(scope="module")
def training():
    # Every record here is synthetic, not an additional real weather observation.
    result = {}
    day = TRAINING_START
    while day < TRAINING_END:
        result[day] = observation(day, day.month in {6, 7, 8})
        day += timedelta(days=1)
    return result


def test_noon_persistence_uses_target_minus2_not_unfinished_issue_day():
    old, unfinished = date(2025, 1, 1), date(2025, 1, 2)
    values = {old: observation(old, True), unfinished: observation(unfinished, False)}
    first = persistence_reference(TARGET, ISSUE, values)
    values[unfinished] = observation(unfinished, True)
    assert persistence_reference(TARGET, ISSUE, values) == first
    assert first["conditional_historical_label"] == "rain"
    assert first["availability"]["input_date"] == "2025-01-01"
    assert first["input_day_lag_from_target"] == 2
    assert first["label_under_declared_availability"] is None
    assert not first["availability"]["available_under_declared_times"]


def test_ended_daily_window_does_not_prove_historic_publication():
    check = daily_value_availability(date(2025, 1, 1), ISSUE)
    assert check["window_complete_at_issue"]
    assert check["reason_codes"] == ["historical_value_publication_time_unknown"]
    assert check["declared_value_published_at"] is None


def test_unfinished_window_is_retained_as_an_explicit_temporal_failure():
    check = daily_value_availability(date(2025, 1, 2), ISSUE)
    assert not check["window_complete_at_issue"]
    assert "observation_window_not_complete_at_issue" in check["reason_codes"]


def test_declared_publication_cannot_precede_completion_or_follow_issue():
    day = date(2025, 1, 1)
    with pytest.raises(ValueError, match="before its end"):
        daily_value_availability(day, ISSUE, datetime(2025, 1, 1, 20, tzinfo=HKT))
    late = daily_value_availability(day, ISSUE, ISSUE + timedelta(seconds=1))
    assert late["reason_codes"] == ["value_published_after_issue"]
    boundary = daily_value_availability(day, ISSUE, daily_window_end(day))
    assert boundary["available_under_declared_times"]
    assert not boundary["publication_provenance_authenticated"]


def test_utc_and_hong_kong_instants_select_the_same_completed_day():
    values = {date(2025, 1, 1): observation(date(2025, 1, 1), True)}
    a = persistence_reference(TARGET, ISSUE, values)
    b = persistence_reference(TARGET, ISSUE.astimezone(timezone.utc), values)
    assert a["availability"]["input_date"] == b["availability"]["input_date"]
    assert a["conditional_historical_label"] == b["conditional_historical_label"]


def test_leap_day_and_exact_midnight_are_civil_day_boundaries():
    day = date(2024, 2, 29)
    issue = datetime(2024, 3, 1, tzinfo=HKT)
    result = persistence_reference(date(2024, 3, 2), issue, {day: observation(day)})
    assert daily_window_end(day) == issue
    assert result["availability"]["input_date"] == "2024-02-29"


@pytest.mark.parametrize(
    "issue", [datetime(2025, 1, 2), datetime(2025, 1, 3, tzinfo=HKT)]
)
def test_unknown_timezone_or_issue_at_target_start_is_rejected(issue):
    with pytest.raises(ValueError):
        persistence_reference(TARGET, issue, {})


def test_absent_or_misdated_observation_cannot_be_persistence_dry():
    result = persistence_reference(TARGET, ISSUE, {})
    assert result["conditional_historical_label"] is None
    day = date(2025, 1, 1)
    with pytest.raises(ValueError, match="dictionary key"):
        persistence_reference(TARGET, ISSUE, {day: observation(TARGET)})


def test_fixed30year_profile_covers10958_days_and12_months(training):
    profile = monthly_climatology_profile(training)
    assert profile["training_days"] == len(training) == 10958
    assert sum(r["expected_days"] for r in profile["months"]) == 10958
    june = profile["months"][5]
    assert june["expected_days"] == june["rain_days"] == 900
    assert june["conditional_historical_label"] == "rain"
    assert profile["months"][0]["conditional_historical_label"] == "dry"
    result = climatology_reference(date(2025, 6, 3), ISSUE, profile)
    assert result["conditional_historical_label"] == "rain"
    assert result["label_under_declared_availability"] is None


def test_one_unknown_training_day_is_not_dropped_from_the_month(training):
    changed = dict(training)
    changed.pop(TRAINING_START)
    row = monthly_climatology_profile(changed)["months"][0]
    assert row["expected_days"] == 930 and row["known_observation_days"] == 929
    assert row["conditional_historical_label"] is None
    assert row["mean_rain_days_per_year"] is None


def test_exact_monthly_tie_is_unresolved_instead_of_selecting_a_winner(training):
    changed = {
        day: observation(day, day.month == 6 and day.day <= 15) for day in training
    }
    june = monthly_climatology_profile(changed)["months"][5]
    assert june["rain_days"] == 450 and june["expected_days"] == 900
    assert june["conditional_historical_label"] is None


def test_declared_training_publications_and_temporal_cutoff_are_both_required(training):
    publication = datetime(2021, 1, 1, tzinfo=HKT)
    profile = monthly_climatology_profile(
        training, publication_times={d: publication for d in training}
    )
    result = climatology_reference(TARGET, ISSUE, profile)
    assert result["label_under_declared_availability"] == "dry"
    assert not result["source_provenance_authenticated"]
    with pytest.raises(ValueError, match="after forecast issue"):
        climatology_reference(
            date(2020, 1, 3), datetime(2019, 12, 31, 12, tzinfo=HKT), profile
        )


@pytest.mark.parametrize(
    "mutation", ["label", "count", "known", "last_end", "publication"]
)
def test_changed_reference_counts_or_times_cannot_create_a_usable_winning_label(
    training, mutation
):
    profile = monthly_climatology_profile(training)
    row = profile["months"][0]
    if mutation == "label":
        row["conditional_historical_label"] = "rain"
    elif mutation == "count":
        row["expected_days"] -= 1
    elif mutation == "known":
        row["known_observation_days"] = True
    elif mutation == "last_end":
        row["last_observation_window_end"] = "2000-01-01T00:00:00+08:00"
    else:
        row["unknown_publication_days"] = 0
    with pytest.raises(ValueError):
        climatology_reference(TARGET, ISSUE, profile)


@pytest.mark.parametrize("threshold", [Decimal(0), Decimal("NaN")])
def test_missing_observations_cannot_bypass_an_invalid_threshold(threshold):
    with pytest.raises(ValueError, match="threshold"):
        persistence_reference(TARGET, ISSUE, {}, threshold=threshold)
    with pytest.raises(ValueError, match="threshold"):
        monthly_climatology_profile({}, threshold=threshold)
