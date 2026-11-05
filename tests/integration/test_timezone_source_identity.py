"""Loaded TZif rules cannot be relabelled with a later file's identity."""

import hashlib
from datetime import datetime, timezone
from io import BytesIO

import pytest

from fatebridge.utils import timezones
from fatebridge.utils.errors import EphemerisSourceError

ZONE = "America/New_York"


@pytest.fixture
def source(monkeypatch):
    original = timezones.pytz.open_resource
    with original(ZONE) as handle:
        ny = handle.read()
    with original("Etc/UTC") as handle:
        utc = handle.read()
    state = {"data": ny, "ny": ny, "utc": utc}

    def open_resource(name):
        if name != ZONE:
            return original(name)
        if isinstance(state["data"], Exception):
            raise state["data"]
        return BytesIO(state["data"])

    timezones._parse_timezone_name_cached.cache_clear()
    monkeypatch.setattr(timezones.pytz, "open_resource", open_resource)
    yield state
    timezones._parse_timezone_name_cached.cache_clear()


def test_same_bytes_determine_rules_and_provenance(source):
    zone = timezones.parse_timezone_name(ZONE)
    at = datetime(1980, 7, 1, 12, tzinfo=zone)
    assert at.astimezone(timezone.utc).isoformat() == "1980-07-01T16:00:00+00:00"
    metadata = timezones.timezone_rules_metadata(ZONE)
    assert metadata["tzif_sha256"] == hashlib.sha256(source["ny"]).hexdigest()
    metadata["tzif_sha256"] = "caller-mutated"
    assert timezones.timezone_rules_metadata(ZONE)["tzif_sha256"] != "caller-mutated"
    assert timezones.parse_timezone_name(ZONE) is zone


@pytest.mark.parametrize(
    "reader", [timezones.parse_timezone_name, timezones.timezone_rules_metadata]
)
@pytest.mark.parametrize(
    "mutation",
    [
        "different_valid_tzif",
        "package_version",
        "iana_version",
        "unavailable",
        "corrupt_after_load",
    ],
)
def test_cached_rules_refuse_a_different_or_unavailable_current_source(
    source, monkeypatch, reader, mutation
):
    zone = timezones.parse_timezone_name(ZONE)
    if mutation == "package_version":
        monkeypatch.setattr(timezones.pytz, "__version__", "different-release")
    elif mutation == "iana_version":
        monkeypatch.setattr(timezones.pytz, "OLSON_VERSION", "different-iana")
    else:
        source["data"] = {
            "different_valid_tzif": source["utc"],
            "unavailable": FileNotFoundError("private/source/path"),
            "corrupt_after_load": b"not a TZif file",
        }[mutation]
    reason = (
        "timezone_rules_unavailable"
        if mutation == "unavailable"
        else "timezone_rules_changed"
    )
    with pytest.raises(EphemerisSourceError) as caught:
        reader(ZONE)
    assert caught.value.reason == reason
    assert "private/source/path" not in str(caught.value)
    # Existing datetimes remain immutable; refusal never rewrites their offsets.
    assert datetime(1980, 7, 1, 12, tzinfo=zone).utcoffset().total_seconds() == -14400


@pytest.mark.parametrize("raw", [b"", b"invalid", b"TZif2" + b"\0" * 8])
def test_invalid_declared_tzif_is_a_source_failure_before_caching(source, raw):
    source["data"] = raw
    with pytest.raises(EphemerisSourceError) as caught:
        timezones.parse_timezone_name(ZONE)
    assert caught.value.reason == "timezone_rules_invalid"
    source["data"] = source["ny"]
    assert (
        datetime(1980, 7, 1, 12, tzinfo=timezones.parse_timezone_name(ZONE))
        .utcoffset()
        .total_seconds()
        == -14400
    )


@pytest.mark.parametrize("zone", ["UTC", "GMT", "Z", "+00:19:32", "-05:00", "5.5"])
def test_explicit_offsets_need_no_named_zone_resource(source, zone):
    source["data"] = FileNotFoundError("private/source/path")
    assert timezones.parse_timezone_name(zone).utcoffset(None) is not None
    assert timezones.timezone_rules_metadata(zone) == {
        "provider": "datetime.timezone",
        "database": "explicit_fixed_offset",
    }


def test_invalid_user_zone_stays_a_validation_error(source):
    with pytest.raises(ValueError) as caught:
        timezones.parse_timezone_name("Private/NotAZone")
    assert not isinstance(caught.value, EphemerisSourceError)


def test_declared_zone_is_not_mistaken_for_bad_input_if_availability_list_omits_it(
    source, monkeypatch
):
    monkeypatch.setattr(timezones.pytz, "all_timezones_set", set())
    source["data"] = FileNotFoundError("private/source/path")
    with pytest.raises(EphemerisSourceError) as caught:
        timezones.parse_timezone_name(ZONE)
    assert caught.value.reason == "timezone_rules_unavailable"
