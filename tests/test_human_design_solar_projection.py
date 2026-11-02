"""Independent geometry and separation of projection from physical visibility."""

import math

import pytest

from fatebridge.core.human_design_solar_projection import nominal_solar_projection
from scripts.check_human_design_solar_projection import checks


def test_all21600_frozen_geometric_inputs_without_narrowing_the_cohort():
    report = checks()
    assert report["case_count"] == report["cases_matched"] == 21600
    assert report["failures"] == []
    assert len(report["inside_nominal_projection_cases"]) == 7
    assert report["native_astronomy_accuracy_certified"] is False
    assert report["physical_occultation_certified"] is False
    assert report["visibility_certified"] is False


def test_same_projection_does_not_confuse_foreground_and_background():
    front = nominal_solar_projection([0, 0, 1], [0, 0, 0.01])
    behind = nominal_solar_projection([0, 0, 1], [0, 0, 2])
    assert front["inside_nominal_solar_disk_projection"] is True
    assert behind["inside_nominal_solar_disk_projection"] is True
    assert front["more_distant_than_sun_in_supplied_coordinates"] is False
    assert behind["more_distant_than_sun_in_supplied_coordinates"] is True
    assert behind["visibility_certified"] is False


def test_nominal_limb_is_reported_as_a_numerical_boundary_not_a_physical_fact():
    radius = nominal_solar_projection([0, 0, 1], [0, 0, 2])[
        "nominal_solar_radius_radians"
    ]
    result = nominal_solar_projection([0, 0, 1], [math.degrees(radius), 0, 2])
    assert result["projection_relation"] == "numerical_boundary_undetermined"
    assert result["inside_nominal_solar_disk_projection"] is None
    assert result["physical_accuracy_certified"] is False


def test_nonzero_solar_latitude_and_antipodal_direction_are_not_flattened():
    result = nominal_solar_projection([0, 30, 1], [0, -30, 2])
    assert abs(result["separation_radians"] - math.pi / 3) < 1e-12
    opposite = nominal_solar_projection([0, 0, 1], [180, 0, 2])
    assert opposite["separation_radians"] == math.pi
    assert opposite["inside_nominal_solar_disk_projection"] is False


@pytest.mark.parametrize(
    "coordinates",
    [[0, 0], [0, float("nan"), 1], [0, 91, 1], [0, 0, 0], [True, 0, 1]],
)
def test_missing_or_invalid_geometry_is_not_filled_with_defaults(coordinates):
    with pytest.raises(ValueError):
        nominal_solar_projection([0, 0, 1], coordinates)
