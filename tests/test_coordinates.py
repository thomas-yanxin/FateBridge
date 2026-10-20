"""Coordinate boundaries and shared parsing across calculation entry points."""

import pytest

from fatebridge.core.local_techniques.chart import _resolve_coordinates
from fatebridge.utils.coordinates import parse_geo_coordinate


@pytest.mark.parametrize(
    "value,axis,expected",
    [
        (0, "longitude", 0),
        (0, "latitude", 0),
        ("121e30", "longitude", 121.5),
        ("31s15", "latitude", -31.25),
        ("-180", "longitude", -180),
        ("90N0", "latitude", 90),
        (None, "latitude", None),
        ("", "longitude", None),
    ],
)
def test_decimal_and_direction_coordinates(value, axis, expected):
    assert parse_geo_coordinate(value, axis=axis) == expected


@pytest.mark.parametrize(
    "value,axis",
    [
        ("31N90", "latitude"),
        ("190", "longitude"),
        (-91, "latitude"),
        (float("nan"), "longitude"),
        (float("inf"), "latitude"),
        ("31E13", "latitude"),
        ("121N28", "longitude"),
        ("bad", "longitude"),
        ("-31N0", "latitude"),
        (True, "latitude"),
    ],
)
def test_invalid_coordinates_never_fall_back_to_a_default(value, axis):
    with pytest.raises(ValueError):
        parse_geo_coordinate(value, axis=axis)


@pytest.mark.parametrize("latitude,longitude", [(0, 0), (0, 32.5), (51.5, 0)])
def test_zero_coordinates_are_preserved(latitude, longitude):
    assert _resolve_coordinates(gps_lat=latitude, gps_lon=longitude) == (
        latitude,
        longitude,
    )


def test_gps_coordinates_take_precedence_over_text_hints():
    assert _resolve_coordinates(lat="bad", lon="bad", gps_lat=0, gps_lon=0) == (0, 0)
