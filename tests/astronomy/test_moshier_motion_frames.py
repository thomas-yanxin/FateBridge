"""Shared physical rates must follow their actual tropical/Lahiri positions."""

import gzip
import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core import guolao
from fatebridge.core.astro import ephemeris, moshier_motion, runtime, solar_decimal
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.longitude_motion import corrected_longitude_motion
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
from fatebridge.core.astro.solar_decimal import MOSHIER_PLANETS
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
        PLANET_SWISSEPH_IDS[body],
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


@pytest.mark.parametrize("body", sorted(moshier_motion.TARGETS))
@pytest.mark.parametrize("sidereal", [False, True])
def test_nearly_coplanar_native_witnesses_do_not_block_motion(
    analytical, body, sidereal
):
    # Frozen sample from the failed2025-03-15election request. The former
    # inverse failed its unchanged1e-10orthogonality gate at this exact TT.
    epoch = 2460726.3028840744
    original = native(epoch, body, sidereal)
    metadata = {}
    if sidereal:
        state = native_lahiri_positions(
            [body],
            julian_day_ut1=epoch,
            julian_day_tt=epoch,
            motion_metadata=metadata,
        )[body]
    else:
        state, model = ephemeris._swisseph_planet_state(
            body, epoch, julian_day_tt=epoch, motion_metadata=metadata
        )
        assert model == "moshier"
    coarse = fourth_order(epoch, body, sidereal, original[0], 2.0**-7)
    fine = fourth_order(epoch, body, sidereal, original[0], 2.0**-8)
    independent = fine + (fine - coarse) / 15
    assert abs(state["longitude_speed"] - independent) * 3600 < 0.002
    assert state["longitude"] == original[0]
    assert state["latitude"] == original[1]
    assert state["longitude_speed_native"] == original[3]
    frame = "lahiri" if sidereal else "tropical"
    assert (
        metadata["complete_position_derivatives"][body + ":" + frame]["status"]
        == "applied"
    )


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
    assert receipt["status"] == "applied"
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


@pytest.fixture(scope="module")
def published_source_reference():
    directory = Path(__file__).parents[1] / "data/astro/moshier_motion_v1"
    raw = gzip.decompress((directory / "reference.json.gz").read_bytes())
    assert (
        hashlib.sha256(raw).hexdigest()
        == (directory / "reference.json.sha256").read_text().strip()
    )
    reference = json.loads(raw)
    assert len(reference["rows"]) == 2720
    return reference


@pytest.mark.parametrize("body", sorted(MOSHIER_PLANETS))
@pytest.mark.parametrize("sidereal", [False, True])
def test_all_published_source_rates_and_unseen_boundaries(
    analytical, published_source_reference, body, sidereal
):
    """The independent source series includes old failures and new domain probes."""
    frame = "lahiri" if sidereal else "tropical"
    reference = published_source_reference
    for row in reference["rows"]:
        if (row["body"], row["frame"]) != (body, frame):
            continue
        original = native(row["jd_tt"], body, sidereal)
        metadata = {}
        state = corrected_longitude_motion(
            body,
            row["jd_tt"],
            original,
            "moshier",
            sidereal=sidereal,
            context=metadata,
        )
        identity = (row["cohort"], row["epoch_id"], body, frame)
        error = float(
            abs(
                Decimal.from_float(state["longitude_speed"])
                - Decimal(row["expected_rate_degrees_per_TT_day"])
            )
            * 3600
        )
        assert error <= reference["rate_line_arcsec_per_day"], identity
        assert error <= row["original_C_native_speed_error_arcsec_per_day"], identity
        policy = metadata["complete_position_derivatives"][body + ":" + frame]
        assert policy["status"] == "applied", identity
        assert policy["convergence_line_arcsec_per_day"] == 0.0002
        assert state["longitude_speed_native"] == original[3]


@pytest.fixture(scope="module")
def published_sun_reference():
    directory = Path(__file__).parents[1] / "data/astro/moshier_sun_motion_v1"
    raw = gzip.decompress((directory / "reference.json.gz").read_bytes())
    assert (
        hashlib.sha256(raw).hexdigest()
        == (directory / "reference.json.sha256").read_text().strip()
    )
    reference = json.loads(raw)
    assert len(reference["rows"]) == 500
    return reference


