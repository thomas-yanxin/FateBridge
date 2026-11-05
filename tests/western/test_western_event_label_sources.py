"""Formatting carriers exercise source failures, not astronomical root accuracy."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from fatebridge.core import horary_events, horary_motion
from fatebridge.utils.errors import EphemerisSourceError
from tests.support.reference_data import verify_source_files

FIX = Path(__file__).parents[1] / "data/astro/event_label_sources"
PLAN = json.loads((FIX / "protocol.json").read_text())
MODULES = {"planetary": horary_events, "lunar": horary_motion}


def install_carriers(monkeypatch):
    # The real nominal native sampler and its provenance remain active. These
    # explicitly synthetic packets only reach the later UTC-formatting boundary.
    def planetary(start, sample):
        states = {p: sample(p, start) for p in horary_events.BODIES}
        event = dict(
            kind="contact",
            bodies=["Sun", "Moon"],
            julian_day_tt=start + 0.25,
            root_bracket_tt=[start + 0.25, start + 0.25],
            epoch_relation="future",
            states={p: states[p] for p in ["Sun", "Moon"]},
            state_brackets={p: [states[p], states[p]] for p in ["Sun", "Moon"]},
            ray_degrees=0,
            direction=1,
            topology="crossing",
            aspect="conjunction",
        )
        return dict(
            status="computed",
            method_id="test_only_synthetic_event_carriers",
            constant_velocity_projection=False,
            time_scale="TT",
            question_julian_day_tt=start,
            window_tt=[start - 1, start + 1],
            scan_step_days=0.125,
            bodies=list(horary_events.BODIES),
            question_states=states,
            events=[event],
            unresolved_intervals=[],
            completeness_scope="Test-only label carrier, not a numerical event search",
            full_original_text_acceptance=False,
            test_only_synthetic_event_carriers=True,
        )

    def lunar(start, sample):
        for planet in ["Moon", *horary_motion.BODIES]:
            sample(planet, start)
        event = dict(
            other="Sun",
            julian_day_tt=start + 0.25,
            root_bracket_tt=[start + 0.25, start + 0.25],
            after_days=0.25,
            aspect="conjunction",
            aspect_label="合",
            angle=0,
            ray_degrees=0,
            orb=0,
            phase="applying",
            applying=True,
        )
        return dict(
            status="computed",
            method_id="test_only_synthetic_event_carriers",
            constant_velocity_projection=False,
            start_julian_day_tt=start,
            sign_exit_julian_day_tt=start + 1,
            sign_exit_root_bracket_tt=[start + 1, start + 1],
            sign_exit_after_days=1,
            degrees_left_in_sign=1,
            contacts=[event],
            ambiguous_boundary_contacts=[],
            void_of_course=False,
            time_scale="TT",
            source_scope="Test-only label carrier, not a numerical event search",
            test_only_synthetic_event_carriers=True,
        )

    monkeypatch.setattr(horary_events, "solve_planetary_events", planetary)
    monkeypatch.setattr(horary_motion, "solve_lunar_contacts", lunar)


def invoke(wrapper, zodiac):
    subject = SimpleNamespace(julian_day_tt=PLAN["start_jd_tt"], zodiac_type=zodiac)
    function = (
        horary_events.native_planetary_events
        if wrapper == "planetary"
        else horary_motion.native_lunar_contacts
    )
    return function(subject)


def labels(value, wrapper):
    return (
        value["events"]
        if wrapper == "planetary"
        else [value, *value["contacts"], *value["ambiguous_boundary_contacts"]]
    )


def test_protocol_is_sealed_and_carriers_are_not_an_astronomical_oracle():
    verify_source_files(FIX)
    assert PLAN["numeric_preservation_tolerance"] == 0
    assert "Synthetic" in PLAN["fault_carriers"]


@pytest.mark.parametrize("wrapper", PLAN["wrappers"])
@pytest.mark.parametrize("zodiac", PLAN["zodiacs"])
@pytest.mark.parametrize("reason", PLAN["source_error_reasons"])
def test_label_source_failure_keeps_original_exception(
    wrapper, zodiac, reason, monkeypatch
):
    install_carriers(monkeypatch)
    failure = EphemerisSourceError(reason)

    def broken(_):
        raise failure

    monkeypatch.setattr(MODULES[wrapper], "utc_from_tt", broken)
    with pytest.raises(EphemerisSourceError) as caught:
        invoke(wrapper, zodiac)
    assert caught.value is failure


@pytest.mark.parametrize("wrapper", PLAN["wrappers"])
@pytest.mark.parametrize("zodiac", PLAN["zodiacs"])
@pytest.mark.parametrize("error_type", [ValueError, OverflowError])
def test_ordinary_label_limit_preserves_computed_tt_events(
    wrapper, zodiac, error_type, monkeypatch
):
    install_carriers(monkeypatch)
    expected = invoke(wrapper, zodiac)

    def broken(_):
        raise error_type("ordinary unsupported civil label")

    monkeypatch.setattr(MODULES[wrapper], "utc_from_tt", broken)
    result = invoke(wrapper, zodiac)
    assert result["status"] == "computed"
    for event in labels(expected, wrapper):
        event["datetime_utc"] = None
    assert result == expected


@pytest.mark.parametrize("wrapper", PLAN["wrappers"])
@pytest.mark.parametrize("zodiac", PLAN["zodiacs"])
def test_valid_nonunique_display_remains_a_missing_label_only(
    wrapper, zodiac, monkeypatch
):
    install_carriers(monkeypatch)
    monkeypatch.setattr(MODULES[wrapper], "utc_from_tt", lambda _: (None, None, False))
    result = invoke(wrapper, zodiac)
    assert (
        result["status"] == "computed" and result["test_only_synthetic_event_carriers"]
    )
    assert all(event["datetime_utc"] is None for event in labels(result, wrapper))
