"""Mathematical/domain guards, then frozen independent acceptance fixtures."""

import json
import math
from pathlib import Path

import pytest

from fatebridge.core.astro import ephemeris, position_motion, runtime
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.zodiac import native_lahiri_positions
from fatebridge.utils.errors import EphemerisSourceError
from scripts.audit_astrodice_position_motion import (
    PROTOCOL_SHA256,
    REFERENCE_SHA256,
    digest,
    validate_reference,
)

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "tests/data/astrodice/tables/inner-position-protocol.json"
REFERENCE = ROOT / "tests/data/astrodice/tables/inner-position-reference.json"


@pytest.mark.parametrize("power", range(7))
def test_stencil_differentiates_polynomials_through_degree_six_across_zero(power):
    h = 0.0625

    def f(x):
        return (359.99 + 0.1 * x + x**power) % 360

    values = [f(k * h) for k in position_motion.OFFSETS]
    expected = 0.1 + (1 if power == 1 else 0)
    assert position_motion.longitude_stencil(values, f(0), h) == pytest.approx(
        expected, abs=2e-12
    )


@pytest.mark.parametrize(
    "values,center,step",
    [
        ([0] * 5, 0, 0.0625),
        ([0] * 5 + [math.nan], 0, 0.0625),
        ([0] * 6, math.inf, 0.0625),
        ([0] * 6, 0, 0),
        ([180] * 6, 0, 0.0625),
    ],
)
def test_bad_or_ambiguous_stencil_is_rejected(values, center, step):
    with pytest.raises(EphemerisSourceError):
        position_motion.longitude_stencil(values, center, step)


@pytest.mark.parametrize("sidereal", [False, True])
@pytest.mark.parametrize("body", ["Mercury", "Venus", "Mars", "Sun"])
def test_domain_keeps_raw_rate_full_correction_and_auxiliary_source_scope(
    body, sidereal, monkeypatch
):
    trace = PhysicalEphemerisTrace()
    metadata = {}
    jd = 2451545.0
    original = runtime.ephemeris_call
    auxiliary_epochs = set()
    auxiliary_models = set()

    def observe(operation, *args, **kwargs):
        value = original(operation, *args, **kwargs)
        if (
            operation == "calc"
            and args[1] == position_motion.PLANET_SWISSEPH_IDS[body]
            and args[0] != jd
        ):
            flags = args[2] if len(args) > 2 else 0
            if bool(flags & runtime.swe.FLG_SIDEREAL) == sidereal:
                auxiliary_epochs.add(args[0])
                auxiliary_models.add(runtime.ephemeris_model_from_retflag(value[1]))
        return value

    monkeypatch.setattr(runtime, "ephemeris_call", observe)
    if sidereal:
        state = native_lahiri_positions(
            [body], julian_day_ut1=jd, julian_day_tt=jd, motion_metadata=metadata
        )[body]
    else:
        state, _ = ephemeris._swisseph_planet_state(
            body, jd, julian_day_tt=jd, source_trace=trace, motion_metadata=metadata
        )
        assert set(trace.finish()["by_factor"]) == {body}
    correction = state["longitude_speed_position_derivative_correction"]
    assert (
        state["longitude_speed"]
        == state["longitude_speed_native"]
        + state.get("longitude_speed_rotation_correction", 0)
        + correction
    )
    policy = metadata["complete_position_derivatives"][
        f"{body}:{'lahiri' if sidereal else 'tropical'}"
    ]
    assert policy["status"] == "applied"
    # Validate every actual auxiliary epoch, including the new directional
    # guards, instead of encoding the former two-step implementation count.
    assert auxiliary_epochs
    assert len(policy["source_contexts"]) == len(auxiliary_epochs)
    assert auxiliary_models == {"swieph"}
    assert {row["model"] for row in policy["source_contexts"].values()} == {"swieph"}
    assert policy["step_difference_arcsec_per_day"] <= 0.0002
    if sidereal:
        assert "longitude_speed_rotation_correction" not in state


@pytest.mark.parametrize("problem", ["frame", "model", "nan", "nonconvergence"])
def test_perturbed_probe_cannot_silently_pass_or_fall_back(problem, monkeypatch):
    original = runtime.ephemeris_call
    swe = runtime.swe
    jd = 2451545.0
    center = original("calc", jd, swe.MERCURY, swe.FLG_SWIEPH | swe.FLG_SPEED)[0]

    def inject(op, *args, **kwargs):
        value = original(op, *args, **kwargs)
        if problem == "nonconvergence" and op == "calc" and args[1] == swe.MERCURY:
            state, flags = value
            changed = list(state)
            x = args[0] - jd
            changed[0] = center[0] + (x * math.log(abs(x)) if x else 0)
            return changed, flags
        if op == "calc" and args[1] == swe.MERCURY and args[0] == jd + 0.0625:
            state, flags = value
            if problem == "frame":
                return state, flags | swe.FLG_TRUEPOS
            if problem == "model":
                return state, (flags & ~swe.FLG_SWIEPH) | swe.FLG_MOSEPH
            changed = list(state)
            changed[0] = math.nan if problem == "nan" else changed[0] + 0.001
            return changed, flags
        return value

    monkeypatch.setattr(runtime, "ephemeris_call", inject)
    with pytest.raises(EphemerisSourceError):
        position_motion.complete_position_rate("Mercury", jd, center, "swieph")


@pytest.mark.parametrize("body,model", [("Moon", "swieph"), ("Mercury", "moseph")])
def test_unimplemented_paths_never_claim_a_correction(body, model):
    rate, policy = position_motion.complete_position_rate(
        body, 2451545.0, (0, 0, 1, 0, 0, 0), model
    )
    assert rate is None and policy["status"] == "not_applied"


def test_unknown_version_remains_explicitly_unapplied(monkeypatch):
    monkeypatch.setattr(
        position_motion, "binding_distribution_version", lambda *a: "future"
    )
    rate, policy = position_motion.complete_position_rate(
        "Mercury", 2451545.0, (0, 0, 1, 0, 0, 0), "swieph"
    )
    assert rate is None and policy["reason"] == "unverified_native_version"


def test_reference_raw_bytes_and_full_stencils_are_frozen():
    assert digest(PROTOCOL) == PROTOCOL_SHA256
    assert digest(REFERENCE) == REFERENCE_SHA256
    counts = validate_reference(
        json.loads(PROTOCOL.read_text()), json.loads(REFERENCE.read_text())
    )
    assert counts == {
        "target_epochs": 120,
        "position_probes": 1320,
        "raw_batches": 66,
        "reference_stencil_failures": [],
    }


@pytest.mark.parametrize(
    "problem", ["angle", "time", "target", "stencil", "missing", "raw"]
)
def test_reference_mutations_are_detected(problem):
    protocol = json.loads(PROTOCOL.read_text())
    reference = json.loads(REFERENCE.read_text())
    target = reference["references"][0]
    batch = target["batches"][0]
    if problem == "angle":
        batch["rows"][0]["ra_degrees"] += 1
    elif problem == "time":
        batch["parameters"]["TIME_TYPE"] = "'UT'"
    elif problem == "target":
        target["target_id"] = 1
    elif problem == "stencil":
        target["rows"][0]["icrf_direction_derivative_per_day"][0] += 0.001
    elif problem == "missing":
        target["rows"].pop()
    else:
        batch["raw_response_utf8"] += " "
    with pytest.raises(ValueError):
        validate_reference(protocol, reference)
