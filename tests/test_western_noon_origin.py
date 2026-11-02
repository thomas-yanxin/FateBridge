"""Original noon-hour labels, composed calendar bounds and native clock identity."""

import hashlib
import json
import zipfile
from datetime import datetime
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.civil_calendar import civil_datetime, gregorian_date
from fatebridge.core.output_western import (
    WesternCivilCalendarConversion,
    WesternHourOriginConversion,
)
from fatebridge.core.requests.western_events import (
    AstroElectionRequest,
    AstroHoraryRequest,
)
from fatebridge.core.western_clock_origin import event_wall_datetime
from fatebridge.core.western_event_clock import build_event_subject

FIXTURES = Path(__file__).parent / "fixtures"
REFERENCE_FILE = FIXTURES / "western-noon-origin-reference.json"
REFERENCE = json.loads(REFERENCE_FILE.read_text())
REFERENCE_SHA = "67685c2edb97b67df94d3c5394d77e20b9876db4aa39066c84523789126c205f"
ARCHIVE_SHA = "8c14b3c73f3d42cbae313974223784f5d16d6cda4207964b450f682c519c2ebb"


def test_original_images_and_controls_were_sealed_before_candidate():
    assert hashlib.sha256(REFERENCE_FILE.read_bytes()).hexdigest() == REFERENCE_SHA
    p = FIXTURES / "western-noon-origin-sources.zip"
    assert hashlib.sha256(p.read_bytes()).hexdigest() == ARCHIVE_SHA
    with zipfile.ZipFile(p) as archive:
        assert archive.read("sources/reference.json") == REFERENCE_FILE.read_bytes()
        for row in REFERENCE["source_assets"]:
            raw = archive.read("sources/" + row["file"])
            assert len(raw) == row["bytes"]
            assert hashlib.sha256(raw).hexdigest() == row["sha256"]
        before = json.loads(archive.read("pre-edit.json"))
        assert (
            before["files"]["src/fatebridge/core/western_clock_origin.py"]["exists"]
            is False
        )


@pytest.mark.parametrize("row", REFERENCE["printed_hour_mappings"])
def test_p31_printed_hour_mappings(row):
    wall, calendar, origin = event_wall_datetime(
        2000, 1, 1, row["hour"], 0, hour_origin="noon"
    )
    assert wall == datetime(2000, 1, 1 + row["day_carry"], row["normalized_hour"])
    assert origin["day_carry"] == row["day_carry"]
    assert calendar["input_clock"] == {"hour": row["hour"], "minute": 0}
    assert origin["source_pages"] == [30, 31]
    assert not origin["physical_duration_applied"]
    assert not origin["source_clock_identification_performed"]


@pytest.mark.parametrize("row", REFERENCE["printed_dated_applications"])
def test_five_printed_dated_applications_without_reconstructing_their_aspects(row):
    wall, calendar, origin = event_wall_datetime(
        *row["date"], row["hour"], row["minute"], row["calendar"], row["hour_origin"]
    )
    assert wall.isoformat() == row["expected"]
    assert wall.strftime("%A") == row["printed_weekday"]
    assert calendar["input_date"] == dict(zip(["year", "month", "day"], row["date"]))
    assert (
        origin["normalized_date_label_jdn"] - origin["source_date_label_jdn"]
        == row["day_carry"]
    )
    WesternCivilCalendarConversion.model_validate(calendar)
    WesternHourOriginConversion.model_validate(origin)


@pytest.mark.parametrize("row", REFERENCE["calendar_boundary_controls"])
def test_frozen_calendar_boundaries_and_final_representability(row):
    args = (
        *row["date"],
        row["hour"],
        row["minute"],
        row["calendar"],
        row["hour_origin"],
    )
    if row["expected"] is None:
        with pytest.raises(ValueError, match="Final hour-origin"):
            event_wall_datetime(*args)
    else:
        wall, calendar, origin = event_wall_datetime(*args)
        assert wall.isoformat() == row["expected"]
        assert origin["day_carry"] == row["day_carry"]
        assert calendar["normalized_date_representable"] == (
            row["source_date_ordinal"] >= 1
        )
        if row["source_date_ordinal"] < 1:
            assert calendar["normalized_local_datetime"] is None
            assert origin["calendar_normalized_label"] is None
        WesternCivilCalendarConversion.model_validate(calendar)
        WesternHourOriginConversion.model_validate(origin)


@pytest.mark.parametrize(
    "model,prefix",
    [(AstroHoraryRequest, "question"), (AstroElectionRequest, "candidate")],
)
@pytest.mark.parametrize("row", REFERENCE["calendar_boundary_controls"])
def test_request_checks_the_final_label_instead_of_rejecting_a_valid_intermediate(
    model, prefix, row
):
    p = {f"{prefix}_{k}": v for k, v in zip(["year", "month", "day"], row["date"])}
    p.update(
        {
            prefix + "_hour": row["hour"],
            prefix + "_minute": row["minute"],
            prefix + "_calendar": row["calendar"],
            prefix + "_hour_origin": row["hour_origin"],
            "longitude": 0,
            "latitude": 40,
        }
    )
    if row["expected"] is None:
        with pytest.raises(ValidationError):
            model.model_validate(p)
    else:
        assert (
            getattr(model.model_validate(p), prefix + "_hour_origin")
            == row["hour_origin"]
        )


