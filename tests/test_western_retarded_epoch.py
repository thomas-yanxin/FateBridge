"""Sub-ULP time recovery, withheld numerical steps and physical-source guards.

Numerical self-consistency here is separate from the independent ephemeris
audit. The two near-Sun epochs are development regressions, not blind cases.
"""

import math
from decimal import Decimal, localcontext

import pytest

from fatebridge.core.astro import position_motion, runtime
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.retarded_epoch import (
    epoch_subtraction_remainder,
    stabilized_longitude_sample,
)
from fatebridge.utils.errors import EphemerisSourceError
from tests.ephemeris_case_runtime import (
    native_ephemeris_files_module as native_ephemeris_files_module,
)

pytestmark = pytest.mark.usefixtures("native_ephemeris_files_module")


@pytest.mark.parametrize("epoch", [2451545.0, 2460465.7716340744, 5373484.25])
@pytest.mark.parametrize("delay", [0.0, 0.005003, 0.0123456789])
def test_epoch_parts_recover_the_exact_binary_input_difference(epoch, delay):
    rounded, remainder = epoch_subtraction_remainder(epoch, delay)
    with localcontext() as context:
        context.prec = 80
        expected = Decimal(epoch) - Decimal(delay) - Decimal(rounded)
    assert remainder == float(expected)
    assert abs(remainder) <= math.ulp(epoch) / 2


@pytest.mark.parametrize("epoch,delay", [(math.nan, 0.1), (1.0, -1), (1.0, math.inf)])
def test_bad_epoch_or_delay_is_rejected(epoch, delay):
    with pytest.raises(EphemerisSourceError):
        epoch_subtraction_remainder(epoch, delay)


@pytest.mark.parametrize("sidereal", [False, True])
@pytest.mark.parametrize(
    "body,epoch", [("Venus", 2460465.7716340744), ("Mercury", 2459891.96875)]
)
def test_near_sun_sampling_uses_a_stable_plateau_and_keeps_native_positions(
    body, epoch, sidereal
):
    swe = runtime.swe
    with runtime.preserve_ephemeris_path():
        runtime.ephemeris_call("set_sid_mode", swe.SIDM_LAHIRI, 0.0, 0.0)
        flags = swe.FLG_SWIEPH | swe.FLG_SPEED | (swe.FLG_SIDEREAL if sidereal else 0)
        ident = getattr(swe, body.upper())
        original, returned = runtime.ephemeris_call("calc", epoch, ident, flags)
        model = runtime.ephemeris_model_from_retflag(returned)
        if model not in {"swieph", "jpl"}:
            pytest.skip("Physical Swiss/JPL data required for retarded-epoch audit")
        rate, policy = position_motion.complete_position_rate(
            body, epoch, original, model, sidereal=sidereal
        )
        assert policy["selected_stencil"] == "retarded_epoch_stabilized_sixth_order"
        receipt = policy["sampling_stabilization"]
        assert receipt["consecutive_converged_pairs"] >= 2
        assert receipt["displayed_native_position_changed"] is False
        assert policy["chosen_step_days"] in policy["candidate_steps_days"]
        assert max(policy["pair_differences_arcsec_per_day"][-2:]) <= 0.0002
        assert runtime.ephemeris_call("calc", epoch, ident, flags)[0] == original
        # These finer steps were not involved in choosing the reported rate.
        trace = PhysicalEphemerisTrace()
        for h in (policy["chosen_step_days"] / 2, policy["chosen_step_days"] / 4):
            values = []
            for offset in position_motion.OFFSETS:
                trial = epoch + offset * h
                raw, _ = runtime.ephemeris_call("calc", trial, ident, flags)
                value, _ = stabilized_longitude_sample(
                    body,
                    trial,
                    raw,
                    model,
                    sidereal=sidereal,
                    source_trace=trace,
                    contexts={},
                    factor_prefix=f"withheld_{trial}",
                )
                values.append(value)
            withheld = position_motion.longitude_stencil(values, original[0], h)
            assert abs(withheld - rate) * 3600 <= 0.0002
        trace.finish()


@pytest.mark.parametrize("problem", ["frame", "model", "values", "configuration"])
def test_auxiliary_states_cannot_drift_between_models_or_frames(problem, monkeypatch):
    swe = runtime.swe
    original = runtime.ephemeris_call
    raw, returned = original(
        "calc", 2451545.0, swe.MERCURY, swe.FLG_SWIEPH | swe.FLG_SPEED
    )
    model = runtime.ephemeris_model_from_retflag(returned)
    if model not in {"swieph", "jpl"}:
        pytest.skip("Physical Swiss/JPL data required for retarded-epoch audit")

    def changed(operation, *args, **kwargs):
        values, flags = original(operation, *args, **kwargs)
        if problem == "frame":
            flags ^= swe.FLG_EQUATORIAL
        elif problem == "model":
            flags = (flags & ~(swe.FLG_SWIEPH | swe.FLG_JPLEPH)) | swe.FLG_MOSEPH
        elif problem == "values":
            values = (math.nan,) * 6
        else:
            monkeypatch.setenv("SE_EPHE_PATH", "/controlled-changed-configuration")
        return values, flags

    monkeypatch.setattr(runtime, "ephemeris_call", changed)
    with runtime.preserve_ephemeris_path(), pytest.raises(EphemerisSourceError):
        stabilized_longitude_sample(
            "Mercury",
            2451545.0,
            raw,
            model,
            sidereal=False,
            source_trace=PhysicalEphemerisTrace(),
            contexts={},
            factor_prefix="guard",
        )
