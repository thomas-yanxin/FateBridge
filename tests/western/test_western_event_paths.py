"""Physical event histories, printed examples and noninterchangeable source gates."""

import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from fatebridge.core.astrology_horary import _applying_aspect
from fatebridge.core.horary_event_paths import evaluate_event_paths
from fatebridge.core.horary_events import (
    BODIES,
    native_planetary_events,
    solve_planetary_events,
)
from tests.western.test_western_horary_motion import state

FIXTURES = Path(__file__).parents[1] / "fixtures"


def synthetic(positions, speeds, *, acceleration=None, past=30, future=30):
    acceleration = acceleration or {}
    defaults = dict(
        Sun=250, Moon=100, Mercury=14.5, Venus=200, Mars=15.5, Jupiter=330, Saturn=74
    )
    rates = dict(
        Sun=0.1, Moon=12, Mercury=-1.5, Venus=0.2, Mars=0.5, Jupiter=0.01, Saturn=0.02
    )
    defaults.update(positions)
    rates.update(speeds)

    def sample(p, t):
        delta = t - 2451545.0
        a = acceleration.get(p, 0)
        return dict(
            longitude=(defaults[p] + rates[p] * delta + a * delta * delta / 2) % 360,
            speed=rates[p] + a * delta,
            latitude=0.0,
        )

    history = solve_planetary_events(
        2451545.0, sample, past_days=past, future_days=future
    )
    states = {p: state(p, defaults[p], rates[p]) for p in BODIES}
    return history, states


def paths(history, states, a="Mars", b="Saturn"):
    return evaluate_event_paths(history, a, b, "day", states, _applying_aspect)


def test_reference_protocol_and_initial_failed_station_oracle_are_preserved():
    reference = json.loads((FIXTURES / "western-event-paths-horizons.json").read_text())
    assert (
        reference["protocol_sha256"]
        == hashlib.sha256(
            (FIXTURES / "western-event-paths-protocol.json").read_bytes()
        ).hexdigest()
    )
    assert (
        reference["station_refinement_protocol_sha256"]
        == hashlib.sha256(
            (FIXTURES / "western-event-station-reference-refinement.json").read_bytes()
        ).hexdigest()
    )
    assert (
        reference["production_imports"] is False
        and reference["initial_expected_retained"] is True
    )
    assert [len(c["expected"]) for c in reference["cases"]] == [49, 57]
    assert all(
        len(c["samples"]) == 7 and len(c["raw_responses"]) == 7
        for c in reference["cases"]
    )


@pytest.mark.parametrize(
    "positions,speeds,expected_aspect",
    [
        (
            {"Mars": 7, "Saturn": 12, "Sun": 6},
            {"Mars": 0.5, "Saturn": 0.03, "Sun": 1},
            "conjunction",
        ),
        (
            {"Mars": 7, "Saturn": 15, "Sun": 65},
            {"Mars": 0.5, "Saturn": 0.03, "Sun": 1},
            "sextile",
        ),
    ],
)
def test_lilly_p111_printed_overtaking_positions_have_actual_order(
    positions, speeds, expected_aspect
):
    # The book supplies positions and qualitative speeds; these rates are an
    # analytical realization, not historical ephemerides supplied by Lilly.
    history, states = synthetic(positions, speeds)
    result = paths(history, states)
    pattern = next(
        p for p in result["prohibition_patterns"] if p["interposer"] == "Sun"
    )
    first, second = pattern["first_contact"], pattern["second_contact"]
    assert first["aspect"] == second["aspect"] == expected_aspect
    direct = next(p for p in result["paths"] if p["mode"] == "direct")
    assert first["root_bracket_tt"][1] < second["root_bracket_tt"][0]
    assert second["root_bracket_tt"][1] < direct["future_contact"]["root_bracket_tt"][0]
    assert (
        next(
            c
            for c in direct["conditions"]
            if c["code"] == "no_selected_prohibition_pattern"
        )["passed"]
        is False
    )


def test_lilly_refranation_is_a_real_reversal_before_contact_not_a_speed_extrapolation():
    history, states = synthetic(
        {"Mars": 7, "Saturn": 12},
        {"Mars": 0.8, "Saturn": 0.02},
        acceleration={"Mars": -0.2},
    )
    pattern = next(
        p
        for p in paths(history, states)["refranation_patterns"]
        if p["applicant"] == "Mars"
    )
    assert pattern["station"]["julian_day_tt"] == 2451549.0
    assert pattern["station"]["direction"] == -1


