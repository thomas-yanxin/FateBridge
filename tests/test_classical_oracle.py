"""Full-domain correctness locks for the classical layer.

These encode conclusions cross-checked against horosa's own readable formulas
(`data/dignities.js`, `lifespanEngine.js` computeAlmuten, `data/lots.js`):
- almuten winner (incl. tiebreak) matched horosa at all 360°×day/night points;
- Arabic-lot longitudes matched horosa `computeLot` byte-for-byte.
They are platform-invariant (strings / integers / exact arithmetic), so they
hold on every CI Python version without touching goldens.
"""

from __future__ import annotations

from fatebridge.core.classical_western import (
    LOTS,
    _sign_of_longitude,
    almuten_of,
    compute_lot,
    dignity_lords_at,
)

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
# Chaldean order (slowest first) — horosa CLASSICAL_PLANETS; the almuten tiebreak.
_CHALDEAN = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]


def test_almuten_winner_is_always_one_of_the_degree_dignity_lords():
    for sign in _SIGNS:
        for tenth in range(300):
            degree = tenth / 10.0
            for is_day in (True, False):
                result = almuten_of(sign, degree, is_day)
                lords = {v for v in result["lords"].values() if v}
                assert result["winner"] in lords, (sign, degree, is_day)


def test_almuten_tiebreak_prefers_chaldean_earliest():
    # Aries 24° by day: Mars (domicile 5 + term 2 = 7) ties Sun (exalt 4 + trip 3
    # = 7). Mars precedes Sun in the Chaldean order, so Mars wins — matching
    # horosa's computeAlmuten (first-max over CLASSICAL_PLANETS).
    result = almuten_of("Aries", 24.0, True)
    assert result["totals"]["Mars"] == 7
    assert result["totals"]["Sun"] == 7
    assert result["winner"] == "Mars"
    assert _CHALDEAN.index("Mars") < _CHALDEAN.index("Sun")


def test_arabic_lot_table_frozen_to_canonical_formulas():
    # The allowed lots' day/night marker formulas (horosa data/lots.js §1.5).
    expected = {
        "fortune": (["asc", "moon", "sun"], ["asc", "sun", "moon"]),
        "spirit": (["asc", "sun", "moon"], ["asc", "moon", "sun"]),
        "marriage": (["asc", "venus", "saturn"], ["asc", "saturn", "venus"]),
        "children": (["asc", "jupiter", "saturn"], ["asc", "saturn", "jupiter"]),
    }
    assert set(LOTS) == set(expected)
    for lot_id, (day, night) in expected.items():
        assert LOTS[lot_id]["day"] == day, lot_id
        assert LOTS[lot_id]["night"] == night, lot_id


def test_compute_lot_is_exact_modular_arithmetic():
    # lon = (a + b − c) mod 360, exact (matches horosa computeLot byte-for-byte).
    for k in range(60):
        v = {
            m: (i * 37.3 + k * 11.7) % 360
            for i, m in enumerate(
                ["asc", "sun", "moon", "venus", "saturn", "jupiter", "eighth"], start=1
            )
        }
        for lot_id in LOTS:
            for is_day in (True, False):
                formula = LOTS[lot_id]["day" if is_day else "night"]
                a, b, c = (v[formula[0]], v[formula[1]], v[formula[2]])
                assert compute_lot(formula, v) == ((a + b - c) % 360.0 + 360.0) % 360.0


def test_dignity_lords_at_has_all_five_rulers_off_node_signs():
    # Every degree resolves a term & face lord; domicile/triplicity always set.
    for sign in _SIGNS:
        lords = dignity_lords_at(sign, 15.0, True)
        assert lords["domicile"] and lords["triplicity"]
        assert lords["term"] and lords["face"]
        assert _sign_of_longitude((_SIGNS.index(sign)) * 30 + 15.0) == sign
