"""Slow-body recrossings and the requested zodiac must survive return search.

Dates isolate the three observed Jupiter crossings in its 2001/02 retrograde
loop. Native Swiss coordinates independently check the solved equations; these
checks are not independent physical ephemeris accuracy certification.
"""

from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.astro import astrology_events
from fatebridge.core.astro.time_scales import datetime_from_tt, ephemeris_time
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.ephemeris_runtime import (
    ephemeris_call,
    preserve_ephemeris_path,
    swe,
)
from fatebridge.services.western_events import calculate_extrareturns
from tests.support.transports import SPECS, business

BIRTH = datetime(1990, 5, 17, 7, 30, tzinfo=timezone.utc)
REFERENCE = datetime(2002, 1, 12, tzinfo=timezone.utc)


def native_longitude(body, moment, sidereal):
    with preserve_ephemeris_path():
        flags = swe.FLG_SWIEPH
        if sidereal:
            swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
            flags |= swe.FLG_SIDEREAL
        else:
            pass
        coordinates, returned = ephemeris_call(
            "calc", ephemeris_time(moment).jd_tt, body, flags
        )
    assert returned >= 0
    return coordinates[0]


@pytest.mark.parametrize("sidereal", [False, True])
def test_nearest_returns_keep_the_third_crossing_in_jupiter_retrograde_loop(
    sidereal: bool,
) -> None:
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


def test_return_count_selects_each_side_instead_of_period_seed_duplicates() -> None:
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


