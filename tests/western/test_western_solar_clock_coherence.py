"""Solar rebase and chart use one physical TT and adopted UT1/GAST model."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.iers_ut1 import use_ut1_source
from fatebridge.core.astro.sensitivity import _sample_birth
from fatebridge.core.astro.solar_rebase import solar_rebase_adjustment
from fatebridge.utils.errors import EphemerisSourceError
from tests.support.reference_data import verify_source_files

FIXTURE = Path(__file__).parents[1] / "data/astro/solar_clock_coherence"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())


def test_reference_precedes_candidate_and_reuses_original96_without_regrading():
    verify_source_files(FIXTURE)
    assert len(REFERENCE["rows"]) == 112
    assert not REFERENCE["fatebridge_imported"]
    assert REFERENCE["shared_swiss_ephemeris_dynamics"]


@pytest.mark.parametrize("sampled", [False, True])
@pytest.mark.parametrize("row", REFERENCE["rows"], ids=lambda r: r["id"])
def test_rebase_on_coherent_sun_tt_and_adopted_rotation(row, sampled):
    target = datetime.fromisoformat(row["utc"])
    offset = timedelta(seconds=30) if sampled else timedelta()
    start = target - offset
    with use_ut1_source(row["source"]):
        birth = build_astro_birth_info(
            birth_year=start.year,
            birth_month=start.month,
            birth_day=start.day,
            birth_hour=start.hour,
            birth_minute=start.minute,
            birth_second=start.second,
            birth_timezone="UTC",
            birth_longitude=0,
            birth_latitude=40,
            use_true_solar_time=True,
        )
        if sampled:
            birth = _sample_birth(birth, offset)
    actual = (birth.require_utc_datetime - target).total_seconds()
    assert abs(actual - row["eot_seconds"]) <= 0.0002
    assert birth.recorded_datetime == target


@pytest.mark.parametrize("row", REFERENCE["rows"], ids=lambda r: r["id"])
def test_same_run_sun_tt_rotation_ut1_and_actual_source_are_observed(row, monkeypatch):
    original = runtime.ephemeris_call
    observed = []

    def capture(operation, *args, **kwargs):
        observed.append((operation, args))
        return original(operation, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", capture)
    with use_ut1_source(row["source"]):
        _, receipt = solar_rebase_adjustment(
            datetime.fromisoformat(row["utc"]), "UTC", 0
        )
    suns = [
        args for op, args in observed if op == "calc" and args[1] == runtime.swe.SUN
    ]
    assert len(suns) == 1
    assert abs(suns[0][0] - row["jd_tt"]) * 86400 <= 0.0002
    assert not any(op == "time_equ" for op, _ in observed)
    assert any(
        op == "sidtime" and abs(args[0] - row["jd_ut1"]) * 86400 <= 0.0002
        for op, args in observed
    )
    assert receipt["method_id"] == "western_solar_rebase_coherent_tt_ut1_v2"
    assert receipt["solar_ephemeris_model"] == "swieph"
    assert abs(receipt["sun_apparent_right_ascension_degrees"] - row["sun_ra"]) <= 1e-10
    assert (
        abs(
            (receipt["greenwich_apparent_sidereal_degrees"] - row["gast"] + 180) % 360
            - 180
        )
        * 240
        <= 0.0002
    )
    source = receipt["solar_ephemeris_source"]
    assert source["by_factor"]["equatorial_Sun"]["model"] == "swieph"
    assert source["files"] and not source["has_unidentified_sources"]
    assert source["accuracy_certified"] is False


def test_rebase_source_error_is_not_an_approximate_eot(monkeypatch):
    original = runtime.ephemeris_call

    def fail_sun(operation, *args, **kwargs):
        if operation == "calc" and args[1] == runtime.swe.SUN:
            raise EphemerisSourceError("unavailable_during")
        return original(operation, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", fail_sun)
    with pytest.raises(EphemerisSourceError):
        solar_rebase_adjustment(
            datetime.fromisoformat("2000-01-01T12:00:00+00:00"), "UTC", 0
        )