def test_rescued_julian_lower_bound_keeps_the_raw_label_and_real_native_epoch():
    with pytest.raises(ValueError):
        gregorian_date(1, 1, 2, "julian")
    wall, c, o = event_wall_datetime(1, 1, 2, 12, 0, "julian", "noon")
    assert wall == datetime(1, 1, 1)
    assert c["date_label_jdn"] == 1721425 and o["normalized_date_label_jdn"] == 1721426
    native, receipt = build_event_subject(
        name="synthetic lower-bound clock",
        local_datetime=wall,
        longitude=0,
        latitude=40,
        timezone_name="UTC",
    )
    assert native.julian_day == 1721425.5
    assert receipt["converted_utc"] == "0001-01-01T00:00:00+00:00"


@pytest.mark.parametrize("row", REFERENCE["published_jd_label_examples"])
def test_usno_published_jd_definitions_are_clock_label_checks_not_utc_assumptions(row):
    wall, _, _ = event_wall_datetime(
        *row["date"], row["hour"], row["minute"], hour_origin=row["hour_origin"]
    )
    assert wall.isoformat() == row["expected_wall"]
    label_jd = (
        Fraction(wall.toordinal())
        + Fraction(3442849, 2)
        + Fraction(wall.hour * 60 + wall.minute, 1440)
    )
    assert label_jd == Fraction(row["jd_ut1"])


def test_noon_origin_reaches_the_previously_unsupported_utc_leap_second():
    wall, _, _ = event_wall_datetime(1977, 12, 31, 12, 0, hour_origin="noon")
    assert wall == datetime(1978, 1, 1)
    subject, receipt = build_event_subject(
        name="synthetic leap-carrier gap",
        local_datetime=wall,
        longitude=0,
        latitude=40,
        clock_basis="local_mean_solar",
    )
    assert subject.julian_day == 2443509.5
    assert receipt["converted_utc"].startswith("1977-12-31T23:59:60.")
    assert receipt["utc_representation"]["utc_is_leap_second"]
    assert not receipt["utc_representation"]["datetime_representable"]


def test_non_leap_usno_epoch_reaches_exact_native_ut1():
    wall, _, _ = event_wall_datetime(1978, 7, 21, 3, 0, hour_origin="noon")
    native, _ = build_event_subject(
        name="synthetic published UT1 label",
        local_datetime=wall,
        longitude=0,
        latitude=40,
        clock_basis="local_mean_solar",
    )
    assert native.julian_day == 2443711.125


def test_p31_supplementary_sexagesimal_minutes_keep_the_same_day():
    # Supplementary original-image reading after candidate construction;
    # deliberately not inserted into the pre-candidate application denominator.
    wall, _, origin = event_wall_datetime(2000, 1, 1, 11, 48, hour_origin="noon")
    assert wall == datetime(2000, 1, 1, 23, 48)
    assert origin["day_carry"] == 0


@pytest.mark.parametrize("basis", ["civil", "local_mean_solar", "local_apparent_solar"])
def test_origin_normalization_precedes_each_clock_basis_without_changing_native_facts(
    basis,
):
    wall, _, _ = event_wall_datetime(1646, 1, 3, 21, 0, "julian", "noon")
    kw = dict(
        name="synthetic epoch identity",
        longitude=0,
        latitude=40,
        clock_basis=basis,
        timezone_name="UTC" if basis == "civil" else None,
    )
    a, _ = build_event_subject(local_datetime=wall, **kw)
    b, _ = build_event_subject(local_datetime=datetime(1646, 1, 14, 9), **kw)
    assert (
        a.points == b.points
        and a.julian_day_tt == b.julian_day_tt
        and a.julian_day == b.julian_day
    )


@pytest.mark.parametrize(
    "parts,zone,error",
    [
        ((2024, 3, 30, 14, 30), "Europe/Paris", "nonexistent"),
        ((2024, 11, 2, 13, 30), "America/New_York", "ambiguous"),
    ],
)
def test_dst_validation_reads_the_final_nominal_clock_label(parts, zone, error):
    wall, _, _ = event_wall_datetime(*parts, hour_origin="noon")
    with pytest.raises(ValueError, match=error):
        build_event_subject(
            name="synthetic DST source label",
            local_datetime=wall,
            longitude=0,
            latitude=40,
            timezone_name=zone,
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"hour": 24},
        {"hour": -1},
        {"minute": 60},
        {"hour": True},
        {"hour_origin": "auto"},
        {"hour_origin": None},
        {"calendar": "auto"},
    ],
)
def test_unknown_origin_or_invalid_labels_are_not_inferred_or_wrapped(changes):
    kw = dict(year=2024, month=1, day=1, hour=0, minute=0, hour_origin="noon")
    with pytest.raises((ValueError, TypeError)):
        event_wall_datetime(**{**kw, **changes})


@pytest.mark.parametrize(
    "parts,calendar",
    [((2024, 6, 1, 14, 30), "proleptic_gregorian"), ((1700, 2, 29, 0, 0), "julian")],
)
def test_default_midnight_keeps_existing_calendar_receipt_and_wall_label(
    parts, calendar
):
    a, old = civil_datetime(*parts, calendar)
    b, new, origin = event_wall_datetime(*parts, calendar)
    assert a == b and old == new
    assert not origin["normalization_performed"] and origin["day_carry"] == 0
