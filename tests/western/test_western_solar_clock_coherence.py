"""Solar rebase and chart use one physical TT and adopted UT1/GAST model."""

import gzip
import hashlib
import json
import math
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.astro import earth_attitude, runtime
from fatebridge.core.astro.iers_ut1 import use_ut1_source
from fatebridge.core.astro.solar_rebase import solar_rebase_adjustment
from fatebridge.utils.errors import EphemerisSourceError
from tests.support.reference_data import verify_source_files
from tests.support.solar_clock_grid import (
    civil_solar_birth,
    verify_recorded_grid_solar_reset,
)

FIXTURE = Path(__file__).parents[1] / "data/astro/solar_clock_coherence"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())
PHYSICAL_REFERENCE = json.loads(
    gzip.decompress(
        (
            Path(__file__).parents[1] / "data/earth_attitude_v1/reference.json.gz"
        ).read_bytes()
    )
)["solar_rebase"]
PHYSICAL_ROWS = {row["id"]: row for row in PHYSICAL_REFERENCE["rows"]}
SAME_DEFINITION = json.loads((FIXTURE / "same-definition-reference.json").read_text())
CLOCK_ROWS = {row["id"]: row for row in SAME_DEFINITION["rows"]}


def test_reference_precedes_candidate_and_reuses_original96_without_regrading() -> None:
    verify_source_files(FIXTURE)
    assert len(REFERENCE["rows"]) == 112
    assert not REFERENCE["fatebridge_imported"]
    assert REFERENCE["shared_swiss_ephemeris_dynamics"]
    assert (
        hashlib.sha256((FIXTURE / "reference.json").read_bytes()).hexdigest()
        == PHYSICAL_REFERENCE["old_reference_sha256"]
    )
    assert PHYSICAL_REFERENCE["production_imported"] is False
    assert PHYSICAL_REFERENCE["old_native_ra_gate_degrees"] == 1e-10
    assert PHYSICAL_REFERENCE["physical_ra_gate_degrees"] == 1e-10
    assert (
        set(PHYSICAL_ROWS)
        == set(CLOCK_ROWS)
        == {row["id"] for row in REFERENCE["rows"]}
    )
    assert (
        SAME_DEFINITION["source"]["original_reference_sha256"]
        == PHYSICAL_REFERENCE["old_reference_sha256"]
    )


@pytest.mark.parametrize("sampled", [False, True])
@pytest.mark.parametrize("row", REFERENCE["rows"], ids=lambda r: r["id"])
def test_rebase_on_coherent_sun_tt_and_adopted_rotation(row, sampled: bool) -> None:
    target = datetime.fromisoformat(row["utc"])
    offset_seconds = 30 if sampled else 0
    start = target - timedelta(seconds=offset_seconds)
    with use_ut1_source(row["source"]):
        birth = civil_solar_birth(start)
        if sampled:
            effective = verify_recorded_grid_solar_reset(
                birth,
                target,
                offset_seconds,
                CLOCK_ROWS[row["id"]]["tt_days"],
                row["eot_seconds"],
                0.0002,
            )
        else:
            effective = birth.require_utc_datetime
            assert birth.recorded_datetime == target
    actual = (effective - target).total_seconds()
    assert abs(actual - row["eot_seconds"]) <= 0.0002


@pytest.mark.parametrize("row", REFERENCE["rows"], ids=lambda r: r["id"])
def test_same_run_sun_tt_rotation_ut1_and_actual_source_are_observed(
    row, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_call = runtime.ephemeris_call
    original_equator = earth_attitude.physical_equator
    observed = []
    equators = []

    def capture_call(operation, *args, **kwargs):
        result = original_call(operation, *args, **kwargs)
        observed.append((operation, args, result))
        return result

    def capture_equator(module, jd_ut1, *, julian_day_tt=None):
        result = original_equator(module, jd_ut1, julian_day_tt=julian_day_tt)
        equators.append(result)
        return result

    monkeypatch.setattr(runtime, "ephemeris_call", capture_call)
    monkeypatch.setattr(earth_attitude, "physical_equator", capture_equator)
    with use_ut1_source(row["source"]):
        _, receipt = solar_rebase_adjustment(
            datetime.fromisoformat(row["utc"]), "UTC", 0
        )
    ((sun_args, sun_result),) = [
        (args, result)
        for op, args, result in observed
        if op == "calc" and args[1] == runtime.swe.SUN
    ]
    (equator,) = equators
    reference = CLOCK_ROWS[row["id"]]
    assert abs(sun_args[0] - row["jd_tt"]) * 86400 <= 0.0002
    assert abs(equator.jd_ut1 - row["jd_ut1"]) * 86400 <= 0.0002
    assert equator.tt.days == Fraction(reference["tt_days"])
    assert abs(equator.ut1.days - Fraction(reference["ut1_days"])) * 86400 <= 0.0002
    assert sun_args[0] == equator.jd_tt == receipt["recorded_julian_day_tt"]
    assert equator.jd_ut1 == receipt["equation_of_time_julian_day_ut1"]
    assert (
        equator.greenwich_sidereal_degrees
        == receipt["greenwich_apparent_sidereal_degrees"]
    )
    assert not any(op == "time_equ" for op, _, _ in observed)
    assert receipt["method_id"] == "western_solar_rebase_coherent_tt_ut1_v2"
    assert receipt["solar_ephemeris_model"] == "swieph"
    assert abs(sun_result[0][0] - reference["native_sun_ra"]) <= 1e-10
    assert (
        abs(
            receipt["sun_apparent_right_ascension_degrees"]
            - reference["physical_sun_ra"]
        )
        <= 1e-10
    )
    assert (
        receipt["equatorial_frame"] == "selected_physical_equator_and_equinox_of_date"
    )
    assert (
        abs(
            math.remainder(
                receipt["greenwich_apparent_sidereal_degrees"] - reference["gast"],
                360,
            )
        )
        * 240
        <= 0.0002
    )
    assert abs(receipt["equation_of_time_seconds"] - reference["eot_seconds"]) <= 0.0002
    source = receipt["solar_ephemeris_source"]
    assert source["by_factor"]["equatorial_Sun"]["model"] == "swieph"
    assert source["files"] and not source["has_unidentified_sources"]
    assert source["accuracy_certified"] is False


def test_rebase_source_error_is_not_an_approximate_eot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = runtime.ephemeris_call

    def fail_sun(operation, *args, **kwargs):
        if operation == "calc" and args[1] == runtime.swe.SUN:
            raise EphemerisSourceError("unavailable_during")
        else:
            pass
        return original(operation, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", fail_sun)
    with pytest.raises(EphemerisSourceError):
        solar_rebase_adjustment(
            datetime.fromisoformat("2000-01-01T12:00:00+00:00"), "UTC", 0
        )
