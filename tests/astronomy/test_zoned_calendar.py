"""Independent Temporal calendar labels, including UTC outside datetime bounds."""

import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.core.almanac import localize_datetime
from fatebridge.core.output_chinese import SolarTerm
from fatebridge.services.timing_clock import resolve_analysis_moment
from fatebridge.utils.civil_time import ZonedCalendar
from fatebridge.utils.timezones import parse_timezone_name

REFERENCE = Path(__file__).parents[1] / "data/zoned_calendar_temporal_v1"


def test_every_independent_temporal_label_and_epoch_microsecond():
    path = REFERENCE / "oracle.json.gz"
    raw = path.read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    reference = json.loads(gzip.decompress(raw))
    plan = gzip.decompress((REFERENCE / "plan.json.gz").read_bytes())
    assert hashlib.sha256(plan).hexdigest() == reference["plan_sha256"]
    assert reference["count"] == len(reference["rows"]) == 4392
    for row in reference["rows"]:
        utc = ZonedCalendar.from_isoformat(row["input"]["utc"]).utc
        clock = ZonedCalendar(utc, parse_timezone_name(row["input"]["zone"]))
        epoch_microseconds = (
            utc.ordinal - 719163
        ) * 86400000000 + utc.microseconds_of_day
        assert str(epoch_microseconds) == row["epoch_microseconds"], row["input"]
        assert list(clock.local_parts) == row["local_parts"], row["input"]
        assert clock.offset.total_seconds() == row["offset_seconds"], row["input"]
        assert ZonedCalendar.from_isoformat(clock.isoformat()).utc == utc
        local = clock.as_datetime()
        if local is not None:
            converted = localize_datetime(local, row["input"]["zone"])
            assert (
                list(
                    (
                        converted.year,
                        converted.month,
                        converted.day,
                        converted.hour,
                        converted.minute,
                        converted.second,
                        converted.microsecond,
                    )
                )
                == row["local_parts"]
            )
            assert ZonedCalendar.from_datetime(converted).utc == utc


def test_every_declared_zone_matches_the_official_iana_c_implementation():
    path = (
        REFERENCE.parents[1] / "fixtures/zoned-calendar-iana2026f-reference-v1.json.gz"
    )
    raw = path.read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    reference = json.loads(gzip.decompress(raw))
    assert len(reference["rows"]) == 11343
    assert len(reference["plan"]["zones"]) == 597
    for row in reference["rows"]:
        utc = ZonedCalendar.from_isoformat(row["utc"]).utc
        clock = ZonedCalendar(utc, parse_timezone_name(row["zone"]))
        assert list(clock.local_parts) == row["local_parts"], row
        assert clock.offset.total_seconds() == row["offset_seconds"], row
        assert ZonedCalendar.from_isoformat(clock.isoformat()).utc == utc


@pytest.mark.parametrize(
    "local,zone,expected_utc",
    [
        ("0001-01-01T00:12:00", "+08:00", "0000-12-31T16:12:00+00:00"),
        ("9999-12-31T23:12:00", "-08:00", "+010000-01-01T07:12:00+00:00"),
    ],
)
def test_analysis_reference_keeps_the_real_instant_at_civil_year_edges(
    local, zone, expected_utc
):
    moment = datetime.fromisoformat(local)
    resolution = resolve_analysis_moment(
        "liuyue_analysis",
        zone,
        analysis_year=moment.year,
        analysis_month=moment.month,
        analysis_day=moment.day,
        analysis_hour=moment.hour,
        analysis_minute=moment.minute,
    )
    assert resolution.reference["utc_datetime"] == expected_utc
    assert resolution.moment == moment


@pytest.mark.parametrize(
    "text",
    ["0000-12-06T01:32:06.707714+00:00", "+010000-01-05T23:59:59.999999-08:00"],
)
def test_auxiliary_solar_labels_validate_without_clipping_the_year(text):
    clock = ZonedCalendar.from_isoformat(text)
    legacy = clock.isoformat(sep=" ", include_offset=False)
    result = SolarTerm.model_validate(
        dict(
            datetime=legacy,
            datetime_with_offset=text,
            utc_offset_seconds=clock.offset.total_seconds(),
        )
    )
    assert result.datetime_with_offset == text
    with pytest.raises(ValueError, match="旧钟面标签"):
        SolarTerm.model_validate(
            dict(datetime="2000-01-01 00:00:00", datetime_with_offset=text)
        )


def test_calendar_labels_require_an_offset_and_keep_invalid_dates_invalid():
    with pytest.raises(ValueError, match="aware"):
        ZonedCalendar.from_datetime(datetime(2000, 1, 1))
    with pytest.raises(ValueError, match="aware"):
        ZonedCalendar.from_isoformat("+010000-01-01T00:00:00")
    with pytest.raises(ValueError):
        ZonedCalendar.from_isoformat("0000-02-30T00:00:00+00:00")
    assert (
        ZonedCalendar.from_datetime(datetime(2000, 1, 1, tzinfo=timezone.utc)).fold == 0
    )
