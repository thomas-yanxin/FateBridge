"""Physical event histories, printed examples and noninterchangeable source gates."""

import hashlib
import json
import math
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

from fatebridge.core.astro.astrology_horary import _applying_aspect
from fatebridge.core.astro.horary_event_paths import evaluate_event_paths
from fatebridge.core.astro.horary_events import (
    BODIES,
    native_planetary_events,
    solve_planetary_events,
)
from tests.unit_test.fixtures.western_event_cases import state

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


def test_reference_protocol_and_initial_failed_station_oracle_are_preserved() -> None:
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
    positions, speeds, expected_aspect: str
) -> None:
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


def test_lilly_refranation_is_a_real_reversal_before_contact_not_a_speed_extrapolation() -> (
    None
):
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


def test_principal_tangent_before_reversal_keeps_refranation_unknown() -> None:
    # The relative longitude is -(t-1/16)^2. It touches conjunction at
    # t=1/16 while both planets remain prograde; Mercury reverses at t=9/16.
    # Treating only crossing roots as contacts would invent "reversal before
    # conjunction". The unclassified tangent must retain unknown judgement.
    history, states = synthetic(
        {"Mercury": 15 - 0.0625**2, "Saturn": 15},
        {"Mercury": 1.125, "Saturn": 1.0},
        acceleration={"Mercury": -2},
        past=0.1,
        future=1,
    )
    contacts = [
        e
        for e in history["events"]
        if e["kind"] == "contact" and set(e["bodies"]) == {"Mercury", "Saturn"}
    ]
    assert len(contacts) == 1
    assert contacts[0]["julian_day_tt"] == 2451545.0625
    assert contacts[0]["topology"] == "relative_station_contact_unresolved"
    result = paths(history, states, "Mercury", "Saturn")
    assert not result["refranation_patterns"]
    condition = next(
        c
        for c in result["paths"][0]["conditions"]
        if c["code"] == "no_selected_refranation_pattern"
    )
    assert condition["passed"] is None


def test_a_station_exactly_on_a_scan_boundary_is_not_lost() -> None:
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


def test_two_contacts_inside_one_cell_are_split_at_relative_speed_reversal() -> None:
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


@pytest.mark.parametrize("ray", [0, 60, 90, 120, 180, 240, 270, 300])
@pytest.mark.parametrize("direction", [-1, 1])
@pytest.mark.parametrize("speed", [2**-20, 1.0])
@pytest.mark.parametrize("origin", [0.1, 123.456789])
@pytest.mark.parametrize("epoch", [0.0, 2451545.0])
def test_contact_root_brackets_retain_supplied_longitude_residual(
    ray: int, direction, speed, origin: float, epoch: float
) -> None:
    nominal_root = epoch + 0.0625

    def sample(planet, at):
        # This supplies controlled binary64 coordinates. Fraction constructs
        # the input trajectory; the independent check below uses Decimal.
        longitude = (
            float(
                (
                    Fraction(origin)
                    + ray
                    + direction
                    * Fraction(speed)
                    * (Fraction(at) - Fraction(nominal_root))
                )
                % 360
            )
            if planet == "Mercury"
            else origin
        )
        return dict(
            longitude=longitude,
            speed=direction * speed if planet == "Mercury" else 0.0,
        )

    history = solve_planetary_events(
        epoch,
        sample,
        past_days=0,
        future_days=0.125,
        bodies=("Mercury", "Saturn"),
    )
    contacts = [e for e in history["events"] if e["kind"] == "contact"]
    assert len(contacts) == 1
    event = contacts[0]
    assert event["ray_degrees"] == ray and event["direction"] == direction
    left, right = event["root_bracket_tt"]
    assert left == right or math.nextafter(left, math.inf) == right
    with localcontext() as context:
        context.prec = 100
        residuals = []
        for at in (left, right):
            residual = (
                Decimal.from_float(sample("Mercury", at)["longitude"])
                - Decimal.from_float(origin)
                - ray
            )
            while residual < -180:
                residual += 360
            while residual >= 180:
                residual -= 360
            residuals.append(residual)
    assert 0 in residuals or (residuals[0] < 0) != (residuals[1] < 0)


def test_tangent_contact_and_continuous_exact_contact_are_not_ordinary_crossings() -> (
    None
):
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


def test_p111_structural_translation_does_not_satisfy_p126_principal_separation() -> (
    None
):
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


def test_non_lunar_translation_can_satisfy_named_sequence_conditions_without_full_judgement() -> (
    None
):
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


