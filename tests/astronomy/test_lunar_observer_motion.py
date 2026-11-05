"""Independent AD/DE441 math and source transactions; no prediction samples."""

import hashlib
import json
import math
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime
from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro import ephemeris, lunar_motion, lunar_observer, runtime
from fatebridge.core.astro.motion_source_window import observed_windows
from fatebridge.core.astro.source_session import source_session
from fatebridge.core.compressed_ephemeris import (
    audit_compressed_endpoints,
    preserve_native_observer_sample_context,
)
from fatebridge.utils.errors import EphemerisSourceError
from tests.jyotish.test_jyotish_sources import data18, restore_runtime  # noqa: F401

FIXTURES = Path(__file__).parents[2] / "tests/fixtures"
SOURCE_PATH = FIXTURES / "lunar-observer-source-reference-v1.json"
DIRECTION_PATH = FIXTURES / "lunar-observer-directional-reference-v1.json"
SOURCE = json.loads(SOURCE_PATH.read_text())
DIRECTION = json.loads(DIRECTION_PATH.read_text())
OWNED = json.loads((FIXTURES / "jyotish-lunar-owned-window-reference.json").read_text())
AS = 180 / math.pi * 3600


def test_reference_identity_and_all_original_failed_gates_remain():
    assert hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest() == (
        "044ad401a4b4a4f7e74e34fce8a3d08d2b1804e8dfaf0f189540a7eb53e7eb86"
    )
    assert hashlib.sha256(DIRECTION_PATH.read_bytes()).hexdigest() == (
        "60098642bc9ccdd60f4d4922ad6f03ab7122bcf075775898af4204cb7e8c4f60"
    )
    assert len(SOURCE["rows"]) == 64 and len(DIRECTION["rows"]) == 192
    assert SOURCE["summary"]["original112_failed"] == 2
    assert SOURCE["summary"]["original96_passed"] == 64
    assert SOURCE["summary"]["new_physical_reference_passes"] == 0
    assert SOURCE["summary"]["human_events"] == 0
    assert not SOURCE["producer_imports_FateBridge_or_Swiss"]
    assert not SOURCE["candidate_used_to_generate_reference"]
    assert SOURCE["summary"]["zero_observer_mutant_rejected_rows"] == 64


@pytest.mark.parametrize(
    "row", SOURCE["rows"], ids=lambda r: f'{r["job_id"]}:{r["clock"]}:{r["frame"]}'
)
def test_beta_jacobian_matches_independent_forward_ad(row):
    position, derivative = lunar_motion.aberration_beta_jvp(
        row["preaberration_position"],
        row["observer_beta"],
        row["observer_beta_derivative"],
    )
    radius = math.hypot(*row["expected_apparent_position"])
    assert math.dist(position, row["expected_apparent_position"]) / radius * AS <= 1e-6
    assert math.dist(derivative, row["expected_beta_JVP"]) / radius * AS <= 1e-6


@pytest.mark.parametrize(
    "row", SOURCE["rows"], ids=lambda r: f'{r["job_id"]}:{r["clock"]}:{r["frame"]}'
)
def test_source_remainder_matches_independent_complete_fixed_derivative(row):
    pre = [*row["preaberration_position"], *row["preaberration_velocity"]]
    native = [*row["native_apparent_position"], *row["native_apparent_velocity"]]
    correction, policy = lunar_observer.fixed_frame_source_remainder(
        pre,
        native,
        row["observer_velocity"],
        row["observer_beta"],
        row["observer_beta_derivative"],
        row["light_time_derivative"],
        row["prior_light_correction_degrees_per_day"],
        row["prior_spatial_correction_degrees_per_day"],
    )
    assert (
        abs(correction - row["expected_source_remainder_degrees_per_day"]) * 3600
        <= 1e-6
    )
    assert (
        abs(
            policy["full_fixed_frame_longitude_speed_degrees_per_day"]
            - row["expected_full_fixed_longitude_rate_degrees_per_day"]
        )
        * 3600
        <= 1e-6
    )
    assert policy["source_position_reproduction_arcsec"] <= 1e-7
    assert (
        math.dist(
            policy["full_fixed_frame_apparent_position_au"],
            row["expected_apparent_position"],
        )
        <= 1e-12
    )
    assert (
        math.dist(
            policy["full_fixed_frame_velocity_au_per_native_argument_day"],
            row["expected_full_fixed_velocity"],
        )
        <= 1e-12
    )


