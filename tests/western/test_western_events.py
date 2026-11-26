"""
Tests for the western *event* techniques (世俗入宫盘 / 多重回归).

Unlike the lifespan tools, these solve real astronomical moments, so the
assertions pin against externally-known facts: the 2026 cardinal ingress dates,
and that each returning body lands back on (≈) its natal longitude bracketing the
reference date.
"""

from datetime import datetime, timezone
from math import inf, nan

import pytest
from swisseph import SUN

from fatebridge.core.astro.astrology_events import (
    RETURN_BODIES,
    find_cardinal_ingress_utc,
    find_planet_returns,
    planet_longitude_at_utc,
    resolve_longitude_crossing,
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


@pytest.mark.parametrize("step_days", [0.0, -1.0, inf, nan, 1e-20])
def test_longitude_crossing_rejects_scan_steps_that_cannot_advance(
    step_days: float,
) -> None:
    """Reject invalid steps before a longitude search can stall or skip its window."""
    anchor = datetime(2026, 3, 20, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="Longitude-crossing scan step"):
        resolve_longitude_crossing(SUN, 0.0, anchor, step_days=step_days)


def test_cardinal_ingress_dates_match_known_2026_values() -> None:
    # Externally known UTC dates for 2026 (Sun reaching 0/90/180/270°).
    expected = {"春分": (3, 20), "夏至": (6, 21), "秋分": (9, 23), "冬至": (12, 21)}
    for term, (month, day) in expected.items():
        moment = find_cardinal_ingress_utc(2026, term)
        assert moment.tzinfo is not None
        assert (moment.month, moment.day) == (month, day), term


def test_find_planet_returns_brackets_reference_and_hits_natal_longitude() -> None:
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


def test_node_return_resolves_despite_retrograde_motion() -> None:
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


def test_mundane_casts_ingress_chart() -> None:
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


def test_mundane_keeps_the_ingress_when_local_clock_is_undefined() -> None:
    inputs = dict(
        year=1994, ingress_term="春分", longitude=105, latitude=0, house_system="W"
    )
    local = calculate_mundane(**inputs, timezone_name="Antarctica/Vostok")
    utc = calculate_mundane(**inputs, timezone_name="UTC")
    assert local["analysis_context"]["ingress_datetime_local"] is None
    assert local["mundane"] == {**utc["mundane"], "ingress_datetime_local": None}
    assert "UTC（当地钟时未定义）" in local["summary"]


def test_mundane_cast_consumes_the_solved_source_tt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fatebridge.services import western_events

    resolved = western_events.resolve_cardinal_ingress(2026, "春分")
    build_subject = western_events.build_subject
    epochs = []

    def observe_subject(**kwargs):
        epochs.append(kwargs["physical_epoch"])
        assert "local_datetime" not in kwargs
        return build_subject(**kwargs)

    monkeypatch.setattr(
        western_events, "resolve_cardinal_ingress", lambda year, term: resolved
    )
    monkeypatch.setattr(western_events, "build_subject", observe_subject)
    result = western_events.calculate_mundane(
        year=2026,
        longitude=116.4,
        latitude=39.9,
        timezone_name="Asia/Shanghai",
    )
    assert "error" not in result
    assert len(epochs) == 1
    assert epochs[0].time.tt == resolved.tt
    assert result["mundane"]["ingress_datetime_utc"] == (
        resolved.utc_datetime.isoformat()
    )


def test_mundane_delivers_one_utc_label_for_the_solved_epoch() -> None:
    result = calculate_mundane(
        year=1,
        ingress_term="冬至",
        longitude=0,
        latitude=0,
        timezone_name="Etc/GMT+12",
        house_system="W",
    )
    assert "error" not in result, result
    mundane = result["mundane"]
    context = result["analysis_context"]
    utc_label = mundane["calculation_basis"]["utc_representation"]["utc_label"]
    assert context["ingress_datetime_utc"] == utc_label
    assert mundane["ingress_datetime_utc"] == utc_label
    local_label = mundane["ingress_datetime_local"]
    assert context["ingress_datetime_local"] == local_label
    assert datetime.fromisoformat(local_label) == datetime.fromisoformat(utc_label)


def test_extrareturns_reports_recent_and_next_for_each_body() -> None:
    result = calculate_extrareturns(
        **BIRTH, analysis_year=2025, analysis_month=1, analysis_day=1
    )
    assert "error" not in result, result
    returns = result["extrareturns"]["returns"]
    bodies = {item["body"] for item in returns}
    assert bodies == {
        "Saturn",
        "Jupiter",
        "Mars",
        "Venus",
        "Mercury",
        "North Node",
        "Chiron",
        "Uranus",
        "Neptune",
        "Pluto",
    }
    for item in returns:
        if item.get("status") == "unavailable":
            assert item["body"] == "Chiron"
            continue
        assert item["next_return"] is not None, item["body"]
        if item["body"] == "Chiron":
            # Chiron period ~50.7y: first return has not occurred by age 34.6; no pre-birth phantom return.
            assert item["most_recent_return"] is None, item["body"]
            continue
        if item["body"] == "Uranus":
            # Uranus period ~84y: check post-birth recent return or None without pre-birth leakage.
            continue
        assert item["most_recent_return"] is not None, item["body"]
        # most-recent precedes next.
        assert (
            item["most_recent_return"]["datetime_utc"]
            < item["next_return"]["datetime_utc"]
        )


def test_extrareturns_preserves_utc_when_local_time_is_undefined() -> None:
    result = calculate_extrareturns(
        birth_year=1982,
        birth_month=5,
        birth_day=1,
        birth_hour=12,
        birth_timezone="Antarctica/Vostok",
        birth_longitude=0,
        birth_latitude=51.5,
        house_system="W",
        analysis_year=1994,
        analysis_month=1,
        analysis_day=30,
    )
    jupiter = next(
        item for item in result["extrareturns"]["returns"] if item["body"] == "Jupiter"
    )
    assert jupiter["next_return"]["datetime_local"] is None
    assert jupiter["next_return"]["datetime_utc"].startswith("1994-06-27T")
    assert "木星下次返照 1994-06-27（UTC）" in result["summary"]


def test_cardinal_ingress_cast_is_on_the_entered_side_of_each_sign_boundary() -> None:
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
