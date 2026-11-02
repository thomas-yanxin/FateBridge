"""Shared physical rates must follow their actual tropical/Lahiri positions."""

import math

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core import guolao
from fatebridge.core.astro import ephemeris, moshier_motion, runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.zodiac import native_lahiri_positions
from fatebridge.utils.errors import EphemerisSourceError


@pytest.fixture
def analytical(tmp_path, monkeypatch):
    previous = e.configured_ephemeris_path()
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    e.swe.close()
    e.configure_ephemeris_path(str(tmp_path))
    try:
        yield tmp_path
    finally:
        monkeypatch.undo()
        e.swe.close()
        e.configure_ephemeris_path(previous or "")


def native(epoch, body, sidereal):
    swe = e.swe
    if sidereal:
        runtime.ephemeris_call("set_sid_mode", swe.SIDM_LAHIRI, 0.0, 0.0)
    values, flags = runtime.ephemeris_call(
        "calc",
        epoch,
        moshier_motion.PLANET_SWISSEPH_IDS[body],
        swe.FLG_MOSEPH | swe.FLG_SPEED | (swe.FLG_SIDEREAL if sidereal else 0),
    )
    assert runtime.ephemeris_model_from_retflag(flags) == "moshier"
    return values


def fourth_order(epoch, body, sidereal, center, h):
    values = [
        math.remainder(native(epoch + k * h, body, sidereal)[0] - center, 360)
        for k in (-2, -1, 1, 2)
    ]
    return math.fsum(w * v for w, v in zip((1, -8, 8, -1), values)) / (12 * h)


@pytest.mark.parametrize("year", [1900, 2000, 2020, 2077])
@pytest.mark.parametrize("body", sorted(moshier_motion.TARGETS))
@pytest.mark.parametrize("sidereal", [False, True])
def test_shared_state_matches_position_derivative_in_its_own_frame(
    analytical, year, body, sidereal
):
    epoch = e.swe.julday(year, 1, 15, 12)
    trace = PhysicalEphemerisTrace()
    policy = {}
    if sidereal:
        state = native_lahiri_positions(
            [body],
            julian_day_ut1=epoch,
            julian_day_tt=epoch,
            motion_metadata=policy,
            source_trace=trace,
        )[body]
    else:
        state, model = ephemeris._swisseph_planet_state(
            body,
            epoch,
            julian_day_tt=epoch,
            source_trace=trace,
            motion_metadata=policy,
        )
        assert model == "moshier"
    original = native(epoch, body, sidereal)
    assert state["longitude"] == original[0]
    assert state["latitude"] == original[1]
    assert state["longitude_speed_native"] == original[3]
    coarse = fourth_order(epoch, body, sidereal, original[0], 2.0**-7)
    fine = fourth_order(epoch, body, sidereal, original[0], 2.0**-8)
    independent = fine + (fine - coarse) / 15
    assert abs(state["longitude_speed"] - independent) * 3600 < 0.002
    assert state["longitude_speed"] == (
        state["longitude_speed_native"]
        + state.get("longitude_speed_rotation_correction", 0.0)
        + state.get("longitude_speed_position_derivative_correction", 0.0)
    )
    frame = "lahiri" if sidereal else "tropical"
    receipt = policy["complete_position_derivatives"][body + ":" + frame]
    if "longitude_speed_position_derivative_correction" in state:
        assert receipt["status"] == "applied"
    else:
        # The frozen source contract withholds a nonconverged derivative.
        # This does not waive the independent 0.002 arcsec/day check above.
        assert receipt["status"] == "not_applied"
        assert receipt["reason"] == "position_motion_not_converged"
        assert len(receipt["attempts"]) == 2
        assert all(row["status"] == "not_converged" for row in receipt["attempts"])
    assert receipt["convergence_line_arcsec_per_day"] == 0.0002
    assert receipt["reference_frame"] == (
        "lahiri_sidereal_ecliptic_of_date" if sidereal else "tropical_ecliptic_of_date"
    )
    if sidereal:
        assert "longitude_speed_rotation_correction" not in state
        assert receipt["method_id"] == moshier_motion.SIDEREAL_METHOD_ID
    else:
        assert receipt["method_id"] == moshier_motion.METHOD_ID
    trace.finish()


@pytest.mark.parametrize("problem", ["frame", "model", "nonfinite"])
def test_lahiri_probes_reject_changed_contracts(analytical, monkeypatch, problem):
    epoch = 2451545.0
    coordinates = native(epoch, "Moon", True)
    original = runtime.ephemeris_call

    def perturb(operation, *args, **kwargs):
        value = original(operation, *args, **kwargs)
        if operation == "calc":
            coords, flags = value
            if problem == "frame":
                return coords, flags & ~e.swe.FLG_SIDEREAL
            if problem == "model":
                return coords, (flags & ~e.swe.FLG_MOSEPH) | e.swe.FLG_SWIEPH
            return (math.nan, *coords[1:]), flags
        return value

    monkeypatch.setattr(runtime, "ephemeris_call", perturb)
    with pytest.raises(EphemerisSourceError):
        moshier_motion.complete_moshier_longitude_rate(
            "Moon", epoch, coordinates, sidereal=True
        )


def test_guolao_reuses_shared_tropical_correction_once(analytical, monkeypatch):
    original = moshier_motion.complete_moshier_longitude_rate
    calls = []

    def observe(body, *args, **kwargs):
        calls.append((body, kwargs.get("sidereal", False)))
        return original(body, *args, **kwargs)

    monkeypatch.setattr(moshier_motion, "complete_moshier_longitude_rate", observe)
    birth = build_astro_birth_info(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
    )
    raw = guolao.positions(birth, observer_geometry=False)
    assert calls == [(body, False) for body in guolao.CN]
    for state in raw["states"].values():
        assert state["longitude_speed"] == (
            state["longitude_speed_native"]
            + state.get("longitude_speed_rotation_correction", 0.0)
            + state["longitude_speed_position_derivative_correction"]
        )
