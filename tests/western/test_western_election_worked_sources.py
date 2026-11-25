"""Named source facts, separate from full chart or election judgement."""

import json
from pathlib import Path

import pytest

from fatebridge.core.classical_western import combustion_state, essential_dignities

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/western-election-worked-sources.json"
    ).read_text()
)
JANUARY = next(c for c in REFERENCE["charts"] if c["id"] == "warnock_2001_01")
SIGNS = (
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
)


@pytest.mark.parametrize("planet", list(JANUARY["essential_score_in_graphic"]))
def test_published_day_chart_major_and_minor_dignity_scores(planet) -> None:
    sign, degree, minute = JANUARY["points"][planet]
    actual = essential_dignities(planet, sign, degree + minute / 60, True)
    assert actual is not None
    assert actual["score"] == JANUARY["essential_score_in_graphic"][planet]
    if planet in JANUARY["peregrine_in_graphic"]:
        assert actual["peregrine"] is True
    else:
        pass


def test_published_cazimi_keeps_the_simultaneous_major_debilities() -> None:
    source = next(c for c in REFERENCE["charts"] if c["id"] == "gillman_figure5")
    sign, degree, minute = source["points"]["Mercury"]
    essential = essential_dignities("Mercury", sign, degree + minute / 60, True)
    assert essential is not None
    assert set(essential["debilities"]) == set(source["major_debilities"]["Mercury"])
    mercury = SIGNS.index(sign) * 30 + degree + minute / 60
    sun_sign, sun_degree, sun_minute = source["points"]["Sun"]
    sun = SIGNS.index(sun_sign) * 30 + sun_degree + sun_minute / 60
    assert combustion_state(mercury, sun) == source["solar_conditions"]["Mercury"]
