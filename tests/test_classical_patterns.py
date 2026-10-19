"""Classical relations, light transfer/collection and nodal configurations."""

from __future__ import annotations

import pytest

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.classical_western import (
    NODE_BENDING_ORB,
    _aspect_is_applying,
    build_classical_patterns,
    overcomes,
    whole_sign_aspect,
)
from fatebridge.core.ephemeris_runtime import swe
from fatebridge.services.astrology import (
    _build_classical_patterns_lines,
    calculate_core_chart_analysis,
)


def test_whole_sign_aspect_and_aversion():
    assert whole_sign_aspect("Aries", "Aries") == "conjunction"
    assert whole_sign_aspect("Aries", "Gemini") == "sextile"
    assert whole_sign_aspect("Aries", "Cancer") == "square"
    assert whole_sign_aspect("Aries", "Leo") == "trine"
    assert whole_sign_aspect("Aries", "Libra") == "opposition"
    # Aversion: 2nd/12th (Taurus/Pisces) and 6th/8th (Virgo/Scorpio) from Aries.
    assert whole_sign_aspect("Aries", "Taurus") is None
    assert whole_sign_aspect("Aries", "Scorpio") is None


def test_overcoming_is_tenth_sign_superior_square():
    # Capricorn is the 10th sign from Aries → Capricorn overcomes Aries.
    assert overcomes("Capricorn", "Aries") is True
    assert overcomes("Aries", "Capricorn") is False  # directional


def _pos(pid, sign, lon):
    return {"id": pid, "sign": sign, "longitude": lon}


def test_besiegement_by_malefics_and_enclosure_by_benefics():
    # Mercury at 10° flanked by Mars (5°) and Saturn (15°) → besieged by malefics.
    positions = [
        _pos("Mars", "Aries", 5.0),
        _pos("Mercury", "Aries", 10.0),
        _pos("Saturn", "Aries", 15.0),
        _pos("Sun", "Aries", 25.0),
        _pos("Moon", "Aries", 28.0),
        _pos("Venus", "Aries", 1.0),
        _pos("Jupiter", "Aries", 2.0),
    ]
    patterns = build_classical_patterns(positions, [], "day")
    assert patterns["besiegement"].get("Mercury") == "besieged_by_malefics"


def test_besiegement_requires_malefics_within_orb():
    # Mercury's nearest neighbours are both malefic but ~50° away on each side.
    # Enclosure by body requires the flanking bodies within ~15°, so this is
    # NOT besiegement.
    positions = [
        _pos("Venus", "Aries", 1.0),
        _pos("Jupiter", "Aries", 2.0),
        _pos("Mars", "Cancer", 100.0),
        _pos("Mercury", "Virgo", 150.0),
        _pos("Saturn", "Libra", 200.0),
        _pos("Sun", "Capricorn", 250.0),
        _pos("Moon", "Capricorn", 280.0),
    ]
    patterns = build_classical_patterns(positions, [], "day")
    assert patterns["besiegement"].get("Mercury") is None


def test_bonification_and_maltreatment_from_aspects():
    positions = [
        _pos(p, "Aries", float(i))
        for i, p in enumerate(
            ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
        )
    ]
    aspects = [
        {"planet_a": "Jupiter", "planet_b": "Moon", "aspect": "trine"},
        {"planet_a": "Saturn", "planet_b": "Moon", "aspect": "square"},
    ]
    patterns = build_classical_patterns(positions, aspects, "day")
    assert patterns["bonification"]["Moon"]["bonified_by"] == ["Jupiter"]
    assert patterns["bonification"]["Moon"]["maltreated_by"] == ["Saturn"]


def test_sect_benefic_malefic_by_sect():
    day = build_classical_patterns([], [], "day")
    night = build_classical_patterns([], [], "night")
    assert (day["sect_benefic"], day["sect_malefic"]) == ("Jupiter", "Saturn")
    assert (night["sect_benefic"], night["sect_malefic"]) == ("Venus", "Mars")


def test_chart_exposes_classical_patterns():
    result = calculate_core_chart_analysis(
        name="t",
        birth_year=2000,
        birth_month=12,
        birth_day=10,
        birth_hour=9,
        birth_minute=55,
        birth_timezone="Asia/Shanghai",
        birth_longitude=120.45,
        birth_latitude=32.54,
        chart_variant="chart",
    )
    cp = result["classical_patterns"]
    assert cp["sect_benefic"] in {"Jupiter", "Venus"}
    assert "aversions" in cp and "overcoming" in cp and "besiegement" in cp
    assert "[古典格局]" in result["snapshot_text"]


_NATAL = dict(
    birth_year=2000,
    birth_month=12,
    birth_day=10,
    birth_hour=9,
    birth_minute=55,
    birth_timezone="Asia/Shanghai",
    birth_longitude=120.4667,
    birth_latitude=32.5417,
    name="左右",
    birth_place="海安",
)


def test_applying_when_gap_to_exact_shrinks():
    # Moon at 11° approaching a trine (120°) to Jupiter at 132° → applying.
    assert _aspect_is_applying(11.0, 13.0, 132.0, 0.08, 120.0) is True
    # Moon at 11° just past a conjunction with Saturn at 10° → separating.
    assert _aspect_is_applying(11.0, 13.0, 10.0, 0.03, 0.0) is False


def test_applying_unknown_without_speed():
    assert _aspect_is_applying(10.0, None, 50.0, 1.0, 0.0) is None


