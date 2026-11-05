"""A civil representation limit cannot erase an already solved lunation."""

import json
from pathlib import Path

import pytest

from fatebridge.core.astro import classical, runtime
from fatebridge.core.astro.physical_epoch import utc_from_tt, utc_representation
from fatebridge.core.output_charts import Syzygy
from fatebridge.utils.errors import EphemerisSourceError
from tests.native_syzygy_witness import NativeSourceWitness
from tests.reference_data import verify_source_files
from tests.syzygy_source_profiles import (  # noqa: F401
    syzygy_profile_directories,
    syzygy_source_profile,
)

FIX = Path(__file__).parent / "data/astro/syzygy_display"
INPUTS = json.loads((FIX / "inputs.json").read_text())
CALENDAR = json.loads((FIX / "calendar-reference.json").read_text())["rows"]


def test_independent_calendar_reference_has_its_current_source_identity():
    verify_source_files(FIX)
    calendar = json.loads((FIX / "calendar-reference.json").read_text())
    assert calendar["production_imports"] is calendar["swiss_imports"] is False
    assert len(INPUTS) == len(CALENDAR) == 16


@pytest.mark.parametrize("index", range(16))
@pytest.mark.parametrize("syzygy_source_profile", ["full37"], indirect=True)
def test_solved_event_survives_display_and_preserves_original_numbers(
    index,
    monkeypatch,
    syzygy_source_profile,  # noqa: F811 - pytest fixture dependency
):
    row = INPUTS[index]
    witness = NativeSourceWitness(runtime)
    with witness.observe(), runtime.preserve_ephemeris_path():
        result = classical._prenatal_syzygy(
            row["birth_ut1"], julian_day_tt=row["birth_tt"], sidereal=row["sidereal"]
        )
    assert result is not None
    witness.assert_matches(result)
    Syzygy.model_validate(result)
    assert result["julian_day_tt"] < row["birth_tt"]
    assert result["julian_day_ut1"] == result["julian_day"]
    assert result["type"] == (
        "full" if result["solver"]["target_elongation"] == 180 else "new"
    )
    assert result["solver"]["strictly_before_birth"]
    representation = result["utc_representation"]
    assert result["event_datetime_utc"] == representation["utc_label"]
    if CALENDAR[index]["gregorian_year"] == 0:
        expected = CALENDAR[index]
        label = representation["utc_label"]
        assert label.startswith("0000-")
        date, time = label.removesuffix("+00:00").split("T")
        assert list(map(int, date.split("-"))) == [
            expected["gregorian_year"],
            expected["gregorian_month"],
            expected["gregorian_day"],
        ]
        hour, minute, second = map(float, time.split(":"))
        assert (
            abs(hour * 3600 + minute * 60 + second - expected["seconds_of_day"])
            <= 0.0002
        )
        assert representation["datetime_representable"] is False
        assert (
            representation["label_status"]
            == "unique_extended_calendar_label_outside_datetime_range"
        )
    else:
        assert representation["datetime_representable"] is True


def test_utc_second60_is_a_label_without_a_python_carrier():
    # A real UTC conversion control, not a claim that a lunation occurred here.
    at = 2457754.5 + (36 + 32.184 + 0.5) / 86400
    label, moment, leap = utc_from_tt(at)
    result = utc_representation(label, moment, leap)
    assert label.startswith("2016-12-31T23:59:60.")
    assert result["datetime_representable"] is False
    assert result["label_status"] == "inserted_UTC_leap_second"


def test_a_nonunique_historical_label_is_not_fabricated():
    result = utc_representation(None, None, False)
    assert result["utc_label"] is None
    assert result["datetime_representable"] is False
    assert (
        result["label_status"] == "unrepresentable_historical_fractional_UTC_adjustment"
    )


def test_display_stage_integrity_error_remains_fatal(monkeypatch):
    def broken(_):
        raise EphemerisSourceError("changed_during")

    monkeypatch.setattr(classical, "utc_from_tt", broken)
    row = INPUTS[-1]
    with pytest.raises(EphemerisSourceError) as caught:
        classical._prenatal_syzygy(row["birth_ut1"], julian_day_tt=row["birth_tt"])
    assert caught.value.reason == "changed_during"