def test_extra_returns_service_uses_native_lahiri_for_natal_and_events() -> None:
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
def test_scan_keeps_an_exact_root_on_a_shared_cell_boundary(
    monkeypatch: pytest.MonkeyPatch, speed
) -> None:
    # Linear synthetic longitude provides an exact known root at JD1, for both
    # crossing directions. Its civil adapter preserves the same artificial JD.
    origin = datetime(2000, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(
        astrology_events,
        "_planet_motion",
        lambda jd, body, **kwargs: ((120 + speed * (jd - 1)) % 360, speed, 0, ()),
    )
    monkeypatch.setattr(
        astrology_events,
        "utc_from_tt",
        lambda point, **options: (
            None,
            origin + timedelta(days=point.as_float()),
            False,
        ),
    )
    monkeypatch.setattr(
        astrology_events,
        "_julian_day",
        lambda at: (at - origin).total_seconds() / 86400,
    )
    roots = [
        event.utc_datetime
        for event in astrology_events._longitude_crossings(5, 120, 0, 2, 1)
    ]
    assert roots == [origin + timedelta(days=1)]


@pytest.mark.parametrize("target, expected_days", [(0, [1]), (180, [])])
def test_scan_distinguishes_a_true_zero_degree_crossing_from_the_antipodal_jump(
    monkeypatch: pytest.MonkeyPatch, target: int, expected_days
) -> None:
    origin = datetime(2000, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(
        astrology_events,
        "_planet_motion",
        lambda jd, body, **kwargs: ((359 + jd) % 360, 1.0, 0, ()),
    )
    monkeypatch.setattr(
        astrology_events,
        "utc_from_tt",
        lambda point, **options: (
            None,
            origin + timedelta(days=point.as_float()),
            False,
        ),
    )
    monkeypatch.setattr(
        astrology_events,
        "_julian_day",
        lambda at: (at - origin).total_seconds() / 86400,
    )
    roots = [
        event.utc_datetime
        for event in astrology_events._longitude_crossings(5, target, 0, 2, 1)
    ]
    assert roots == [origin + timedelta(days=day) for day in expected_days]


def test_scan_keeps_the_final_fractional_cell(monkeypatch: pytest.MonkeyPatch) -> None:
    origin = datetime(2000, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(
        astrology_events,
        "_planet_motion",
        lambda jd, body, **kwargs: (120 + jd - 1.125, 1.0, 0, ()),
    )
    monkeypatch.setattr(
        astrology_events,
        "utc_from_tt",
        lambda point, **options: (
            None,
            origin + timedelta(days=point.as_float()),
            False,
        ),
    )
    monkeypatch.setattr(
        astrology_events,
        "_julian_day",
        lambda at: (at - origin).total_seconds() / 86400,
    )
    roots = [
        event.utc_datetime
        for event in astrology_events._longitude_crossings(5, 120, 0, 1.25, 1)
    ]
    assert roots == [origin + timedelta(days=1.125)]


@pytest.mark.parametrize(
    "reference",
    [
        datetime(1990, 4, 6, 1, 33, tzinfo=timezone.utc),
        datetime(1990, 5, 17, 7, 30, tzinfo=timezone.utc),
        datetime(2001, 1, 25, 3, tzinfo=timezone.utc),
    ],
)
def test_return_membership_uses_native_tt_before_rounded_display(
    reference, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_tt = ephemeris_time(reference).jd_tt
    assert source_tt is not None
    # A declared five-day source has an exact native equation witness at
    # the reference. Only the real clock adapter supplies display rounding;
    # this control does not claim a physical Jupiter ephemeris or root.
    monkeypatch.setattr(
        astrology_events,
        "_planet_motion",
        lambda jd, body, **kwargs: (
            (120 + 72 * (jd - source_tt)) % 360,
            72,
            0,
            (),
        ),
    )
    resolved = astrology_events.resolve_planet_returns(
        5, 120, period_days=5, reference_utc=reference
    )
    assert resolved.past[-1].tt.days == Fraction(source_tt)
    assert resolved.past[-1].utc_datetime == datetime_from_tt(source_tt)
    assert all(at.tt.days > Fraction(source_tt) for at in resolved.future)


def test_extra_returns_service_preserves_selected_side_and_original_display(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fatebridge.services import western_events

    reference = datetime(2001, 1, 25, 3, tzinfo=timezone.utc)
    source_tt = TTInstant.from_float(2451934.6257428704)
    displayed_past = reference + timedelta(microseconds=1)
    displayed_future = reference + timedelta(days=5)
    selected = astrology_events.ResolvedPlanetReturns(
        (astrology_events.LongitudeCrossing(source_tt, displayed_past),),
        (
            astrology_events.LongitudeCrossing(
                TTInstant(source_tt.days + 5), displayed_future
            ),
        ),
    )
    monkeypatch.setattr(
        western_events, "resolve_planet_returns", lambda *a, **k: selected
    )
    monkeypatch.setattr(
        western_events, "planet_motion_at_utc", lambda *a, **k: (120.0, 0.0, 0, ())
    )
    result = western_events.calculate_extrareturns(
        birth_year=2001,
        birth_month=1,
        birth_day=25,
        birth_hour=3,
        birth_minute=0,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=40,
        analysis_year=2001,
        analysis_month=1,
        analysis_day=25,
    )
    assert "error" not in result
    for row in result["extrareturns"]["returns"]:
        assert row["most_recent_return"]["datetime_utc"] == displayed_past.isoformat()
        assert row["next_return"]["datetime_utc"] == displayed_future.isoformat()


def test_extra_returns_service_keeps_extended_utc_clock_coordinates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fatebridge.services import western_events

    birth_labels = []
    reference_labels = []

    def natal_motion(planet_id, moment, *, sidereal=False):
        birth_labels.append(moment.isoformat())
        return 120.0, 0.0, 0, ()

    def resolve_returns(planet_id, longitude, *, reference_utc, **options):
        reference_labels.append(reference_utc.isoformat())
        return astrology_events.ResolvedPlanetReturns((), ())

    monkeypatch.setattr(western_events, "planet_motion_at_utc", natal_motion)
    monkeypatch.setattr(western_events, "resolve_planet_returns", resolve_returns)
    result = calculate_extrareturns(
        birth_year=1,
        birth_month=1,
        birth_day=1,
        birth_hour=13,
        birth_minute=59,
        birth_timezone="Etc/GMT-14",
        birth_longitude=0,
        birth_latitude=0,
        analysis_year=1,
        analysis_month=1,
        analysis_day=1,
    )
    assert "error" not in result
    body_count = len(result["extrareturns"]["returns"])
    assert body_count == 10
    assert (
        birth_labels == reference_labels == ["0000-12-31T23:59:00+00:00"] * body_count
    )


@pytest.mark.parametrize("latitude", [0, 80])
@pytest.mark.parametrize("zodiac, expected_day", [("Tropic", 24), ("Sidereal", 25)])
def test_nearest_return_and_zodiac_agree_across_rest_mcp_cli(
    zodiac: str, expected_day: int, latitude: int, surface_calls
) -> None:
    spec = SPECS["planetary_returns"]
    inputs = dict(
        birth_year=1990,
        birth_month=5,
        birth_day=17,
        birth_hour=7,
        birth_minute=30,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=latitude,
        analysis_year=2002,
        analysis_month=1,
        analysis_day=12,
        zodiac_type=zodiac,
    )
    fields = ["extrareturns.returns", "analysis_context.zodiac_type"]
    query = [("fields", field) for field in fields] + [("detail", "audit")]
    http, protocol, code, cli = surface_calls(
        spec,
        inputs,
        params=query,
        options={
            "fields": fields,
            "detail": "audit",
        },
        flags=["--fields", *fields, "--detail", "audit"],
    )
    assert http.status_code == 200, http.text
    assert code == 0 and not protocol.is_error
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


@pytest.mark.local_data
@pytest.mark.parametrize(
    ("birth", "offset", "reference", "expected_tt", "utc_label", "status"),
    [
        (
            (1998, 5, 22, 14, 33),
            "-0.00404984027777777777777777777777777777777777778",
            (2016, 12, 30),
            2457754.500794954,
            "2016-12-31T23:59:60.500037+00:00",
            "inserted_UTC_leap_second",
        ),
        (
            (1945, 8, 20, 15, 10),
            "-0.00642599277777777777777777777777777777777777778",
            (1964, 3, 30),
            2438486.500406455,
            None,
            "unrepresentable_historical_fractional_UTC_adjustment",
        ),
    ],
)
def test_extra_returns_preserve_the_root_when_utc_has_no_datetime(
    birth,
    offset: str,
    reference,
    expected_tt: float,
    utc_label: str | None,
    status: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Real Swiss 2.10.03 north-node returns. IERS Bulletin C52 and the
    # USNO tai-utc.dat affine rows determine the two clock representations.
    year, month, day, hour, minute = birth
    analysis_year, analysis_month, analysis_day = reference
    ephe = Path(__file__).resolve().parents[2] / "ephe"
    with preserve_ephemeris_path(), monkeypatch.context() as native:
        native.setenv("SE_EPHE_PATH", str(ephe))
        native.delenv("FATEBRIDGE_JPL_FILE", raising=False)
        result = calculate_extrareturns(
            birth_year=year,
            birth_month=month,
            birth_day=day,
            birth_hour=hour,
            birth_minute=minute,
            birth_timezone=offset,
            birth_longitude=0,
            birth_latitude=0,
            analysis_year=analysis_year,
            analysis_month=analysis_month,
            analysis_day=analysis_day,
            house_system="W",
        )
    assert "error" not in result, result
    returns = result["extrareturns"]["returns"]
    assert {row["body"] for row in returns} == {
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
    node = next(row for row in returns if row["body"] == "North Node")
    assert (
        datetime.fromisoformat(node["most_recent_return"]["datetime_utc"]).year == year
    )
    event = node["next_return"]
    assert abs(event["julian_day_tt"] - expected_tt) * 86400 <= 0.002
    assert event["datetime_utc"] == utc_label
    assert event["datetime_local"] is None
    assert event["utc_representation"]["utc_label"] == utc_label
    assert event["utc_representation"]["label_status"] == status
    assert event["utc_representation"]["datetime_representable"] is False
