"""A position-only sky must not require auxiliary velocity epochs or angles."""

import json
import os
import shutil
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core import guolao, suzhan_astronomy
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.time_scales import datetime_from_tt

FIXTURES = Path(__file__).parent / "data/guolao"
KERNEL = "guolao-de441-j2000.eph"


@pytest.fixture
def selected(tmp_path, monkeypatch):
    previous = e.configured_ephemeris_path()
    shutil.copyfile(FIXTURES / KERNEL, tmp_path / KERNEL)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", KERNEL)
    e.swe.close()
    e.configure_ephemeris_path(str(tmp_path))
    try:
        yield tmp_path
    finally:
        monkeypatch.undo()
        e.swe.close()
        e.configure_ephemeris_path(previous or "")


def birth(jd_tt=2451545.0):
    moment = datetime_from_tt(jd_tt)
    return build_astro_birth_info(
        birth_year=moment.year,
        birth_month=moment.month,
        birth_day=moment.day,
        birth_hour=moment.hour,
        birth_minute=moment.minute,
        birth_second=moment.second,
        birth_microsecond=moment.microsecond,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
    )


def test_position_only_sky_works_inside_kernel_without_auxiliary_epochs(
    selected, monkeypatch
):
    # The physical epoch is inside the original coefficient window, while
    # the ordinary +/-0.375-day first derivative stencil would leave it.
    jd = 2451408.625

    def unexpected(*args, **kwargs):
        pytest.fail("Equatorial mansion positions do not need this calculation")

    monkeypatch.setattr(guolao, "corrected_longitude_motion", unexpected)
    from fatebridge.core.astro import moshier_motion

    monkeypatch.setattr(moshier_motion, "complete_moshier_longitude_rate", unexpected)
    monkeypatch.setattr(guolao, "reference_geometry", unexpected)
    result = suzhan_astronomy.build_equatorial_mansions(birth(jd))
    assert abs(result["julian_day_tt"] - jd) < 1e-9
    assert result["ephemeris_models"] == ["jpl"]
    assert {body["id"] for body in result["bodies"]} == set(guolao.CN)
    assert len(result["boundaries"]) == 28
    assert os.environ["SE_EPHE_PATH"] == str(selected)
    assert os.environ["FATEBRIDGE_JPL_FILE"] == KERNEL


def test_opt_out_keeps_native_rates_and_explicit_not_requested_status(selected):
    raw = guolao.positions(birth(), observer_geometry=False, correct_motion=False)
    assert raw["longitude_motion"]["status"] == "not_requested"
    assert set(
        raw["longitude_motion"]["physical_ephemeris_source"]["by_factor"]
    ) == set(guolao.CN)
    assert all("longitude_speed_native" not in s for s in raw["states"].values())
    assert "lunar_light_time" not in raw["longitude_motion"]


def test_default_guolao_motion_and_position_only_sky_keep_same_coordinates(
    selected, monkeypatch
):
    observed = []
    original = guolao.corrected_longitude_motion

    def record(name, *args, **kwargs):
        observed.append(name)
        return original(name, *args, **kwargs)

    monkeypatch.setattr(guolao, "corrected_longitude_motion", record)
    raw = guolao.positions(birth(), observer_geometry=False)
    assert observed == list(guolao.CN)
    assert raw["longitude_motion"]["lunar_light_time"]["status"] == "applied"
    expected = suzhan_astronomy.build_equatorial_mansions(birth())
    native = guolao.positions(birth(), observer_geometry=False, correct_motion=False)
    for name, state in raw["states"].items():
        assert state["longitude"] == native["states"][name]["longitude"]
        assert state["right_ascension"] == native["states"][name]["right_ascension"]

    def prior_caller(context, **kwargs):
        # The previous adapter requested both corrections and synthetic
        # observer geometry; compare that path with the position-only result.
        return guolao.positions(context, hsys=0, zodiacal=0)

    monkeypatch.setattr(suzhan_astronomy, "positions", prior_caller)
    assert json.dumps(expected, sort_keys=True) == json.dumps(
        suzhan_astronomy.build_equatorial_mansions(birth()), sort_keys=True
    )
