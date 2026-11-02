"""Numerical boundaries and counterfactual prose checks; no self-awarded score."""

import copy
import json
import math
from pathlib import Path

import pytest

from fatebridge.core.astro.aspects import _build_aspects
from fatebridge.core.astro.geometry import normalize_angle
from fatebridge.core.astro.parts import _build_houses, _build_planet_record
from fatebridge.core.classical_western import build_planet_classical
from fatebridge.core.predictive._common import longitude_to_point_dict
from fatebridge.core.ptolemy import build_ptolemy_layer, sign_relationship
from fatebridge.services.astrology import (
    SIGN_INTERPRETATION,
    _augment_core_chart_reading,
    _build_angle_lines,
    _build_aspect_pattern,
    _build_development_advice,
    _build_dominant_energy,
    _build_house_lines,
    _build_life_focus,
    _build_planet_lines,
    _build_social_style,
    _house_focus,
    _sign_focus,
    calculate_core_chart_analysis,
)
from tests.test_western_accuracy import BIRTH

SIGNS = [
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
]
PRIMARY = json.loads(
    (
        Path(__file__).parent
        / "fixtures/western-ptolemy-sign-relations-robbins-1940.json"
    ).read_text()
)


@pytest.mark.parametrize("index", range(12))
@pytest.mark.parametrize("side", [-1, 0, 1])
def test_public_coordinate_and_sign_stay_on_the_same_boundary_side(index, side):
    cusp = index * 30.0
    longitude = (
        cusp if side == 0 else math.nextafter(cusp, math.inf if side > 0 else -math.inf)
    )
    expected_sign = SIGNS[(index - (side < 0)) % 12]
    point = _build_planet_record("Sun", longitude, 0, 0, "whole_sign")
    predictive = longitude_to_point_dict("Sun", longitude)
    assert point["sign"] == predictive["sign"] == expected_sign
    assert 0 <= point["longitude"] < 360
    assert 0 <= point["degree_in_sign"] < 30
    assert 0 <= predictive["degree"] < 30
    assert (
        point["longitude"] == predictive["longitude"] == predictive["absolute_degree"]
    )
    assert point["degree_in_sign"] == point["longitude"] % 30


def test_term_lord_is_not_changed_by_rounding_before_classification():
    point = _build_planet_record("Jupiter", 5.99999999, 0, 0, "whole_sign")
    conditions = build_planet_classical(
        planet="Jupiter",
        sign=point["sign"],
        degree_in_sign=point["degree_in_sign"],
        longitude=point["longitude"],
        house=point["house"],
        sun_longitude=90,
        chart_sect="day",
    )
    assert conditions["essential"]["bound_lord"] == "Jupiter"


@pytest.mark.parametrize(
    "offset,included",
    [
        (math.nextafter(8.0, 0), True),
        (8.0, True),
        (math.nextafter(8.0, math.inf), False),
    ],
)
def test_modern_aspect_acceptance_uses_unrounded_longitudes(offset, included):
    # The existing named policy gives Mercury/Saturn conjunction an 8° limit.
    planets = [
        _build_planet_record("Mercury", 0, 0, 0, "whole_sign"),
        _build_planet_record("Saturn", offset, 0, 0, "whole_sign"),
    ]
    aspects = _build_aspects(planets, include_evidence=True)
    assert bool(aspects) is included
    if included:
        assert aspects[0]["orb"] == offset
        assert aspects[0]["orb_limit"] == 8.0
        assert aspects[0]["rule_id"] == "fatebridge_modern_dynamic_orbs_v1"


def test_exported_sign_degrees_are_not_absolute_longitudes_or_30_degrees():
    houses = _build_houses(75.1234567, "equal")
    assert houses[0]["cusp_longitude"] == 75.1234567
    assert "第1宫：双子 15.12°" in _build_house_lines(houses)
    assert "双子 75.12°" not in _build_house_lines(houses)
    text = _build_angle_lines(
        {
            "ascendant": {"longitude": 75.1234567, "sign_zh": "双子"},
            "midheaven": {"longitude": 359.9999999, "sign_zh": "双鱼"},
        }
    )
    assert "Asc：双子 15.12°" in text
    assert "双鱼 29.99…°" in text and "30.00°" not in text
    assert "30.00°" not in _build_planet_lines(
        [_build_planet_record("Sun", 29.9999999, 0, 0, "whole_sign")]
    )


def test_parallel_count_leaders_remain_tied_in_reading_and_advice():
    elements = {"Fire": 2, "Air": 2, "Earth": 1}
    modalities = {"Fixed": 2, "Cardinal": 2, "Mutable": 1}
    text = _build_dominant_energy(elements, modalities)
    assert "风、火元素数量并列最多（各2颗）" in text
    assert "基本、固定模式数量并列最多（各2颗）" in text
    assert "偏强" not in text
    assert text == _build_dominant_energy(
        dict(reversed(elements.items())), dict(reversed(modalities.items()))
    )
    assert text in _build_development_advice([], elements, modalities)


def test_both_nodes_are_excluded_from_counted_house_and_sign_emphasis():
    planets = [
        {"id": "Sun", "house": 1, "sign": "Aries"},
        {"id": "Moon", "house": 2, "sign": "Taurus"},
        {"id": "North Node", "house": 3, "sign": "Gemini"},
        {"id": "South Node", "house": 3, "sign": "Gemini"},
    ]
    assert _house_focus(planets) == [(1, 1), (2, 1)]
    assert _sign_focus(planets) == [("Aries", 1), ("Taurus", 1)]
    assert "第3宫(2)" not in _build_life_focus(planets)


