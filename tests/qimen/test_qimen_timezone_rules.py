"""IANA text-derived reference cases outside dateutil's 32-bit interval."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.services.metaphysics import calculate_qimen_analysis
from fatebridge.utils import timezones

ROOT = Path(__file__).parents[1] / "fixtures/qimen_timezone_iana_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text())


def test_iana_source_excerpts_are_frozen():
    for source in REFERENCE["sources"]:
        assert (
            hashlib.sha256((ROOT / source["excerpt_file"]).read_bytes()).hexdigest()
            == source["excerpt_sha256"]
        )


@pytest.mark.parametrize("case", REFERENCE["cases"])
def test_64bit_transitions_and_future_rules_match_iana_text(case):
    zone = timezones.parse_timezone_name(case["zone"])
    at = datetime.fromisoformat(case["at"]).replace(tzinfo=zone)
    assert at.utcoffset().total_seconds() == case["offset_seconds"]
    assert at.dst().total_seconds() == case["dst_seconds"]
    timezones.validate_local_clock(at)


@pytest.mark.parametrize("case", REFERENCE["invalid_clocks"])
def test_future_dst_gap_and_fold_checks_do_not_stop_at_2037(case):
    zone = timezones.parse_timezone_name(case["zone"])
    at = datetime.fromisoformat(case["at"]).replace(tzinfo=zone)
    with pytest.raises(ValueError, match=case["kind"]):
        timezones.validate_local_clock(at)


@pytest.mark.parametrize(
    "year,hour,minute,expected_hour_branch",
    [(2040, 1, 30, "子"), (1900, 1, 1, "丑")],
)
def test_wrong_utc_offset_previously_changed_qimen_solar_hour(
    year, hour, minute, expected_hour_branch
):
    result = calculate_qimen_analysis(
        analysis_year=year,
        analysis_month=7,
        analysis_day=1,
        analysis_hour=hour,
        analysis_minute=minute,
        analysis_timezone="America/New_York",
        analysis_longitude=-74.006,
        use_true_solar_time=True,
    )
    assert "error" not in result
    assert result["qimen"]["time_ganzhi"][-1] == expected_hour_branch
    metadata = result["qimen"]["calendar_policy"]["timezone_rules"]
    assert metadata["provider"] == "zoneinfo.from_file"
    assert metadata["iana_version"]
    assert len(metadata["tzif_sha256"]) == 64


def test_named_zones_use_declared_data_even_if_host_reader_is_unavailable(monkeypatch):
    def fail_if_used(*args, **kwargs):
        raise AssertionError(
            "host dateutil database must not determine named-zone rules"
        )

    monkeypatch.setattr(timezones.tz, "gettz", fail_if_used)
    timezones._parse_timezone_name_cached.cache_clear()
    try:
        zone = timezones.parse_timezone_name("America/Coyhaique")
        assert datetime(2026, 7, 1, tzinfo=zone).utcoffset().total_seconds() == -10800
    finally:
        timezones._parse_timezone_name_cached.cache_clear()


def test_explicit_offset_metadata_does_not_claim_named_zone_dst_rules():
    assert timezones.timezone_rules_metadata("-04:00") == {
        "provider": "datetime.timezone",
        "database": "explicit_fixed_offset",
    }
