"""A civil representation limit cannot erase an already solved lunation."""

import hashlib
import importlib.machinery
import importlib.util
import inspect
import json
from pathlib import Path

import pytest

from fatebridge.core.astro import classical, runtime
from fatebridge.core.astro.physical_epoch import utc_from_tt, utc_representation
from fatebridge.core.output_charts import Syzygy
from fatebridge.utils.errors import EphemerisSourceError
from tests.native_syzygy_witness import NativeSourceWitness
from tests.syzygy_source_profiles import (  # noqa: F401
    syzygy_profile_directories,
    syzygy_source_profile,
)

FIX = Path(__file__).parent / "fixtures/western-syzygy-display-v1"
BEFORE = json.loads((FIX / "before-solved-locals.json").read_text())["rows"]
CALENDAR = json.loads((FIX / "calendar-reference.json").read_text())["rows"]


@pytest.fixture(scope="module")
def prior_classical():
    # Preserve the original cross-platform failures; compare this change
    # against sealed old code in the same native runtime without a tolerance.
    path = FIX / "classical-before.py.txt"
    receipt = json.loads((FIX / "replay-reference.json").read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == receipt["old_source_sha256"]
    loader = importlib.machinery.SourceFileLoader("prior_syzygy_display", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_before_and_calendar_reference_are_immutable():
    seal = json.loads((FIX / "seal.json").read_text())
    for name, digest in seal["files"].items():
        assert hashlib.sha256((FIX / name).read_bytes()).hexdigest() == digest
    calendar = json.loads((FIX / "calendar-reference.json").read_text())
    assert calendar["production_imports"] is calendar["swiss_imports"] is False
    assert len(BEFORE) == len(CALENDAR) == 16


@pytest.mark.parametrize("index", range(16))
@pytest.mark.parametrize("syzygy_source_profile", ["full37"], indirect=True)
def test_solved_event_survives_display_and_preserves_original_numbers(
    index, prior_classical, monkeypatch, syzygy_source_profile
):
    row = BEFORE[index]
    captures = []
    original = prior_classical.datetime_from_tt

    def observed(tt):
        # Observe the solved state and preserve the original return/error.
        values = inspect.currentframe().f_back.f_locals
        captures.append(
            dict(
                jd_tt=tt,
                solved_ut1=values["event_ut1"],
                solved_longitude=values["longitude"],
                solved_tropical_longitude=values["tropical"][0],
                solved_residual=values["residual"],
                solved_target=values["target"],
            )
        )
        return original(tt)

    monkeypatch.setattr(prior_classical, "datetime_from_tt", observed)
    with runtime.preserve_ephemeris_path():
        previous = prior_classical._prenatal_syzygy(
            row["birth_ut1"], julian_day_tt=row["birth_tt"], sidereal=row["sidereal"]
        )
    assert len(captures) == 1
    witness = NativeSourceWitness(runtime)
    with witness.observe(), runtime.preserve_ephemeris_path():
        result = classical._prenatal_syzygy(
            row["birth_ut1"], julian_day_tt=row["birth_tt"], sidereal=row["sidereal"]
        )
    assert result is not None
    witness.assert_matches(result)
    Syzygy.model_validate(result)
    solved = captures[0]
    assert result["julian_day_tt"] == solved["jd_tt"]
    assert result["julian_day_ut1"] == result["julian_day"] == solved["solved_ut1"]
    assert result["longitude"] == solved["solved_longitude"]
    assert result["tropical_longitude"] == solved["solved_tropical_longitude"]
    assert result["solver"]["residual_degrees"] == solved["solved_residual"]
    assert result["solver"]["target_elongation"] == solved["solved_target"]
    assert result["type"] == ("full" if solved["solved_target"] == 180 else "new")
    assert result["solver"]["strictly_before_birth"]
    representation = result["utc_representation"]
    assert result["event_datetime_utc"] == representation["utc_label"]
    if row["before"] is None:
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
        # Preserve the concurrent same-runtime old-code replay for every
        # non-source field. The raw native witness above checks the corrected
        # source receipt; the old source metadata failure remains archived.
        assert {
            k: v
            for k, v in result.items()
            if k not in {"utc_representation", "ephemeris_source"}
        } == {k: v for k, v in previous.items() if k != "ephemeris_source"}
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
    row = BEFORE[-1]
    with pytest.raises(EphemerisSourceError) as caught:
        classical._prenatal_syzygy(row["birth_ut1"], julian_day_tt=row["birth_tt"])
    assert caught.value.reason == "changed_during"
