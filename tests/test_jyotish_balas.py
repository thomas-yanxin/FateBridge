"""Primary-rule arithmetic, independent oracle, direction and nature boundaries."""

import json
import math
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish import build_india, positions
from fatebridge.core.jyotish_balas import (
    PLANETS,
    aspect_strength,
    aspect_value,
    directed_angle,
    directional_strength,
    natural_strength,
)
from tests.fixtures.surface_payloads import astro_payload

FIXTURES = Path(__file__).parent / "fixtures"
PRIMARY = json.loads((FIXTURES / "jyotish-balas-classical.json").read_text())
ORACLE = json.loads((FIXTURES / "jyotish-balas-reference.json").read_text())


@pytest.mark.parametrize(
    "angle,expected", zip(PRIMARY["base_angles"], PRIMARY["base_virupa"])
)
def test_primary_ordinary_aspect_table(angle, expected):
    assert aspect_value("Sun", 0, angle)["value"] == expected


@pytest.mark.parametrize("planet,angle,expected", PRIMARY["special_cases"])
def test_literal_special_additions_without_invented_sixty_cap(planet, angle, expected):
    assert aspect_value(planet, 0, angle)["value"] == expected


def test_directed_angles_match_primary_book_pairs_and_are_not_symmetric():
    data = PRIMARY["raman_directed_example53"]
    for aspector, target, (degrees, minutes) in data["pair_examples"]:
        a = sum(
            Fraction(v, scale)
            for v, scale in zip(data["longitudes"][aspector], [1, 60])
        )
        b = sum(
            Fraction(v, scale) for v, scale in zip(data["longitudes"][target], [1, 60])
        )
        assert float(directed_angle(float(a), float(b))) == pytest.approx(
            degrees + minutes / 60, abs=1e-12
        )
    assert aspect_value("Sun", 0, 75)["value"] == 30
    assert aspect_value("Sun", 75, 0)["value"] == 7.5


def test_partition_sides_use_exact_input_ratios_and_keep_special_discontinuities():
    for longitude in [60.0, 90.0, 120.0, 150.0, 180.0, 210.0, 240.0, 270.0, 300.0]:
        left = math.nextafter(longitude, -math.inf)
        assert directed_angle(0, left) < Fraction(longitude)
        assert directed_angle(0, longitude) == Fraction(longitude)
    assert aspect_value("Saturn", 0, math.nextafter(90, -math.inf))["value"] > 89.99
    assert aspect_value("Saturn", 0, 90)["value"] == 45
    assert aspect_value("Saturn", 0, math.nextafter(300, -math.inf))["value"] > 44.99
    assert aspect_value("Saturn", 0, 300)["value"] == 0
    # Subtraction before modulo could round this exact near-360 angle to360.
    assert directed_angle(math.nextafter(0, 1), 0) < 360
    with pytest.raises(ValueError):
        aspect_value("Rahu", 0, 180)


def test_directional_hand_arithmetic_uses_cardinal_points_and_folds_wrap():
    row = PRIMARY["zero_asc_90_mc_diagonal"]
    result = directional_strength(
        {"ascendant": 0.0, "midheaven": 90.0, "longitudes": row["longitudes"]}
    )
    assert result["summary"] == row["expected_dig_virupa"]
    raw = {
        "ascendant": 350.0,
        "midheaven": 260.0,
        "longitudes": dict.fromkeys(PLANETS, 10.0),
    }
    assert directional_strength(raw)["summary"]["Saturn"] == pytest.approx(20 / 3)
    # Whole-sign house start would yield0, but the physical ascending degree is10.
    raw.update(ascendant=10.0)
    assert directional_strength(raw)["summary"]["Saturn"] == 0
    for planet, point in {
        "Sun": 90,
        "Mars": 90,
        "Moon": 270,
        "Venus": 270,
        "Mercury": 0,
        "Jupiter": 0,
        "Saturn": 180,
    }.items():
        raw = {
            "ascendant": 0.0,
            "midheaven": 90.0,
            "longitudes": dict.fromkeys(PLANETS, 0.0),
        }
        raw["longitudes"][planet] = float(point)
        assert directional_strength(raw)["summary"][planet] == 60
        raw["longitudes"][planet] = float((point + 180) % 360)
        assert directional_strength(raw)["summary"][planet] == 0


def test_natural_coefficients_follow_primary_exact_sevenths_without_false_photometry():
    result = natural_strength()
    for planet, numerator in PRIMARY["natural_exact_numerators_over7"].items():
        assert result["summary"][planet] == float(Fraction(numerator, 7))
    assert "not observed luminosity" in result["basis"]["scope"]
    assert set(result["summary"]) == set(PLANETS)


def test_conditional_nature_results_keep_negative_values_and_unknown_separate_from_zero():
    case = PRIMARY["hand_conditional_case"]
    result = aspect_strength(case["longitudes"])
    assert result["summary"]["Sun"] is None
    assert (
        result["nature_context"]["mercury_status"]
        == "association_predicate_not_adjudicated"
    )
    for nature, expected in case["Sun_by_mercury_nature"].items():
        branch = result["scenarios"][f"moon_benefic__mercury_{nature}"]
        assert branch["summary"]["Sun"] == expected
        assert branch["summary"]["Sun"] == sum(branch["contributions"]["Sun"].values())
    # Mercury self-aspect is zero; its own ambiguous nature cannot alter itself.
    for moon in ("benefic", "malefic"):
        assert (
            result["scenarios"][f"moon_{moon}__mercury_benefic"]["summary"]["Mercury"]
            == result["scenarios"][f"moon_{moon}__mercury_malefic"]["summary"][
                "Mercury"
            ]
        )
    zero = aspect_strength(dict.fromkeys(PLANETS, 0.0))
    assert zero["summary"] == dict.fromkeys(PLANETS, 0.0)
    assert len(zero["scenarios"]) == 4


