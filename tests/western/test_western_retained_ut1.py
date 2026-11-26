"""Source UT1 must reach rotation without becoming its displayed JD float."""

import json
from datetime import datetime
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.earth_attitude import physical_equator
from fatebridge.core.astro.iers_ut1 import use_ut1_source
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant
from tests.support.c04_clock import CLOCK, assert_clock_point

PATH = Path(__file__).parents[1] / "data/ut1_retained_source_v1.json"
ROWS = json.loads(PATH.read_text())["rows"]


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row["id"])
def test_c04_clock_and_inverse_preserve_the_retained_epoch_pair(row) -> None:
    with use_ut1_source("iers_c04"):
        scales = ephemeris_time(datetime.fromisoformat(row["utc"]))
        reference = CLOCK["utc"][row["utc"].removesuffix("+00:00")]
        assert scales.tt.days == Fraction(row["source_tt_exact"])
        assert scales.tt.days == Fraction(reference["tt"])
        assert_clock_point(scales.ut1.days, reference["ut1"])
        assert scales.ut1.days != Fraction(scales.jd_ut1)
        assert scales.jd_ut1.hex() == row["projection_ut1_hex"]
        original = UT1Instant(Fraction(row["source_ut1_exact"]))
        primary = PhysicalEpoch.from_ut1(original)
        inverse = CLOCK["nominal_inverse"][row["id"]]
        assert original.days == Fraction(inverse["ut1"])
        assert primary.time.ut1 == original
        assert_clock_point(primary.time.tt.days, inverse["tt"])
        recovered = PhysicalEpoch.from_ut1(scales.ut1)
        assert recovered.time.ut1 == scales.ut1
        assert abs(recovered.time.tt.days - scales.tt.days) * 86400 <= Fraction(
            CLOCK["gate_seconds"]
        )
        forward = PhysicalEpoch.from_tt(TTInstant(Fraction(row["source_tt_exact"])))
        assert forward.time.ut1 == scales.ut1


@pytest.mark.parametrize(
    "row", [r for r in ROWS if "source_gast_hex" in r], ids=lambda row: row["id"]
)
def test_physical_equator_keeps_source_and_explicit_ieee_contracts_distinct(
    row,
) -> None:
    with use_ut1_source("iers_c04"):
        scales = ephemeris_time(datetime.fromisoformat(row["utc"]))
        retained = physical_equator(runtime.swe, scales.ut1, julian_day_tt=scales.tt)
        projected = physical_equator(
            runtime.swe, scales.jd_ut1, julian_day_tt=scales.tt
        )
        reference = CLOCK["gast"][row["source_tt_exact"]]
        assert retained.ut1 == scales.ut1
        assert retained.ut1 != projected.ut1
        assert projected.ut1.days == Fraction(float.fromhex(row["projection_ut1_hex"]))
        assert retained.greenwich_sidereal_degrees.hex() == reference["retained"]
        assert (
            projected.greenwich_sidereal_degrees.hex()
            == reference["ieee"]
            == row["explicit_ieee_gast_hex"]
        )
