"""A solar clock label cannot select a second civil UTC offset."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from fatebridge.core.astro import sensitivity_timing
from fatebridge.core.astro.birth import AstroBirthInfo, build_astro_birth_info
from fatebridge.utils.timezones import parse_timezone_name, timezone_rules_metadata
from tests.support.reference_data import verify_source_files

FIXTURE = Path(__file__).parents[1] / "data/astro/solar_offset"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())
PHYSICAL_REFERENCE = json.loads((FIXTURE / "physical-clock-reference.json").read_text())
PHYSICAL_ROWS = {row["id"]: row for row in PHYSICAL_REFERENCE["rows"]}
ROWS = REFERENCE["rows"]
NAMED = [r for r in ROWS if not r["ambiguous_nominal_label"]]
AMBIGUOUS = [r for r in ROWS if r["ambiguous_nominal_label"]]


def test_reference_and_copied_timezone_rules_are_frozen_before_candidate() -> None:
    verify_source_files(FIXTURE)
    for name, digest in json.loads((FIXTURE / "timezone-data.json").read_text())[
        "sha256"
    ].items():
        assert (
            hashlib.sha256((FIXTURE / "tzif" / name).read_bytes()).hexdigest() == digest
        )
    for name, digest in json.loads((FIXTURE / "timezone-data.json").read_text())[
        "sha256"
    ].items():
        assert timezone_rules_metadata(name)["tzif_sha256"] == digest
    assert len(ROWS) == 96 and len(NAMED) == 78 and len(AMBIGUOUS) == 18
    assert len(REFERENCE["transitions"]) == 12
    assert not REFERENCE["fatebridge_imported"]
    assert set(PHYSICAL_ROWS) == {row["id"] for row in ROWS}
    assert (
        hashlib.sha256((FIXTURE / "reference.json").read_bytes()).hexdigest()
        == PHYSICAL_REFERENCE["source"]["original_reference_sha256"]
    )


def kwargs(row, *, named=True):
    wall = datetime.fromisoformat(row["recorded_local"])
    return dict(
        birth_year=wall.year,
        birth_month=wall.month,
        birth_day=wall.day,
        birth_hour=wall.hour,
        birth_minute=wall.minute,
        birth_second=wall.second,
        birth_timezone=row["zone"] if named else row["recorded_local"][-6:],
        birth_longitude=row["longitude"],
        birth_latitude=row["latitude"],
        use_true_solar_time=True,
    )


def assert_expected(birth, row):
    actual = birth.require_utc_datetime
    expected = PHYSICAL_ROWS[row["id"]]
    assert (
        abs(
            (
                actual - datetime.fromisoformat(row["expected_effective_utc"])
            ).total_seconds()
        )
        <= 0.0002
    )
    assert actual == datetime.fromisoformat(expected["effective_utc"])
    assert (
        birth.solar_datetime.replace(tzinfo=None).isoformat() == expected["solar_wall"]
    )
    assert (
        birth.solar_datetime.utcoffset().total_seconds()
        == row["recorded_offset_seconds"]
    )
    assert (
        birth.recorded_datetime.astimezone(timezone.utc).isoformat()
        == row["recorded_utc"]
    )


@pytest.mark.parametrize("row", NAMED, ids=lambda r: r["id"])
def test_nominal_confirmed_named_clock_keeps_recorded_offset(row) -> None:
    assert_expected(build_astro_birth_info(**kwargs(row)), row)


@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["id"])
def test_explicit_offset_control_keeps_the_same_arithmetic(row) -> None:
    assert_expected(build_astro_birth_info(**kwargs(row, named=False)), row)


@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["id"])
def test_utc_sensitivity_sample_does_not_reinterpret_gap_or_fold_label(
    row, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = datetime.fromisoformat(row["recorded_utc"])
    offset = timedelta(seconds=30)
    recorded = (target - offset).astimezone(parse_timezone_name(row["zone"]))
    template = AstroBirthInfo(
        name="Engineering fixture",
        birth_place="Synthetic engineering inputs",
        timezone=row["zone"],
        longitude=row["longitude"],
        latitude=row["latitude"],
        local_datetime=recorded,
        utc_datetime=target - offset,
        recorded_datetime=recorded,
        applied_true_solar=True,
    )
    original = sensitivity_timing.solar_rebase_correction
    rule_samples = {}

    def observe(scales, rule_clock, zone, longitude):
        rule_samples[scales.tt] = (rule_clock, zone)
        return original(scales, rule_clock, zone, longitude)

    monkeypatch.setattr(sensitivity_timing, "solar_rebase_correction", observe)
    interval = sensitivity_timing.specialty_sample_times(template, 0.5)
    sample = interval.samples[interval.label_offsets.index(offset)]
    rule_clock, zone = rule_samples[sample.recorded.tt]
    assert rule_clock == sample.recorded.epoch.require_datetime() == target
    assert zone == row["zone"]
    with (FIXTURE / "tzif" / zone).open("rb") as stream:
        frozen_zone = ZoneInfo.from_file(stream)
    rule_offset = rule_clock.astimezone(frozen_zone).utcoffset()
    assert rule_offset.total_seconds() == row["recorded_offset_seconds"]
    actual = sample.effective.require_datetime()
    expected = PHYSICAL_ROWS[row["id"]]
    assert (
        abs(
            (
                actual - datetime.fromisoformat(row["expected_effective_utc"])
            ).total_seconds()
        )
        <= 0.0002
    )
    assert actual == datetime.fromisoformat(expected["effective_utc"])
    solar = actual.astimezone(timezone(rule_offset))
    assert solar.replace(tzinfo=None).isoformat() == expected["solar_wall"]


@pytest.mark.parametrize("row", AMBIGUOUS, ids=lambda r: r["id"])
def test_ambiguous_nominal_label_stays_rejected_without_an_explicit_offset(row) -> None:
    with pytest.raises(ValueError, match="ambiguous local time"):
        build_astro_birth_info(**kwargs(row))
