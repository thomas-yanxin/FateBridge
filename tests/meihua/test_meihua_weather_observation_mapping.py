"""Source flags, units and missingness must not manufacture clear-sky facts."""

from datetime import date
from decimal import Decimal

import pytest

from fatebridge.validation.meihua_weather_observation_mapping import (
    CloudObservation,
    audit_rainfall_cloud_mapping,
    parse_hko_cloud,
)
from fatebridge.validation.meihua_weather_study import RainObservation

DAY = date(2025, 1, 1)


def source(*rows, title="Daily Mean Amount of Cloud (%) at the Hong Kong Observatory"):
    return (
        "日平均雲量(百分比) - 天文台\n"
        + title
        + "\n年/Year,月/Month,日/Day,數值/Value,數據完整性/data Completeness\n"
        + "\n".join(rows)
        + "\n*** Unavailable\n# data incomplete\nC data Complete\n"
    ).encode("utf-8-sig")


def parse(raw):
    return parse_hko_cloud(raw, start=DAY, end=date(2025, 1, 4))


def test_complete_cloud_is_a_percentage_not_sunshine_hours_or_eighths():
    values = parse(source("2025,1,1,100,C", "2025,1,2,0,C"))
    assert values[DAY].complete_percent() == Decimal("100")
    assert values[date(2025, 1, 2)].complete_percent() == Decimal("0")
    with pytest.raises(ValueError, match="dataset"):
        parse(source("2025,1,1,100,C", title="Bright Sunshine (hours)"))


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "100.1", "trace", "x"])
def test_invalid_cloud_measurements_fail_closed(value):
    with pytest.raises(ValueError):
        parse(source(f"2025,1,1,{value},C"))


def test_incomplete_and_unavailable_values_remain_unknown():
    values = parse(source("2025,1,1,100,#", "2025,1,2,***,C"))
    assert values[DAY].cloud_percent == 100
    assert values[DAY].complete_percent() is None
    assert values[date(2025, 1, 2)].complete_percent() is None


def test_duplicate_dates_and_undocumented_flags_are_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        parse(source("2025,1,1,0,C", "2025,1,1,100,C"))
    with pytest.raises(ValueError, match="completeness"):
        parse(source("2025,1,1,100,unknown"))


def test_dry_and100percent_cloud_does_not_supply_sunny_or_prior_weather():
    clouds = parse(source("2025,1,1,100,C", "2025,1,2,90,C"))
    rains = {
        DAY: RainObservation(DAY, "0", "C", "complete_numeric", Decimal("0")),
        date(2025, 1, 2): RainObservation(
            date(2025, 1, 2), "trace", "C", "complete_trace", None, Decimal("0.05")
        ),
    }
    report = audit_rainfall_cloud_mapping(
        ["2025-01-01", "2025-01-02", "2025-01-03"], rains, clouds
    )
    assert report["cohort_days"] == 3
    assert report["paired_complete_days"] == 2
    assert report["days_with_unknown_rain_or_cloud"] == 1
    assert report["below_rain_threshold_paired_days"] == 2
    assert report["below_rain_threshold_and_reported100percent_cloud_days"] == 1
    assert report["reported100percent_cloud_days_including_unknown_rain"] == 1
    assert report["complete_cloud_percent_histogram"] == {"100": 1, "90": 1}
    assert report["below_rain_threshold_cloud_percent_histogram"] == {"100": 1, "90": 1}
    assert report["sunny_labels_generated"] == 0
    assert report["prior_condition_inputs_generated"] == 0
    assert not report["forecast_skill_evaluated"]
    assert not report["historical_as_of_availability_established"]
    assert not report["records"][2]["paired_complete"]


@pytest.mark.parametrize(
    "cohort", [[], ["2025-01-01", "2025-01-01"], ["2025-01-02", "2025-01-01"]]
)
def test_mapping_does_not_drop_repeated_or_reordered_dates(cohort):
    with pytest.raises(ValueError, match="cohort"):
        audit_rainfall_cloud_mapping(cohort, {}, {})


def test_inconsistent_observation_key_is_rejected():
    other = date(2025, 1, 2)
    clouds = {
        DAY: CloudObservation(other, "100", "C", "complete_numeric", Decimal(100))
    }
    with pytest.raises(ValueError, match="cohort key"):
        audit_rainfall_cloud_mapping(["2025-01-01"], {}, clouds)


@pytest.mark.parametrize("threshold", [Decimal("0"), Decimal("NaN")])
def test_even_empty_observations_cannot_bypass_invalid_rain_threshold(threshold):
    with pytest.raises(ValueError, match="threshold"):
        audit_rainfall_cloud_mapping(
            ["2025-01-01"], {}, {}, rain_threshold_mm=threshold
        )
