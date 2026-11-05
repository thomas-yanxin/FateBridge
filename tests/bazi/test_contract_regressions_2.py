"""Related contract regressions with shared imports; original cases retained."""

from __future__ import annotations

from fatebridge.core.classical_western import (
    EXALT_RULER_BY_SIGN,
    SIGN_BODY_PARTS,
    almuten_of,
    build_dispositor_layer,
    build_temperament,
    dignity_lords_at,
    dispositor_chain,
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


def test_exalt_ruler_reverse_map():
    # Aries=Sun, Taurus=Moon, Cancer=Jupiter, Libra=Saturn, Capricorn=Mars, Pisces=Venus.
    assert EXALT_RULER_BY_SIGN["Aries"] == "Sun"
    assert EXALT_RULER_BY_SIGN["Capricorn"] == "Mars"
    assert EXALT_RULER_BY_SIGN["Pisces"] == "Venus"
    # Signs without a 7-planet exaltation are absent.
    assert "Leo" not in EXALT_RULER_BY_SIGN
    assert "Aquarius" not in EXALT_RULER_BY_SIGN


def test_dignity_lords_at_aries_day():
    lords = dignity_lords_at("Aries", 5.0, True)
    assert lords["domicile"] == "Mars"
    assert lords["exaltation"] == "Sun"
    assert lords["triplicity"] == "Sun"  # Fire, day
    assert lords["term"] == "Jupiter"  # Egyptian bound 0–6 Aries = Jupiter
    assert lords["face"] == "Mars"  # 0–10 Aries = Mars


def test_almuten_of_degree_ground_truth():
    # 5° Aries by day: Sun = exalt(4)+trip(3) = 7; Mars = domicile(5)+face(1) = 6;
    # Jupiter = term(2). Sun wins.
    result = almuten_of("Aries", 5.0, True)
    assert result["totals"]["Sun"] == 7
    assert result["totals"]["Mars"] == 6
    assert result["totals"]["Jupiter"] == 2
    assert result["winner"] == "Sun"


def test_almuten_weights_match_horosa_dig_w():
    # horosa lifespanEngine.js DIG_W = {domicile:5, exaltation:4, triplicity:3, term:2, face:1}.
    # 15° Cancer (day): Moon domicile-only 5; Jupiter exalt-only 4; Venus triplicity-only 3
    # (term 13–19 = Mercury, face 10–20 = Mercury, so Venus holds nothing else).
    res = almuten_of("Cancer", 15.0, True)
    assert res["totals"]["Moon"] == 5
    assert res["totals"]["Jupiter"] == 4
    assert res["totals"]["Venus"] == 3


def test_dispositor_final_in_own_domicile():
    chain = dispositor_chain("Mars", {"Mars": "Aries"})  # Mars rules Aries
    assert chain["terminal"] == "Mars"
    assert chain["terminal_type"] == "domicile"
    assert chain["chain"] == ["Mars"]


def test_dispositor_mutual_reception_loop():
    # Mars in Taurus (ruled by Venus), Venus in Aries (ruled by Mars) → mutual reception.
    chain = dispositor_chain("Mars", {"Mars": "Taurus", "Venus": "Aries"})
    assert chain["terminal_type"] == "mutual_reception"
    assert chain["chain"] == ["Mars", "Venus", "Mars"]


def test_build_dispositor_layer_finds_final_dispositors():
    # Jupiter in Sagittarius (own domicile) is a final dispositor; Mars in Sag → Jupiter.
    layer = build_dispositor_layer({"Jupiter": "Sagittarius", "Mars": "Sagittarius"})
    assert layer["final_dispositors"] == ["Jupiter"]
    assert layer["chains"]["Mars"]["terminal"] == "Jupiter"
    assert layer["chains"]["Mars"]["terminal_type"] == "domicile"


def test_chart_exposes_dispositors_and_topic_almutens():
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
    classical = result["classical"]
    assert "dispositors" in classical and "topic_almutens" in classical
    assert set(classical["dispositors"]["chains"]) >= {"Sun", "Moon", "Saturn"}
    # All 12 houses get a topic almuten winner.
    assert len(classical["topic_almutens"]) == 12
    for house in classical["topic_almutens"].values():
        assert house["winner"] in {
            "Sun",
            "Moon",
            "Mercury",
            "Venus",
            "Mars",
            "Jupiter",
            "Saturn",
        }
    assert "[主宰]" in result["snapshot_text"]
    assert "[宫主星]" in result["snapshot_text"]
