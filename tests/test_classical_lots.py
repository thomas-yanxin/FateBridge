"""Classical lots tests: Arabic lots (parts).

Lot formulas are ported verbatim from horosa data/lots.js; checked by the
day/night reversal invariant, a hand-computable position, and consistency with
FateBridge's pre-existing Lot of Fortune (`_fortune_lot`).
"""

from __future__ import annotations

from fatebridge.core.classical_western import (
    LOTS,
    build_lots_layer,
    compute_lot,
    lot_dispositor,
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


def test_compute_lot_formula_and_wrap():
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


def test_fortune_spirit_day_night_reversal():
    # Spirit is the day/night mirror of Fortune: by day Spirit = asc+sun−moon,
    # Fortune = asc+moon−sun; swapping is_day swaps the two.
    lons = {"asc": 100.0, "sun": 30.0, "moon": 50.0}
    day = build_lots_layer(lons, True)
    night = build_lots_layer(lons, False)
    assert day["fortune"]["longitude"] == night["spirit"]["longitude"]
    assert day["spirit"]["longitude"] == night["fortune"]["longitude"]


def test_lot_dispositor_is_domicile_ruler():
    # A lot at 15° Cancer is disposited by the Moon (Cancer's domicile ruler).
    assert lot_dispositor(105.0) == "Moon"  # 105° = 15° Cancer


def test_all_allowed_lots_present_with_required_markers():
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


def test_chart_lots_match_existing_fortune_lot():
    # The new classical.lots.fortune must equal the pre-existing hellenistic
    # Lot of Fortune (single source of truth — uses the EXACT ascendant).
    result = calculate_core_chart_analysis(chart_variant="hellen_chart", **_BIRTH)
    hel = result["hellenistic"]["lot_of_fortune"]["longitude"]
    classical = result["classical"]["lots"]["fortune"]["longitude"]
    assert abs(hel - classical) < 1e-3


def test_chart_exposes_lots_layer():
    result = calculate_core_chart_analysis(chart_variant="chart", **_BIRTH)
    lots = result["classical"]["lots"]
    assert set(lots) == {"fortune", "spirit", "marriage", "children"}
    assert lots["fortune"]["dispositor"] is not None
    assert "[阿拉伯点]" in result["snapshot_text"]
