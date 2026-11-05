"""Phase 5b tests: ninth-part (九分部 / navamsa) sign.

Pure degree-geometry twin of the dodekatemorion: each sign's nine 3°20′ parts
open on the cardinal sign of the placement's triplicity (the dominant Parashari
convention, = the Hellenistic ninth-part's triplicity reset). No degree-ruler
doctrine, no interpretation — just the division sign.
"""

from __future__ import annotations

import pytest

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.classical_western import ninth_part
from fatebridge.core.ephemeris_runtime import swe
from fatebridge.services.astrology import calculate_core_chart_analysis

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


def test_each_triplicity_opens_on_its_cardinal_sign():
    # 0° of any sign → the cardinal sign of its element.
    assert ninth_part("Aries", 0.0) == "Aries"  # fire
    assert ninth_part("Leo", 0.0) == "Aries"
    assert ninth_part("Taurus", 0.0) == "Capricorn"  # earth
    assert ninth_part("Gemini", 0.0) == "Libra"  # air
    assert ninth_part("Cancer", 0.0) == "Cancer"  # water


def test_parts_advance_one_sign_every_three_and_a_third_degrees():
    # Aries: part boundaries at 0, 3°20′, 6°40′ … advance Aries→Taurus→Gemini…
    assert ninth_part("Aries", 3.0) == "Aries"
    assert ninth_part("Aries", 3.4) == "Taurus"
    assert ninth_part("Aries", 13.34) == "Leo"  # 5th part
    assert ninth_part("Aries", 29.9) == "Sagittarius"  # 9th part


def test_non_zodiacal_sign_is_none():
    assert ninth_part("Ophiuchus", 5.0) is None


@pytest.mark.skipif(swe is None, reason="swisseph 不可用")
def test_chart_planets_carry_ninth_part():
    info = build_astro_birth_info(use_true_solar_time=True, **_NATAL)
    planets = build_core_chart_payload(info, "hellen_chart")["classical"]["planets"]
    # Sun at ~18.3° Sagittarius (fire → start Aries, 5th part) → Virgo.
    assert planets["Sun"]["ninth_part"] == "Virgo"
    for entry in planets.values():
        assert "ninth_part" in entry


def test_snapshot_renders_ninth_part_line():
    payload = calculate_core_chart_analysis(
        chart_variant="hellen_chart", use_true_solar_time=True, **_NATAL
    )
    assert "九分部：" in payload["snapshot_text"]
