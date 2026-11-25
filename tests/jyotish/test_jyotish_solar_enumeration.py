"""Solar event enumeration must not drop a second rise in one UT1 date."""

import json
from datetime import datetime
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish.jyotish import build_india, nakshatra
from fatebridge.core.jyotish.jyotish_kala import solar_packet, solar_parts
from fatebridge.core.jyotish.jyotish_panchanga import compute_panchanga
from tests.support.solar_events import fixed_crossings, solar_event

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/jyotish-solar-enumeration-reference.json"
    ).read_text()
)
START = 2451544.5


@pytest.mark.parametrize(
    "jd_ut1,civil_labels,before_sunrise",
    [
        (2461117.48, ("2026-03-17T23:31+00:00", "2026-03-18T05:31+06:00"), True),
        (2461117.55, ("2026-03-18T01:12+00:00", "2026-03-17T17:12-08:00"), False),
    ],
)
def test_panchanga_sunrise_flag_uses_solar_day_under_any_civil_zone(
    jd_ut1: float, civil_labels, before_sunrise: bool
) -> None:
    reference = REFERENCE["cases"][0]
    context = solar_parts(jd_ut1, reference["longitude"], reference)
    for label in civil_labels:
        result = compute_panchanga(
            0.0,
            30.0,
            nakshatra(30.0),
            local_datetime=datetime.fromisoformat(label),
            solar_context=context,
        )
        assert result["vara"]["before_local_sunrise"] is before_sunrise


def test_panchanga_public_angles_stay_within_their_exact_bands() -> None:
    sun, moon = 180.0, float.fromhex("0x1.67fffffffffffp+7")
    result = compute_panchanga(sun, moon, nakshatra(moon))
    tithi, yoga, karana = (result[key] for key in ("tithi", "yoga", "karana"))
    assert (tithi["number"], yoga["number"], karana["half_tithi_index"]) == (30, 27, 60)
    assert 354 <= tithi["elongation_degrees"] < 360
    assert 26 * Fraction(40, 3) <= yoga["lunisolar_sum_degrees"] < 360
    for limb in (tithi, yoga, karana):
        assert 0 < limb["fraction_elapsed"] < 1
        assert 0 < limb["fraction_remaining"] <= 1

    near_mansion_end = Fraction(40, 3) - Fraction(1, 2**45)
    lunar_mansion = compute_panchanga(
        0.0, near_mansion_end, nakshatra(near_mansion_end)
    )["nakshatra"]
    assert lunar_mansion["index"] == 1
    assert lunar_mansion["fraction_remaining"] == float(Fraction(3, 40 * 2**45))


def test_two_rises_in_one_ut1_date_do_not_keep_the_previous_day_lord() -> None:
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
def test_complete_event_list_against_independent_de421_skyfield_altitude_scan(
    case,
) -> None:
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


