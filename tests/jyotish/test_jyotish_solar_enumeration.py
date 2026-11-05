"""Solar event enumeration must not drop a second rise in one UT1 date."""

import json
import math
from pathlib import Path

import pytest

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish import build_india
from fatebridge.core.jyotish_kala import solar_packet

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/jyotish-solar-enumeration-reference.json"
    ).read_text()
)
START = 2451544.5


def test_two_rises_in_one_ut1_date_do_not_keep_the_previous_day_lord():
    birth = build_astro_birth_info(
        birth_year=2026,
        birth_month=3,
        birth_day=24,
        birth_hour=0,
        birth_minute=10,
        birth_timezone="UTC",
        birth_longitude=91,
        birth_latitude=30,
    )
    kala = build_india(birth, divisions=[])["strengths"]["kala_bala"]
    assert kala["components"]["dina_bala"]["ruler"] == "Mars"
    assert kala["components"]["hora_bala"]["ruler"] == "Mars"
    assert kala["components"]["tribhaga_bala"]["ruler"] == "Mercury"


@pytest.mark.parametrize("case", REFERENCE["cases"])
def test_complete_event_list_against_independent_de421_skyfield_altitude_scan(case):
    actual = solar_packet(
        case["start_jd_ut1"] + 3.5, case["longitude"], case["latitude"], "auto"
    )
    assert actual["search_start_jd_ut1"] == case["start_jd_ut1"]
    assert actual["search_end_jd_ut1"] == case["end_jd_ut1"]
    assert len(actual["events"]) == len(case["events"])
    for observed, expected in zip(actual["events"], case["events"]):
        assert observed["kind"] == expected["kind"]
        assert (
            abs(observed["julian_day_ut1"] - expected["julian_day_ut1"]) * 86400
            < REFERENCE["matching_tolerance_seconds"]
        )


