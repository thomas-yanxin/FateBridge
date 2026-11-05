"""Match the actual native house epoch before global path restoration.

These are non-vector geometry probes. A short JPL fixture selects the runtime
policy; epochs outside its vector interval do not certify planetary coverage.
"""

import os
import shutil
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as configuration
from fatebridge.core.astro import runtime
from fatebridge.core.astro.meridian_houses import native_meridian_houses
from fatebridge.services.astrology import calculate_germany_chart_analysis
from scripts.western.audit_meridian_house_geometry import signed, vector_longitude

HAS_SWE = pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")


@pytest.fixture
def selected_jpl(monkeypatch, tmp_path):
    previous = configuration.configured_ephemeris_path()
    old_path = os.environ.get("SE_EPHE_PATH")
    old_jpl = os.environ.get("FATEBRIDGE_JPL_FILE")
    kernel = "human-design-de441-j2000.eph"
    shutil.copy2(Path(__file__).parents[1] / "fixtures" / kernel, tmp_path / kernel)
    with monkeypatch.context() as patch:
        patch.setenv("SE_EPHE_PATH", str(tmp_path))
        patch.setenv("FATEBRIDGE_JPL_FILE", kernel)
        configuration.configure_ephemeris_path()
        try:
            yield
        finally:
            for key, value in (
                ("SE_EPHE_PATH", old_path),
                ("FATEBRIDGE_JPL_FILE", old_jpl),
            ):
                if value is None:
                    patch.delenv(key, raising=False)
                else:
                    patch.setenv(key, value)
            configuration.configure_ephemeris_path(previous or "")


@HAS_SWE
@pytest.mark.parametrize("jd", [1500000.25, 2000000.25, 2451545.0, 2800000.25])
@pytest.mark.parametrize("sidereal", [False, True])
def test_reported_native_clock_exactly_matches_house_backend(
    selected_jpl, monkeypatch, jd, sidereal
):
    swe = runtime.swe
    flags = swe.FLG_SIDEREAL if sidereal else 0
    actual_houses = swe.houses_ex
    entry_epochs = []

    def capture_house_entry(tjdut, lat, lon, hsys, flags):
        # Capture the C house routine's first operand in its actual native
        # context. preserve_ephemeris_path resets the JPL state on exit, so a
        # subsequent deltat_ex call is not an equivalent reference context.
        entry_epochs.append((hsys, tjdut + swe.deltat_ex(tjdut, flags)))
        return actual_houses(tjdut, lat, lon, hsys, flags)

    monkeypatch.setattr(swe, "houses_ex", capture_house_entry)
    with runtime.preserve_ephemeris_path():
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        _, physical = runtime.ephemeris_call("houses_ex", jd, 30.0, 10.0, b"E", flags)
        result = native_meridian_houses(
            julian_day_ut1=jd,
            julian_day_tt=jd + 0.001,
            latitude=30.0,
            longitude=10.0,
            sidereal=sidereal,
            physical_angles=physical,
        )
        assert entry_epochs[-1][0] == b"X"
        expected_tt = entry_epochs[-1][1]
        expected_epsilon = swe.calc(expected_tt, swe.ECL_NUT, 0)[0][0]
        expected_offset = (
            swe.get_ayanamsa_ex(expected_tt, flags)[1] if sidereal else 0.0
        )
    profile = result["profile"]
    assert profile["native_angle_julian_day_tt"] == expected_tt
    assert profile["true_obliquity"] == expected_epsilon
    assert profile["ayanamsha_apparent"] == expected_offset
    for row in result["cusps"]:
        expected = (
            vector_longitude(row["right_ascension"], expected_epsilon) - expected_offset
        )
        assert abs(signed(row["longitude"], expected)) <= 1e-8


@HAS_SWE
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_service_meridian_replay_preserves_strict_jpl_physical_sources(
    selected_jpl, zodiacal
):
    result = calculate_germany_chart_analysis(
        name="虚构：子午角度历元回归",
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0.0,
        birth_latitude=0.0,
        zodiacal=zodiacal,
    )
    layer = result["midpoint_analysis"]
    assert layer["meridian_houses"]["status"] == "computed"
    physical = layer["profile"]["physical_ephemeris_source"]
    assert len(physical["by_factor"]) == 10
    assert {row["model"] for row in physical["by_factor"].values()} == {"jpl"}
    assert len(physical["files"]) == 1
    assert physical["files"][0]["de_number"] == 441
    assert physical["accuracy_certified"] is False
