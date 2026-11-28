"""Observed station-loop roots survive a daily return-search cell."""

import math
from datetime import datetime, timedelta, timezone

import pytest

from fatebridge.core.astro import astrology_events
from fatebridge.utils.errors import EphemerisSourceError
from tests.support.transports import SPECS, business

BIRTH = datetime(2001, 1, 25, 3, tzinfo=timezone.utc)
REFERENCE = BIRTH + timedelta(days=2)
INDEPENDENT_RECENT = datetime(2001, 1, 25, 14, 15, 53, 98888, tzinfo=timezone.utc)


def test_real_jupiter_two_return_roots_in_one_daily_cell_match_independent_de421() -> (
    None
):
    target = astrology_events.planet_longitude_at_utc(5, BIRTH)
    roots = astrology_events.find_planet_returns(
        5, target, period_days=4332.59, reference_utc=REFERENCE
    )
    recent, following = roots
    assert abs((recent - INDEPENDENT_RECENT).total_seconds()) <= 30
    assert BIRTH < recent < REFERENCE < following
    residual = (
        astrology_events.planet_longitude_at_utc(5, recent) - target + 180
    ) % 360 - 180
    assert abs(residual) * 3600 < 0.001


def synthetic_clock(monkeypatch):
    origin = datetime(2000, 1, 1, tzinfo=timezone.utc)
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
    return origin


@pytest.mark.parametrize("offset, expected", [(-0.0625, [0.25, 0.75]), (0.0, [0.5])])
def test_actual_longitude_brackets_both_roots_or_an_exact_turn_contact(
    monkeypatch: pytest.MonkeyPatch, offset, expected
) -> None:
    origin = synthetic_clock(monkeypatch)
    monkeypatch.setattr(
        astrology_events,
        "_planet_motion",
        lambda jd, body, **kw: (120 + (jd - 0.5) ** 2 + offset, 2 * (jd - 0.5), 0, ()),
    )
    roots = [
        event.utc_datetime
        for event in astrology_events._longitude_crossings(5, 120, 0, 1, 1)
    ]
    assert roots == [origin + timedelta(days=at) for at in expected]


