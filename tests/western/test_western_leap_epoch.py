"""Frozen published UTC offsets; physical-native clocks must keep second60."""

import hashlib
import json
import math
import zipfile
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

import pytest
import swisseph as swe

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth_clock import (
    resolve_solar_birth_clock,
    resolve_solar_epoch,
)
from fatebridge.core.astro.physical_epoch import PhysicalEpoch, utc_from_tt
from fatebridge.core.astro.time_scales import datetime_from_tt, leap_table
from fatebridge.core.contracts.output_western import WesternEventClockConversion
from fatebridge.core.predictive._common import determine_sect
from fatebridge.core.predictive.native_chart import build_native_subject
from fatebridge.core.western_event_clock import build_event_subject
from tests.support.ephemeris_case_runtime import (
    native_ephemeris_files_module as native_ephemeris_files_module,
)

pytestmark = pytest.mark.usefixtures("native_ephemeris_files_module")


FIXTURES = Path(__file__).parents[1] / "fixtures"
REFERENCE_PATH = FIXTURES / "western-leap-epoch-reference.json"
REFERENCE = json.loads(REFERENCE_PATH.read_text())
REFERENCE_SHA = "189c6afab46acdc40dc29633573c8bc97c76fa443687c92ad97b183aaa230144"
ARCHIVE_SHA = "956575c07ac07a69c8a97f992f64814e4af51175aad91ee39519cfbd7856fea3"


def test_reference_is_sealed_and_contains_the_original_failures() -> None:
    assert hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest() == REFERENCE_SHA
    archive = FIXTURES / "western-leap-epoch-sources.zip"
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == ARCHIVE_SHA
    with zipfile.ZipFile(archive) as z:
        text = z.read("usno-post1972-transcription.txt")
    assert hashlib.sha256(text).hexdigest() == REFERENCE["source_sha256"]
    rows = [
        s.split() for s in text.decode().splitlines() if s and not s.startswith("#")
    ]
    assert len(rows) == 28
    assert [
        (r["effective_date"], r["tai_minus_utc_seconds"])
        for r in leap_table()["entries"]
    ] == [(r[0], int(r[2])) for r in rows]
    for day, jd, _ in rows:
        assert datetime.fromisoformat(day).toordinal() + 1721424.5 == float(jd)
    assert len(REFERENCE["before_failures"]) == 2
    assert all("UTC leap second" in r["error"] for r in REFERENCE["before_failures"])
    assert REFERENCE["frozen_before_candidate"]


@pytest.mark.parametrize("row", REFERENCE["controls"])
def test_published_leap_offsets_and_both_adjacent_boundaries(row) -> None:
    value = float(row["jd_tt"])
    point = Fraction(value)
    midnight = Fraction(row["midnight_jd"])
    start = midnight + (Fraction(row["old_offset"]) + Fraction("32.184")) / 86400
    stop = midnight + (Fraction(row["new_offset"]) + Fraction("32.184")) / 86400
    effective = datetime.fromisoformat(row["effective"]).replace(tzinfo=timezone.utc)
    label, moment, leap = utc_from_tt(value)
    # The frozen decimal labels retain their nominal meaning below. A float
    # made from those labels is a distinct exact IEEE point at an endpoint.
    assert leap is (start <= point < stop)
    assert (
        abs(float((point - start) * 86400) - float(row["seconds_from_leap_start"]))
        <= REFERENCE["tolerance_seconds"]
    )
    assert label is not None
    if leap:
        assert moment is None
        prior_day = (effective - timedelta(days=1)).date().isoformat()
        micros = int((point - start) * 86_400_000_000)
        assert label == f"{prior_day}T23:59:60.{micros:06d}+00:00"
    else:
        assert moment is not None
        micros = round((point - (start if point < start else stop)) * 86_400_000_000)
        if point < start:
            micros = min(-1, micros)
        else:
            pass
        expected = effective + timedelta(microseconds=micros)
        assert (
            abs((moment - expected).total_seconds()) <= REFERENCE["tolerance_seconds"]
        )
    # Preserve every original row's separate nominal scalar API obligation,
    # including the source's 0/1-second endpoint meanings and old tolerance.
    if row["utc_is_leap_second"]:
        with pytest.raises(ValueError, match="UTC leap second"):
            datetime_from_tt(value)
    else:
        expected = datetime.fromisoformat(row["utc_label"]).replace(tzinfo=timezone.utc)
        assert (
            abs((datetime_from_tt(value) - expected).total_seconds())
            <= REFERENCE["tolerance_seconds"]
        )