@pytest.mark.parametrize(
    "row",
    DIRECTION["rows"],
    ids=lambda r: f'{r["job_id"]}:{r["clock"]}:{r["direction"]}:{r["step_days"]}',
)
def test_every_direction_and_step_matches_raw_de441_acceleration(row):
    acceleration = lunar_observer.acceleration_from_velocities(
        row["sample_velocities"], row["step_days"], row["direction"]
    )
    assert math.dist(acceleration, row["expected_acceleration"]) <= 1e-10


@pytest.mark.parametrize(
    "bounds,expected",
    [
        ((-1.0, 1.0), "central"),
        ((0.0, 1.0), "forward"),
        ((-1.0, 0.0), "backward"),
        ((-1e-5, 1e-5), None),
        ((1.0, 2.0), None),
        ((math.nan, 1.0), None),
    ],
)
def test_direction_is_chosen_only_by_source_coverage(bounds, expected):
    epoch = 2451545.0
    assert (
        lunar_observer.select_source_stencil(
            epoch, epoch + bounds[0], epoch + bounds[1]
        )
        == expected
    )


@pytest.mark.parametrize("bad", ["shape", "nan", "superluminal", "zero_position"])
def test_beta_derivative_rejects_invalid_inputs(bad):
    p, b, db = [1.0, 2.0, 3.0], [0.0001, 0.0002, 0.0003], [0.000001, 0.000002, 0.000003]
    if bad == "shape":
        db.pop()
    elif bad == "nan":
        db[0] = math.nan
    elif bad == "superluminal":
        b[0] = 2.0
    else:
        p = [0.0, 0.0, 0.0]
    with pytest.raises(EphemerisSourceError):
        lunar_motion.aberration_beta_jvp(p, b, db)


@pytest.mark.parametrize("row", OWNED["rows"], ids=lambda r: r["date_tt"])
def test_actual_owned_boundary_cohort_restores_exact_center_and_source(row):
    e.configure_ephemeris_path(str(Path(__file__).resolve().parents[2] / "ephe"))
    context = {}
    tt = row["jd_tt"]
    with audit_compressed_endpoints(), source_session() as session:
        state, model = ephemeris._swisseph_planet_state(
            "Moon",
            tt,
            julian_day_tt=tt,
            motion_metadata=context,
            source_trace=session.trace,
        )
    policy = context["lunar_light_time"]["fixed_frame_source_derivative"]
    assert model == "swieph" and policy["status"] == "applied"
    assert policy["center_native_states_reproduced_exactly"] is True
    assert policy["center_file_context_reproduced_exactly"] is True
    assert policy["complete_moving_frame_derivative_certified"] is False
    assert policy["native_binary_arithmetic_identity_certified"] is False
    assert (
        state["longitude_speed_lunar_source_remainder_correction"]
        == policy["longitude_speed_correction"]
    )
    assert policy["observer_derivative_disagreement_arcsec_per_day"] <= 1e-6
    samples = {s["epoch_jd_tt"]: s for s in policy["acceleration_samples"]}
    assert len(samples) == policy["sample_count"] + 1
    assert sum(s["is_center"] for s in samples.values()) == 1
    for step, estimate in zip(
        policy["acceleration_steps_days"], policy["acceleration_estimates_au_per_day2"]
    ):
        velocities = [
            samples[tt + offset * step]["velocity_au_per_native_argument_day"]
            for offset in policy["stencil_offsets"]
        ]
        reproduced = tuple(
            math.fsum(
                w * v[i] for w, v in zip(policy["stencil_integer_weights"], velocities)
            )
            / (policy["stencil_divisor"] * step)
            for i in range(3)
        )
        assert reproduced == tuple(estimate)


@pytest.mark.parametrize(
    "problem", ["flags", "model", "nan", "epoch", "body", "restore"]
)
def test_auxiliary_faults_propagate_and_restore_managed_sidereal_mode(
    problem, monkeypatch
):
    e.configure_ephemeris_path(str(Path(__file__).resolve().parents[2] / "ephe"))
    original = runtime.ephemeris_call
    tt = 2451545.0
    original("set_sid_mode", e.swe.SIDM_LAHIRI, 0, 0)
    flags = e.swe.FLG_SWIEPH | e.swe.FLG_SPEED | e.swe.FLG_SIDEREAL
    expected = original("calc", tt, e.swe.MOON, flags)
    sampled = False

    def inject(operation, *args, **kwargs):
        nonlocal sampled
        auxiliary = operation == "calc" and args[1] == e.swe.EARTH and args[0] != tt
        if auxiliary:
            sampled = True
            if problem == "epoch":
                return original(operation, args[0] + 1 / 8, *args[1:], **kwargs)
            if problem == "body":
                return original(operation, args[0], e.swe.MOON, *args[2:], **kwargs)
        values = original(operation, *args, **kwargs)
        if auxiliary and problem in {"flags", "model", "nan"}:
            data, returned = values
            if problem == "flags":
                return data, returned & ~e.swe.FLG_SPEED
            if problem == "model":
                return data, (returned & ~7) | e.swe.FLG_MOSEPH
            return (math.nan, *data[1:]), returned
        if (
            problem == "restore"
            and sampled
            and operation == "calc"
            and args[0] == tt
            and args[1] == e.swe.EARTH
        ):
            data, returned = values
            return (data[0] + 1e-12, *data[1:]), returned
        return values

    monkeypatch.setattr(runtime, "ephemeris_call", inject)
    with pytest.raises(EphemerisSourceError):
        with audit_compressed_endpoints(), source_session() as session:
            ephemeris._swisseph_planet_state(
                "Moon", tt, julian_day_tt=tt, source_trace=session.trace
            )
    assert sampled
    assert original("calc", tt, e.swe.MOON, flags) == expected