def test_second_event_and_exact_window_edges_without_shifting_returned_times(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fatebridge.core.jyotish import jyotish_kala

    rises = [START, START + 0.999, START + 2.5, START + 8]
    sets = [START + 0.3, START + 1.2]
    monkeypatch.setattr(
        jyotish_kala, "solar_crossings_in_window", fixed_crossings(rises, sets)
    )
    packet = solar_packet(START + 3.5, 0, 0, "auto")
    assert [(e["kind"], e["julian_day_ut1"]) for e in packet["events"]] == sorted(
        [("rise", t) for t in rises[:-1]] + [("set", t) for t in sets],
        key=lambda row: row[1],
    )
    assert packet["enumeration"]["partition_hours"] == 24
    assert all(
        e["julian_day_tt"] == e["julian_day_ut1"] + 70 / 86400 for e in packet["events"]
    )


def test_polar_no_event_does_not_stop_later_daily_searches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fatebridge.core.jyotish import jyotish_kala

    calls = []
    real = fixed_crossings([START + 1.3], [START + 1.7])

    def crossings(start, end, **kwargs):
        calls.append((start, end))
        return real(start, end, **kwargs)

    monkeypatch.setattr(jyotish_kala, "solar_crossings_in_window", crossings)
    packet = solar_packet(START + 3.5, 0, 80, "auto")
    assert calls == [(START + day, START + day + 1) for day in range(8)]
    assert len(packet["no_event_searches"]) == 14
    assert [e["julian_day_ut1"] for e in packet["events"]] == [START + 1.3, START + 1.7]


def test_domain_strict_policy_failure_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fatebridge.core.jyotish import jyotish_kala

    failure = ValueError("require_data_files rejects event source")

    def fail(start, end, **kwargs):
        assert kwargs["ephemeris_policy"] == "require_data_files"
        raise failure

    monkeypatch.setattr(jyotish_kala, "solar_crossings_in_window", fail)
    with pytest.raises(ValueError) as raised:
        solar_packet(START + 3.5, 0, 0, "require_data_files")
    assert raised.value is failure


def test_actual_event_sources_are_retained_without_a_second_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fatebridge.core.jyotish import jyotish_kala

    monkeypatch.setattr(jyotish_kala, "tt_from_ut1", lambda ut1: ut1 + 64 / 86400)
    events = [
        solar_event(START + 0.1, rising=True),
        solar_event(START + 1.1, rising=True, model="moshier"),
    ]
    monkeypatch.setattr(
        jyotish_kala,
        "solar_crossings_in_window",
        lambda start, end, **kwargs: [
            e for e in events if start <= e.julian_day_ut1 <= end
        ],
    )
    monkeypatch.setattr(
        jyotish_kala.runtime,
        "ephemeris_call",
        lambda *args, **kwargs: pytest.fail(
            "Consume the event's verified source and TT"
        ),
    )
    packet = solar_packet(START + 3.5, 0, 0, "auto")
    assert packet["ephemeris_models"] == ["moshier", "swieph"]
    assert set(packet["ephemeris_sources"]) == {"moshier", "swieph"}


def test_solver_failure_cannot_masquerade_as_a_polar_no_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fatebridge.core.jyotish import jyotish_kala

    failure = RuntimeError("Solar crossing did not converge")

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(jyotish_kala, "solar_crossings_in_window", fail)
    with pytest.raises(RuntimeError) as raised:
        solar_packet(START + 3.5, 0, 0, "auto")
    assert raised.value is failure


def test_subsecond_arc_across_day_boundary_is_not_erased_by_a_repeat_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fatebridge.core.jyotish import jyotish_kala

    first = START + 1 - 0.25 / 86400
    setting = START + 1
    second = START + 1 + 0.001 / 86400
    monkeypatch.setattr(
        jyotish_kala,
        "solar_crossings_in_window",
        fixed_crossings([first, second], [setting]),
    )
    packet = solar_packet(START + 3.5, 0, 0, "auto")
    assert [(e["kind"], e["julian_day_ut1"]) for e in packet["events"]] == [
        ("rise", first),
        ("set", setting),
        ("rise", second),
    ]


@pytest.mark.parametrize("fraction_of_ulp", [-0.25, 0.0, 0.25])
def test_physical_root_bracket_has_one_owner_at_a_daily_partition(
    monkeypatch: pytest.MonkeyPatch, fraction_of_ulp
) -> None:
    """An analytic linear height isolates ownership from ephemeris accuracy."""
    import math

    from fatebridge.core.astro import solar_events

    boundary = START + 1
    step = math.ulp(boundary)

    def observe(ut1, *, definition, **kwargs):
        altitude = (ut1 - boundary) - fraction_of_ulp * step
        return solar_events.SolarObservation(
            ut1, ut1 + 70 / 86400, altitude, (1.0, 0.0, 0.0), "swieph", 2, definition
        )

    monkeypatch.setattr(solar_events, "solar_observation", observe)
    packet = solar_packet(boundary + 2.5, 0, 0, "auto")
    assert len(packet["events"]) == 1
    expected = math.nextafter(boundary, -math.inf) if fraction_of_ulp < 0 else boundary
    assert packet["events"][0]["julian_day_ut1"] == expected
    assert packet["events"][0]["kind"] == "rise"