@pytest.mark.parametrize(
    "row", [r for r in REFERENCE["controls"] if r["seconds_from_leap_start"] == "0.25"]
)
def test_all_27_leaps_can_be_primary_physical_epochs(row) -> None:
    # Supplementary after-candidate model inversion controls. Published TT is
    # frozen above; raw Swiss Delta T derives the test input, not its answer.
    tt = float(row["jd_tt"])
    ut1 = tt
    for _ in range(4):
        ut1 = tt - swe.deltat_ex(ut1, swe.FLG_SWIEPH)
    epoch = PhysicalEpoch.from_ut1(ut1)
    assert epoch.utc_datetime is None and epoch.utc_is_leap_second
    assert epoch.time.jd_utc is None
    assert epoch.time.jd_ut1 == ut1
    assert abs(epoch.time.jd_tt - tt) * 86400 <= REFERENCE["tolerance_seconds"]


@pytest.mark.parametrize("basis", ["local_mean_solar", "local_apparent_solar"])
def test_original_failed_ut1_reaches_real_native_tt_ut1_and_geometry(
    basis: str,
) -> None:
    row = REFERENCE["reused_ut1_epoch"]
    lon = 0 if basis == "local_mean_solar" else row["synthetic_lat_longitude"]
    subject, receipt = build_event_subject(
        name="frozen leap witness",
        local_datetime=datetime(1978, 1, 1),
        longitude=lon,
        latitude=40,
        clock_basis=basis,
    )
    assert subject.julian_day == float(row["jd_ut1"])
    assert (
        abs(subject.julian_day_tt - row["jd_tt"]) * 86400
        <= REFERENCE["tolerance_seconds"]
    )
    assert subject.iso_formatted_utc_datetime.startswith("1977-12-31T23:59:60.")
    assert subject.iso_formatted_local_datetime == subject.iso_formatted_utc_datetime
    assert receipt["utc_representation"]["utc_is_leap_second"]
    assert not receipt["utc_representation"]["datetime_representable"]
    assert receipt["solar_conversion"]["ut1_roundtrip_error_seconds"] == 0
    assert (
        abs(receipt["solar_conversion"]["input_clock_roundtrip_error_seconds"])
        <= 0.0002
    )
    sun, _ = swe.calc(subject.julian_day_tt, swe.SUN, swe.FLG_SWIEPH | swe.FLG_SPEED)
    # Reuse the retained TT/UT1 for the same IERS rotation as the chart.
    # The scalar UT1 rounds away the fraction resolved by the LAT clock.
    _, axes = runtime.ephemeris_call(
        "houses_ex",
        subject.ut1,
        40,
        lon,
        b"R",
        _julian_day_tt=subject.tt,
    )
    assert abs(subject.sun.abs_pos - sun[0]) < 1e-10
    assert abs(subject.first_house.abs_pos - axes[0]) < 1e-10
    assert determine_sect(subject) == ("day" if subject.is_diurnal else "night")
    WesternEventClockConversion.model_validate(receipt)
    if basis == "local_apparent_solar":
        assert (
            receipt["clock_chart_source_comparison"]["status"]
            == "compatible_observed_sun_contexts"
        )
    else:
        pass
    # The historical datetime-only interface keeps its explicit type limit.
    with pytest.raises(ValueError, match="UTC leap second"):
        resolve_solar_birth_clock(datetime(1978, 1, 1), lon, basis)


def test_native_builder_cannot_accept_two_conflicting_time_inputs() -> None:
    epoch, _ = resolve_solar_epoch(datetime(1978, 1, 1), 0, "local_mean_solar")
    with pytest.raises(ValueError, match="exactly one"):
        build_native_subject(
            name="invalid two clocks",
            local_datetime=datetime(2000, 1, 1),
            physical_epoch=epoch,
            longitude=0,
            latitude=40,
            timezone_name="UTC",
        )


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_nonfinite_primary_epochs_cannot_enter_native_calculation(bad) -> None:
    with pytest.raises(ValueError):
        PhysicalEpoch.from_ut1(bad)
