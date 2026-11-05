"""
Tests for the western *event* techniques (世俗入宫盘 / 多重回归).

Unlike the lifespan tools, these solve real astronomical moments, so the
assertions pin against externally-known facts: the 2026 cardinal ingress dates,
and that each returning body lands back on (≈) its natal longitude bracketing the
reference date.
"""

from datetime import datetime, timezone

from fatebridge.core.astrology_events import (
    RETURN_BODIES,
    find_cardinal_ingress_utc,
    find_planet_returns,
    planet_longitude_at_utc,
)
from fatebridge.services.western_events import (
    calculate_extrareturns,
    calculate_mundane,
)

BIRTH = dict(
    name="测试者",
    birth_year=1990,
    birth_month=4,
    birth_day=6,
    birth_hour=9,
    birth_minute=33,
    birth_timezone="Asia/Shanghai",
    birth_longitude=121.47,
    birth_latitude=31.23,
)


def test_cardinal_ingress_dates_match_known_2026_values():
    # Externally known UTC dates for 2026 (Sun reaching 0/90/180/270°).
    expected = {"春分": (3, 20), "夏至": (6, 21), "秋分": (9, 23), "冬至": (12, 21)}
    for term, (month, day) in expected.items():
        moment = find_cardinal_ingress_utc(2026, term)
        assert moment.tzinfo is not None
        assert (moment.month, moment.day) == (month, day), term


def test_find_planet_returns_brackets_reference_and_hits_natal_longitude():
    # Saturn's natal longitude in 1990, returns around 2025.
    natal_utc = datetime(1990, 4, 6, 1, 33, tzinfo=timezone.utc)
    natal_lon = planet_longitude_at_utc(6, natal_utc)
    reference = datetime(2025, 1, 1, tzinfo=timezone.utc)
    moments = find_planet_returns(
        6, natal_lon, period_days=10759.22, reference_utc=reference, past=1, future=1
    )
    assert moments, "expected at least one Saturn return"
    # Every solved moment must put Saturn back on its natal longitude.
    for moment in moments:
        assert abs(planet_longitude_at_utc(6, moment) - natal_lon) < 0.01


def test_node_return_resolves_despite_retrograde_motion():
    # The mean node moves retrograde; the crossing finder must still bracket it.
    natal_utc = datetime(1990, 4, 6, 1, 33, tzinfo=timezone.utc)
    node_lon = planet_longitude_at_utc(10, natal_utc)
    reference = datetime(2025, 1, 1, tzinfo=timezone.utc)
    moments = find_planet_returns(
        10,
        node_lon,
        period_days=RETURN_BODIES["North Node"]["period_days"],
        reference_utc=reference,
        past=1,
        future=1,
    )
    assert moments, "node return must resolve under retrograde motion"
    for moment in moments:
        assert abs(planet_longitude_at_utc(10, moment) - node_lon) < 0.05


def test_mundane_casts_ingress_chart():
    result = calculate_mundane(
        year=2026,
        ingress_term="春分",
        longitude=116.40,
        latitude=39.90,
        timezone_name="Asia/Shanghai",
    )
    assert "error" not in result, result
    payload = result["mundane"]
    assert payload["ingress_datetime_utc"].startswith("2026-03-20")
    assert payload["ascendant"]["sign"]
    assert result["snapshot_text"]


def test_extrareturns_reports_recent_and_next_for_each_body():
    result = calculate_extrareturns(
        **BIRTH, analysis_year=2025, analysis_month=1, analysis_day=1
    )
    assert "error" not in result, result
    returns = result["extrareturns"]["returns"]
    bodies = {item["body"] for item in returns}
    assert bodies == {"Saturn", "Jupiter", "North Node"}
    for item in returns:
        assert item["most_recent_return"] is not None, item["body"]
        assert item["next_return"] is not None, item["body"]
        # most-recent precedes next.
        assert (
            item["most_recent_return"]["datetime_utc"]
            < item["next_return"]["datetime_utc"]
        )


def test_cardinal_ingress_cast_is_on_the_entered_side_of_each_sign_boundary():
    expected = {
        "春分": (0.0, "Aries"),
        "夏至": (90.0, "Cancer"),
        "秋分": (180.0, "Libra"),
        "冬至": (270.0, "Capricorn"),
    }
    for term, (target, sign) in expected.items():
        result = calculate_mundane(
            year=2026,
            ingress_term=term,
            longitude=116.4,
            latitude=39.9,
            timezone_name="Asia/Shanghai",
        )
        assert "error" not in result
        sun = result["mundane"]["points"]["sun"]
        assert sun["sign"] == sign
        assert 0 <= (sun["longitude"] - target) % 360 < 1e-6
        assert 0 <= sun["absolute_degree"] < 360
        assert 0 <= sun["degree"] < 30
        assert (
            result["mundane"]["calculation_basis"]["julian_day_tt"]
            > result["mundane"]["calculation_basis"]["julian_day_ut1"]
        )
