"""A solar clock label cannot select a second civil UTC offset."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core.astro.birth import AstroBirthInfo, build_astro_birth_info
from fatebridge.core.astro.sensitivity import _sample_birth
from fatebridge.utils.timezones import parse_timezone_name, timezone_rules_metadata

FIXTURE = Path(__file__).parent / "fixtures/western-solar-offset-v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())
ROWS = REFERENCE["rows"]
NAMED = [r for r in ROWS if not r["ambiguous_nominal_label"]]
AMBIGUOUS = [r for r in ROWS if r["ambiguous_nominal_label"]]


def test_reference_and_copied_timezone_rules_are_frozen_before_candidate():
    for name, digest in json.loads(
        (FIXTURE / "reference-seal.json").read_text()
    ).items():
        path = FIXTURE / (
            "collector.py.txt" if name == "collect-reference.py" else name
        )
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
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
    assert (
        abs(
            (
                actual - datetime.fromisoformat(row["expected_effective_utc"])
            ).total_seconds()
        )
        <= 0.0002
    )
    assert (
        birth.solar_datetime.replace(tzinfo=None).isoformat()
        == row["expected_solar_wall"]
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
def test_nominal_confirmed_named_clock_keeps_recorded_offset(row):
    assert_expected(build_astro_birth_info(**kwargs(row)), row)


@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["id"])
def test_explicit_offset_control_keeps_the_same_arithmetic(row):
    assert_expected(build_astro_birth_info(**kwargs(row, named=False)), row)


@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["id"])
def test_utc_sensitivity_sample_does_not_reinterpret_gap_or_fold_label(row):
    target = datetime.fromisoformat(row["recorded_utc"])
    recorded = (target - timedelta(seconds=30)).astimezone(
        parse_timezone_name(row["zone"])
    )
    template = AstroBirthInfo(
        name="Engineering fixture",
        birth_place="Synthetic engineering inputs",
        timezone=row["zone"],
        longitude=row["longitude"],
        latitude=row["latitude"],
        local_datetime=recorded,
        utc_datetime=target - timedelta(seconds=30),
        recorded_datetime=recorded,
        applied_true_solar=True,
    )
    assert_expected(_sample_birth(template, timedelta(seconds=30)), row)


@pytest.mark.parametrize("row", AMBIGUOUS, ids=lambda r: r["id"])
def test_ambiguous_nominal_label_stays_rejected_without_an_explicit_offset(row):
    with pytest.raises(ValueError, match="ambiguous local time"):
        build_astro_birth_info(**kwargs(row))
