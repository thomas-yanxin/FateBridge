"""Local refinement retains the convergence line and rejects non-convergence."""

import math

import pytest

from fatebridge.core.astro import position_motion as motion
from fatebridge.utils.errors import EphemerisSourceError
from tests.ephemeris_case_runtime import native_ephemeris_files


class Trace:
    def observe(self, *args, **kwargs):
        return {"model": "swieph"}


@pytest.fixture
def analytical_provider(monkeypatch):
    def install(function):
        def call(operation, epoch, body, flags):
            assert operation == "calc"
            x = epoch - 2451545.0
            return (100.0 + function(x), 0.0, 1.0, 0.4, 0.0, 0.0), flags

        monkeypatch.setattr(motion.runtime, "ephemeris_call", call)
        # This synthetic signal has no light-time rounding. Its physical
        # stabilization is the identity; retarded-state API contracts have
        # separate real-provider tests.
        if hasattr(motion, "stabilized_longitude_sample"):

            def identity(planet, epoch, coordinates, model, **kwargs):
                return 100.0 + function(epoch - 2451545.0), {
                    "epoch_remainder_days": 0.0,
                    "sampling_longitude_shift_arcseconds": 0.0,
                }

            monkeypatch.setattr(motion, "stabilized_longitude_sample", identity)
        monkeypatch.setattr(
            motion, "assert_physical_configuration", lambda selected: None
        )
        # Scalar analytical states carry no physical Sun/Earth interpolation
        # cell. They cannot authorize the source-specific one-sided fallback.
        monkeypatch.setattr(
            motion, "solar_interpolation_branch", lambda *args, **kwargs: {"cell": None}
        )

    return install


def test_seventh_order_signal_refines_to_its_known_derivative(analytical_provider):
    analytical_provider(lambda x: 0.4 * x + 2 * x**7)
    rate, policy = motion.complete_position_rate(
        "Mercury", 2451545.0, (100, 0, 1), "swieph", source_trace=Trace()
    )
    assert len(policy["steps_days"]) > 2
    assert abs(rate - 0.4) * 3600 < 0.0002
    assert policy["convergence_line_arcsec_per_day"] == 0.0002
    assert policy["pair_differences_arcsec_per_day"][0] > 0.0002
    assert policy["step_difference_arcsec_per_day"] <= 0.0002


def test_nondifferentiable_signal_still_fails_after_bounded_refinement(
    analytical_provider,
):
    analytical_provider(lambda x: x * math.log(abs(x)) if x else 0.0)
    with pytest.raises(EphemerisSourceError) as caught:
        motion.complete_position_rate(
            "Mercury", 2451545.0, (100, 0, 1), "swieph", source_trace=Trace()
        )
    assert caught.value.reason == "position_motion_not_converged"


def test_local_polynomial_derivative_preserves_degree_six_exactness():
    for power in range(7):
        values = [x**power for x in motion.LOCAL_NODES]
        # This checks a mathematical identity, independently of ephemeris data.
        expected = 1.0 if power == 1 else 0.0
        value = math.fsum(w * v for w, v in zip(motion.LOCAL_WEIGHTS, values))
        assert abs(value - expected) < 1e-12


def test_real_solar_disc_venus_keeps_guard_and_failed_primary_evidence(
    native_ephemeris_files,
):
    from fatebridge.core.astro import runtime

    epoch = 2460465.5216340744
    state, returned = runtime.ephemeris_call(
        "calc", epoch, runtime.swe.VENUS, runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED
    )
    assert runtime.ephemeris_model_from_retflag(returned) == "swieph"
    rate, policy = motion.complete_position_rate("Venus", epoch, state, "swieph")
    assert math.isfinite(rate)
    assert policy["primary_attempt"]["status"] == "not_converged"
    assert policy["selected_stencil"] == "retarded_epoch_stabilized_sixth_order"
    assert (
        policy["sampling_stabilization"]["unstabilized_attempt"]["status"]
        == "not_converged"
    )
    # The unchanged independent reference pins the number while v5's stronger
    # directional guard rejects the previously selected unstabilized plateau.
    import json
    from pathlib import Path

    reference = json.loads(
        (
            Path(__file__).parent / "fixtures/western-retarded-model-reference.json"
        ).read_text()
    )
    row = next(
        r
        for r in reference["rows"]
        if r["body"] == "Venus"
        and r["julian_day_tt"] == epoch
        and r["frame"] == "Tropic"
    )
    assert (
        abs(rate - float(row["estimates"][-1]["rate_degrees_per_day"])) * 3600 <= 0.002
    )
    assert policy["step_difference_arcsec_per_day"] <= 0.0002
    assert policy["convergence_line_arcsec_per_day"] == 0.0002


def test_future_position_roots_use_native_guard_but_question_keeps_complete_motion(
    monkeypatch,
):
    from types import SimpleNamespace

    from fatebridge.core import horary_motion

    epoch = 2460465.5216340744
    calls = []

    def state(planet, **kwargs):
        calls.append((kwargs["julian_day_tt"], kwargs["correct_motion"]))
        if kwargs["correct_motion"]:
            kwargs["motion_metadata"]["method_id"] = "complete_question_motion"
        return {
            "longitude": 1.0,
            "latitude": 0.0,
            "longitude_speed": 13.0 if planet == "Moon" else 1.0,
        }, "swieph"

    def solve(at, sample):
        sample("Moon", at)
        sample("Venus", at + 0.25)
        return {
            "status": "computed",
            "contacts": [],
            "ambiguous_boundary_contacts": [],
            "sign_exit_julian_day_tt": at + 0.5,
        }

    monkeypatch.setattr(horary_motion, "_swisseph_planet_state", state)
    monkeypatch.setattr(horary_motion, "solve_lunar_contacts", solve)
    result = horary_motion.native_lunar_contacts(
        SimpleNamespace(julian_day_tt=epoch, zodiac_type="Tropic")
    )
    assert calls == [(epoch, True), (epoch + 0.25, False)]
    assert result["future_speed_policy"]["precision_derivative_certified"] is False
    assert result["future_speed_policy"]["constant_velocity_projection"] is False
    assert result["longitude_motion"]["method_id"] == "complete_question_motion"
