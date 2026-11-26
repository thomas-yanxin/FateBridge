"""RA-meridian geometry, frame inputs, actual clocks and strict projection."""

import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.astro import runtime
from fatebridge.core.astro.meridian_houses import native_meridian_houses
from fatebridge.core.astro.midpoints import build_midpoint_analysis
from fatebridge.core.contracts.output_midpoints import MidpointAnalysis
from fatebridge.services.astrology import calculate_germany_chart_analysis
from scripts.western import audit_meridian_house_geometry as oracle
from tests.fixtures.surface_payloads import astro_payload

PROTOCOL = oracle.read_protocol()
TOLERANCE = PROTOCOL["geometry_tolerance_degrees"]
HAS_SWE = pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")


@HAS_SWE
def test_all_predeclared_meridians_obliquities_and_poles_against_plane_intersections() -> (
    None
):
    report = oracle.geometry_grid(PROTOCOL)
    assert report["passed"]
    assert report["configurations"] == 240
    assert report["cusp_comparisons"] == 2880
    assert report["independent_sky_observations"] == 0
    assert report["physical_or_clock_error_bound"] is False


@HAS_SWE
@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize("uncertainty", [None, 0, 1])
def test_natal_cusps_and_every_confirmed_sample_replay_in_their_actual_angle_frame(
    zodiacal: int, uncertainty: int | None
) -> None:
    layer = calculate_germany_chart_analysis(
        **astro_payload(),
        zodiacal=zodiacal,
        birth_time_uncertainty_minutes=uncertainty,
    )["midpoint_analysis"]
    MidpointAnalysis.model_validate(layer)
    meridian = layer["meridian_houses"]
    profile = meridian["profile"]
    factors = {row["id"]: row["longitude"] for row in layer["factors"]}
    assert meridian["status"] == "computed"
    assert meridian["original_text_conformance"] == "not_assessed"
    assert "real_world_efficacy" not in meridian
    assert profile["physical_ascendant"] == factors["Ascendant"]
    assert profile["physical_midheaven"] == factors["Midheaven"]
    assert profile["first_cusp_definition"] == "equatorial_ascendant"
    assert profile["first_cusp_replaces_physical_ascendant"] is False
    assert profile["base_chart_houses_replaced"] is False
    assert len(meridian["cusps"]) == 12
    # This fixed fictional stimulus separates the points; equality at some
    # other geometry would not make the two definitions interchangeable.
    assert (
        abs(oracle.signed(meridian["cusps"][0]["longitude"], factors["Ascendant"])) > 1
    )
    for row in meridian["cusps"]:
        expected = (
            oracle.vector_longitude(row["right_ascension"], profile["true_obliquity"])
            + profile["source_ecliptic_longitude_origin"]
        )
        assert abs(oracle.signed(row["tropical_longitude"], expected)) <= TOLERANCE
        assert (
            abs(
                oracle.signed(
                    row["longitude"], expected - profile["ayanamsha_apparent"]
                )
            )
            <= TOLERANCE
        )
        assert 0 <= row["longitude"] < 360
    assert (
        abs(oracle.signed(meridian["cusps"][9]["longitude"], factors["Midheaven"]))
        <= TOLERANCE
    )
    sensitivity = meridian["birth_time_sensitivity"]
    assert sensitivity["uncertainty_minutes"] == uncertainty
    assert sensitivity["continuous_interval_proven"] is False
    if uncertainty is None:
        assert sensitivity["status"] == "not_assessed"
        assert "cusp_spans" not in sensitivity
        return
    else:
        pass
    samples = layer["time_sensitivity"]["samples"]
    assert len(samples) == sensitivity["sample_count"] == (1 if uncertainty == 0 else 5)
    origins = {
        sample["meridian_source_ecliptic_longitude_origin"] for sample in samples
    }
    assert len(origins) == len(samples)
    for sample in samples:
        assert len(sample["meridian_house_cusps"]) == 12
        for index, longitude in enumerate(sample["meridian_house_cusps"], 1):
            alpha = (sample["meridian_armc"] + (index - 10) * 30) % 360
            expected = (
                oracle.vector_longitude(alpha, sample["meridian_obliquity"])
                + sample["meridian_source_ecliptic_longitude_origin"]
                - sample["meridian_ayanamsha"]
            )
            assert abs(oracle.signed(longitude, expected)) <= TOLERANCE
    for index, span in enumerate(sensitivity["cusp_spans"]):
        nominal = meridian["cusps"][index]["longitude"]
        offsets = [
            oracle.signed(s["meridian_house_cusps"][index], nominal) for s in samples
        ]
        assert span["minimum_offset_from_nominal_degrees"] == pytest.approx(
            min(offsets), abs=1e-12
        )
        assert span["maximum_offset_from_nominal_degrees"] == pytest.approx(
            max(offsets), abs=1e-12
        )