@pytest.mark.parametrize("sidereal", [False, True])
def test_all_solar_source_rates_preserve_their_own_optical_dependencies(
    analytical, published_sun_reference, sidereal, monkeypatch
):
    def unrelated_mass_table():
        pytest.fail("The Moshier Sun has no solar self-deflection dependency")

    monkeypatch.setattr(solar_decimal, "mass_profile", unrelated_mass_table)
    frame = "lahiri" if sidereal else "tropical"
    for row in published_sun_reference["rows"]:
        if row["frame"] != frame:
            continue
        original = native(row["epoch"]["jd_tt"], "Sun", sidereal)
        metadata = {}
        state = corrected_longitude_motion(
            "Sun",
            row["epoch"]["jd_tt"],
            original,
            "moshier",
            sidereal=sidereal,
            context=metadata,
        )
        error = float(
            abs(
                Decimal.from_float(state["longitude_speed"])
                - Decimal(row["expected_rate_degrees_per_TT_day"])
            )
            * 3600
        )
        identity = (row["epoch"]["id"], frame)
        assert error <= published_sun_reference["rate_line_arcsec_per_TT_day"], identity
        assert error <= row["original_C_native_speed_error_arcsec_per_day"], identity
        policy = metadata["complete_position_derivatives"]["Sun:" + frame]
        assert policy["status"] == "applied", identity
        assert policy["convergence_line_arcsec_per_day"] == 0.0002
        assert state["longitude_speed_native"] == original[3]


@pytest.fixture(scope="module")
def published_lunar_reference():
    directory = Path(__file__).parents[1] / "data/astro/moshier_lunar_motion_v1"
    raw = gzip.decompress((directory / "reference.json.gz").read_bytes())
    assert (
        hashlib.sha256(raw).hexdigest()
        == (directory / "reference.json.sha256").read_text().strip()
    )
    reference = json.loads(raw)
    assert len(reference["rows"]) == 628
    return reference


@pytest.mark.parametrize("sidereal", [False, True])
def test_full_lunar_source_rates_and_unseen_range_boundaries(
    analytical, published_lunar_reference, sidereal, monkeypatch
):
    def unrelated_mass_table():
        pytest.fail("The geocentric Moshier Moon has no solar-deflection dependency")

    monkeypatch.setattr(solar_decimal, "mass_profile", unrelated_mass_table)
    frame = "lahiri" if sidereal else "tropical"
    for row in published_lunar_reference["rows"]:
        if row["frame"] != frame:
            continue
        epoch = row["epoch"]["jd_tt"]
        original = native(epoch, "Moon", sidereal)
        metadata = {}
        state = corrected_longitude_motion(
            "Moon", epoch, original, "moshier", sidereal=sidereal, context=metadata
        )
        error = float(
            abs(
                Decimal.from_float(state["longitude_speed"])
                - Decimal(row["expected_rate_degrees_per_TT_day"])
            )
            * 3600
        )
        identity = (row["epoch"]["id"], frame)
        assert (
            error <= published_lunar_reference["rate_line_arcsec_per_TT_day"]
        ), identity
        assert error <= row["original_C_native_speed_error_arcsec_per_day"], identity
        assert state["longitude_speed_native"] == original[3]
        receipt = metadata["complete_position_derivatives"]["Moon:" + frame]
        assert receipt["status"] == "applied", identity
        assert receipt["convergence_line_arcsec_per_day"] == 0.0002


@pytest.mark.parametrize("body", sorted(moshier_motion.TARGETS))
@pytest.mark.parametrize("sidereal", [False, True])
@pytest.mark.parametrize("fault", ["rotated", "reflected", "sheared"])
def test_auxiliary_common_frame_must_reproduce_actual_native_basis(
    analytical, monkeypatch, body, sidereal, fault
):
    original = solar_decimal.reference_frames.native_equatorial_frame

    def different_frame(*args):
        matrix = original(*args)
        if fault == "rotated":
            return tuple(
                solar_decimal.reference_frames.rotate(row, "z", 0.001) for row in matrix
            )
        if fault == "reflected":
            return tuple(-value for value in matrix[0]), *matrix[1:]
        return (
            (matrix[0][0] + 0.1, *matrix[0][1:]),
            *matrix[1:],
        )

    monkeypatch.setattr(
        solar_decimal.reference_frames, "native_equatorial_frame", different_frame
    )
    epoch = 2451545.0
    coordinates = native(epoch, body, sidereal)
    with pytest.raises(EphemerisSourceError) as failure:
        moshier_motion.complete_moshier_longitude_rate(
            body, epoch, coordinates, sidereal=sidereal
        )
    assert failure.value.reason == "coordinate_contract_changed"