@pytest.mark.parametrize("violation", ["body", "time", "truepos", "frame"])
def test_positive_context_rejects_every_other_coordinate_contract(violation):
    e.configure_ephemeris_path(str(Path(__file__).resolve().parents[2] / "ephe"))
    epoch = 2451545.0
    e.ephemeris_call("calc", epoch, e.swe.MOON, e.swe.FLG_SWIEPH | e.swe.FLG_SPEED)
    at, body = epoch + 1 / 1024, e.swe.EARTH
    flags = (
        e.swe.FLG_SWIEPH
        | e.swe.FLG_SPEED
        | e.swe.FLG_XYZ
        | e.swe.FLG_TRUEPOS
        | e.swe.FLG_SIDEREAL
        | e.swe.FLG_BARYCTR
    )
    if violation == "body":
        body = e.swe.MOON
    elif violation == "time":
        at += 1 / 1024
    elif violation == "truepos":
        flags &= ~e.swe.FLG_TRUEPOS
    else:
        flags &= ~e.swe.FLG_SIDEREAL
    with pytest.raises(EphemerisSourceError) as error:
        with preserve_native_observer_sample_context(
            epoch, epoch + 1 / 1024, "swieph", native=ephemeris_runtime.swe
        ):
            e.ephemeris_call("calc", at, body, flags)
    assert error.value.reason == "observer_source_window_incoherent"


@pytest.mark.parametrize("direction", ["central", "forward", "backward"])
def test_actual_native_window_edges_use_the_predeclared_direction_and_restore(
    direction,
):
    e.configure_ephemeris_path(str(Path(__file__).resolve().parents[2] / "ephe"))
    runtime.ephemeris_call(
        "calc",
        2451545.0,
        e.swe.MOON,
        e.swe.FLG_SWIEPH | e.swe.FLG_SPEED | e.swe.FLG_TRUEPOS,
    )
    windows = observed_windows()
    lower, upper = max(w[1] for w in windows), min(w[2] for w in windows)
    epoch = {
        "central": 2451545.0,
        "forward": lower + 1 / 8192,
        "backward": upper - 1 / 8192,
    }[direction]
    runtime.ephemeris_call(
        "set_sid_mode", e.swe.SIDM_USER | e.swe.SIDBIT_ECL_T0, epoch, 0.0
    )

    def sample(at, body, *, barycentric, factor, kind="geometric"):
        flags = e.swe.FLG_SWIEPH | e.swe.FLG_SPEED | e.swe.FLG_XYZ | e.swe.FLG_SIDEREAL
        if barycentric:
            flags |= e.swe.FLG_BARYCTR
        if kind == "geometric":
            flags |= e.swe.FLG_TRUEPOS
        if kind == "preaberration":
            flags |= e.swe.FLG_NOABERR
        data, returned = runtime.ephemeris_call("calc", at, body, flags)
        assert e.ephemeris_model_from_retflag(returned) == "swieph"
        return tuple(data), int(returned)

    try:
        geo, _ = sample(epoch, e.swe.MOON, barycentric=False, factor="geo")
        earth = sample(epoch, e.swe.EARTH, barycentric=True, factor="earth")
        tau_prime = (
            math.fsum(x * v for x, v in zip(geo[:3], geo[3:]))
            / math.hypot(*geo[:3])
            / lunar_motion.LIGHT_SPEED_AU_PER_DAY
        )
        remainder, policy = lunar_observer.lunar_observer_remainder(
            epoch, "swieph", sample, earth, tau_prime, 0.0, 0.0
        )
        assert remainder is not None and policy["status"] == "applied"
        assert policy["selected_stencil"] == direction
        assert policy["center_native_states_reproduced_exactly"] is True
        assert policy["center_file_context_reproduced_exactly"] is True
        assert observed_windows() == windows
    finally:
        runtime.ephemeris_call("set_sid_mode", e.swe.SIDM_LAHIRI, 0.0, 0.0)