@HAS_SWE
def test_shared_tt_drives_the_reported_cusp_geometry() -> None:
    jd = 1500000.25
    with runtime.preserve_ephemeris_path():
        _, physical = runtime.ephemeris_call("houses_ex", jd, 0.0, 0.0, b"E", 0)
        result = native_meridian_houses(
            julian_day_ut1=jd,
            julian_day_tt=jd + 1,
            latitude=0.0,
            longitude=0.0,
            sidereal=False,
            physical_angles=physical,
        )
        native_tt = jd + runtime.ephemeris_call("deltat_ex", jd, 0)
    profile = result["profile"]
    assert (
        profile["native_angle_julian_day_tt"]
        == profile["shared_julian_day_tt"]
        == jd + 1
    )
    assert profile["native_angle_julian_day_tt"] != native_tt
    assert profile["native_angle_minus_shared_tt_seconds"] == 0.0
    for cusp in result["cusps"]:
        expected = (
            oracle.vector_longitude(cusp["right_ascension"], profile["true_obliquity"])
            + profile["source_ecliptic_longitude_origin"]
        )
        assert abs(oracle.signed(cusp["longitude"], expected)) <= TOLERANCE


@HAS_SWE
@pytest.mark.parametrize("latitude", [-90.0, 90.0])
def test_exact_poles_keep_meridian_convention_without_claiming_a_rise(latitude) -> None:
    with runtime.preserve_ephemeris_path():
        _, physical = runtime.ephemeris_call(
            "houses_ex", 2451545.0, latitude, 0.0, b"E", 0
        )
        result = native_meridian_houses(
            julian_day_ut1=2451545.0,
            julian_day_tt=2451545.001,
            latitude=latitude,
            longitude=0.0,
            sidereal=False,
            physical_angles=physical,
        )
    assert result["profile"]["geographic_pole_meridian_convention"] is True
    assert len(result["cusps"]) == 12


def test_missing_backend_has_no_fabricated_cusps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "swe", None)
    layer = build_midpoint_analysis(None, {"chart_profile": {"zodiac": "tropical"}})
    assert layer["status"] == layer["meridian_houses"]["status"] == "unavailable"
    assert "cusps" not in layer["meridian_houses"]


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_nonfinite_geometry_is_not_accepted(bad) -> None:
    with pytest.raises(ValueError, match="finite"):
        native_meridian_houses(
            julian_day_ut1=bad,
            julian_day_tt=2451545.0,
            latitude=0.0,
            longitude=0.0,
            sidereal=False,
            physical_angles=[0.0, 0.0, 0.0],
        )


def test_invalid_nested_cusp_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        MidpointAnalysis.model_validate(
            {"meridian_houses": {"cusps": [{"longitude": "unknown"}]}}
        )


def test_predeclared_protocol_tampering_cannot_become_a_new_reference(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    changed = tmp_path / "protocol.json"
    changed.write_bytes(oracle.PROTOCOL.read_bytes() + b"\n")
    monkeypatch.setattr(oracle, "PROTOCOL", changed)
    with pytest.raises(ValueError, match="checksum"):
        oracle.read_protocol()
