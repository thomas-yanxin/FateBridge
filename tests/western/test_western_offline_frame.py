"""Frozen official-source controls for the analytic ray's shared horizon frame.

The reference uses original Swiss ECL_NUT/houses_armc and ERFA LTP, NUMAT,
GST06's equation of origins, and ATIOQ without refraction or diurnal
aberration. Its exact affine ERA is evaluated independently at 90 digits.
Same-source geometry does not certify the physical model at remote epochs.
"""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime
from fatebridge.core.astro import runtime
from fatebridge.core.astro.classical import _build_classical_layer
from fatebridge.core.astro.earth_attitude import analytic_earth_attitude
from fatebridge.core.astro.geometry import _angles
from fatebridge.core.astro.horizon import horizon_altitude
from fatebridge.core.astro.iers_ut1 import use_ut1_source
from fatebridge.services.astrology import calculate_core_chart_analysis

REFERENCE_PATH = Path(__file__).parents[1] / "data/offline_frame_v1.json"
REFERENCE = json.loads(REFERENCE_PATH.read_text())
CLASSICAL_REFERENCE_PATH = (
    Path(__file__).parents[1] / "data/offline_classical_frame_v1.json"
)
CLASSICAL_REFERENCE = json.loads(CLASSICAL_REFERENCE_PATH.read_text())


def test_offline_true_ecliptic_geometry_matches_frozen_source_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest() == (
        "d00fe241573d9cf6f91d757db8bd7802e58ad0741b2f012c38ab4a274aa56035"
    )
    monkeypatch.setattr(runtime, "swe", None)
    tolerance = REFERENCE["reference_criterion_arcsec"]
    for row in REFERENCE["rows"]:
        attitude = analytic_earth_attitude(row["jd_ut1"], row["jd_tt"])
        source = row["source"]
        assert (
            abs(attitude.true_obliquity - source["true_obliquity"]) * 3600 < tolerance
        )
        assert (
            abs(attitude.equator.greenwich_sidereal_degrees - source["gast"]) * 3600
            < tolerance
        )
        actual = _angles(
            row["jd_ut1"],
            row["longitude"],
            row["latitude"],
            julian_day_tt=row["jd_tt"],
        )
        for key, expected in row["reference_axes"].items():
            assert abs((actual[key] - expected + 180) % 360 - 180) * 3600 < tolerance
        altitude, method = horizon_altitude(
            row["jd_ut1"],
            row["longitude"],
            row["latitude"],
            row["ray"]["longitude"],
            row["ray"]["latitude"],
            julian_day_tt=row["jd_tt"],
        )
        assert abs(altitude - row["reference_altitude"]) * 3600 < tolerance
        assert method == "approximate_geometric_altitude"


def test_public_missing_native_chart_keeps_the_same_source_solar_sect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "swe", None)
    monkeypatch.setattr(ephemeris_runtime, "swe", None)
    with use_ut1_source("swiss_delta_t"):
        result = calculate_core_chart_analysis(**REFERENCE["public_input"])
    assert "error" not in result
    profile = result["chart_profile"]
    assert profile["julian_day_ut1"] == REFERENCE["public_default_ut1"]
    assert profile["julian_day_tt"] == REFERENCE["public_tt"]
    assert profile["engine_precision"] == "approximate_orbital_model"
    assert result["classical"]["sect"] == REFERENCE["public_expected_sect"]


def test_offline_classical_bounds_use_the_available_same_tt_source_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert hashlib.sha256(CLASSICAL_REFERENCE_PATH.read_bytes()).hexdigest() == (
        "ba2d21111648297cf239b7e732b6274c3c52eaf1d4b2b8a2a93372cab687f0c4"
    )
    monkeypatch.setattr(runtime, "swe", None)
    monkeypatch.setattr(ephemeris_runtime, "swe", None)
    with use_ut1_source("swiss_delta_t"):
        for row in CLASSICAL_REFERENCE["rows"]:
            result = calculate_core_chart_analysis(**row["payload"])
            assert "error" not in result
            assert result["chart_profile"]["julian_day_tt"] == row["jd_tt"]
            assert (
                abs(result["classical"]["obliquity"] - row["source_true_obliquity"])
                * 3600
                < 0.001
            )
            for body in row["bodies"]:
                assert (
                    result["classical"]["planets"][body["planet"]]["out_of_bounds"]
                    is body["expected_out_of_bounds"]
                )
            # The source-frame threshold alone does not provide an offline
            # topocentric sunrise/set solver or planetary-hour qualification.
            assert result["planetary_hours"] is None
    assert _build_classical_layer([], [], 0, chart_sect="day")["obliquity"] is None


@pytest.mark.skipif(runtime.swe is None, reason="Native ECL_NUT source unavailable")
def test_classical_obliquity_preserves_explicit_tt_without_a_ut1_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = CLASSICAL_REFERENCE["rows"][1]
    calls = []
    original = runtime.ephemeris_call

    def observe(operation, *args, **kwargs):
        calls.append((operation, args))
        return original(operation, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", observe)
    result = _build_classical_layer(
        [], [], 0, chart_sect="day", julian_day_tt=row["jd_tt"]
    )
    assert abs(result["obliquity"] - row["source_true_obliquity"]) * 3600 < 0.001
    assert calls == [("calc", (row["jd_tt"], runtime.swe.ECL_NUT))]


def test_unrounded_ecliptic_cone_matches_independent_arb_source_controls() -> None:
    from fatebridge.core.classical_western import ecliptic_out_of_bounds

    reference = CLASSICAL_REFERENCE["cone_reference"]
    assert reference["controls"] == 200
    assert reference["legacy_mismatches"] == 15
    for row in reference["rows"]:
        assert (
            ecliptic_out_of_bounds(row["longitude"], row["latitude"], row["obliquity"])
            is row["expected"]
        ), row["id"]


@pytest.mark.parametrize("zodiacal", [0, 1])
def test_public_ecliptic_plane_ray_stays_within_its_source_cone(
    monkeypatch: pytest.MonkeyPatch, zodiacal: int
) -> None:
    monkeypatch.setattr(runtime, "swe", None)
    monkeypatch.setattr(ephemeris_runtime, "swe", None)
    result = calculate_core_chart_analysis(
        **CLASSICAL_REFERENCE["node_public_input"], zodiacal=zodiacal
    )
    assert "error" not in result
    assert result["classical"]["planets"]["North Node"]["out_of_bounds"] is False
    assert result["chart_profile"]["future_leap_seconds_assumed_unchanged"] is True