@pytest.mark.parametrize("mc_sign", SIGNS)
def test_mc_symbolism_tracks_mc_and_does_not_borrow_ascendant(mc_sign):
    ascendant = {"sign": "Aries", "sign_zh": "白羊"}
    text = _build_social_style(
        [], {"ascendant": ascendant, "midheaven": {"sign": mc_sign, "sign_zh": mc_sign}}
    )
    first, second = text.split("MC落在", 1)
    assert SIGN_INTERPRETATION["Aries"]["persona"] in first
    assert SIGN_INTERPRETATION[mc_sign]["core"] in second
    assert "这类气质" not in second


def test_orb_is_reported_as_geometric_proximity_not_strength():
    text = _build_aspect_pattern(
        [
            {"planet_a": "Sun", "planet_b": "Moon", "aspect": "square", "orb": 4.0},
            {"planet_a": "Venus", "planet_b": "Mars", "aspect": "trine", "orb": 0.1},
        ]
    )
    assert "最强" not in text
    assert "偏离精确角度最小的主相位是金星与火星的拱相" in text
    assert "各1条" in text


@pytest.mark.parametrize("row", PRIMARY["signs"])
def test_robbins_sign_familiarities_against_manual_primary_text_annotation(row):
    for other in SIGNS:
        relation = sign_relationship(row["sign"], other)
        reverse = sign_relationship(other, row["sign"])
        is_command_pair = other == row["command_obey_partner"]
        assert bool(relation["commanding_sign"]) is is_command_pair
        if is_command_pair:
            assert relation["commanding_sign"] == (
                row["sign"] if row["hemisphere"] == "summer" else other
            )
        assert relation["beholding_equal_power"] is (other == row["beholding_partner"])
        assert relation["disjunct"] == reverse["disjunct"]
        assert relation["sign_aspect"] == reverse["sign_aspect"]
        assert not (
            relation["disjunct"]
            and (
                relation["commanding_sign"]
                or relation["beholding_equal_power"]
                or relation["sign_aspect"]
            )
        )


@pytest.mark.parametrize("case", PRIMARY["aspect_cases"])
def test_robbins_four_sign_aspects_and_their_qualities(case):
    relation = sign_relationship(case["a"], case["b"])
    assert relation["sign_aspect"] == case["aspect"]
    assert relation["aspect_quality"] == case["quality"]


@pytest.mark.parametrize("case", PRIMARY["disjunct_cases"])
def test_robbins_i16_does_not_discard_other_familiarities(case):
    assert sign_relationship(case["a"], case["b"])["disjunct"] is case["expected"]


def test_original_sign_relation_and_modern_degree_aspect_are_distinct():
    positions = {"Sun": 29.9, "Moon": 60.1}
    layer = build_ptolemy_layer(positions, "day", tropical=True)
    assert layer["sign_relationships"][0]["sign_aspect"] == "sextile"
    assert (
        _build_aspects(
            [
                _build_planet_record(name, longitude, 0, 0, "whole_sign")
                for name, longitude in positions.items()
            ]
        )
        == []
    )


def test_every_generated_reading_has_resolvable_dependencies_and_correct_policy():
    result = calculate_core_chart_analysis(
        **BIRTH, chart_variant="hellen_chart", node_mode="both"
    )
    assert "error" not in result
    for key in result["interpretation"]:
        if key == "evidence_scope":
            continue
        assert key in result["interpretation_evidence"]
        for path in result["interpretation_evidence"][key]["source_paths"]:
            value = result
            for token in path.split("."):
                value = value[int(token)] if isinstance(value, list) else value[token]
            assert value is not None
    assert (
        result["interpretation_evidence"]["original_text_relations"]["policy_id"]
        == "ptolemy_robbins_sign_relations_v1"
    )
    assert (
        result["interpretation_evidence"]["core_identity"]["policy_id"]
        == "modern_symbolic_templates_v2"
    )
    assert "日盘" in result["interpretation"]["variant_note"]
    assert "day盘" not in result["interpretation"]["variant_note"]


def test_changing_mc_changes_its_reading_without_changing_sun_or_moon_readings():
    result = calculate_core_chart_analysis(**BIRTH, chart_variant="chart")
    altered = copy.deepcopy(result)
    altered["angles"]["midheaven"] = {
        "longitude": 130.0,
        "sign": "Leo",
        "sign_zh": "狮子",
    }
    before = _augment_core_chart_reading(result, "chart")["interpretation"]
    after = _augment_core_chart_reading(altered, "chart")["interpretation"]
    assert before["social_style"] != after["social_style"]
    assert before["core_identity"] == after["core_identity"]
    assert before["emotional_style"] == after["emotional_style"]


def test_lot_reduction_preserves_tiny_positive_and_negative_boundary_sides():
    from fatebridge.core.classical_western import compute_lot, lot_dispositor
    from fatebridge.core.ptolemy import fortune_longitude

    assert (
        compute_lot(["asc", "moon", "sun"], {"asc": 1e-14, "moon": 0, "sun": 0})
        == 1e-14
    )
    negative = fortune_longitude(0, 1e-14, 0)
    assert 330 < negative < 360
    assert lot_dispositor(negative) == "Jupiter"


@pytest.mark.parametrize(
    "model,payload",
    [
        ("ChartPlanet", {"longitude": 360.0}),
        ("ChartPlanet", {"degree_in_sign": 30.0}),
        ("ChartAngle", {"longitude": -0.001}),
        ("ChartHouse", {"cusp_longitude": 360.0}),
        ("ChartAspect", {"orb": -0.001}),
    ],
)
def test_output_contract_rejects_impossible_coordinate_facts(model, payload):
    from pydantic import ValidationError

    from fatebridge.core import output_charts

    with pytest.raises(ValidationError):
        getattr(output_charts, model).model_validate(payload)
