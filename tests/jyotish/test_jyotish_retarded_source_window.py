"""Owned derivatives keep their exact center and original convergence line.

These 96 related controls cover 16 file-start groups; independent astronomical
rates are checked separately against frozen NASA/ERFA reference material.
"""

import math
from datetime import date
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro.position_motion import complete_position_rate
from fatebridge.core.astro.source_session import source_session
from fatebridge.core.compressed_ephemeris import audit_compressed_endpoints
from tests.jyotish.test_jyotish_sources import restore_runtime  # noqa: F401


@pytest.mark.parametrize("year", range(600, 9601, 600))
@pytest.mark.parametrize("planet", ["Mercury", "Venus", "Mars"])
@pytest.mark.parametrize("sidereal", [False, True])
def test_owned_derivative_keeps_center_and_fixed_line_at_file_start(
    year, planet, sidereal
):
    e.configure_ephemeris_path(str(Path(__file__).resolve().parents[2] / "ephe"))
    epoch = float(
        Fraction(date(year, 1, 1).toordinal())
        + Fraction(3442849, 2)
        + Fraction(333, 86400000)
    )
    flags = e.swe.FLG_SWIEPH | e.swe.FLG_SPEED
    if sidereal:
        e.ephemeris_call("set_sid_mode", e.swe.SIDM_LAHIRI, 0, 0)
        flags |= e.swe.FLG_SIDEREAL
    with audit_compressed_endpoints(), source_session() as session:
        raw, returned = e.ephemeris_call(
            "calc", epoch, getattr(e.swe, planet.upper()), flags
        )
        assert e.ephemeris_model_from_retflag(returned) == "swieph"
        original = tuple(raw)
        rate, policy = complete_position_rate(
            planet,
            epoch,
            raw,
            "swieph",
            sidereal=sidereal,
            source_trace=session.trace,
        )
        assert rate is not None and math.isfinite(rate)
        assert policy["status"] == "applied"
        assert policy["convergence_line_arcsec_per_day"] == 0.0002
        assert policy["step_difference_arcsec_per_day"] <= 0.0002
        assert tuple(raw) == original
        replay, flags_after = e.ephemeris_call(
            "calc", epoch, getattr(e.swe, planet.upper()), flags
        )
        assert flags_after == returned
        assert tuple(replay) == original
