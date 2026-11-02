"""Actual Guolao motion against fixed-TT references and adverse source probes."""

import json
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core import guolao
from fatebridge.core.astro import longitude_motion, lunar_motion, position_motion
from fatebridge.core.astro.time_scales import datetime_from_tt
from fatebridge.utils.errors import EphemerisSourceError
from tests import test_other_chart_physical_sources as shared_sources

ephemeris_files = shared_sources.ephemeris_files
restore_configuration = shared_sources.restore_configuration

REFERENCE = json.loads(
    (
        Path(__file__).parent / "fixtures/astrodice-apparent-position-derivative.json"
    ).read_text()
)
BY_BODY = {
    target["body"]: {
        row["date_tt"]: row for row in target["rows"] if "erfa_display_frame" in row
    }
    for target in REFERENCE["references"]
    if target["body"] in guolao.CN
}
DATES = sorted(set.intersection(*(set(rows) for rows in BY_BODY.values())))


def birth(jd_tt=2451545.0):
    # Swiss's native inverse can return UT1 in the distant future. Use the
    # domain's declared frozen-leap UTC inverse and check the actual TT below.
    return shared_sources.birth(datetime_from_tt(jd_tt))


@pytest.fixture
def physical(ephemeris_files):
    _, path = ephemeris_files
    e.swe.close()
    e.configure_ephemeris_path(str(path))
    return path


@pytest.mark.parametrize("date_tt", DATES)
def test_all_seven_actual_rates_against_preexisting_fixed_tt_reference(
    physical, date_tt
):
    """Prior development evidence, never presented as a new holdout."""
    jd = BY_BODY["Moon"][date_tt]["jd_tt"]
    raw = guolao.positions(birth(jd), observer_geometry=False)
    assert abs(raw["julian_day_tt"] - jd) < 1e-9
    assert raw["models"] == ["swieph"]
    assert len(DATES) == 30
    for name, state in raw["states"].items():
        reference = BY_BODY[name][date_tt]
        assert reference["stencil_difference_arcsec_per_day"] <= 0.002
        expected = reference["erfa_display_frame"]["longitude_speed_degrees_per_day"]
        assert abs(state["longitude_speed"] - expected) * 3600 <= 0.002
        coordinates, _ = e.swe.calc(
            raw["julian_day_tt"],
            getattr(e.swe, name.upper()),
            e.swe.FLG_SWIEPH | e.swe.FLG_SPEED,
        )
        assert state["longitude"] == coordinates[0]
        assert state["latitude"] == coordinates[1]
        assert state["longitude_speed_native"] == coordinates[3]
        assert state["longitude_speed_reference_frame"] == "tropical_ecliptic_of_date"
    policy = raw["longitude_motion"]
    assert set(policy["physical_ephemeris_source"]["by_factor"]) == set(guolao.CN)
    assert policy["lunar_light_time"]["status"] == "applied"
    assert all(
        value["status"] == "applied"
        for value in policy["complete_position_derivatives"].values()
    )


@pytest.mark.parametrize("problem", ["frame", "model", "missing_speed"])
def test_initial_state_and_derivative_probes_enforce_their_contract(
    physical, monkeypatch, problem
):
    original = guolao.runtime.ephemeris_call

    def inject(operation, *args, **kwargs):
        value = original(operation, *args, **kwargs)
        if operation == "calc" and args[1] == e.swe.SUN:
            coordinates, flags = value
            if problem == "missing_speed":
                return coordinates, flags & ~e.swe.FLG_SPEED
            if args[0] != 2451545.0:
                if problem == "frame":
                    return coordinates, flags | e.swe.FLG_TRUEPOS
                return coordinates, (flags & ~e.swe.FLG_SWIEPH) | e.swe.FLG_MOSEPH
        return value

    monkeypatch.setattr(guolao.runtime, "ephemeris_call", inject)
    with pytest.raises(EphemerisSourceError):
        guolao.positions(birth(), observer_geometry=False)


def test_auxiliary_file_change_remains_a_source_failure(physical, monkeypatch):
    original = guolao.runtime.ephemeris_call
    changed = False

    def inject(operation, *args, **kwargs):
        nonlocal changed
        value = original(operation, *args, **kwargs)
        if (
            not changed
            and operation == "calc"
            and args[1] == e.swe.MOON
            and args[2] & e.swe.FLG_XYZ
        ):
            changed = True
            path = physical / "semo_18.se1"
            raw = bytearray(path.read_bytes())
            raw[-1] ^= 1
            path.write_bytes(raw)
        return value

    monkeypatch.setattr(guolao.runtime, "ephemeris_call", inject)
    with pytest.raises(EphemerisSourceError):
        guolao.positions(birth(), observer_geometry=False)
    assert changed


def test_unverified_native_version_keeps_raw_values_with_explicit_status(
    physical, monkeypatch
):
    def unverified(_):
        return "0.0.0-unverified"

    for module in (longitude_motion, lunar_motion, position_motion):
        monkeypatch.setattr(module, "version", unverified)
    raw = guolao.positions(birth(), observer_geometry=False)
    assert all(
        state["longitude_speed"] == state["longitude_speed_native"]
        for state in raw["states"].values()
    )
    policy = raw["longitude_motion"]
    assert policy["tropical_rotation"]["reason"] == "unverified_native_version"
    assert policy["lunar_light_time"]["reason"] == "unverified_native_version"
    assert all(
        value["reason"] == "unverified_native_version"
        for value in policy["complete_position_derivatives"].values()
    )


def test_sidereal_display_does_not_relabel_tropical_motion_or_correct_extras(
    physical, monkeypatch
):
    original = guolao.corrected_longitude_motion
    called = []

    def observe(name, *args, **kwargs):
        called.append(name)
        return original(name, *args, **kwargs)

    monkeypatch.setattr(guolao, "corrected_longitude_motion", observe)
    tropical = guolao.positions(birth(), zodiacal=0, observer_geometry=False)
    sidereal = guolao.positions(birth(), zodiacal=1, observer_geometry=False)
    assert called == list(guolao.CN) * 2
    assert tropical["states"] == sidereal["states"]
    assert tropical["extra"] == sidereal["extra"]
    assert not any("longitude_speed_native" in x for x in sidereal["extra"].values())
    assert (
        sidereal["longitude_motion"]["reference_frame"] == "tropical_ecliptic_of_date"
    )
    for name, state in sidereal["states"].items():
        placed = guolao.body_placement(
            name, state, sidereal["boundaries"], sidereal["ayanamsha"]
        )
        assert placed["longitude"] == state["longitude"]
        assert placed["zodiac_longitude"] != state["longitude"]
