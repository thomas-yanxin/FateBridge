"""Traditional correspondence tests: dodekatemoria (12分度) + melothesia (身体部位) + temperament (气质).

Pure degree-table / qualities-tally derivations (no ephemeris). Body-part and
quality tables are ported verbatim from horosa data/signs.js + data/planets.js.
"""

from __future__ import annotations

from fatebridge.core.classical_western import (
    SIGN_BODY_PARTS,
    build_temperament,
    dodekatemorion,
    melothesia,
)
from fatebridge.services.astrology import calculate_core_chart_analysis


def test_dodekatemorion_advances_by_2p5_degree_steps():
    # 0° of a sign → the sign itself; each 2.5° advances one sign zodiacally.
    assert dodekatemorion("Aries", 0.0) == "Aries"
    assert dodekatemorion("Aries", 2.4) == "Aries"
    assert dodekatemorion("Aries", 2.5) == "Taurus"
    assert dodekatemorion("Aries", 27.5) == "Pisces"  # 11 steps
    # Hand check: Sagittarius 18.32° → step 7 → Cancer.
    assert dodekatemorion("Sagittarius", 18.32) == "Cancer"


def test_melothesia_body_parts_and_position_band():
    mel = melothesia("Aries", 5.0)
    assert mel["body_parts"] == ["头", "脸", "眼", "鼻", "耳"]
    assert mel["position"] == "上方"
    assert melothesia("Aries", 15.0)["position"] == "中间"
    assert melothesia("Aries", 25.0)["position"] == "下方"
    assert len(SIGN_BODY_PARTS) == 12


def test_temperament_humor_quadrants():
    # All-fire significators → hot + dry → choleric.
    choleric = build_temperament("Aries", "Mars", "Leo", "Sagittarius")
    assert (choleric["thermal"], choleric["hygral"]) == ("hot", "dry")
    assert choleric["humor"] == "choleric"
    # All-water → cold + moist → phlegmatic.
    phleg = build_temperament("Cancer", "Moon", "Scorpio", "Pisces")
    assert phleg["humor"] == "phlegmatic"


def test_chart_exposes_traditional_correspondences():
    result = calculate_core_chart_analysis(
        name="左右",
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
    classical = result["classical"]
    assert classical["temperament"]["humor"] in {
        "sanguine",
        "choleric",
        "melancholic",
        "phlegmatic",
    }
    sun = classical["planets"]["Sun"]
    assert sun["dodekatemorion"] is not None
    assert "body_parts" in sun["melothesia"] and "position" in sun["melothesia"]
    assert "[体质]" in result["snapshot_text"]
