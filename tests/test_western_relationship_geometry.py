"""Independent geographic answers, method recipes, and numerical counterexamples."""

import json
import math
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from fatebridge.core.astro.aspects import (
    _build_directional_relative_midpoints,
    _match_cross_aspect,
)
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.astro.relationship_geometry import (
    davison_birth,
    geographic_midpoint,
    midpoint_candidates,
    unique_midpoint,
)
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.ephemeris_runtime import swe
from fatebridge.services.astrology import calculate_relative_chart_analysis

REFERENCE = json.loads(
    (
        Path(__file__).parent / "fixtures/western-geographiclib-midpoints.json"
    ).read_text()
)
A = dict(
    name="甲",
    birth_year=1990,
    birth_month=4,
    birth_day=6,
    birth_hour=9,
    birth_minute=33,
    birth_timezone="UTC",
    birth_longitude=179,
    birth_latitude=10,
)
B = dict(
    name="乙",
    birth_year=1992,
    birth_month=3,
    birth_day=2,
    birth_hour=8,
    birth_minute=18,
    birth_timezone="UTC",
    birth_longitude=-179,
    birth_latitude=20,
)


def separation(a, b):
    return abs((a - b + 180) % 360 - 180)


@pytest.mark.parametrize("case", REFERENCE["cases"])
def test_spherical_midpoints_against_independent_geographiclib(case):
    args = case["input_longitudes_latitudes"]
    for inputs in (args, args[2:] + args[:2]):
        longitude, latitude = geographic_midpoint(*inputs, spherical=True)
        assert (
            abs(latitude - case["expected_latitude"]) <= REFERENCE["tolerance_degrees"]
        )
        if abs(case["expected_latitude"]) != 90:
            assert (
                separation(longitude, case["expected_longitude"])
                <= REFERENCE["tolerance_degrees"]
            )


@pytest.mark.parametrize(
    "lon1,lon2,expected", [(179, -179, -180), (-180, 180, -180), (10, 20, 15)]
)
def test_coordinate_mean_is_dateline_and_alias_aware(lon1, lon2, expected):
    assert geographic_midpoint(lon1, 10, lon2, 20) == (expected, 15)
    assert geographic_midpoint(lon2, 20, lon1, 10) == (expected, 15)


def test_sphere_and_coordinate_mean_remain_distinct_methods():
    assert geographic_midpoint(179, 10, -179, 10) == (-180, 10)
    assert geographic_midpoint(179, 10, -179, 10, spherical=True)[1] > 10.001


@pytest.mark.parametrize("args", [(0, 10, 180, -10), (50, 90, -20, -90)])
def test_exact_antipodes_have_no_unique_spherical_midpoint(args):
    with pytest.raises(ValueError, match="对跖"):
        geographic_midpoint(*args, spherical=True)


def test_near_antipodes_preserve_the_unique_side_without_epsilon_rejection():
    for longitude in (math.nextafter(180.0, 0), math.nextafter(-180.0, 0)):
        actual_lon, actual_lat = geographic_midpoint(
            0, 10, longitude, -10, spherical=True
        )
        assert actual_lat == 0
        assert actual_lon == longitude / 2


@pytest.mark.parametrize(
    "second",
    [math.nextafter(180.0, 0), math.nextafter(180.0, math.inf), 359.9999999, 0.0000001],
)
def test_circular_midpoint_uses_independent_exact_decimal_arithmetic(second):
    with localcontext() as context:
        context.prec = 1100
        a, b = Decimal(0), Decimal.from_float(second)
        delta = b % 360
        if delta > 180:
            delta -= 360
        expected = ((a + delta / 2) % 360 + 360) % 360
    assert unique_midpoint(0, second) == unique_midpoint(second, 0) == float(expected)


def test_exact_diametric_points_keep_both_candidates_for_comparison_only():
    assert midpoint_candidates(0, 180) == midpoint_candidates(180, 0) == (90, 270)
    with pytest.raises(ValueError, match="没有唯一"):
        unique_midpoint(0, 180)
    hits = _build_directional_relative_midpoints(
        [{"id": "Jupiter", "longitude": 90}],
        [{"id": "Sun", "longitude": 0}, {"id": "Moon", "longitude": 180}],
    )["Jupiter"]
    assert [row["midpoint"]["longitude"] for row in hits] == [90, 270]
    assert [row["aspect"] for row in hits] == ["conjunction", "opposition"]
    assert all(row["midpoint"]["antipodal_inputs"] for row in hits)


@pytest.mark.parametrize("degree,expected", [(33.0, False), (32.9999999, True)])
def test_relative_midpoint_orb_is_not_changed_by_four_decimal_rounding(
    degree, expected
):
    targets = [
        {"id": "Sun", "longitude": 29.99999996},
        {"id": "Moon", "longitude": 29.99999998},
    ]
    hits = _build_directional_relative_midpoints(
        [{"id": "Jupiter", "longitude": degree}], targets
    )
    assert bool(hits) is expected
    if expected:
        assert hits["Jupiter"][0]["midpoint"]["longitude"] < 30


