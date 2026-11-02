"""Source tables, hand arithmetic, independent implementation and cusp tests."""

import json
import math
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astrology_tables import SIGNS
from fatebridge.core.jyotish import GRAHAS, build_india, divisional_chart
from fatebridge.core.jyotish_sthana import COMPONENTS, calculate_sthana, saptavargaja
from fatebridge.core.jyotish_vargas import (
    varga_coordinates,
    varga_longitude,
    varga_sign,
)
from tests.fixtures.surface_payloads import astro_payload

FIXTURES = Path(__file__).parent / "fixtures"
CLASSICAL = json.loads((FIXTURES / "jyotish-sthana-classical.json").read_text())
ORACLE = json.loads((FIXTURES / "jyotish-sthana-reference.json").read_text())


@pytest.mark.parametrize("division", [2, 3, 7, 12])
def test_equal_divisions_against_transcribed_source_tables_and_exact_cusp_sides(
    division,
):
    table = CLASSICAL[f"D{division}"]
    for sign, row in enumerate(table):
        for part, target in enumerate(row):
            midpoint = float(
                Fraction(sign * 30) + Fraction((2 * part + 1) * 15, division)
            )
            assert varga_sign(midpoint, division) == target - 1
            if part == 0:
                assert varga_sign(sign * 30.0, division) == target - 1
                continue
            exact = Fraction(sign * 30) + Fraction(part * 30, division)
            rounded = float(exact)
            for value in (
                math.nextafter(rounded, -math.inf),
                rounded,
                math.nextafter(rounded, math.inf),
            ):
                expected = row[part - 1] if Fraction(value) < exact else target
                actual_sign, degree = varga_coordinates(value, division)
                assert actual_sign == expected - 1
                assert 0 <= degree < 30
                assert int(varga_longitude(value, division) // 30) == expected - 1


def test_unequal_d30_intervals_exact_boundaries_and_no_fabricated_degree():
    for sign in range(12):
        row = CLASSICAL["D30"]["odd" if sign % 2 == 0 else "even"]
        start = 0
        for part, (end, target) in enumerate(zip(row["ends"], row["signs"])):
            for value in (
                sign * 30 + start,
                sign * 30 + (start + end) / 2,
                math.nextafter(sign * 30.0 + end, -math.inf),
            ):
                assert varga_coordinates(value, 30) == (target - 1, None)
            if end < 30:
                assert varga_coordinates(sign * 30.0 + end, 30) == (
                    row["signs"][part + 1] - 1,
                    None,
                )
            start = end
    with pytest.raises(ValueError, match="D30"):
        varga_longitude(5, 30)
    chart = divisional_chart(
        {"ascendant": 0.0, "longitudes": dict.fromkeys(GRAHAS, 5.0)}, 30
    )
    for point in [chart["ascendant"], *chart["planets"]]:
        assert point["longitude"] is None
        assert point["degree_in_sign"] is None
        assert point["sign"] in SIGNS
        assert 1 <= point["house"] <= 12
        assert "physical_state" not in point


@pytest.mark.parametrize("profile", ["santhanam_27", "raman_30"])
def test_five_components_against_independent_hand_arithmetic(profile):
    raw = {"ascendant": 0.0, "longitudes": dict.fromkeys(GRAHAS, 0.0)}
    result = calculate_sthana(raw, profile)
    hand = CLASSICAL["all_grahas_at_zero"]
    for i, planet in enumerate(GRAHAS[:7]):
        expected = {
            "uchcha_bala": hand["uchcha_bala_numerators_divide_by_three"][i] / 3,
            "saptavargaja_bala": hand[
                (
                    "santhanam_saptavargaja"
                    if profile == "santhanam_27"
                    else "raman_saptavargaja"
                )
            ][i],
            "ojayugma_bala": hand["ojayugma"][i],
            "kendradi_bala": hand["kendradi"][i],
            "drekkana_bala": hand["drekkana"][i],
        }
        actual = result["summary"][planet]
        for key, value in expected.items():
            assert actual[key] == pytest.approx(value, abs=1e-12, rel=0)
        assert actual["total_virupa"] == pytest.approx(sum(expected.values()))
        assert actual["total_rupa"] == pytest.approx(sum(expected.values()) / 60)
    assert set(result["summary"]) == set(GRAHAS[:7])
    assert result["shadbala_status"] == "not_complete"
    assert len(result["remaining_shadbala"]) == 5


def test_raman_primary_book_sun_example_without_using_its_corrupted_ocr_totals():
    row = CLASSICAL["raman_example9"]
    longitudes = {
        key: degrees + minutes / 60 + seconds / 3600
        for key, (degrees, minutes, seconds) in row["longitudes_dms"].items()
    }
    actual = saptavargaja(longitudes, "Sun", "raman_30")
    assert [r["value"] for r in actual["rows"]] == row["Sun_saptavargaja_values"]
    assert actual["value"] == row["Sun_saptavargaja_total"]


def test_d1_relationship_is_used_in_d30_even_when_varga_distance_differs():
    longitudes = {**dict.fromkeys(GRAHAS, 0.0), "Sun": 30.0, "Venus": 132.0}
    row = saptavargaja(longitudes, "Sun", "santhanam_27")["rows"][-1]
    assert row["division"] == 30
    assert row["relationship"]["compound"] == "neutral"
    assert row["value"] == 10


def test_author_profile_changes_only_saptavargaja_and_preserves_disagreement():
    raw = {"ascendant": 0.0, "longitudes": dict.fromkeys(GRAHAS, 0.0)}
    santhanam, raman = [
        calculate_sthana(raw, profile) for profile in ("santhanam_27", "raman_30")
    ]
    for planet in GRAHAS[:7]:
        a, b = santhanam["summary"][planet], raman["summary"][planet]
        for component in COMPONENTS:
            if component != "saptavargaja_bala":
                assert a[component] == b[component]
        assert (
            santhanam["profile_comparison"]["raman_30"][planet]["saptavargaja_bala"]
            == b["saptavargaja_bala"]
        )
    assert (
        santhanam["summary"]["Mars"]["saptavargaja_bala"]
        != raman["summary"]["Mars"]["saptavargaja_bala"]
    )
    assert "other four components keep Santhanam" in raman["profile"]["scope"]


@pytest.mark.parametrize("case", ORACLE["examples"])
def test_all_vargas_and_aligned_strength_components_against_isolated_pyjhora(
    case, monkeypatch, tmp_path
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    year, month, day = case["date"]
    hour, minute, _ = case["time"]
    birth = build_astro_birth_info(
        birth_year=year,
        birth_month=month,
        birth_day=day,
        birth_hour=hour,
        birth_minute=minute,
        birth_longitude=case["longitude"],
        birth_latitude=case["latitude"],
        birth_timezone=str(case["timezone_offset"]),
    )
    india = build_india(
        birth,
        node_mode=case["node_mode"],
        divisions=[2, 3, 7, 9, 10, 12, 30],
        saptavargaja_profile="raman_30",
    )
    assert india["profile"]["ephemeris_models"] == ["moshier"]
    for name, chart in india["charts"].items():
        for point in [chart["ascendant"], *chart["planets"]]:
            sign, degree = case["vargas"][name][point["id"]]
            assert point["sign"] == SIGNS[sign]
            if name != "D30":
                # Existing independent D1 audit bounds 2e-7 deg; true node
                # cross-platform Swiss noise 1e-6 deg, amplified by division.
                base = (
                    1e-6
                    if point["id"] in {"Rahu", "Ketu"} and case["node_mode"] == "true"
                    else 2e-7
                )
                assert point["longitude"] == pytest.approx(
                    sign * 30 + degree, abs=base * chart["division"], rel=0
                )
    for planet, expected in case["strength"].items():
        actual = india["strengths"]["sthana_bala"]["summary"][planet]
        for component in COMPONENTS:
            # Oracle follows Raman section36, whose middle/last categories
            # reverse Santhanam 27.6. Keep this documented disagreement.
            if component == "drekkana_bala":
                continue
            assert actual[component] == pytest.approx(
                expected[component], abs=0.0051, rel=0
            ), (planet, component)
        assert actual["total_virupa"] - actual["drekkana_bala"] == pytest.approx(
            expected["total_virupa"] - expected["drekkana_bala"], abs=0.0101, rel=0
        )
        longitude = next(
            p["longitude"]
            for p in india["charts"]["D1"]["planets"]
            if p["id"] == planet
        )
        section = int(longitude % 30 // 10)
        raman_categories = (
            ("Sun", "Mars", "Jupiter"),
            ("Mercury", "Saturn"),
            ("Moon", "Venus"),
        )
        assert expected["drekkana_bala"] == (
            15 if planet in raman_categories[section] else 0
        )


@pytest.mark.parametrize(
    "planet,degree,expected",
    [
        ("Moon", 10, 15),
        ("Moon", 20, 0),
        ("Venus", 10, 15),
        ("Mercury", 10, 0),
        ("Mercury", 20, 15),
        ("Saturn", 20, 15),
        ("Sun", 0, 15),
        ("Sun", 10, 0),
    ],
)
def test_santhanam_drekkana_boundaries_do_not_inherit_raman_categories(
    planet, degree, expected
):
    raw = {
        "ascendant": 0.0,
        "longitudes": {**dict.fromkeys(GRAHAS, 0.0), planet: float(degree)},
    }
    result = calculate_sthana(raw, "raman_30")
    # Selecting Raman Saptavargaja never silently switches Drekkana's source.
    assert result["summary"][planet]["drekkana_bala"] == expected


def test_strengths_exist_without_exporting_extra_charts_and_sensitivity_contains_actual_values():
    birth = build_astro_birth_info(**astro_payload())
    india = build_india(birth, divisions=[], birth_time_uncertainty_minutes=1)
    assert set(india["charts"]) == {"D1"}
    ranges = india["birth_time_sensitivity"]["sthana_bala_sample_ranges"]
    for planet, values in india["strengths"]["sthana_bala"]["summary"].items():
        for component, value in values.items():
            assert (
                ranges[planet][component]["minimum"]
                <= value
                <= ranges[planet][component]["maximum"]
            )
    assert india["birth_time_sensitivity"]["sample_count"] == 5


def test_all_rasi_groups_and_parities_against_source_component_tables():
    # D1 degree0 falls in the first Navamsa, whose parity follows D1.
    kendra_by_house = [60, 30, 15, 60, 30, 15, 60, 30, 15, 60, 30, 15]
    for sign in range(12):
        result = calculate_sthana(
            {"ascendant": 0.0, "longitudes": dict.fromkeys(GRAHAS, float(sign * 30))}
        )
        for planet, values in result["summary"].items():
            assert values["kendradi_bala"] == kendra_by_house[sign]
            expected = (
                30
                if (sign % 2 == 1 if planet in {"Moon", "Venus"} else sign % 2 == 0)
                else 0
            )
            assert values["ojayugma_bala"] == expected


@pytest.mark.native_engine_fault
def test_unexported_varga_strength_change_is_not_reported_as_no_categorical_change(
    monkeypatch,
):
    from fatebridge.core import jyotish

    birth = build_astro_birth_info(**astro_payload())
    base = jyotish.positions(birth)

    def synthetic_positions(birth, when=None, *args, **kwargs):
        # Freeze every physical-state label to isolate the internal D2 change.
        # This is a sampling-control test, not an astronomical reference.
        longitude = 15.01 if when is not None and when > birth.utc_datetime else 14.99
        return {**base, "longitudes": {**base["longitudes"], "Sun": longitude}}

    monkeypatch.setattr(jyotish, "positions", synthetic_positions)
    result = build_india(birth, divisions=[], birth_time_uncertainty_minutes=1)
    sensitivity = result["birth_time_sensitivity"]
    assert sensitivity["alternatives"] == {"D1": {}}
    assert sensitivity["physical_condition_alternatives"] == {}
    assert (
        len(
            sensitivity["sthana_discrete_component_alternatives"]["Sun"][
                "saptavargaja_bala"
            ]
        )
        == 2
    )
    assert sensitivity["status"] == "changes_detected"