def test_translation_of_light_fires():
    planets = [
        {"id": "Moon", "sign": "Aries", "longitude": 11.0},
        {"id": "Saturn", "sign": "Aries", "longitude": 10.0},
        {"id": "Jupiter", "sign": "Leo", "longitude": 132.0},
    ]
    aspects = [
        {"planet_a": "Moon", "planet_b": "Saturn", "aspect": "conjunction"},
        {"planet_a": "Moon", "planet_b": "Jupiter", "aspect": "trine"},
    ]
    speeds = {"Moon": 13.0, "Saturn": 0.03, "Jupiter": 0.08}
    result = build_classical_patterns(planets, aspects, "day", speeds=speeds)
    assert result["translation_of_light"] == [
        {"translator": "Moon", "from": "Saturn", "to": "Jupiter"}
    ]


def test_translation_requires_the_endpoints_to_be_in_aversion():
    # If Saturn and Jupiter DO aspect each other, no light needs carrying.
    planets = [
        {"id": "Moon", "sign": "Aries", "longitude": 11.0},
        {"id": "Saturn", "sign": "Aries", "longitude": 10.0},
        {"id": "Jupiter", "sign": "Leo", "longitude": 132.0},
    ]
    aspects = [
        {"planet_a": "Moon", "planet_b": "Saturn", "aspect": "conjunction"},
        {"planet_a": "Moon", "planet_b": "Jupiter", "aspect": "trine"},
        {"planet_a": "Saturn", "planet_b": "Jupiter", "aspect": "trine"},
    ]
    speeds = {"Moon": 13.0, "Saturn": 0.03, "Jupiter": 0.08}
    result = build_classical_patterns(planets, aspects, "day", speeds=speeds)
    assert result["translation_of_light"] == []


def test_collection_of_light_fires():
    planets = [
        {"id": "Saturn", "sign": "Aries", "longitude": 10.0},
        {"id": "Moon", "sign": "Aries", "longitude": 8.0},
        {"id": "Mercury", "sign": "Leo", "longitude": 129.0},
    ]
    aspects = [
        {"planet_a": "Saturn", "planet_b": "Moon", "aspect": "conjunction"},
        {"planet_a": "Saturn", "planet_b": "Mercury", "aspect": "trine"},
    ]
    speeds = {"Saturn": 0.03, "Moon": 13.0, "Mercury": 1.2}
    result = build_classical_patterns(planets, aspects, "day", speeds=speeds)
    assert result["collection_of_light"] == [
        {"collector": "Saturn", "from": ["Mercury", "Moon"]}
    ]


def test_nodal_bending_north_and_south_within_orb():
    node = 100.0
    planets = [
        {"id": "Mars", "sign": "Libra", "longitude": (node + 90.0) + 1.0},  # north
        {"id": "Venus", "sign": "Aries", "longitude": (node - 90.0) - 0.5},  # south
        {"id": "Jupiter", "sign": "Leo", "longitude": node + 45.0},  # clear of bending
    ]
    result = build_classical_patterns(planets, [], "day", node_longitude=node)
    bending = {b["planet"]: b["bending"] for b in result["nodal_bending"]}
    assert bending == {"Mars": "north", "Venus": "south"}


def test_nodal_bending_excluded_beyond_orb():
    node = 100.0
    planets = [
        {"id": "Mars", "sign": "Libra", "longitude": node + 90.0 + NODE_BENDING_ORB + 1}
    ]
    result = build_classical_patterns(planets, [], "day", node_longitude=node)
    assert result["nodal_bending"] == []


def test_light_patterns_empty_without_speeds():
    planets = [
        {"id": "Moon", "sign": "Aries", "longitude": 11.0},
        {"id": "Saturn", "sign": "Aries", "longitude": 10.0},
        {"id": "Jupiter", "sign": "Leo", "longitude": 132.0},
    ]
    aspects = [
        {"planet_a": "Moon", "planet_b": "Saturn", "aspect": "conjunction"},
        {"planet_a": "Moon", "planet_b": "Jupiter", "aspect": "trine"},
    ]
    # No speeds passed → applying/separating undefined → no translation/collection.
    result = build_classical_patterns(planets, aspects, "day")
    assert result["translation_of_light"] == []
    assert result["collection_of_light"] == []


def test_nodal_bending_empty_without_node():
    planets = [{"id": "Mars", "sign": "Libra", "longitude": 190.0}]
    result = build_classical_patterns(planets, [], "day")
    assert result["nodal_bending"] == []


@pytest.mark.skipif(swe is None, reason="swisseph 不可用")
def test_chart_exposes_light_and_nodal_patterns():
    info = build_astro_birth_info(use_true_solar_time=True, **_NATAL)
    patterns = build_core_chart_payload(info, "hellen_chart")["classical_patterns"]
    for key in ("translation_of_light", "collection_of_light", "nodal_bending"):
        assert isinstance(patterns[key], list)


def test_snapshot_renders_light_and_nodal_configurations():
    payload = {
        "classical_patterns": {
            "sect_benefic": "Jupiter",
            "sect_malefic": "Saturn",
            "overcoming": [],
            "besiegement": {},
            "bonification": {},
            "translation_of_light": [
                {"translator": "Moon", "from": "Saturn", "to": "Jupiter"}
            ],
            "collection_of_light": [{"collector": "Saturn", "from": ["Mars", "Venus"]}],
            "nodal_bending": [{"planet": "Mars", "bending": "north", "orb": 1.0}],
        }
    }
    text = _build_classical_patterns_lines(payload)
    assert "光的传递：月亮 自 土星 递光至 木星" in text
    assert "光的聚集：土星 聚 火星、金星 之光" in text
    assert "交点弯曲：火星北弯" in text