@pytest.mark.parametrize(
    "moon,options",
    [
        (0, ["benefic", "malefic"]),
        (90, ["benefic", "malefic"]),
        (180, ["benefic", "malefic"]),
        (270, ["benefic", "malefic"]),
    ],
)
def test_phase_boundaries_preserve_conditional_classification(moon, options):
    result = aspect_strength({**dict.fromkeys(PLANETS, 0.0), "Moon": float(moon)})
    assert result["nature_context"]["moon_options"] == options
    assert len(result["scenarios"]) == len(options) * 2


@pytest.mark.parametrize("case", ORACLE["examples"])
def test_balas_against_isolated_pyjhora_with_unfolded_method_failure_retained(
    case, monkeypatch, tmp_path
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    y, m, d = case["date"]
    h, minute, _ = case["time"]
    birth = build_astro_birth_info(
        birth_year=y,
        birth_month=m,
        birth_day=d,
        birth_hour=h,
        birth_minute=minute,
        birth_longitude=case["longitude"],
        birth_latitude=case["latitude"],
        birth_timezone=str(case["timezone_offset"]),
    )
    raw = positions(birth)
    assert raw["ephemeris_models"] == ["moshier"]
    actual_dig = directional_strength(raw)
    actual_aspects = aspect_strength(raw["longitudes"])
    for p in PLANETS:
        assert actual_dig["summary"][p] == pytest.approx(
            case["dig_bala_shortest_arc_method2"][p], abs=0.0051, rel=0
        )
        assert natural_strength()["summary"][p] == pytest.approx(
            case["naisargika_bala_rounded"][p], abs=0.0051, rel=0
        )
        for q in PLANETS:
            assert actual_aspects["matrix"][p][q] == pytest.approx(
                case["aspect_matrix"][p][q], abs=0.0151, rel=0
            )
    for branch, data in actual_aspects["scenarios"].items():
        signs = {
            "Sun": -1,
            "Mars": -1,
            "Saturn": -1,
            "Jupiter": 1,
            "Venus": 1,
            "Moon": 1 if branch.startswith("moon_benefic__") else -1,
            "Mercury": 1 if branch.endswith("__mercury_benefic") else -1,
        }
        for target in PLANETS:
            expected = (
                sum(signs[p] * case["aspect_matrix"][p][target] for p in PLANETS) / 4
            )
            assert data["summary"][target] == pytest.approx(expected, abs=0.0227, rel=0)
    # The reference's legacy method1 forgets the shortest-arc reduction.
    assert max(case["dig_bala_shortest_arc_method2"].values()) <= 60
    for p, value in case["dig_bala_legacy_method1"].items():
        if value > 60:
            assert actual_dig["summary"][p] == pytest.approx(
                120 - value, abs=0.0051, rel=0
            )


def test_integrated_missing_branches_and_same_grid_sensitivity_are_explicit():
    india = build_india(
        build_astro_birth_info(**astro_payload()), birth_time_uncertainty_minutes=1
    )
    strengths = india["strengths"]
    assessment = strengths["shadbala_assessment"]
    assert assessment["total_virupa"] is None
    assert "cheshta_bala_five_star_mean_model" in assessment["missing"]
    assert assessment["conditional"] == ["drik_bala", "kala_bala"]
    assert assessment["partial"] == ["cheshta_bala"]
    for p, value in strengths["dig_bala"]["summary"].items():
        band = india["birth_time_sensitivity"]["dig_bala_sample_ranges"][p]
        assert band["minimum"] <= value <= band["maximum"]
    for branch, data in strengths["drik_bala"]["scenarios"].items():
        for p, value in data["summary"].items():
            band = india["birth_time_sensitivity"]["drik_bala_scenario_sample_ranges"][
                branch
            ][p]
            assert band["minimum"] <= value <= band["maximum"]
            assert band["sample_count"] == 5


def test_midheaven_against_independent_meridian_ecliptic_intersection():
    # Shared sidereal-time/obliquity inputs; independent spherical construction
    # checks returned MC/axis choice, not an independent astronomical ephemeris.
    for longitude, latitude in [
        (0, 0),
        (121.4667, 31.2167),
        (-74.006, 40.7128),
        (151.2093, -33.8688),
    ]:
        birth = build_astro_birth_info(
            **{
                **astro_payload(),
                "birth_longitude": longitude,
                "birth_latitude": latitude,
            }
        )
        actual = positions(birth)
        with runtime.preserve_ephemeris_path():
            epsilon = math.radians(
                runtime.swe.calc(actual["julian_day_tt"], runtime.swe.ECL_NUT)[0][0]
            )
            theta = math.radians(
                (runtime.swe.sidtime(actual["julian_day_ut"]) * 15 + longitude) % 360
            )
        tropical_mc = (
            math.degrees(
                math.atan2(math.sin(theta), math.cos(theta) * math.cos(epsilon))
            )
            % 360
        )
        expected = (tropical_mc - actual["ayanamsha"]) % 360
        error = (actual["midheaven"] - expected + 180) % 360 - 180
        assert abs(error) < 1e-7
