"""GMT source labels and numeric instants are separate acceptance criteria."""

from datetime import datetime, timedelta, timezone

import pytest

from fatebridge.utils.timezones import (
    parse_timezone_name,
    timezone_rules_metadata,
    validate_local_clock,
)


@pytest.mark.parametrize(
    "label",
    ["GMT", "GMT0", "GMT+0", "GMT-0", "gmt", "gMt+00:00", "GMT-00:00:00"],
)
def test_gmt_zero_retains_its_declared_label_and_known_instant(label):
    # Official tzdata2026e etcetera/backward and independent C observations
    # agree on offset0/GMT/DST0 for the four exact legacy IANA names. The
    # parser also accepts case-insensitive and numeric spellings of GMT.
    zone = parse_timezone_name(label)
    for year in (1800, 1900, 2000, 2038, 2399):
        local = datetime(year, 9, 1, 12, tzinfo=zone)
        validate_local_clock(local)
        assert local.tzname() == "GMT"
        assert local.utcoffset() == timedelta(0)
        assert local.dst() is None
        assert local.astimezone(timezone.utc) == local
    assert timezone_rules_metadata(label) == {
        "provider": "datetime.timezone",
        "database": "explicit_fixed_offset",
    }


@pytest.mark.parametrize("label", ["UTC", "Z", "+00:00", "-00:00", "0", "UTC+0"])
def test_other_known_zero_spellings_keep_their_utc_label(label):
    assert parse_timezone_name(label).tzname(None) == "UTC"


def test_nonzero_gmt_offset_keeps_its_numeric_convention():
    zone = parse_timezone_name("GMT+8")
    assert zone.tzname(None) == "UTC+08:00"
    assert datetime(1900, 1, 1, 12, tzinfo=zone).astimezone(timezone.utc) == datetime(
        1900, 1, 1, 4, tzinfo=timezone.utc
    )