def test_an_intervening_body_cannot_be_skipped_to_select_a_favourable_recipient() -> (
    None
):
    history, states = synthetic({"Moon": 102}, {})
    result = paths(history, states)
    assert not any(
        p["mode"] == "translation" and p["actors"] == ["Mars", "Mercury", "Saturn"]
        for p in result["paths"]
    )


def test_absence_and_native_failure_are_unknown_not_a_negative_full_judgement() -> None:
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


def test_event_search_releases_unpublished_policies_and_keeps_question_receipts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import gc
    import weakref

    from fatebridge.core.astro import horary_events as events

    class Policy:
        pass

    at = 2451545.0
    observed = []

    def state(
        planet,
        *,
        julian_day_tt,
        motion_metadata,
        source_trace,
        correct_motion: bool = True,
        include_declination: bool = True,
    ):
        assert correct_motion is include_declination is (julian_day_tt == at)
        metadata = motion_metadata if motion_metadata is not None else {}
        policy = Policy()
        metadata.setdefault("sample_policies", {})[planet] = policy
        observed.append((julian_day_tt, weakref.ref(policy)))
        return {
            "longitude": 42.0 + (julian_day_tt - at) / 10,
            "latitude": 0.0,
            "longitude_speed": 0.1,
        }, "moshier"

    def search(epoch, sample):
        for step in range(1, 9):
            for planet in events.BODIES:
                value = sample(planet, epoch + step / 8)
                assert value["speed"] == 0.1
                assert value["longitude"] == 42.0 + step / 80
        gc.collect()
        assert all(ref() is None for epoch, ref in observed if epoch != at)
        return {
            "question_states": {p: sample(p, epoch) for p in events.BODIES},
            "events": [],
        }

    monkeypatch.setattr(events, "_swisseph_planet_state", state)
    monkeypatch.setattr(events, "solve_planetary_events", search)
    result = events.native_planetary_events(
        SimpleNamespace(julian_day_tt=at, zodiac_type="Tropic")
    )
    gc.collect()
    assert len(observed) == 9 * len(events.BODIES)
    assert sum(ref() is not None for _, ref in observed) == len(events.BODIES)
    assert set(result["longitude_motion"]["sample_policies"]) == set(events.BODIES)
    assert set(result["question_states"]) == set(events.BODIES)


@pytest.mark.parametrize("invalid", [math.inf, math.nan])
def test_nonfinite_motion_is_rejected(invalid) -> None:
    with pytest.raises(ValueError, match="finite"):
        solve_planetary_events(
            0,
            lambda p, t: dict(longitude=0.0, speed=invalid),
            past_days=0,
            future_days=1,
            bodies=("Mercury", "Saturn"),
        )


def test_overlapping_next_event_brackets_keep_the_target_as_unknown_not_alphabetical_choice() -> (
    None
):
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


def test_reception_degree_boundary_preserves_unknown_and_guaranteed_positive_separately() -> (
    None
):
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


