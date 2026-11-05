"""Geocentric TT events do not consume out-of-range Earth-rotation data."""

import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from fatebridge.core.astro import geometry, runtime
from fatebridge.core.astro.ephemeris import _swisseph_planet_state
from fatebridge.core.astro.iers_ut1 import C04Table, use_ut1_source
from fatebridge.core.horary_motion import native_lunar_contacts

FIXTURE = Path(__file__).parent / "data/astro/tt_events"
PROTOCOL = json.loads((FIXTURE / "protocol.json").read_text())
REFERENCE = json.loads(gzip.decompress((FIXTURE / "reference.json.gz").read_bytes()))


def refuse_ut1(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError("Pure TT ephemeris must not consume UT1")

    monkeypatch.setattr(C04Table, "ut1_from_tt", reject)
    monkeypatch.setattr(C04Table, "tt_from_ut1", reject)
    native = runtime.ephemeris_call

    def ephemeris(operation, *args, **kwargs):
        if operation in {"calc_ut", "deltat", "deltat_ex", "get_ayanamsa_ex_ut"}:
            reject()
        return native(operation, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", ephemeris)


def test_external_corpus_remains_predeclared_and_not_a_production_oracle():
    from scripts.audit_western_tt_events import validate_reference_identity

    validate_reference_identity(FIXTURE)
    assert REFERENCE["production_imports"] is False
    assert (
        REFERENCE["protocol_sha256"]
        == hashlib.sha256((FIXTURE / "protocol.json").read_bytes()).hexdigest()
    )
    assert PROTOCOL["comparison_tolerance_arcseconds"] == 0.02
    assert PROTOCOL["comparison_tolerance_event_seconds"] == 30
    assert PROTOCOL["real_world_outcomes"] == 0
    assert not PROTOCOL["full_original_text_acceptance"]


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda r: r["case_id"])
@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
def test_native_lunar_search_without_any_trial_ut1(case, zodiac, monkeypatch):
    refuse_ut1(monkeypatch)
    with use_ut1_source("iers_c04"):
        value = native_lunar_contacts(
            SimpleNamespace(
                julian_day_tt=case["start_julian_day_tt"], zodiac_type=zodiac
            )
        )
    assert value["status"] == "computed", value
    assert value["time_scale"] == "TT"
    assert value["constant_velocity_projection"] is False
    assert value["longitude_frame"] == (
        "sidereal_lahiri" if zodiac == "Sidereal" else "tropical_true_ecliptic_of_date"
    )
    if zodiac == "Tropic":
        expected = case["expected"]
        assert value["void_of_course"] == expected["void_of_course"]
        assert (
            abs(value["sign_exit_julian_day_tt"] - expected["sign_exit_julian_day_tt"])
            * 86400
            <= PROTOCOL["comparison_tolerance_event_seconds"]
        )
        assert [(c["other"], c["ray_degrees"]) for c in value["contacts"]] == [
            (c["other"], c["ray_degrees"]) for c in expected["contacts"]
        ]
        for actual, reference in zip(value["contacts"], expected["contacts"]):
            assert (
                abs(actual["julian_day_tt"] - reference["julian_day_tt"]) * 86400
                <= PROTOCOL["comparison_tolerance_event_seconds"]
            )


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda r: r["case_id"])
@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
def test_planetary_sampler_uses_tt_outside_both_edges(case, zodiac, monkeypatch):
    # Probe the real sampler at distant trial epochs. The full +/-30-day
    # histories are retained separately by audit_western_tt_events.py.
    from fatebridge.core import horary_events

    refuse_ut1(monkeypatch)
    probes = []

    def probe(start, sample):
        for delta in (-31, 0, 31):
            probes.append({p: sample(p, start + delta) for p in horary_events.BODIES})
        return dict(status="computed", question_states=probes[1], events=[])

    monkeypatch.setattr(horary_events, "solve_planetary_events", probe)
    with use_ut1_source("iers_c04"):
        value = horary_events.native_planetary_events(
            SimpleNamespace(
                julian_day_tt=case["start_julian_day_tt"], zodiac_type=zodiac
            )
        )
    assert value["status"] == "computed", value
    assert len(probes) == 3
    assert all(len(row) == 7 for row in probes)
    assert value["longitude_motion"]["display_frame"] == (
        "sidereal_lahiri" if zodiac == "Sidereal" else "tropical_true_ecliptic_of_date"
    )


@pytest.mark.parametrize("epoch", [None, float("nan"), float("inf")])
def test_tt_helper_requires_a_real_finite_epoch(epoch):
    with pytest.raises(ValueError):
        _swisseph_planet_state("Moon", julian_day_tt=epoch)
    with pytest.raises(ValueError):
        geometry.native_lahiri_ayanamsha(julian_day_tt=epoch)
