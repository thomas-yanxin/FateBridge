"""Slow-body recrossings and the requested zodiac must survive return search.

Dates isolate the three observed Jupiter crossings in its 2001/02 retrograde
loop. Native Swiss coordinates independently check the solved equations; these
checks are not independent physical ephemeris accuracy certification.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from fatebridge.core import astrology_events
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.ephemeris_runtime import (
    ephemeris_call,
    preserve_ephemeris_path,
    swe,
)
from fatebridge.services.western_events import calculate_extrareturns
from tests.support.transports import SPECS, business, rest, surface_calls

BIRTH = datetime(1990, 5, 17, 7, 30, tzinfo=timezone.utc)
REFERENCE = datetime(2002, 1, 12, tzinfo=timezone.utc)


def native_longitude(body, moment, sidereal):
    with preserve_ephemeris_path():
        flags = swe.FLG_SWIEPH
        if sidereal:
            swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
            flags |= swe.FLG_SIDEREAL
        coordinates, returned = ephemeris_call(
            "calc", ephemeris_time(moment).jd_tt, body, flags
        )
    assert returned >= 0
    return coordinates[0]


@pytest.mark.parametrize("sidereal", [False, True])
def test_nearest_returns_keep_the_third_crossing_in_jupiter_retrograde_loop(sidereal):
    target = native_longitude(swe.JUPITER, BIRTH, sidereal)
    moments = astrology_events.find_planet_returns(
        swe.JUPITER,
        target,
        period_days=4332.59,
        reference_utc=REFERENCE,
        sidereal=sidereal,
    )
    assert len(moments) == 2
    past, future = moments
    assert past < REFERENCE < future
    assert (past.year, past.month) == (2002, 1)
    assert (future.year, future.month) == (2002, 4)
    # Independently verify the event equation and each crossing's direction.
    for at, direction in ((past, -1), (future, 1)):
        residual = (
            native_longitude(swe.JUPITER, at, sidereal) - target + 180
        ) % 360 - 180
        assert abs(residual) * 3600 < 0.001
        before = native_longitude(swe.JUPITER, at - timedelta(days=1), sidereal)
        after = native_longitude(swe.JUPITER, at + timedelta(days=1), sidereal)
        assert direction * ((after - before + 180) % 360 - 180) > 0


def test_return_count_selects_each_side_instead_of_period_seed_duplicates():
    target = native_longitude(swe.JUPITER, BIRTH, False)
    moments = astrology_events.find_planet_returns(
        swe.JUPITER,
        target,
        period_days=4332.59,
        reference_utc=REFERENCE,
        past=2,
        future=0,
    )
    assert [(at.year, at.month) for at in moments] == [(2001, 8), (2002, 1)]


def test_extra_returns_service_uses_native_lahiri_for_natal_and_events():
    result = calculate_extrareturns(
        birth_year=1990,
        birth_month=5,
        birth_day=17,
        birth_hour=7,
        birth_minute=30,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        analysis_year=2002,
        analysis_month=1,
        analysis_day=12,
        zodiac_type="Sidereal",
    )
    assert "error" not in result, result
    row = next(
        row for row in result["extrareturns"]["returns"] if row["body"] == "Jupiter"
    )
    target = native_longitude(swe.JUPITER, BIRTH, True)
    assert row["natal_longitude"]["absolute_degree"] == pytest.approx(target, abs=1e-10)
    at = datetime.fromisoformat(row["next_return"]["datetime_utc"])
    assert (at.year, at.month, at.day) == (2002, 4, 25)
    assert (
        abs((native_longitude(swe.JUPITER, at, True) - target + 180) % 360 - 180) < 1e-8
    )


@pytest.mark.parametrize("speed", [-1.0, 1.0])
def test_scan_keeps_an_exact_root_on_a_shared_cell_boundary(monkeypatch, speed):
    # Linear synthetic longitude provides an exact known root at JD1, for both
    # crossing directions. Its civil adapter preserves the same artificial JD.
    origin = datetime(2000, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(
        astrology_events,
        "_planet_motion",
        lambda jd, body, **kwargs: ((120 + speed * (jd - 1)) % 360, speed, 0, ()),
    )
    monkeypatch.setattr(
        astrology_events, "_jd_to_utc", lambda jd: origin + timedelta(days=jd)
    )
    monkeypatch.setattr(
        astrology_events,
        "_julian_day",
        lambda at: (at - origin).total_seconds() / 86400,
    )
    roots = astrology_events._longitude_crossings_utc(5, 120, 0, 2, 1)
    assert roots == [origin + timedelta(days=1)]


@pytest.mark.parametrize("target, expected_days", [(0, [1]), (180, [])])
def test_scan_distinguishes_a_true_zero_degree_crossing_from_the_antipodal_jump(
    monkeypatch, target, expected_days
):
    origin = datetime(2000, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(
        astrology_events,
        "_planet_motion",
        lambda jd, body, **kwargs: ((359 + jd) % 360, 1.0, 0, ()),
    )
    monkeypatch.setattr(
        astrology_events, "_jd_to_utc", lambda jd: origin + timedelta(days=jd)
    )
    monkeypatch.setattr(
        astrology_events,
        "_julian_day",
        lambda at: (at - origin).total_seconds() / 86400,
    )
    roots = astrology_events._longitude_crossings_utc(5, target, 0, 2, 1)
    assert roots == [origin + timedelta(days=day) for day in expected_days]


def test_scan_keeps_the_final_fractional_cell(monkeypatch):
    origin = datetime(2000, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(
        astrology_events,
        "_planet_motion",
        lambda jd, body, **kwargs: (120 + jd - 1.125, 1.0, 0, ()),
    )
    monkeypatch.setattr(
        astrology_events, "_jd_to_utc", lambda jd: origin + timedelta(days=jd)
    )
    monkeypatch.setattr(
        astrology_events,
        "_julian_day",
        lambda at: (at - origin).total_seconds() / 86400,
    )
    roots = astrology_events._longitude_crossings_utc(5, 120, 0, 1.25, 1)
    assert roots == [origin + timedelta(days=1.125)]


@pytest.mark.parametrize("zodiac, expected_day", [("Tropic", 24), ("Sidereal", 25)])
def test_nearest_return_and_zodiac_agree_across_rest_mcp_cli(
    zodiac, expected_day, surface_calls
):
    spec = SPECS["astro_extrareturns"]
    inputs = dict(
        birth_year=1990,
        birth_month=5,
        birth_day=17,
        birth_hour=7,
        birth_minute=30,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        analysis_year=2002,
        analysis_month=1,
        analysis_day=12,
        zodiac_type=zodiac,
    )
    fields = ["extrareturns.returns", "analysis_context.zodiac_type"]
    query = [("fields", field) for field in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", 0),
    ]
    http, protocol, code, cli = surface_calls(
        spec,
        inputs,
        params=query,
        options={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
        flags=["--fields", *fields],
    )
    assert http.status_code == 200, http.text
    assert code == 0 and not protocol.is_error
    assert json.loads(protocol.content[0].text) == protocol.structured_content
    outputs = [http.json(), cli, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        assert output["analysis_context"]["zodiac_type"] == zodiac
        row = next(
            row for row in output["extrareturns"]["returns"] if row["body"] == "Jupiter"
        )
        target = native_longitude(swe.JUPITER, BIRTH, zodiac == "Sidereal")
        assert row["natal_longitude"]["absolute_degree"] == pytest.approx(
            target, abs=1e-10
        )
        at = datetime.fromisoformat(row["next_return"]["datetime_utc"])
        assert (at.year, at.month, at.day) == (2002, 4, expected_day)
        assert (
            abs(
                (native_longitude(swe.JUPITER, at, zodiac == "Sidereal") - target + 180)
                % 360
                - 180
            )
            < 1e-8
        )
