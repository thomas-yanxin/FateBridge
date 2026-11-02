"""Phase 1 tests for the western classical layer.

No closed byte-oracle (horosa computes this in its backend), so correctness is
pinned by (1) parity with the authoritative reference tables horosa ships in
`data/dignities.js`, and (2) classical invariants / ground truths.
"""

from __future__ import annotations

from fatebridge.core.classical_western import (
    CHALDEAN_FACES,
    DIGNITY_SCORE,
    DOROTHEAN_TRIPLICITY,
    bound_lord,
    combustion_state,
    essential_dignities,
    face_lord,
    triplicity_members,
)
from fatebridge.services.astrology import calculate_core_chart_analysis

_SIGNS = [
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

# horosa data/dignities.js FACES (lowercase) — table-parity reference.
_HOROSA_FACES = {
    "aries": ["mars", "sun", "venus"],
    "taurus": ["mercury", "moon", "saturn"],
    "gemini": ["jupiter", "mars", "sun"],
    "cancer": ["venus", "mercury", "moon"],
    "leo": ["saturn", "jupiter", "mars"],
    "virgo": ["sun", "venus", "mercury"],
    "libra": ["moon", "saturn", "jupiter"],
    "scorpio": ["mars", "sun", "venus"],
    "sagittarius": ["mercury", "moon", "saturn"],
    "capricorn": ["jupiter", "mars", "sun"],
    "aquarius": ["venus", "mercury", "moon"],
    "pisces": ["saturn", "jupiter", "mars"],
}
# horosa TRIPLICITY (element → day/night/participating).
_HOROSA_TRIPLICITY = {
    "fire": {"day": "sun", "night": "jupiter", "participating": "saturn"},
    "earth": {"day": "venus", "night": "moon", "participating": "mars"},
    "air": {"day": "saturn", "night": "mercury", "participating": "jupiter"},
    "water": {"day": "venus", "night": "mars", "participating": "moon"},
}
# horosa DIGNITY_SCORE.
_HOROSA_SCORE = {
    "domicile": 5,
    "exaltation": 4,
    "triplicity": 3,
    "term": 2,
    "face": 1,
    "detriment": -5,
    "fall": -4,
}


def test_faces_table_parity_with_horosa():
    for sign in _SIGNS:
        assert [p.lower() for p in CHALDEAN_FACES[sign]] == _HOROSA_FACES[sign.lower()]


def test_triplicity_table_parity_with_horosa():
    for element, rulers in DOROTHEAN_TRIPLICITY.items():
        ref = _HOROSA_TRIPLICITY[element.lower()]
        for role in ("day", "night", "participating"):
            assert rulers[role].lower() == ref[role]


def test_dignity_score_parity_with_horosa():
    # FB names: rulership↔domicile, bound↔term; values must match Lilly/horosa.
    assert DIGNITY_SCORE["rulership"] == _HOROSA_SCORE["domicile"]
    assert DIGNITY_SCORE["bound"] == _HOROSA_SCORE["term"]
    for key in ("exaltation", "triplicity", "face", "detriment", "fall"):
        assert DIGNITY_SCORE[key] == _HOROSA_SCORE[key]


# Canonical Egyptian terms (Ptolemy Tetrabiblos I.20 "Egyptians" / Valens), as
# cumulative end-degrees per sign. The whole table must match this — locks the
# Aries & Leo correction (they previously carried Ptolemaic-variant values).
_CANONICAL_EGYPTIAN_TERMS = {
    "Aries": [
        ("Jupiter", 6),
        ("Venus", 12),
        ("Mercury", 20),
        ("Mars", 25),
        ("Saturn", 30),
    ],
    "Taurus": [
        ("Venus", 8),
        ("Mercury", 14),
        ("Jupiter", 22),
        ("Saturn", 27),
        ("Mars", 30),
    ],
    "Gemini": [
        ("Mercury", 6),
        ("Jupiter", 12),
        ("Venus", 17),
        ("Mars", 24),
        ("Saturn", 30),
    ],
    "Cancer": [
        ("Mars", 7),
        ("Venus", 13),
        ("Mercury", 19),
        ("Jupiter", 26),
        ("Saturn", 30),
    ],
    "Leo": [
        ("Jupiter", 6),
        ("Venus", 11),
        ("Saturn", 18),
        ("Mercury", 24),
        ("Mars", 30),
    ],
    "Virgo": [
        ("Mercury", 7),
        ("Venus", 17),
        ("Jupiter", 21),
        ("Mars", 28),
        ("Saturn", 30),
    ],
    "Libra": [
        ("Saturn", 6),
        ("Mercury", 14),
        ("Jupiter", 21),
        ("Venus", 28),
        ("Mars", 30),
    ],
    "Scorpio": [
        ("Mars", 7),
        ("Venus", 11),
        ("Mercury", 19),
        ("Jupiter", 24),
        ("Saturn", 30),
    ],
    "Sagittarius": [
        ("Jupiter", 12),
        ("Venus", 17),
        ("Mercury", 21),
        ("Saturn", 26),
        ("Mars", 30),
    ],
    "Capricorn": [
        ("Mercury", 7),
        ("Jupiter", 14),
        ("Venus", 22),
        ("Saturn", 26),
        ("Mars", 30),
    ],
    "Aquarius": [
        ("Mercury", 7),
        ("Venus", 13),
        ("Jupiter", 20),
        ("Mars", 25),
        ("Saturn", 30),
    ],
    "Pisces": [
        ("Venus", 12),
        ("Jupiter", 16),
        ("Mercury", 19),
        ("Mars", 28),
        ("Saturn", 30),
    ],
}


def test_bound_lord_matches_canonical_egyptian_terms_all_signs():
    """Every degree's term lord == the canonical Egyptian table (whole-table lock)."""
    for sign, table in _CANONICAL_EGYPTIAN_TERMS.items():

        def expected(deg: float) -> str:
            for planet, end in table:
                if deg < end:
                    return planet
            return table[-1][0]

        for tenth in range(300):  # 0.0–29.9 in 0.1° steps
            degree = tenth / 10.0
            assert bound_lord(sign, degree) == expected(degree), (sign, degree)


def test_every_degree_has_exactly_one_bound_and_face_lord():
    for sign in _SIGNS:
        for degree in range(30):
            assert bound_lord(sign, float(degree) + 0.5) is not None
            assert face_lord(sign, float(degree) + 0.5) is not None
    # face boundaries: 0–10 / 10–20 / 20–30.
    assert face_lord("Aries", 0.0) == "Mars"
    assert face_lord("Aries", 9.99) == "Mars"
    assert face_lord("Aries", 10.0) == "Sun"
    assert face_lord("Aries", 25.0) == "Venus"


def test_classical_dignity_ground_truths():
    # Sun rules Leo; exalts in Aries; falls in Libra.
    assert "rulership" in essential_dignities("Sun", "Leo", 15.0, True)["dignities"]
    assert "exaltation" in essential_dignities("Sun", "Aries", 15.0, True)["dignities"]
    assert "fall" in essential_dignities("Sun", "Libra", 15.0, True)["debilities"]
    # Mars rules Aries → detriment in Libra.
    assert "detriment" in essential_dignities("Mars", "Libra", 5.0, True)["debilities"]
    # Sect triplicity: Fire day ruler = Sun; at night it's Jupiter.
    assert (
        essential_dignities("Sun", "Sagittarius", 5.0, True)["triplicity_ruler"]
        == "Sun"
    )
    assert (
        essential_dignities("Jupiter", "Sagittarius", 5.0, False)["triplicity_ruler"]
        == "Jupiter"
    )
    # Lilly score: domicile +5 alone (Saturn in Aquarius, late degree to avoid bound/face overlap checks aside).
    saturn_aqua = essential_dignities("Saturn", "Aquarius", 5.0, True)
    assert "rulership" in saturn_aqua["dignities"]
    assert saturn_aqua["score"] >= 5


def test_non_traditional_bodies_have_no_essential_dignity():
    for body in ("Uranus", "Neptune", "Pluto", "North Node", "Chiron"):
        assert essential_dignities(body, "Leo", 1.0, True) is None


def test_combustion_thresholds_match_chartfacts():
    assert combustion_state(100.1, 100.0) == "cazimi"  # ≤17′
    assert combustion_state(105.0, 100.0) == "combust"  # <8.5°
    assert combustion_state(112.0, 100.0) == "under_beams"  # <17°
    assert combustion_state(130.0, 100.0) is None
    assert combustion_state(100.0, None) is None


def test_under_beams_uses_lilly_p113_seventeen_degrees():
    # Printed Lilly 1647 p.113 says the planet clears the beams at 17°.
    # The pair-aspect ray allowance is a distinct quantity.
    assert combustion_state(114.0, 100.0) == "under_beams"  # 14° — under beams
    assert combustion_state(116.0, 100.0) == "under_beams"  # 16° — within printed 17°
    assert combustion_state(117.0, 100.0) is None


def test_triplicity_members_unordered_set_of_three():
    members = triplicity_members("Aries")  # Fire
    assert set(members) == {"Sun", "Jupiter", "Saturn"}


def test_chart_exposes_classical_layer():
    result = calculate_core_chart_analysis(
        name="测试",
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
    assert classical["sect"] in {"day", "night"}
    assert set(classical["planets"]) >= {"Sun", "Moon", "Mars", "Saturn"}
    # Traditional planets carry essential dignity; outers do not.
    assert classical["planets"]["Sun"]["essential"] is not None
    if "Pluto" in classical["planets"]:
        assert classical["planets"]["Pluto"]["essential"] is None
    assert "[古典]" in result["snapshot_text"]