def test_a_station_exactly_on_a_scan_boundary_is_not_lost():
    def sample(p, t):
        return (
            dict(longitude=(10 + (t - 0.125) ** 2) % 360, speed=2 * (t - 0.125))
            if p == "Mercury"
            else dict(longitude=150.0, speed=0.0)
        )

    result = solve_planetary_events(
        0, sample, past_days=0, future_days=0.25, bodies=("Mercury", "Saturn")
    )
    stations = [e for e in result["events"] if e["kind"] == "station"]
    assert len(stations) == 1 and stations[0]["julian_day_tt"] == 0.125


def test_two_contacts_inside_one_cell_are_split_at_relative_speed_reversal():
    def sample(p, t):
        return (
            dict(longitude=(0.001 - (t - 0.0625) ** 2) % 360, speed=-2 * (t - 0.0625))
            if p == "Mercury"
            else dict(longitude=0.0, speed=0.0)
        )

    result = solve_planetary_events(
        0, sample, past_days=0, future_days=0.125, bodies=("Mercury", "Saturn")
    )
    contacts = [e for e in result["events"] if e["kind"] == "contact"]
    assert len(contacts) == 2
    assert [e["julian_day_tt"] for e in contacts] == pytest.approx(
        [0.0625 - math.sqrt(0.001), 0.0625 + math.sqrt(0.001)], abs=1e-11
    )
    assert [e["direction"] for e in contacts] == [1, -1]


def test_tangent_contact_and_continuous_exact_contact_are_not_ordinary_crossings():
    def tangent(p, t):
        return (
            dict(longitude=(t - 0.0625) ** 2, speed=2 * (t - 0.0625))
            if p == "Mercury"
            else dict(longitude=0.0, speed=0.0)
        )

    result = solve_planetary_events(
        0, tangent, past_days=0, future_days=0.125, bodies=("Mercury", "Saturn")
    )
    contacts = [e for e in result["events"] if e["kind"] == "contact"]
    assert (
        len(contacts) == 1
        and contacts[0]["topology"] == "relative_station_contact_unresolved"
    )
    result = solve_planetary_events(
        0,
        lambda p, t: dict(longitude=t, speed=1.0),
        past_days=0,
        future_days=0.125,
        bodies=("Mercury", "Saturn"),
    )
    assert result["unresolved_intervals"] and not any(
        e["kind"] == "contact" for e in result["events"]
    )


def test_p111_structural_translation_does_not_satisfy_p126_principal_separation():
    history, states = synthetic(
        {"Mercury": 16, "Mars": 15, "Saturn": 20, "Moon": 345},
        {"Mercury": 1.5, "Mars": 0.5, "Saturn": 0.02},
    )
    row = next(
        p
        for p in paths(history, states)["paths"]
        if p["mode"] == "translation" and p["actors"] == ["Mars", "Mercury", "Saturn"]
    )
    assert row["prior_carrier_contact"]["bodies"] == ["Mercury", "Mars"]
    condition = next(
        c
        for c in row["conditions"]
        if c["code"] == "principals_separating_from_prior_ray_at_question"
    )
    assert (
        condition["passed"] is False and row["sequence_conditions_satisfied"] is False
    )


def test_non_lunar_translation_can_satisfy_named_sequence_conditions_without_full_judgement():
    history, states = synthetic({}, {})
    row = next(
        p
        for p in paths(history, states)["paths"]
        if p["mode"] == "translation" and p["actors"] == ["Mars", "Mercury", "Saturn"]
    )
    assert row["sequence_conditions_satisfied"] is True
    assert row["full_path_accepted"] is False
    assert row["prior_principal_contact"]["aspect"] == "sextile"
    assert row["prior_carrier_contact"]["aspect"] == "conjunction"
    assert row["future_contact"]["aspect"] == "sextile"
    assert (
        row["prior_principal_contact"]["julian_day_tt"]
        < row["prior_carrier_contact"]["julian_day_tt"]
        < 2451545
        < row["future_contact"]["julian_day_tt"]
    )
    r = row["event_receptions"][0]
    assert r["reception"]["receiver"] == "Mars" and r["reception"]["guest"] == "Mercury"
    assert r["reception"]["guest_longitude"] != states["Mercury"]["longitude"]


