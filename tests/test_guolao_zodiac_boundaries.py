"""Selected-zodiac palace edges must keep both representable sides."""

import math
from fractions import Fraction

import pytest

from fatebridge.core import guolao
from tests.test_guolao_depth import chart


@pytest.mark.parametrize("ayanamsha", [0.0, 1.0, 23.6, 24.0, 100.0, 350.0])
def test_rotation_never_rounds_previous_palace_into_next(monkeypatch, ayanamsha):
    # Isolate the zodiac transform; these are synthetic boundary inputs, not
    # externally measured planets or a substitute for historical mansion data.
    monkeypatch.setattr(guolao, "mansion_at", lambda *a: {"degree_lord": "木"})
    for index in range(12):
        edge = (30 * index + ayanamsha) % 360
        for raw in [
            math.nextafter(edge, -math.inf),
            edge,
            math.nextafter(edge, math.inf),
        ]:
            exact = (Fraction(raw) - Fraction(ayanamsha)) % 360
            expected = int(exact // 30)
            body = guolao.body_placement(
                "Sun", {"longitude": raw, "right_ascension": 0.0}, [], ayanamsha
            )
            assert body["palace_branch"] == guolao.PALACE_BRANCHES[expected]
            assert 30 * expected <= body["zodiac_longitude"] < 30 * (expected + 1)


def test_previous_spring_zero_remainder_is_last_palace_not_index_error(monkeypatch):
    monkeypatch.setattr(guolao, "mansion_at", lambda *a: {"degree_lord": "木"})
    raw = math.nextafter(24.0, -math.inf)
    assert (raw - 24.0) % 360 == 360.0  # Reproduces the old crash.
    body = guolao.body_placement(
        "Sun", {"longitude": raw, "right_ascension": 0.0}, [], 24.0
    )
    assert body["palace_branch"] == "亥"
    assert body["zodiac_longitude"] == math.nextafter(360.0, 0.0)


@pytest.mark.parametrize(
    "longitude,branch,sign",
    [
        (math.nextafter(24.0, -math.inf), "亥", "Pisces"),
        (113.6, "申", "Gemini"),
    ],
)
def test_natal_planet_record_reuses_exact_guolao_selected_placement(
    monkeypatch, longitude, branch, sign
):
    original = guolao.positions

    def controlled(*args, **kwargs):
        raw = original(*args, **kwargs)
        raw["ayanamsha"] = 24.0 if branch == "亥" else 23.6
        raw["states"]["Sun"]["longitude"] = longitude
        return raw

    monkeypatch.setattr(guolao, "positions", controlled)
    result = chart(zodiacal=1)
    body = next(b for b in result["guolao"]["bodies"] if b["id"] == "Sun")
    planet = next(p for p in result["planets"] if p["id"] == "Sun")
    assert body["palace_branch"] == branch
    assert planet["sign"] == sign
    assert planet["longitude"] == body["zodiac_longitude"]
