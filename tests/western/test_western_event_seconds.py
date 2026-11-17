"""Event seconds preserve declared labels and the existing physical time axis."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from fatebridge.core.requests.western_events import (
    AstroElectionRequest,
    AstroHoraryRequest,
)
from fatebridge.core.western_clock_origin import event_wall_datetime
from fatebridge.core.western_event_clock import build_event_subject


@pytest.mark.parametrize(
    "model,prefix",
    [(AstroElectionRequest, "candidate"), (AstroHoraryRequest, "question")],
)
def test_confirmed_seconds_survive_request_binding_and_reject_fractional_labels(
    model, prefix
):
    inputs = {
        f"{prefix}_year": 2001,
        f"{prefix}_month": 10,
        f"{prefix}_day": 19,
        f"{prefix}_hour": 8,
        f"{prefix}_minute": 15,
        f"{prefix}_second": 39,
        "timezone_name": "-04:00",
        "longitude": -77.06583333333333,
        "latitude": 38.93611111111111,
    }
    bound = model.model_validate(inputs).model_dump()
    assert bound[f"{prefix}_second"] == 39
    for invalid in (39.5, True, 60):
        with pytest.raises(ValidationError):
            model.model_validate({**inputs, f"{prefix}_second": invalid})


@pytest.mark.parametrize(
    "parts,calendar,origin,expected",
    [
        (
            (2001, 10, 19, 8, 15, 39),
            "proleptic_gregorian",
            "midnight",
            "2001-10-19T08:15:39",
        ),
        ((1700, 2, 29, 23, 59, 59), "julian", "noon", "1700-03-12T11:59:59"),
        ((1, 1, 2, 12, 0, 1), "julian", "noon", "0001-01-01T00:00:01"),
        (
            (9999, 12, 31, 23, 59, 59),
            "proleptic_gregorian",
            "midnight",
            "9999-12-31T23:59:59",
        ),
    ],
)
def test_seconds_are_preserved_across_calendar_and_noon_carry(
    parts, calendar, origin, expected
):
    wall, calendar_receipt, origin_receipt = event_wall_datetime(
        *parts[:5], calendar, origin, second=parts[5]
    )
    assert wall.isoformat() == expected
    assert calendar_receipt["input_clock"]["second"] == parts[5]
    assert origin_receipt["input_clock"]["second"] == parts[5]
    assert origin_receipt["normalized_wall_datetime"] == expected


def test_published_second_label_reaches_the_physical_civil_epoch():
    subject, receipt = build_event_subject(
        name="Published2001chartreference",
        local_datetime=datetime(2001, 10, 19, 8, 15, 39),
        longitude=-77.06583333333333,
        latitude=38.93611111111111,
        timezone_name="-04:00",
        house_system="R",
    )
    assert receipt["input_wall_datetime"] == "2001-10-19T08:15:39"
    assert receipt["converted_utc"] == "2001-10-19T12:15:39+00:00"
    assert receipt["julian_day_tt"] == subject.julian_day_tt
    assert receipt["input_granularity"] == "second"
    assert not receipt["input_clock_accuracy_certified"]


def test_lmt_second_label_is_a_ut1_label_and_not_truncated_to_the_minute():
    subject, receipt = build_event_subject(
        name="Synthetic second label",
        local_datetime=datetime(2000, 1, 1, 1, 0, 59),
        longitude=15,
        latitude=40,
        clock_basis="local_mean_solar",
    )
    # At15E, 01:00:59 LMT is00:00:59 UT1. The UTC label differs by DUT1.
    expected = 2451544.5 + 59 / 86400
    assert abs(subject.julian_day - expected) * 86400 <= 0.0002
    assert receipt["input_wall_datetime"].endswith("01:00:59")
    assert receipt["solar_conversion"]["solar_model_call_count"] == 0


def test_subsecond_event_label_is_rejected_instead_of_silently_truncated():
    with pytest.raises(ValueError, match="whole.second"):
        build_event_subject(
            name="Unsupported subsecond label",
            local_datetime=datetime(2001, 10, 19, 8, 15, 39, 1),
            longitude=0,
            latitude=40,
            timezone_name="UTC",
        )