def test_an_intervening_body_cannot_be_skipped_to_select_a_favourable_recipient():
    history, states = synthetic({"Moon": 102}, {})
    result = paths(history, states)
    assert not any(
        p["mode"] == "translation" and p["actors"] == ["Mars", "Mercury", "Saturn"]
        for p in result["paths"]
    )


def test_absence_and_native_failure_are_unknown_not_a_negative_full_judgement():
    history, states = synthetic({}, {}, past=0.1, future=0.1)
    direct = next(p for p in paths(history, states)["paths"] if p["mode"] == "direct")
    assert direct["future_contact"] is None
    assert (
        next(
            c
            for c in direct["conditions"]
            if c["code"] == "first_future_principal_contact_in_window"
        )["passed"]
        is None
    )
    result = evaluate_event_paths(
        {"status": "unavailable"}, "Mars", "Saturn", "day", states, _applying_aspect
    )
    assert result["status"] == "unavailable" and result["paths"] == []
    assert (
        native_planetary_events(SimpleNamespace(zodiac_type="Tropic"))["status"]
        == "unavailable"
    )
    assert (
        native_planetary_events(SimpleNamespace(julian_day_tt=2451545.0))["status"]
        == "unavailable"
    )


@pytest.mark.parametrize("invalid", [math.inf, math.nan])
def test_nonfinite_motion_is_rejected(invalid):
    with pytest.raises(ValueError, match="finite"):
        solve_planetary_events(
            0,
            lambda p, t: dict(longitude=0.0, speed=invalid),
            past_days=0,
            future_days=1,
            bodies=("Mercury", "Saturn"),
        )


def test_overlapping_next_event_brackets_keep_the_target_as_unknown_not_alphabetical_choice():
    history, states = synthetic({}, {})
    target = next(
        e
        for e in history["events"]
        if e["kind"] == "contact"
        and e["bodies"] == ["Mercury", "Saturn"]
        and e["epoch_relation"] == "future"
    )
    other = deepcopy(target)
    other["bodies"] = ["Moon", "Mercury"]
    other["states"]["Moon"] = other["states"].pop("Saturn")
    other["state_brackets"]["Moon"] = other["state_brackets"].pop("Saturn")
    index = history["events"].index(target)
    history["events"].insert(index, other)
    path = next(
        p
        for p in paths(history, states)["paths"]
        if p["mode"] == "translation" and p["actors"] == ["Mars", "Mercury", "Saturn"]
    )
    assert (
        next(
            c
            for c in path["conditions"]
            if c["code"] == "carrier_next_contact_is_recipient_before_other_planets"
        )["passed"]
        is None
    )
    assert path["sequence_conditions_satisfied"] is None


def test_reception_degree_boundary_preserves_unknown_and_guaranteed_positive_separately():
    history, states = synthetic({}, {})
    event = {
        "kind": "contact",
        "bodies": ["Mars", "Saturn"],
        "julian_day_tt": 2451546.0,
        "root_bracket_tt": [2451546.0, math.nextafter(2451546.0, math.inf)],
        "epoch_relation": "future",
        "topology": "crossing",
        "aspect": "conjunction",
        "states": {},
        "state_brackets": {},
    }
    for p in event["bodies"]:
        event["states"][p] = dict(longitude=26.0, speed=0.5, latitude=0.0)
        event["state_brackets"][p] = [
            dict(longitude=math.nextafter(26.0, 0), speed=0.5, latitude=0.0),
            dict(longitude=math.nextafter(26.0, math.inf), speed=0.5, latitude=0.0),
        ]
    history["events"] = [event]
    direct = next(p for p in paths(history, states)["paths"] if p["mode"] == "direct")
    receipts = {r["reception"]["receiver"]: r for r in direct["event_receptions"]}
    assert receipts["Saturn"]["boundary_uncertainty"] is True
    assert receipts["Saturn"]["reception"]["receives"] is None
    assert receipts["Mars"]["boundary_uncertainty"] is True
    assert receipts["Mars"]["reception"]["receives"] is True