def test_nonconvergent_acceleration_retains_only_the_verified_prior_terms(monkeypatch):
    e.configure_ephemeris_path(str(Path(__file__).resolve().parents[2] / "ephe"))
    original = runtime.ephemeris_call
    tt = 2451545.0
    altered = False

    def inject(operation, *args, **kwargs):
        nonlocal altered
        values = original(operation, *args, **kwargs)
        if (
            not altered
            and operation == "calc"
            and args[1] == e.swe.EARTH
            and args[0] != tt
        ):
            altered = True
            data, returned = values
            return (*data[:3], data[3] + 1e-5, *data[4:]), returned
        return values

    monkeypatch.setattr(runtime, "ephemeris_call", inject)
    context = {}
    with audit_compressed_endpoints(), source_session() as session:
        state, _ = ephemeris._swisseph_planet_state(
            "Moon",
            tt,
            julian_day_tt=tt,
            source_trace=session.trace,
            motion_metadata=context,
        )
    policy = context["lunar_light_time"]["fixed_frame_source_derivative"]
    assert altered and policy["status"] == "not_applied"
    assert policy["reason"] == "observer_acceleration_not_converged"
    assert policy["center_native_states_reproduced_exactly"] is True
    assert len(policy["acceleration_estimates_au_per_day2"]) == 2
    assert "selected_step_days" not in policy
    assert "longitude_speed_lunar_source_remainder_correction" not in state
    assert state["longitude_speed"] == (
        state["longitude_speed_native"]
        + state["longitude_speed_light_time_correction"]
        + state["longitude_speed_spatial_aberration_correction"]
        + state["longitude_speed_rotation_correction"]
    )


def test_physical_file_change_during_sampling_is_never_a_partial_success(
    data18, monkeypatch
):
    _, directory = data18
    original = runtime.ephemeris_call
    changed = False
    tt = 2451545.0

    def inject(operation, *args, **kwargs):
        nonlocal changed
        value = original(operation, *args, **kwargs)
        if (
            not changed
            and operation == "calc"
            and args[1] == e.swe.EARTH
            and args[0] != tt
        ):
            changed = True
            path = directory / "semo_18.se1"
            with path.open("r+b") as f:
                f.seek(-1, 2)
                last = f.read(1)
                f.seek(-1, 2)
                f.write(bytes([last[0] ^ 1]))
        return value

    monkeypatch.setattr(runtime, "ephemeris_call", inject)
    with pytest.raises(EphemerisSourceError) as error:
        with audit_compressed_endpoints(), source_session() as session:
            ephemeris._swisseph_planet_state(
                "Moon", tt, julian_day_tt=tt, source_trace=session.trace
            )
    assert changed
    assert "changed" in error.value.reason
    assert error.value.as_result()["retryable"] is False


def test_four_component_reuse_keeps_source_remainder_without_recalculating(monkeypatch):
    from fatebridge.core.astro import longitude_motion
    from fatebridge.core.astro.zodiac import native_lahiri_positions

    e.configure_ephemeris_path(str(Path(__file__).resolve().parents[2] / "ephe"))
    context = {}
    state, model = ephemeris._swisseph_planet_state(
        "Moon", 2451545.0, julian_day_tt=2451545.0, motion_metadata=context
    )
    fields = [
        "longitude_speed_light_time_correction",
        "longitude_speed_spatial_aberration_correction",
        "longitude_speed_lunar_source_remainder_correction",
    ]

    def forbidden(*args, **kwargs):
        raise AssertionError("An already computed physical correction must be reused")

    monkeypatch.setattr(longitude_motion, "lunar_light_time_correction", forbidden)
    lahiri = native_lahiri_positions(
        ["Moon"],
        julian_day_ut1=2451545.0,
        julian_day_tt=2451545.0,
        motion_metadata=context,
        lunar_adjustments={
            "Moon": (state[fields[0]], model, state[fields[1]], state[fields[2]])
        },
    )["Moon"]
    assert all(lahiri[name] == state[name] for name in fields)
    assert "longitude_speed_rotation_correction" not in lahiri
    assert lahiri["longitude_speed"] == (
        lahiri["longitude_speed_native"]
        + lahiri[fields[0]]
        + lahiri[fields[1]]
        + lahiri[fields[2]]
    )