def mock_rise_calls(monkeypatch, solver):
    """Replace event roots only; keep other managed calls and their spies."""
    from fatebridge.core.astro import runtime

    managed = runtime.ephemeris_call

    def dispatch(name, *args, **kwargs):
        if name == "rise_trans":
            return solver(name, *args, **kwargs)
        return managed(name, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", dispatch)


def fake_solver(monkeypatch, rises, sets):
    from fatebridge.core.astro import runtime

    def next_event(name, cursor, body, flags, *args):
        assert name == "rise_trans" and body == runtime.swe.SUN
        sequence = rises if flags & runtime.swe.CALC_RISE else sets
        event = next((t for t in sequence if t >= cursor), START + 9)
        return 0, (event,)

    mock_rise_calls(monkeypatch, next_event)
    managed = runtime.ephemeris_call

    def event_model(operation, *args, **kwargs):
        # Enumeration consumes this managed seam. Fabricated native flags must
        # not masquerade as real planet/Moon file coverage below that seam.
        if operation == "calc_ut":
            return (0.0,) * 6, runtime.swe.FLG_SWIEPH
        return managed(operation, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", event_model)


def test_second_event_and_exact_window_edges_without_shifting_returned_times(
    monkeypatch,
):
    rises = [START, START + 0.999, START + 2.5, START + 8]
    sets = [START + 0.3, START + 1.2]
    fake_solver(monkeypatch, rises, sets)
    packet = solar_packet(START + 3.5, 0, 0, "auto")
    pairs = [(e["kind"], e["julian_day_ut1"]) for e in packet["events"]]
    assert pairs == sorted(
        [("rise", t) for t in rises[:-1]] + [("set", t) for t in sets],
        key=lambda row: row[1],
    )
    assert packet["enumeration"]["post_event_search_advance_seconds"] == 1
    assert packet["fallback_event_count"] == 0


def test_polar_no_event_does_not_stop_later_daily_searches(monkeypatch):
    from fatebridge.core.astro import runtime

    fake_solver(monkeypatch, [START + 1.3], [START + 1.7])
    real = runtime.ephemeris_call

    def no_first_day(name, cursor, *args):
        return (-2, (0.0,)) if cursor < START + 1 else real(name, cursor, *args)

    mock_rise_calls(monkeypatch, no_first_day)
    packet = solar_packet(START + 3.5, 0, 80, "auto")
    assert len(packet["no_event_searches"]) == 2
    assert [e["julian_day_ut1"] for e in packet["events"]] == [START + 1.3, START + 1.7]


def test_second_same_day_event_has_its_own_strict_backend_check(monkeypatch):
    from fatebridge.core.astro import runtime

    fake_solver(monkeypatch, [START + 0.1, START + 0.9], [])
    checked = []

    def second_event_falls_back(jd, *args):
        checked.append(jd)
        model = runtime.swe.FLG_SWIEPH if jd == START + 0.1 else runtime.swe.FLG_MOSEPH
        return (0.0,) * 6, model

    managed = runtime.ephemeris_call

    def checked_event(operation, *args, **kwargs):
        if operation == "calc_ut":
            return second_event_falls_back(*args)
        return managed(operation, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", checked_event)
    with pytest.raises(ValueError, match="require_data_files"):
        solar_packet(START + 3.5, 0, 0, "require_data_files")
    # Every enumerated event is checked independently at the managed boundary.
    assert checked == [START + 0.1, START + 0.9]


def test_automatic_backend_counts_include_second_same_day_event(monkeypatch):
    from fatebridge.core.astro import runtime

    fake_solver(monkeypatch, [START + 0.1, START + 0.9], [])
    managed = runtime.ephemeris_call

    def event_model(operation, *args, **kwargs):
        if operation == "calc_ut":
            model = (
                runtime.swe.FLG_SWIEPH
                if args[0] == START + 0.1
                else runtime.swe.FLG_MOSEPH
            )
            return (0.0,) * 6, model
        return managed(operation, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", event_model)
    packet = solar_packet(START + 3.5, 0, 0, "auto")
    assert packet["fallback_event_count"] == 1
    assert packet["ephemeris_models"] == ["moshier", "swieph"]


@pytest.mark.parametrize(
    "result,value", [(-1, START), (1, START), (0, math.nan), (0, math.inf)]
)
def test_invalid_event_return_codes_or_values_are_not_admitted(
    monkeypatch, result, value
):
    mock_rise_calls(monkeypatch, lambda *args: (result, (value,)))
    with pytest.raises(ValueError, match="could not compute"):
        solar_packet(START + 3.5, 0, 0, "auto")


def test_nonadvancing_solver_is_an_error_instead_of_a_duplicate_event(monkeypatch):
    fake_solver(monkeypatch, [], [])
    mock_rise_calls(monkeypatch, lambda *args: (0, (START,)))
    with pytest.raises(ValueError, match="did not advance"):
        solar_packet(START + 3.5, 0, 0, "auto")


def test_pathological_backend_cannot_silently_truncate_or_loop_forever(monkeypatch):
    fake_solver(monkeypatch, [], [])
    mock_rise_calls(
        monkeypatch,
        lambda name, cursor, *args: (0, (cursor + 2 / 86400,)),
    )
    with pytest.raises(ValueError, match="enumeration limit exceeded"):
        solar_packet(START + 3.5, 0, 0, "auto")


def test_repeat_guard_survives_a_ut1_day_boundary(monkeypatch):
    from fatebridge.core.astro import runtime

    fake_solver(monkeypatch, [], [])
    before_midnight = START + 1 - 0.25 / 86400
    rounded_duplicate = START + 1 + 0.001 / 86400

    def root_rounds_across_midnight(name, cursor, body, flags, *args):
        if flags & runtime.swe.CALC_SET:
            return 0, (START + 9,)
        # Repeated searches can round one root to opposite sides of a date
        # cut. The anti-repeat cursor must span that cut.
        if cursor <= before_midnight:
            return 0, (before_midnight,)
        if cursor <= rounded_duplicate:
            return 0, (rounded_duplicate,)
        return 0, (START + 2.5 if cursor <= START + 2.5 else START + 9,)

    mock_rise_calls(monkeypatch, root_rounds_across_midnight)
    packet = solar_packet(START + 3.5, 0, 0, "auto")
    assert [e["julian_day_ut1"] for e in packet["events"]] == [
        before_midnight,
        START + 2.5,
    ]
