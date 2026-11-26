"""Loaded TZif rules cannot be relabelled with a later file's identity."""

import hashlib
from datetime import datetime, timezone
from io import BytesIO

import pytest
from pydantic_core import PydanticCustomError

from fatebridge.utils import timezones
from fatebridge.utils.civil_clock import resolve_civil_clock
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
        else:
            pass
        if isinstance(state["data"], Exception):
            raise state["data"]
        else:
            pass
        return BytesIO(state["data"])

    timezones._parse_timezone_name_cached.cache_clear()
    monkeypatch.setattr(timezones.pytz, "open_resource", open_resource)
    yield state
    timezones._parse_timezone_name_cached.cache_clear()


def test_same_bytes_determine_rules_and_provenance(source) -> None:
    zone = timezones.parse_timezone_name(ZONE)
    at = datetime(1980, 7, 1, 12, tzinfo=zone)
    assert at.astimezone(timezone.utc).isoformat() == "1980-07-01T16:00:00+00:00"
    metadata = timezones.timezone_rules_metadata(ZONE)
    assert metadata["iana_version"] == timezones.pytz.OLSON_VERSION
    metadata["iana_version"] = "caller-mutated"
    assert timezones.timezone_rules_metadata(ZONE)["iana_version"] != "caller-mutated"
    assert timezones.parse_timezone_name(ZONE) is zone


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
def test_cached_rules_keep_the_loaded_source_identity(
    source, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    zone = timezones.parse_timezone_name(ZONE)
    metadata = timezones.timezone_rules_metadata(ZONE)
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
    assert timezones.parse_timezone_name(ZONE) is zone
    assert timezones.timezone_rules_metadata(ZONE) == metadata
    assert datetime(1980, 7, 1, 12, tzinfo=zone).utcoffset().total_seconds() == -14400


@pytest.mark.parametrize("raw", [b"", b"invalid", b"TZif2" + b"\0" * 8])
def test_invalid_declared_tzif_is_a_source_failure_before_caching(source, raw) -> None:
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
def test_explicit_offsets_need_no_named_zone_resource(source, zone: str) -> None:
    source["data"] = FileNotFoundError("private/source/path")
    assert timezones.parse_timezone_name(zone).utcoffset(None) is not None
    assert timezones.timezone_rules_metadata(zone) == {
        "provider": "datetime.timezone",
        "database": "explicit_fixed_offset",
    }


@pytest.mark.parametrize("zone", ["Private/NotAZone", "Etc/Unknown"])
def test_invalid_user_zone_stays_a_validation_error(source, zone: str) -> None:
    with pytest.raises(ValueError) as caught:
        timezones.parse_timezone_name(zone)
    assert not isinstance(caught.value, EphemerisSourceError)
    assert not isinstance(caught.value, PydanticCustomError)


def test_factory_zone_cannot_supply_a_defined_offset() -> None:
    with pytest.raises(PydanticCustomError) as caught:
        timezones.parse_timezone_name("Factory")
    assert caught.value.type == "unresolved_timezone_offset"


@pytest.mark.parametrize(
    "zone,wall",
    [
        ("Antarctica/Casey", datetime(1969, 1, 1, 4)),
        ("Antarctica/Vostok", datetime(1994, 11, 1, 3, 30)),
        ("Antarctica/Vostok", datetime(1994, 1, 31, 20)),
    ],
)
def test_mixed_tzif_clock_types_report_unresolved_offset(zone: str, wall) -> None:
    # IANA 2026f transitions between -00 and a known station offset.
    # The stored zero for -00 cannot establish a civil gap or overlap.
    with pytest.raises(PydanticCustomError) as caught:
        resolve_civil_clock(wall, zone)
    assert caught.value.type == "unresolved_timezone_offset"


@pytest.mark.parametrize(
    "zone,wall,offset,fold,expected_utc",
    [
        (
            "America/Cambridge_Bay",
            datetime(1919, 12, 31, 20),
            "-07:00",
            1,
            datetime(1920, 1, 1, 3, tzinfo=timezone.utc),
        ),
        (
            "Antarctica/Vostok",
            datetime(1994, 1, 31, 20),
            "+07:00",
            0,
            datetime(1994, 1, 31, 13, tzinfo=timezone.utc),
        ),
    ],
)
def test_mixed_tzif_clock_types_preserve_an_explicitly_selected_defined_occurrence(
    zone: str, wall, offset: str, fold: int, expected_utc
) -> None:
    chosen = resolve_civil_clock(wall, zone, offset)
    assert chosen.fold == fold
    assert chosen.astimezone(timezone.utc) == expected_utc
    with pytest.raises(PydanticCustomError) as caught:
        resolve_civil_clock(wall, zone, "+00:00")
    assert caught.value.type == "unresolved_timezone_offset"


def test_declared_zone_is_not_mistaken_for_bad_input_if_availability_list_omits_it(
    source, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(timezones.pytz, "all_timezones_set", set())
    source["data"] = FileNotFoundError("private/source/path")
    with pytest.raises(EphemerisSourceError) as caught:
        timezones.parse_timezone_name(ZONE)
    assert caught.value.reason == "timezone_rules_unavailable"
