"""A circle offset's branch cut cannot add a turn per day to every planet."""

import json
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.astro.geometry import native_lahiri_ayanamsha
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.time_scales import EphemerisTime, ut1_from_tt
from fatebridge.core.predictive.native_chart import build_native_subject

FIXTURE = Path(__file__).parent / "data/astro/lahiri_wrap"
PLAN = json.loads((FIXTURE / "protocol.json").read_text())


@pytest.mark.parametrize("tt", PLAN["tt_epochs"])
def test_native_offset_rate_is_a_circle_difference_and_preserves_retrograde(tt):
    epoch = PhysicalEpoch(
        EphemerisTime(None, ut1_from_tt(tt), tt, "controlled TT input", False),
        None,
        None,
        False,
    )
    args = dict(
        name="fictional circle control",
        physical_epoch=epoch,
        longitude=0,
        latitude=40,
        timezone_name="UTC",
        house_system="R",
    )
    tropical = build_native_subject(**args)
    sidereal = build_native_subject(**args, zodiac_type="Sidereal")
    upper = native_lahiri_ayanamsha(julian_day_tt=tt + 0.5)
    lower = native_lahiri_ayanamsha(julian_day_tt=tt - 0.5)
    expected = float((Fraction(upper) - Fraction(lower) + 180) % 360 - 180)
    actual = sidereal.calculation_basis["longitude_motion"][
        "display_longitude_offset_speed_degrees_per_day"
    ]
    assert (
        abs(actual - expected) <= PLAN["same_build_arithmetic_line_degrees_per_tt_day"]
    )
    for name in ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"):
        t = getattr(tropical, name.lower())
        s = getattr(sidereal, name.lower())
        assert abs(s.speed - (t.speed - expected)) <= 2e-12
        assert s.retrograde == (s.speed < 0)
    assert sidereal.saturn.retrograde and sidereal.saturn.speed < 0
    assert PLAN["independent_astronomy"] is False
