"""Secular-mean transcription and independent DE421 geometric frame checks."""

import json
import math
from pathlib import Path

import pytest

from fatebridge.core.jyotish_mean import (
    FRAME,
    LOWER_TT,
    MODEL,
    UPPER_TT,
    admitted,
    geometric_points,
    icrs_to_j2000_ecliptic,
    mean_longitudes,
    model_balas,
)

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/jyotish-mean-de421-reference.json").read_text()
)


def error_arcsec(a, b):
    return abs((a - b + 180) % 360 - 180) * 3600


@pytest.mark.parametrize("case", REFERENCE["rows"])
def test_primary_secular_means_and_geometric_positions_against_frozen_independent_references(
    case, monkeypatch, tmp_path
):
    jd = case["jd_tt_substituted_for_tdb"]
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    if not admitted(jd):
        with pytest.raises(ValueError, match="1900-2050"):
            mean_longitudes(jd)
        assert geometric_points(jd, "auto") == {}
        return
    means = mean_longitudes(jd)
    for planet, expected in case["mean_j2000_degrees"].items():
        assert error_arcsec(means[planet], expected) < 0.01, (
            planet,
            jd,
            means[planet],
            expected,
        )
    actual = geometric_points(jd, "auto")
    assert all(point["ephemeris_model"] == "moshier" for point in actual.values())
    for planet, expected in case["true_geocentric_j2000"].items():
        assert actual[planet]["frame"] == FRAME
        assert error_arcsec(actual[planet]["longitude"], expected["longitude"]) < 2.0, (
            planet,
            jd,
        )
        assert abs(actual[planet]["latitude"] - expected["latitude"]) * 3600 < 2.0, (
            planet,
            jd,
        )


def test_coordinate_rotation_matches_independent_erfa_matrix():
    for column in range(3):
        value = tuple(1.0 if i == column else 0.0 for i in range(3))
        actual = icrs_to_j2000_ecliptic(value)
        expected = [
            row[column]
            for row in REFERENCE["frame_rotation_icrs_to_mean_ecliptic_j2000"]
        ]
        assert actual == pytest.approx(expected, abs=2e-15, rel=0)


def test_j2000_published_mean_constants_and_millennial_time_unit():
    result = mean_longitudes(2451545.0)
    assert result["Mercury"] == pytest.approx(252.25090552, abs=1e-12)
    assert result["Mars"] == pytest.approx(355.43299958, abs=1e-12)
    assert result["Jupiter"] == pytest.approx(34.35151874, abs=1e-12)
    assert result["Sun"] == pytest.approx(280.46645683, abs=1e-12)
    # Mercury's secular rate is arcseconds per MILLENNIUM, not degrees or
    # arcseconds per century. A single mean day advances about4.09degrees.
    advance = (mean_longitudes(2451546.0)["Mercury"] - result["Mercury"]) % 360
    assert 4.09 < advance < 4.10


def test_validated_tt_window_is_half_open_not_a_guessed_source_validity():
    assert admitted(LOWER_TT)
    assert admitted(math.nextafter(UPPER_TT, -math.inf))
    assert not admitted(UPPER_TT)
    assert not admitted(math.nextafter(LOWER_TT, -math.inf))
    assert not admitted(math.nan)
    assert not admitted(math.inf)


def test_declared_model_uses_mean_sun_and_separate_geometric_frame():
    raw = {
        "cheshta_model": MODEL,
        "julian_day_tt": 2451545.0,
        "motion_true_j2000": geometric_points(2451545.0, "auto"),
        "longitudes": {"Sun": 123.0},
    }
    result = model_balas(raw)
    assert result["model_context"]["status"] == "computed_declared_secular_model"
    evidence = result["model_context"]["planet_evidence"]
    means = mean_longitudes(raw["julian_day_tt"])
    for p in ("Mars", "Jupiter", "Saturn"):
        assert evidence[p]["mean_longitude"] == means[p]
        assert evidence[p]["seeghrochcha"] == means["Sun"]
    for p in ("Mercury", "Venus"):
        assert evidence[p]["mean_longitude"] == means["Sun"]
        assert evidence[p]["seeghrochcha"] == means[p]
    assert all(0 <= value <= 60 for value in result["summary"].values())
    raw["longitudes"] = {"Sun": 321.0, "Mars": 0.0}
    assert model_balas(raw) == result  # no D1 longitude or varga masquerade


def test_default_and_outside_window_remain_missing_without_model_substitution():
    result = model_balas({})
    assert all(value is None for value in result["summary"].values())
    result = model_balas({"cheshta_model": MODEL, "julian_day_tt": UPPER_TT})
    assert result["model_context"]["status"] == "outside_validated_model_window"
    assert all(value is None for value in result["summary"].values())
    with pytest.raises(ValueError, match="Unsupported"):
        model_balas({"cheshta_model": "fitted_JPL_elements_are_not_means"})


def test_strict_policy_covers_geometric_positions(monkeypatch, tmp_path):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    auto = geometric_points(2451545.0, "auto")
    assert all(value["ephemeris_model"] == "moshier" for value in auto.values())
    with pytest.raises(ValueError, match="require_data_files"):
        geometric_points(2451545.0, "require_data_files")
