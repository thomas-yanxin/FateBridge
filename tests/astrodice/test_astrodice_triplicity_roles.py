"""I.18 overall assignments and conditional roles are different facts."""

import json
from pathlib import Path

import pytest

from fatebridge.core.astrodice import PLANETS, build_symbolic_evidence
from fatebridge.core.local_techniques.otherbu import build_otherbu_result
from fatebridge.core.ptolemy import triplicity_assigned_rulers, triplicity_rulers

REFERENCE = json.loads(
    (
        Path(__file__).parents[1]
        / "data/astrodice/tables/triangle-assignment-robbins-1940.json"
    ).read_text()
)
CASES = [
    (row, sign, planet)
    for row in REFERENCE["triangles"]
    for sign in row["signs"]
    for planet in PLANETS
]


@pytest.mark.parametrize("row,sign,planet", CASES)
def test_assignment_and_conditional_roles_against_manually_annotated_passage(
    row, sign, planet
):
    result = build_symbolic_evidence(planet, sign, 0)
    relation = result["symbolic_details"]["triplicity_condition"]
    supported = planet in REFERENCE["seven_planets"]
    assert relation["assigned_rulers"] == row["assigned_rulers"]
    assert triplicity_assigned_rulers(sign) == row["assigned_rulers"]
    assert relation["in_assigned_group"] is (
        planet in row["assigned_rulers"] if supported else None
    )
    assert relation["sect"] is None
    assert relation["match_definition"] == (
        "selected_primary_or_explicit_co_ruler_under_named_sect"
    )
    for sect in ["day", "night"]:
        expected = row[sect]
        assert relation["rulers_by_sect"][sect] == expected
        assert triplicity_rulers(sign, sect) == expected
        if not supported:
            role = "outside_seven_planet_scope"
            matched = None
        elif planet == expected["primary"]:
            role, matched = "primary", True
        elif planet == expected["co_ruler"]:
            role, matched = "co_ruler", True
        elif planet in row["assigned_rulers"]:
            role, matched = "assigned_not_selected", False
        else:
            role, matched = "not_assigned", False
        assert relation["roles_by_sect"][sect] == role
        assert relation["matches_by_sect"][sect] is matched
    trace = next(
        t for t in result["rule_trace"] if t["rule_id"] == "conditional_triplicity"
    )
    assert trace["result"] == relation
    assert trace["ruleset_id"] == relation["ruleset_id"]
    assert "不属于该组" not in result["interpretation"]["triplicity_meaning"]


@pytest.mark.parametrize(
    "planet,sign,sect",
    [
        ("Jupiter", "Aries", "day"),
        ("Sun", "Leo", "night"),
        ("Moon", "Virgo", "day"),
        ("Venus", "Taurus", "night"),
        ("Saturn", "Libra", "night"),
        ("Mercury", "Gemini", "day"),
        ("Venus", "Cancer", "night"),
        ("Moon", "Pisces", "day"),
    ],
)
def test_an_assigned_planet_is_not_described_as_absent_from_the_triangle(
    planet, sign, sect
):
    result = build_otherbu_result(planet=planet, sign=sign, house=0)
    relation = result["symbolic_details"]["triplicity_condition"]
    assert relation["in_assigned_group"] is True
    assert relation["matches_by_sect"][sect] is False
    assert relation["roles_by_sect"][sect] == "assigned_not_selected"
    meaning = result["interpretation"]["triplicity_meaning"]
    assert "本骰星属总体分派，未列为该条件的首要或明确共管主星" in meaning
    assert "不属于该组" not in meaning
    assert meaning in result["snapshot_text"]
    assert "附加天象也不替骰面选定条件" in meaning


def test_fire_mars_is_explicitly_excluded_while_water_mars_remains_primary():
    fire = build_symbolic_evidence("Mars", "Aries", 0)
    water = build_symbolic_evidence("Mars", "Cancer", 0)
    assert "domicile" in fire["symbolic_details"]["sign_condition"]["conditions"]
    assert (
        fire["symbolic_details"]["triplicity_condition"]["in_assigned_group"] is False
    )
    assert fire["symbolic_details"]["triplicity_condition"]["roles_by_sect"] == {
        "day": "not_assigned",
        "night": "not_assigned",
    }
    assert water["symbolic_details"]["triplicity_condition"]["roles_by_sect"] == {
        "day": "primary",
        "night": "primary",
    }
    assert (
        "本骰星不在本章该三角的总体分派内"
        in fire["interpretation"]["triplicity_meaning"]
    )


def test_general_assignment_returned_list_does_not_mutate_the_reference():
    assigned = triplicity_assigned_rulers("Aries")
    assigned.append("Saturn")
    assert triplicity_assigned_rulers("Aries") == ["Sun", "Jupiter"]


@pytest.mark.parametrize(
    "planet", ["Uranus", "Neptune", "Pluto", "NorthNode", "SouthNode"]
)
def test_unsupported_body_keeps_unknown_membership_and_conditional_matches(planet):
    relation = build_symbolic_evidence(planet, "Aries", 0)["symbolic_details"][
        "triplicity_condition"
    ]
    assert relation["assigned_rulers"] == ["Sun", "Jupiter"]
    assert relation["in_assigned_group"] is None
    assert relation["matches_by_sect"] == {"day": None, "night": None}
    assert set(relation["roles_by_sect"].values()) == {"outside_seven_planet_scope"}