def test_cross_aspect_offset_retains_computed_precision():
    assert _match_cross_aspect(0, 0.123456789)["delta"] == 0.123456789


@pytest.mark.skipif(swe is None, reason="Native ephemeris required")
@pytest.mark.parametrize("variant", ["uncorrected", "corrected", "spherical"])
@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize("hsys", [0, 3])
def test_davison_uses_native_positions_houses_and_declared_variant(
    variant, zodiacal, hsys
):
    first, second = build_astro_birth_info(**A), build_astro_birth_info(**B)
    birth, policy = davison_birth(first, second, variant=variant)
    reversed_birth, _ = davison_birth(second, first, variant=variant)
    assert birth.utc_datetime == reversed_birth.utc_datetime
    assert separation(birth.longitude, reversed_birth.longitude) < 1e-12
    assert abs(birth.latitude - reversed_birth.latitude) < 1e-12
    native = build_core_chart_payload(birth, "chart", hsys=hsys, zodiacal=zodiacal)
    result = calculate_relative_chart_analysis(
        inner_payload=A,
        outer_payload=B,
        relative_mode="TimeSpace",
        davison_variant=variant,
        hsys=hsys,
        zodiacal=zodiacal,
    )
    assert "error" not in result
    chart = result["chart"]
    assert chart["planets"] == native["planets"]
    assert chart["houses"] == native["houses"]
    assert chart["angles"] == native["angles"]
    assert (
        chart["chart_profile"]["julian_day_tt"]
        == native["chart_profile"]["julian_day_tt"]
    )
    assert chart["chart_profile"]["derivation_policy"]["variant"] == variant
    if variant == "corrected":
        natal_mcs = [
            build_core_chart_payload(p, "chart", hsys=0)["angles"]["midheaven"][
                "longitude"
            ]
            for p in (first, second)
        ]
        expected_axis = sum(natal_mcs) / 2 % 180
        assert (
            abs((policy["mc_actual_tropical"] - expected_axis + 90) % 180 - 90) < 1e-5
        )
        assert policy["mc_residual_degrees"] < 1e-5


@pytest.mark.skipif(swe is None, reason="Native ephemeris required")
def test_time_mean_is_explicit_ut1_not_naive_utc_calendar_arithmetic():
    first = build_astro_birth_info(**{**A, "birth_year": 1900})
    second = build_astro_birth_info(**{**B, "birth_year": 2099})
    birth, policy = davison_birth(first, second)
    expected = (
        ephemeris_time(first.utc_datetime).jd_ut1
        + ephemeris_time(second.utc_datetime).jd_ut1
    ) / 2
    assert abs(ephemeris_time(birth.utc_datetime).jd_ut1 - expected) < 1e-9
    naive = first.utc_datetime + (second.utc_datetime - first.utc_datetime) / 2
    assert abs((birth.utc_datetime - naive).total_seconds()) > 0.1
    assert "UT1" in policy["time_policy"]
    assert "not a quote" in policy["time_source_scope"]


@pytest.mark.skipif(swe is None, reason="Native ephemeris required")
def test_marks_is_two_natal_to_davison_charts_with_quarter_time_identities():
    result = calculate_relative_chart_analysis(
        inner_payload=A, outer_payload=B, relative_mode="Marks", hsys=0
    )
    swapped = calculate_relative_chart_analysis(
        inner_payload=B, outer_payload=A, relative_mode="Marks", hsys=0
    )
    assert result["relationship_profile"]["primary_layer"] == "marks_chart_pair"
    assert result["chart"] == result["marks_charts"]["inner"]
    assert result["relationship_profile"]["primary_chart_role"] == "inner"
    times = [
        ephemeris_time(build_astro_birth_info(**p).utc_datetime).jd_ut1 for p in (A, B)
    ]
    for role, index, opposite_role in [("inner", 0, "outer"), ("outer", 1, "inner")]:
        chart = result["marks_charts"][role]
        expected = (3 * times[index] + times[1 - index]) / 4
        assert abs(chart["chart_profile"]["julian_day_ut1"] - expected) < 1e-9
        assert chart["planets"] == swapped["marks_charts"][opposite_role]["planets"]
        policy = chart["chart_profile"]["derivation_policy"]
        assert policy["method_id"] == "marks_natal_davison_v1"
        assert "mirror" in policy["source_kind"]
        assert policy["positions_from_single_instant"] is True
    assert (
        result["marks_charts"]["inner"]["planets"]
        != result["marks_charts"]["outer"]["planets"]
    )


def test_non_davison_mode_does_not_silently_accept_a_davison_variant():
    result = calculate_relative_chart_analysis(
        inner_payload=A,
        outer_payload=B,
        relative_mode="Compare",
        hsys=0,
        davison_variant="corrected",
    )
    assert "error" in result and "仅适用于" in result["error"]
