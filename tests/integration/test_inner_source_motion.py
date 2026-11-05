"""Source-branch and transaction guards for the new analytic inner-planet path."""

import math
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro import inner_motion
from fatebridge.core.astro.inner_source import (
    Dual,
    SourceDerivativeUnavailable,
    chebyshev,
    group,
)
from fatebridge.core.astro.jpl_records import source_records
from fatebridge.core.astro.longitude_motion import corrected_longitude_motion
from fatebridge.utils.errors import EphemerisSourceError

FIXTURE = Path(__file__).parents[1] / "data/astrodice/tables/de441-j2000.eph"


@pytest.fixture
def jpl(tmp_path, monkeypatch):
    previous = e.configured_ephemeris_path()
    kernel = tmp_path / FIXTURE.name
    kernel.write_bytes(FIXTURE.read_bytes())
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", kernel.name)
    e.configure_ephemeris_path()
    try:
        yield kernel
    finally:
        monkeypatch.undo()
        e.configure_ephemeris_path(previous if previous is not None else "")


@pytest.mark.parametrize("x", ["-0.5", "0", "0.25"])
def test_dual_clenshaw_carries_the_known_second_derivative(x):
    # 2+3T1-5T2+7T3 = 7-18x-10x^2+28x^3.
    with localcontext() as context:
        context.prec = 70
        t = Decimal(x)
        p, v = chebyshev([2.0, 3.0, -5.0, 7.0], Dual(t, 3))
        assert p.v == 7 - 18 * t - 10 * t * t + 28 * t**3
        assert p.d == 3 * (-18 - 20 * t + 84 * t * t)
        assert v.v == -18 - 20 * t + 84 * t * t
        assert v.d == 3 * (-20 + 168 * t)


def test_fractional_source_epoch_is_not_rounded_to_a_float():
    with source_records(FIXTURE) as reader, localcontext() as context:
        context.prec = 70
        epoch = Decimal.from_float(2451545.0)
        p = group(reader, Dual(epoch, 1), 0)
        shifted = group(reader, Dual(epoch + Decimal("1e-30"), 1), 0)
        assert p[0].v != shifted[0].v
        assert float(epoch) == float(epoch + Decimal("1e-30"))
        assert len(reader.receipts) == 1


def test_exact_polynomial_seam_is_unqualified():
    with source_records(FIXTURE) as reader:
        with pytest.raises(SourceDerivativeUnavailable, match="polynomial_boundary"):
            group(reader, Dual(2451544.5, 1), 0)
        assert reader.evidence()["polynomial_cells"]


def test_source_mutation_is_fatal_after_a_cached_read(tmp_path):
    path = tmp_path / "mutated.eph"
    path.write_bytes(FIXTURE.read_bytes())
    with pytest.raises(EphemerisSourceError, match="changed"):
        with source_records(path) as reader:
            reader.record(Fraction(2451545.0))
            payload = bytearray(path.read_bytes())
            payload[-1] ^= 1
            path.write_bytes(payload)
            reader.record(Fraction(2451545.0))


@pytest.mark.parametrize("body", [e.swe.MERCURY, e.swe.VENUS])
@pytest.mark.parametrize("sidereal", [False, True])
def test_actual_domain_path_preserves_position_and_exposes_complete_rate(
    jpl, body, sidereal
):
    with e.preserve_ephemeris_path():
        e.ephemeris_call("set_sid_mode", e.swe.SIDM_LAHIRI, 0.0, 0.0)
        flags = (
            e.swe.FLG_SWIEPH | e.swe.FLG_SPEED | (e.swe.FLG_SIDEREAL if sidereal else 0)
        )
        raw, returned = e.ephemeris_call("calc", 2451545.123, body, flags)
        metadata = {}
        name = "Mercury" if body == e.swe.MERCURY else "Venus"
        motion = corrected_longitude_motion(
            name, 2451545.123, raw, "jpl", sidereal=sidereal, context=metadata
        )
        policy = metadata["complete_position_derivatives"][
            name + (":lahiri" if sidereal else ":tropical")
        ]
        assert policy["method_id"] == inner_motion.METHOD_ID
        assert policy["status"] == "applied"
        assert policy["center_native_states_reproduced_exactly"]
        assert policy["center_file_context_reproduced_exactly"]
        assert (
            motion["longitude_speed"]
            == policy["complete_display_rate_degrees_per_native_argument_day"]
        )
        assert math.isfinite(motion["longitude_speed_position_derivative_correction"])
        assert policy["sample_count"] == 0
        assert policy["physical_TT_TDB_equivalence_certified"] is False
        assert e.ephemeris_call("calc", 2451545.123, body, flags) == (raw, returned)


@pytest.mark.parametrize("failure", ["unqualified", "fatal"])
def test_failure_restores_the_center_and_retains_its_kind(jpl, monkeypatch, failure):
    epoch = 2451545.123
    with e.preserve_ephemeris_path():
        e.ephemeris_call("set_sid_mode", e.swe.SIDM_LAHIRI, 0.0, 0.0)
        flags = e.swe.FLG_SWIEPH | e.swe.FLG_SPEED | e.swe.FLG_SIDEREAL
        raw, returned = e.ephemeris_call("calc", epoch, e.swe.MERCURY, flags)

        def fail(*args):
            raise (
                SourceDerivativeUnavailable("manufactured_knot")
                if failure == "unqualified"
                else EphemerisSourceError("jpl_kinematics_invalid")
            )

        monkeypatch.setattr(inner_motion, "apparent_source", fail)
        if failure == "fatal":
            with pytest.raises(EphemerisSourceError) as caught:
                inner_motion.complete_inner_rate(
                    "Mercury", epoch, raw, "jpl", sidereal=True
                )
            assert caught.value.reason == "jpl_kinematics_invalid"
        else:
            rate, policy = inner_motion.complete_inner_rate(
                "Mercury", epoch, raw, "jpl", sidereal=True
            )
            assert rate is None and policy["reason"] == "manufactured_knot"
            assert policy["center_native_states_reproduced_exactly"]
            assert policy["source_records"]["atomic_file_read_proven"] is False
        assert e.ephemeris_call("calc", epoch, e.swe.MERCURY, flags) == (raw, returned)


def test_isolated_native_J2000_shortcut_is_never_called_an_analytic_derivative():
    rate, policy = inner_motion.complete_inner_rate(
        "Mercury", 2451545.0, [0.0] * 6, "jpl"
    )
    assert rate is None
    assert policy["reason"] == "isolated_native_J2000_precession_identity_shortcut"
