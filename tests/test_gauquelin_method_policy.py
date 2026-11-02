"""Native controls distinguish a requested flag from the actual observer model."""

import hashlib

import pytest

from fatebridge.core.astro import runtime
from fatebridge.validation.gauquelin import method_profile
from scripts.audit_gauquelin_definitions import (
    BASELINE_POLICY,
    BASELINE_POLICY_SHA256,
    PROTOCOL,
    PROTOCOL_SHA256,
    read_baseline,
)


@pytest.mark.parametrize("method", range(6))
def test_each_method_reports_its_source_defined_observer_and_horizon(method):
    profile = method_profile(method)
    assert profile["requested_topocentric_flag"] is False
    assert profile["observer_origin"] == ("geocentric" if method < 2 else "topocentric")
    assert profile["atmosphere_inputs_used"] == (method in (3, 5))
    assert profile["disk_reference"] == (
        "position_point"
        if method < 2
        else "center" if method in (2, 3) else "upper_limb"
    )
    assert profile["historical_cfepp_method_identified"] is False


@pytest.mark.parametrize("method", [True, False, -1, 6, 2.0, "2", None])
def test_method_selection_does_not_coerce_invalid_definitions(method):
    with pytest.raises(ValueError):
        method_profile(method)


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
@pytest.mark.parametrize("method", range(6))
@pytest.mark.parametrize("body_name", ["MOON", "MARS"])
def test_actual_native_observer_and_atmosphere_follow_the_reported_policy(
    method, body_name
):
    swe = runtime.swe
    body = getattr(swe, body_name)

    def position(*, height=0.0, topo=False, pressure=1013.25, temperature=0.0):
        # These are fictional controls in a test process, never a birth estimate.
        runtime.ephemeris_call("set_topo", 0.0, 45.0, height)
        return runtime.ephemeris_call(
            "gauquelin_sector",
            2451545.0,
            body,
            method,
            (0.0, 45.0, height),
            pressure,
            temperature,
            swe.FLG_MOSEPH | (swe.FLG_TOPOCTR if topo else 0),
        )

    base = position()
    with_flag = position(topo=True)
    raised = position(height=10000.0)
    reduced_pressure = position(pressure=800.0)
    warmer = position(temperature=30.0)
    profile = method_profile(method)
    if profile["observer_origin"] == "geocentric":
        assert base != with_flag
        assert base == raised
    else:
        assert base == with_flag
        assert base != raised
    if profile["atmosphere_inputs_used"]:
        assert base != reduced_pressure and base != warmer
    else:
        assert base == reduced_pressure == warmer


def test_diagnostic_protocol_and_baseline_remain_pinned():
    assert hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() == PROTOCOL_SHA256
    assert (
        hashlib.sha256(BASELINE_POLICY.read_bytes()).hexdigest()
        == BASELINE_POLICY_SHA256
    )
    with pytest.raises(ValueError, match="baseline_hash_mismatch"):
        read_baseline(b'{"rows": []}')
