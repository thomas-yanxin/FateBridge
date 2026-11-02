"""Independent calendar controls, leap-day legality, range and clock ordering."""

import json
from datetime import date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.civil_calendar import civil_datetime, gregorian_date
from fatebridge.core.output_western import WesternCivilCalendarConversion
from fatebridge.core.predictive.native_chart import build_native_subject
from fatebridge.core.requests.western_events import (
    AstroElectionRequest,
    AstroHoraryRequest,
)
from scripts.audit_western_civil_calendar import audit
from tests.test_western_election import CANDIDATE
from tests.test_western_horary import QUESTION

REFERENCE = json.loads(
    (
        Path(__file__).parent / "fixtures/western-civil-calendar-reference.json"
    ).read_text()
)


def test_sealed_primary_and_supplementary_implementation_controls():
    value = audit()
    assert value["primary_numeric_examples"] == 2
    assert value["manual_conversion_controls"] == 13
    assert value["supplementary_implementation_vectors"] == 192
    assert value["bounded_date_conversion_passed"]
    assert not value["historical_clock_reconstruction_accepted"]


@pytest.mark.parametrize("row", REFERENCE["manual_conversion_controls"])
def test_frozen_manual_date_controls_and_clock_preservation(row):
    at, receipt = civil_datetime(*row["date"], 23, 59, row["calendar"])
    assert at.date() == date(*row["gregorian"]) and at.time().isoformat() == "23:59:00"
    WesternCivilCalendarConversion.model_validate(receipt)
    assert receipt["input_date"] == dict(zip(["year", "month", "day"], row["date"]))
    assert receipt["normalized_local_datetime"] == at.isoformat()
    assert receipt["automatic_regional_reform_applied"] is False
    assert receipt["historical_clock_reconstruction_performed"] is False


@pytest.mark.parametrize(
    "model,prefix,inputs",
    [
        (AstroHoraryRequest, "question_", QUESTION),
        (AstroElectionRequest, "candidate_", CANDIDATE),
    ],
)
@pytest.mark.parametrize("year", [1700, 1800, 1900, 2100])
def test_julian_century_leap_dates_validate_before_binding_and_gregorian_rejects(
    model, prefix, inputs, year
):
    changed = {**inputs, prefix + "year": year, prefix + "month": 2, prefix + "day": 29}
    with pytest.raises(ValidationError):
        model.model_validate(changed)
    request = model.model_validate({**changed, prefix + "calendar": "julian"})
    assert request.model_dump()[prefix + "day"] == 29
    with pytest.raises(ValidationError):
        model.model_validate(
            {**changed, prefix + "calendar": "julian", prefix + "day": 30}
        )


@pytest.mark.parametrize(
    "calendar,values",
    [
        ("julian", (0, 1, 1)),
        ("julian", (1, 1, 1)),
        ("julian", (9999, 12, 31)),
        ("julian", (1700, 2, 30)),
        ("julian", (1701, 2, 29)),
        ("julian", (2000, 13, 1)),
        ("julian", (True, 1, 3)),
        ("auto", (2024, 1, 1)),
        ("gregorian", (2024, 1, 1)),
    ],
)
def test_invalid_dates_unknown_reform_and_unrepresentable_ranges_are_rejected(
    calendar, values
):
    with pytest.raises(ValueError):
        gregorian_date(*values, calendar)


def test_a_julian_only_label_has_no_fictional_same_label_gregorian_offset():
    at, value = civil_datetime(1700, 2, 29, 12, 0, "julian")
    assert at == datetime(1700, 3, 11, 12)
    assert value["same_label_gregorian_date_valid"] is False
    assert value["same_label_gregorian_offset_days"] is None


@pytest.mark.parametrize(
    "label,zone,error",
    [
        ((2024, 3, 18, 2, 30), "Europe/Paris", "nonexistent"),
        ((2024, 10, 21, 1, 30), "America/New_York", "ambiguous"),
    ],
)
def test_timezone_gap_and_fold_validation_uses_the_converted_date(label, zone, error):
    normalized, _ = civil_datetime(*label, "julian")
    with pytest.raises(ValueError, match=error):
        build_native_subject(
            name="fictional clock control",
            local_datetime=normalized,
            longitude=0,
            latitude=45,
            timezone_name=zone,
        )


@pytest.mark.parametrize("zodiac,house", [("Tropic", "R"), ("Sidereal", "W")])
def test_equivalent_calendars_preserve_exact_native_epoch_positions_and_house_cusps(
    zodiac, house
):
    at, receipt = civil_datetime(1634, 7, 16, 11, 0, "julian")
    options = dict(
        name="fictional historical date-label control",
        longitude=0,
        latitude=51.5,
        timezone_name="UTC",
        zodiac_type=zodiac,
        house_system=house,
    )
    selected = build_native_subject(local_datetime=at, **options)
    expected = build_native_subject(local_datetime=datetime(1634, 7, 26, 11), **options)
    assert selected.julian_day == expected.julian_day
    assert selected.julian_day_tt == expected.julian_day_tt
    assert [(k, v.abs_pos, v.house) for k, v in selected.points.items()] == [
        (k, v.abs_pos, v.house) for k, v in expected.points.items()
    ]
    assert selected.calculation_basis["calendar"] == "proleptic_gregorian"
    assert receipt["same_label_gregorian_offset_days"] == 10
    assert receipt["historical_clock_reconstruction_performed"] is False
