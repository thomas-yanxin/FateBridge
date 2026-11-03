"""Second-pass counterexamples: joys, self-dispositors, cusp rounding and lots."""

import json
from itertools import product
from pathlib import Path

import pytest

from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.astrodice import build_symbolic_evidence, normalize_sign
from fatebridge.core.local_techniques.chart import (
    _adapt_chart_objects,
    _build_birth_info,
    _build_house_ring,
    _build_local_chart_response,
)

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/astrodice-house-reference.json").read_text()
)


@pytest.mark.parametrize(
    "planet,house", tuple(product(REFERENCE["joy_houses"], range(12)))
)
def test_house_joy_against_lilly_transcription(planet, house):
    result = build_symbolic_evidence(planet, "Virgo", house)
    condition = result["symbolic_details"]["house_condition"]
    assert condition["joy_house_number"] == REFERENCE["joy_houses"][planet]
    assert condition["in_joy"] is (house + 1 == REFERENCE["joy_houses"][planet])
    assert "planetary_house_joy" in result["interpretation"]["basis"]
    assert any(
        r["author"] == "William Lilly" and r["source_url"] == REFERENCE["source"]
        for r in result["rulesets"]
    )


@pytest.mark.parametrize(
    "planet", ["Uranus", "Neptune", "Pluto", "NorthNode", "SouthNode"]
)
def test_unsupported_joy_is_unknown_not_false(planet):
    result = build_symbolic_evidence(planet, "Virgo", 0)
    assert result["symbolic_details"]["house_condition"]["in_joy"] is None
    assert result["symbolic_details"]["house_condition"]["joy_house_number"] is None


@pytest.mark.parametrize(
    "planet,sign",
    [
        ("Sun", "Leo"),
        ("Moon", "Cancer"),
        ("Mercury", "Gemini"),
        ("Mercury", "Virgo"),
        ("Venus", "Taurus"),
        ("Venus", "Libra"),
        ("Mars", "Aries"),
        ("Mars", "Scorpio"),
        ("Jupiter", "Sagittarius"),
        ("Jupiter", "Pisces"),
        ("Saturn", "Capricorn"),
        ("Saturn", "Aquarius"),
    ],
)
def test_known_self_dispositor_is_never_described_as_missing(planet, sign):
    result = build_symbolic_evidence(planet, sign, 0)
    assert (
        result["symbolic_details"]["sign_condition"]["dispositor_status"]
        == "self_symbolic"
    )
    assert "自定位" in result["interpretation"]["dispositor_meaning"]
    assert "未给出" not in result["interpretation"]["dispositor_meaning"]


def test_unknown_other_dispositor_is_not_filled_from_sky_or_ring():
    result = build_symbolic_evidence("Mercury", "Aries", 0)
    assert result["symbolic_details"]["sign_condition"]["domicile_ruler"] == "Mars"
    assert (
        result["symbolic_details"]["sign_condition"]["dispositor_status"]
        == "not_in_roll"
    )
    assert "未给出" in result["interpretation"]["dispositor_meaning"]


@pytest.mark.parametrize("glyph", ["♈\ufe0e", "♈\ufe0f", "♈"])
def test_text_and_emoji_presentation_do_not_change_the_sign(glyph):
    assert normalize_sign(glyph) == "Aries"


@pytest.mark.parametrize(
    "hsys,zodiacal,time", tuple(product([0, 3, 5, 8], [0, 1], ["06:30:00", "00:30:00"]))
)
def test_optional_sky_preserves_canonical_fortune_and_house_assignments(
    hsys, zodiacal, time
):
    inputs = dict(
        date_text="2024-03-20", time_text=time, timezone_name="UTC", lat="51.5", lon="0"
    )
    birth, _, _ = _build_birth_info(**inputs)
    core = build_core_chart_payload(birth, "chart", hsys=hsys, zodiacal=zodiacal)
    local = _build_local_chart_response(
        **inputs,
        hsys=hsys,
        zodiacal=zodiacal,
        allow_extended_hsys=True,
        include_su28=False,
        preserve_context_geometry=True,
    )
    points = {p["id"]: p for p in local["chart"]["objects"]}
    assert (
        points["Pars Fortuna"]["lon"]
        == core["classical"]["lots"]["fortune"]["longitude"]
    )
    assert all(
        points[p["id"]]["house"] == f"House{p['house']}" for p in core["planets"]
    )
    if time == "06:30:00" and hsys == 0 and zodiacal == 0:
        assert core["classical"]["sect"] == "day"
        assert points["Sun"]["house"] == "House1"
        asc = core["angles"]["ascendant"]["longitude"]
        expected = (asc + points["Moon"]["lon"] - points["Sun"]["lon"]) % 360
        assert points["Pars Fortuna"]["lon"] == pytest.approx(expected, abs=1e-12)
        assert core["houses"][0]["cusp_longitude"] != asc


def test_preformatted_cusp_values_do_not_reassign_a_core_house():
    # Core had a body at 29.99996 in H1; formatting both it and the cusp to
    # four decimals displays 30.0, and must not reclassify it into H2.
    source = {
        "planets": [
            {
                "id": "Mercury",
                "longitude": 30.0,
                "sign": "Aries",
                "degree_in_sign": 30.0,
                "house": 1,
            }
        ]
    }
    points = _adapt_chart_objects(
        source,
        tradition=False,
        include_su28=False,
        houses=_build_house_ring(0),
        preserve_core_houses=True,
    )
    assert points[0]["house"] == "House1"
    assert not any(p["id"] == "Pars Fortuna" for p in points)
