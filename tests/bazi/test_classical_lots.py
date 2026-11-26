"""Classical lots tests: Arabic lots (parts).

Lot formulas are ported verbatim from horosa data/lots.js; checked by the
day/night reversal invariant, a hand-computable position, and consistency
between the classical and Hellenistic views.
"""

from __future__ import annotations

import math

import pytest

from fatebridge.core.classical_western import (
    LOTS,
    build_almuten_figuris,
    build_lots_layer,
    compute_lot,
)
from fatebridge.services.astrology import calculate_core_chart_analysis

_BIRTH = dict(
    name="t",
    birth_year=2000,
    birth_month=12,
    birth_day=10,
    birth_hour=9,
    birth_minute=55,
    birth_timezone="Asia/Shanghai",
    birth_longitude=120.45,
    birth_latitude=32.54,
)


def test_compute_lot_formula_and_wrap() -> None:
    # Fortune day = asc + moon − sun.
    lons = {"asc": 100.0, "moon": 50.0, "sun": 30.0}
    assert compute_lot(["asc", "moon", "sun"], lons) == 120.0
    # Wraps into [0, 360).
    assert (
        compute_lot(["asc", "moon", "sun"], {"asc": 350.0, "moon": 50.0, "sun": 30.0})
        == 10.0
    )
    # Missing marker → None.
    assert compute_lot(["asc", "venus", "saturn"], {"asc": 1.0, "venus": 2.0}) is None


def test_fortune_spirit_day_night_reversal() -> None:
    # Spirit is the day/night mirror of Fortune: by day Spirit = asc+sun−moon,
    # Fortune = asc+moon−sun; swapping is_day swaps the two.
    lons = {"asc": 100.0, "sun": 30.0, "moon": 50.0}
    day = build_lots_layer(lons, True)
    night = build_lots_layer(lons, False)
    assert day["fortune"]["longitude"] == night["spirit"]["longitude"]
    assert day["spirit"]["longitude"] == night["fortune"]["longitude"]


def test_lot_dispositor_is_domicile_ruler() -> None:
    # A lot at 15° Cancer is disposited by the Moon (Cancer's domicile ruler).
    layer = build_lots_layer({"asc": 105.0, "moon": 0.0, "sun": 0.0}, True)
    assert layer["fortune"]["longitude"] == 105.0
    assert layer["fortune"]["dispositor"] == "Moon"


@pytest.mark.parametrize(
    "cut,is_day,left_winner,exact_winner,left_tally,exact_tally",
    [
        (
            20.0,
            True,
            "Sun",
            "Mars",
            {"Mars": 5, "Mercury": 2, "Sun": 8},
            {"Mars": 7, "Sun": 7, "Venus": 1},
        ),
        (
            38.0,
            False,
            "Venus",
            "Moon",
            {"Mercury": 1, "Moon": 7, "Venus": 7},
            {"Mercury": 3, "Moon": 7, "Venus": 5},
        ),
    ],
)
def test_fortune_degree_classification_precedes_longitude_rounding(
    cut: float,
    is_day: bool,
    left_winner: str,
    exact_winner: str,
    left_tally,
    exact_tally,
) -> None:
    exact = {"asc": cut, "moon": 1.0, "sun": 1.0}
    decreasing_body = "moon" if is_day else "sun"
    left = dict(exact, **{decreasing_body: math.nextafter(1.0, 0.0)})
    for markers, winner, tally in (
        (left, left_winner, left_tally),
        (exact, exact_winner, exact_tally),
    ):
        fortune = build_lots_layer(markers, is_day)["fortune"]
        assert fortune["longitude"] == cut
        assert fortune["almuten"] == winner
        point = build_almuten_figuris({"fortune": fortune}, is_day)["points"]["fortune"]
        assert point["winner"] == winner
        assert point["totals"] == tally


def test_all_allowed_lots_present_with_required_markers() -> None:
    assert set(LOTS) == {"fortune", "spirit", "marriage", "children"}
    lons = {
        "asc": 100.0,
        "sun": 30.0,
        "moon": 50.0,
        "venus": 200.0,
        "saturn": 250.0,
        "jupiter": 300.0,
        "eighth": 220.0,
    }
    layer = build_lots_layer(lons, True)
    assert set(layer) == set(LOTS)
    for lot in layer.values():
        assert 0 <= lot["longitude"] < 360
        assert lot["dispositor"] in {
            "Sun",
            "Moon",
            "Mercury",
            "Venus",
            "Mars",
            "Jupiter",
            "Saturn",
        }


def test_chart_lots_match_existing_fortune_lot() -> None:
    result = calculate_core_chart_analysis(chart_variant="hellen_chart", **_BIRTH)
    hel = result["hellenistic"]["lot_of_fortune"]
    classical = result["classical"]["lots"]["fortune"]
    for field in ("longitude", "sign", "degree_in_sign"):
        assert hel[field] == classical[field]


def test_chart_exposes_lots_layer() -> None:
    result = calculate_core_chart_analysis(chart_variant="chart", **_BIRTH)
    lots = result["classical"]["lots"]
    assert set(lots) == {"fortune", "spirit", "marriage", "children"}
    assert lots["fortune"]["dispositor"] is not None
    assert "[阿拉伯点]" in result["snapshot_text"]
