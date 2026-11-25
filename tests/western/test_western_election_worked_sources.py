"""Named source facts, separate from full chart or election judgement."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.core.classical_western import combustion_state, essential_dignities
from tests.support.transports import SPECS, business

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


@pytest.mark.parametrize(
    "case_id,utc_clock",
    [("w2003-body-EST", (18, 14, 0)), ("w2003-image-EDT", (17, 14, 50))],
)
def test_election_clock_hypotheses_are_distinct_on_all_surfaces(
    case_id: str, utc_clock: tuple[int, int, int], surface_calls
) -> None:
    case = next(item for item in REFERENCE["cases"] if item["id"] == case_id)
    assert case["source_clock_or_calendar_resolved"] is False
    response, protocol, code, cli = surface_calls(
        SPECS["astro_election"],
        case["input"],
        projection={
            "fields": ["analysis_context.candidate_datetime", "clock_conversion"],
            "strict_fields": True,
            "include_snapshot_text": False,
        },
        rest_as_of=case["as_of"],
    )
    assert response.status_code == 200, response.text
    assert not protocol.is_error and code == 0
    result = response.json()
    assert business(result) == business(protocol.structured_content) == business(cli)
    candidate = datetime.fromisoformat(result["clock_conversion"]["converted_utc"])
    assert candidate == datetime(2003, 4, 14, *utc_clock, tzinfo=timezone.utc)