def test_two_roots_on_opposite_sides_of_annual_chunk_boundary_are_both_retained(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = synthetic_clock(monkeypatch)
    turn = 365.25
    monkeypatch.setattr(
        astrology_events,
        "_planet_motion",
        lambda jd, body, **kw: (
            120 + 0.0001 * ((jd - turn) ** 2 - 0.0625),
            0.0002 * (jd - turn),
            0,
            (),
        ),
    )
    roots = astrology_events.find_planet_returns(
        5,
        120,
        period_days=4332.59,
        reference_utc=origin + timedelta(days=730.5),
        past=2,
        future=0,
    )
    assert len(roots) == 2
    for actual, expected in zip(roots, [365.0, 365.5]):
        assert (
            abs((actual - (origin + timedelta(days=expected))).total_seconds()) < 0.001
        )


def test_native_speed_is_only_a_split_guide_and_cannot_invent_a_longitude_contact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = synthetic_clock(monkeypatch)
    # The deliberately inaccurate speed reverses at0.5 while the actual
    # longitude is monotone and has exactly one root at0.25.
    monkeypatch.setattr(
        astrology_events,
        "_planet_motion",
        lambda at, body, **kw: (120 + at - 0.25, 2 * (at - 0.5), 0, ()),
    )
    roots = [
        event.utc_datetime
        for event in astrology_events._longitude_crossings(5, 120, 0, 1, 1)
    ]
    assert roots == [origin + timedelta(days=0.25)]


@pytest.mark.parametrize("change", ["model", "file"])
def test_local_station_refinement_rejects_changed_native_source(
    monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    origin = synthetic_clock(monkeypatch)

    def motion(at, body, **kwargs):
        modified = at == 0.5
        flags = int(modified and change == "model")
        context = (("changed", 0.0, 1.0, 441),) if modified and change == "file" else ()
        return 120 + (at - 0.5) ** 2 - 0.0625, 2 * (at - 0.5), flags, context

    monkeypatch.setattr(astrology_events, "_planet_motion", motion)
    with pytest.raises(EphemerisSourceError) as caught:
        astrology_events.resolve_longitude_crossing(
            5, 120, origin + timedelta(days=0.5), window_days=0.5, step_days=1.0
        )
    assert caught.value.reason == "model_changed"


def test_station_cell_root_is_the_same_on_rest_mcp_cli(surface_calls) -> None:
    spec = SPECS["planetary_returns"]
    inputs = dict(
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
        analysis_day=27,
    )
    fields = ["planetary_returns.returns"]
    http, protocol, code, cli = surface_calls(
        spec,
        inputs,
        params=[
            ("fields", fields[0]),
        ],
        options={
            "fields": fields,
        },
        flags=["--fields", *fields],
    )
    assert http.status_code == 200, http.text
    assert code == 0 and not protocol.is_error
    values = [http.json(), cli, protocol.structured_content]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for value in values:
        row = next(
            row
            for row in value["planetary_returns"]["returns"]
            if row["body"] == "Jupiter"
        )
        recent = datetime.fromisoformat(row["most_recent_return"]["datetime_utc"])
        assert abs((recent - INDEPENDENT_RECENT).total_seconds()) <= 30


@pytest.mark.parametrize("base", [0.0, 1.0, 61.18774508129519, 180.0, 359.0])
def test_signed_residual_retains_the_negative_neighbor_of_the_target(
    base: float,
) -> None:
    previous = math.nextafter(base, -math.inf)
    assert astrology_events._wrapped_diff(previous, base) == previous - base < 0
    assert astrology_events._wrapped_diff(base, previous) == base - previous > 0


@pytest.mark.parametrize(
    "longitude,target,expected",
    [(0.25, 359.75, 0.5), (359.75, 0.25, -0.5), (360.0, 0.0, 0.0), (0.0, 360.0, 0.0)],
)
def test_signed_residual_preserves_true_longitude_wrap(
    longitude: float, target: float, expected
) -> None:
    assert astrology_events._wrapped_diff(longitude, target) == expected


@pytest.mark.parametrize("speed_zero", [0.0, 0.70, 1.0])
@pytest.mark.parametrize(
    "target_offset,expected_count", [(0, 1), (0.0001, 2), (-0.0001, 0)]
)
def test_return_contact_uses_actual_longitude_extremum(
    monkeypatch: pytest.MonkeyPatch,
    speed_zero: float,
    target_offset: float,
    expected_count: int,
) -> None:
    origin = synthetic_clock(monkeypatch)
    turn = 0.46
    monkeypatch.setattr(
        astrology_events,
        "_planet_motion",
        lambda jd, body, **kw: (
            120 + min((jd - turn) ** 2, 1.0),
            2 * (jd - speed_zero),
            0,
            (),
        ),
    )
    result = astrology_events.resolve_planet_returns(
        5, 120 + target_offset, period_days=720, reference_utc=origin, past=0, future=2
    )
    # The synthetic coordinate reaches the target only near the prescribed turn.
    assert len(result.future) == expected_count
    expected_days = [turn] if target_offset == 0 else [turn - 0.01, turn + 0.01]
    for event, expected_day in zip(result.future, expected_days):
        assert event.tt.as_float() == pytest.approx(expected_day, abs=1e-7)


def test_return_rejects_changed_flags_even_in_a_cell_without_a_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = synthetic_clock(monkeypatch)
    monkeypatch.setattr(
        astrology_events,
        "_planet_motion",
        lambda at, body, **kw: (120 + at - 0.25, 1.0, int(at < 1.5), ()),
    )
    with pytest.raises(EphemerisSourceError) as caught:
        astrology_events.resolve_planet_returns(
            5,
            120,
            period_days=0.5,
            reference_utc=origin + timedelta(days=2),
            past=1,
            future=0,
        )
    assert caught.value.reason == "model_changed"


@pytest.mark.parametrize("direction", [-1.0, 1.0])
def test_return_stops_before_a_more_distant_native_source_change(
    monkeypatch: pytest.MonkeyPatch, direction: float
) -> None:
    origin = synthetic_clock(monkeypatch)
    monkeypatch.setattr(
        astrology_events,
        "_planet_motion",
        lambda at, body, **kw: (
            120 + at - direction * 0.25,
            1.0,
            int(abs(at) > 0.5),
            (),
        ),
    )
    result = astrology_events.resolve_planet_returns(
        5,
        120,
        period_days=0.5,
        reference_utc=origin,
        past=int(direction < 0),
        future=int(direction > 0),
    )
    selected = result.past or result.future
    assert len(selected) == 1
    assert selected[0].utc_datetime == origin + timedelta(days=direction * 0.25)


def test_return_rejects_a_different_known_de_edition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = synthetic_clock(monkeypatch)
    monkeypatch.setattr(
        astrology_events,
        "_planet_motion",
        lambda at, body, **kw: (120 + at - 0.25, 1.0, 2, (("segment", 0.0, 2.0, 441),)),
    )
    with pytest.raises(EphemerisSourceError) as caught:
        astrology_events.resolve_planet_returns(
            5,
            120,
            period_days=2,
            reference_utc=origin,
            past=0,
            future=1,
            natal_motion=(120, 1.0, 2, (("earlier", -2.0, 0.0, 431),)),
        )
    assert caught.value.reason == "model_changed"


@pytest.mark.parametrize("reported_station_days", [0.52, 0.96])
def test_return_retains_contact_at_a_single_representable_tt(
    monkeypatch: pytest.MonkeyPatch, reported_station_days: float
) -> None:
    reference_tt = 2451545.0
    turn = math.nextafter(reference_tt + 0.46, math.inf)
    monkeypatch.setattr(astrology_events, "_julian_day", lambda at: reference_tt)
    monkeypatch.setattr(
        astrology_events, "utc_from_tt", lambda at, **options: (None, None, False)
    )
    monkeypatch.setattr(
        astrology_events,
        "_planet_motion",
        lambda at, body, **options: (
            (at - turn) ** 2,
            2 * (at - reference_tt - reported_station_days),
            0,
            (),
        ),
    )
    result = astrology_events.resolve_planet_returns(
        5,
        0.0,
        period_days=720,
        reference_utc=BIRTH,
        past=0,
        future=1,
    )
    assert tuple(event.tt.as_float() for event in result.future) == (turn,)
