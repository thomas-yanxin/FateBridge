"""I.7 textual assignments and the unknown chart sect are separate facts."""

import json
from itertools import product
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.astrodice import PLANETS, build_symbolic_evidence
from fatebridge.core.local_techniques.otherbu import build_otherbu_result
from fatebridge.core.output_astrodice import PlanetSectCondition

REFERENCE = json.loads(
    (
        Path(__file__).parent / "data/astrodice/tables/planet-sect-robbins-1940.json"
    ).read_text()
)
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


@pytest.mark.parametrize("planet", PLANETS)
def test_planet_assignment_agrees_with_separately_annotated_robbins_i7(planet):
    result = build_otherbu_result(planet=planet, sign="Aries", house=0)
    condition = result["symbolic_details"]["planet_sect_condition"]
    expected = (
        "day"
        if planet in REFERENCE["natural_day_planets"]
        else "night" if planet in REFERENCE["natural_night_planets"] else None
    )
    assert condition["natural_sect"] == expected
    if planet == REFERENCE["conditional_planet"]:
        assert (
            condition["assignments_by_solar_phase"]
            == REFERENCE["conditional_assignments"]
        )
        assert condition["status"] == "conditional_on_solar_phase_not_in_roll"
    elif planet in REFERENCE["outside_seven_planet_scope"]:
        assert condition["status"] == "outside_seven_planet_scope"
        assert condition["assignments_by_solar_phase"] is None
    else:
        assert condition["status"] == "natural_assignment_without_chart_sect"
        assert condition["assignments_by_solar_phase"] is None
    for key in ("solar_phase", "applied_chart_sect", "matches_chart_sect"):
        assert condition[key] is None
    trace = next(
        t for t in result["rule_trace"] if t["rule_id"] == "natural_planet_sect"
    )
    assert trace["result"] == condition
    assert trace["inputs"] == {"planet": planet}
    source = next(r for r in result["rulesets"] if r["id"] == condition["ruleset_id"])
    assert source["source_url"] == REFERENCE["source_url"]
    assert source["version"].endswith("1940, I.7")
    meaning = result["interpretation"]["planet_sect_meaning"]
    assert meaning in result["snapshot_text"]
    if expected is not None:
        assert ("分派为昼曜" if expected == "day" else "分派为夜曜") in meaning
        assert ("分派为夜曜" if expected == "day" else "分派为昼曜") not in meaning
    elif planet == "Mercury":
        assert "晨星时属昼曜" in meaning and "昏星时属夜曜" in meaning
        assert "未选定水星的分派" in meaning
    else:
        assert "不在" in meaning and "未定义不等于逆派或失势" in meaning


def test_all_1728_rolls_cannot_infer_sect_from_sign_or_house_number():
    for planet in PLANETS:
        baseline = build_symbolic_evidence(planet, "Aries", 0)
        for sign, house in product(SIGNS, range(12)):
            result = build_symbolic_evidence(planet, sign, house)
            assert (
                result["symbolic_details"]["planet_sect_condition"]
                == baseline["symbolic_details"]["planet_sect_condition"]
            )
            assert (
                result["interpretation"]["planet_sect_meaning"]
                == baseline["interpretation"]["planet_sect_meaning"]
            )
            assert result["symbolic_details"]["triplicity_condition"]["sect"] is None


@pytest.mark.parametrize(
    "planet,sign,natural,triangle_night_role",
    [
        ("Jupiter", "Aries", "day", "primary"),
        ("Sun", "Leo", "day", "assigned_not_selected"),
        ("Mars", "Cancer", "night", "primary"),
        ("Saturn", "Gemini", "day", "assigned_not_selected"),
        ("Mercury", "Libra", None, "primary"),
    ],
)
def test_i7_natural_assignment_does_not_replace_i18_conditional_governance(
    planet, sign, natural, triangle_night_role
):
    details = build_symbolic_evidence(planet, sign, 0)["symbolic_details"]
    assert details["planet_sect_condition"]["natural_sect"] == natural
    assert (
        details["triplicity_condition"]["roles_by_sect"]["night"] == triangle_night_role
    )
    assert details["triplicity_condition"]["sect"] is None


@pytest.mark.parametrize("planet", ["Mercury", "Saturn", "Mars", "NorthNode"])
@pytest.mark.parametrize("time,zodiacal", list(product(["00:30", "12:30"], [0, 1])))
def test_actual_sky_day_night_and_zodiac_never_supply_the_roll_conditions(
    planet, time, zodiacal
):
    faces = {"planet": planet, "sign": "Aries", "house": 0}
    plain = build_otherbu_result(**faces)
    sky = build_otherbu_result(
        **faces,
        date="2024-03-20",
        time=time,
        zone="UTC",
        lat=0.0,
        lon=0.0,
        zodiacal=zodiacal,
    )
    assert sky["chart"] is not None
    for key in (
        "symbolic_details",
        "interpretation",
        "rule_trace",
        "rulesets",
        "diceChart",
    ):
        assert sky[key] == plain[key]


@pytest.mark.parametrize(
    "planet,phrase",
    [("Saturn", "白昼的温暖调和土星的冷性"), ("Mars", "夜间的湿润调和火星的干性")],
)
def test_destructive_stars_follow_i7_moderation_not_like_quality_assignment(
    planet, phrase
):
    result = build_symbolic_evidence(planet, "Aries", 0)
    assert phrase in result["interpretation"]["planet_sect_meaning"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("applied_chart_sect", "day"),
        ("solar_phase", "morning_star"),
        ("matches_chart_sect", True),
        ("natural_sect", "neutral"),
    ],
)
def test_contract_rejects_an_invented_observed_condition(field, value):
    with pytest.raises(ValidationError):
        PlanetSectCondition.model_validate({field: value})