@pytest.mark.parametrize("quantity", ["default", "full", "narrow"])
@pytest.mark.parametrize("source_failure", [None, "required", "equatorial"])
def test_shared_state_declination_choice_preserves_motion_and_required_sources(
    monkeypatch: pytest.MonkeyPatch, quantity: str, source_failure: str | None
) -> None:
    from contextlib import nullcontext

    from fatebridge.core.astro import ephemeris
    from fatebridge.utils.errors import EphemerisSourceError

    # Given coordinate operands isolate quantity admission, not sky accuracy.
    at = 2451545.0
    ecliptic = (42.0, 1.0, 1.0, 0.25, 0.0, 0.0)
    equatorial = (84.0, -12.0, 1.0, 0.0, 0.0, 0.0)
    calls, motions, sources = [], [], []
    trace = SimpleNamespace(
        observe=lambda planet, model: sources.append((planet, model))
    )
    context = {}
    native = ephemeris.runtime.swe
    assert native is not None

    def calculate(operation, epoch, body, flags):
        calls.append((operation, epoch, body, flags))
        assert (operation, epoch, body) == ("calc", at, native.MARS)
        if flags & native.FLG_EQUATORIAL:
            if source_failure == "equatorial":
                raise EphemerisSourceError("coordinate_model_changed")
            else:
                pass
            return equatorial, 2050
        else:
            pass
        if source_failure == "required":
            raise EphemerisSourceError("changed_during")
        else:
            pass
        return ecliptic, 258

    def motion(planet, epoch, coordinates, model, *, source_trace, context):
        assert source_trace is trace
        motions.append((planet, epoch, coordinates, model))
        return {
            "longitude_speed": 0.375,
            "longitude_speed_native": 0.25,
            "longitude_speed_position_derivative_correction": 0.125,
        }

    monkeypatch.setattr(ephemeris.runtime, "preserve_ephemeris_path", nullcontext)
    monkeypatch.setattr(native, "set_ephe_path", lambda path: None)
    monkeypatch.setattr(ephemeris.runtime, "ephemeris_call", calculate)
    monkeypatch.setattr(ephemeris, "corrected_longitude_motion", motion)
    options = (
        {} if quantity == "default" else {"include_declination": quantity == "full"}
    )
    requested = quantity != "narrow"
    if source_failure == "required" or (source_failure == "equatorial" and requested):
        with pytest.raises(EphemerisSourceError) as error:
            ephemeris._swisseph_planet_state(
                "Mars",
                julian_day_tt=at,
                source_trace=trace,
                motion_metadata=context,
                **options,
            )
        assert error.value.reason == (
            "changed_during"
            if source_failure == "required"
            else "coordinate_model_changed"
        )
    else:
        result, model = ephemeris._swisseph_planet_state(
            "Mars",
            julian_day_tt=at,
            source_trace=trace,
            motion_metadata=context,
            **options,
        )
        expected = {
            "longitude": 42.0,
            "latitude": 1.0,
            "longitude_speed": 0.375,
            "longitude_speed_native": 0.25,
            "longitude_speed_position_derivative_correction": 0.125,
        }
        if requested:
            expected["declination"] = -12.0
        else:
            pass
        assert result == expected
        assert model == "swieph"
    expected_flags = (
        [258, 2050] if requested and source_failure != "required" else [258]
    )
    assert [call[3] for call in calls] == expected_flags
    assert motions == (
        [] if source_failure == "required" else [("Mars", at, ecliptic, "swieph")]
    )
    assert sources == [("Mars", "swieph")] * (
        0
        if source_failure == "required"
        else 2 if requested and source_failure is None else 1
    )


@pytest.mark.parametrize("history", ["planetary", "lunar"])
def test_event_samplers_keep_question_declination_and_original_motion_policy(
    monkeypatch: pytest.MonkeyPatch, history: str
) -> None:
    from fatebridge.core.astro import horary_events, horary_motion

    module = horary_events if history == "planetary" else horary_motion
    at, later = 2451545.0, 2451546.0
    observed = []

    def supplied(
        planet,
        *,
        julian_day_tt,
        source_trace,
        motion_metadata,
        correct_motion=True,
        include_declination=True,
    ):
        observed.append((planet, julian_day_tt, correct_motion, include_declination))
        return {
            "longitude": 42.0,
            "latitude": 1.0,
            "longitude_speed": 0.25,
        }, "moshier"

    def search(epoch, sample):
        assert epoch == at
        body = "Sun" if history == "planetary" else "Moon"
        assert sample(body, epoch)["speed"] == 0.25
        expected = {"longitude": 42.0, "latitude": 1.0, "speed": 0.25}
        if history == "planetary":
            expected["speed_display_offset_correction"] = -0.0
        else:
            pass
        assert sample(body, later) == expected
        if history == "planetary":
            return {
                "question_states": {p: sample(p, epoch) for p in BODIES},
                "events": [],
            }
        else:
            pass
        return {
            "contacts": [],
            "ambiguous_boundary_contacts": [],
            "sign_exit_julian_day_tt": later,
        }

    monkeypatch.setattr(module, "_swisseph_planet_state", supplied)
    monkeypatch.setattr(
        module,
        "solve_planetary_events" if history == "planetary" else "solve_lunar_contacts",
        search,
    )
    # Date delivery is outside this supplied sampler control, and stays unknown.
    monkeypatch.setattr(module, "utc_from_tt", lambda epoch: (None, None))
    subject = SimpleNamespace(julian_day_tt=at, zodiac_type="Tropic")
    result = (
        module.native_planetary_events(subject)
        if history == "planetary"
        else module.native_lunar_contacts(subject)
    )
    if history == "planetary":
        assert observed == [(p, at, True, True) for p in BODIES] + [
            ("Sun", later, False, False)
        ]
        assert set(result["question_states"]) == set(BODIES)
    else:
        assert observed == [("Moon", at, True, True), ("Moon", later, False, False)]
        assert (
            result["future_speed_policy"]["question_epoch_complete_motion_retained"]
            is True
        )
    assert result["longitude_frame"] == "tropical_true_ecliptic_of_date"
