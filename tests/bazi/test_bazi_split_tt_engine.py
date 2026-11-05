"""Split TT retains sub-JD motion and matches original SPK kernel vectors."""

import math
from pathlib import Path

import pytest

from fatebridge.core import de440_solar
from fatebridge.core.astro.tt_epoch import TTInstant

ROOT = Path(__file__).resolve().parents[2]


def test_time_smaller_than_a_scalar_jd_ulp_reaches_the_actual_orbit():
    day, fraction = 2457754.0, 0.501
    following = fraction + 1e-10
    assert day + fraction == day + following
    assert de440_solar.solar_longitude_parts(
        day, fraction
    ) != de440_solar.solar_longitude_parts(day, following)


def test_full_split_root_bracket_is_preserved_without_scalar_reassembly():
    result = de440_solar.longitude_crossing_tt_parts(285, 2457754.5, 2457765.5)
    low, high = (TTInstant.from_parts(*p) for p in result["tt_bracket_parts"])
    root = TTInstant.from_parts(*result["tt_parts"])
    assert low.days <= root.days <= high.days
    assert 0 < result["bracket_seconds"] < 0.000001
    assert result["numerical_resolution_is_physical_accuracy"] is False


@pytest.mark.parametrize("value", [math.inf, math.nan])
def test_nonfinite_fraction_is_rejected_before_any_source_evaluation(value):
    with pytest.raises(ValueError, match="finite"):
        de440_solar.state((0, 3), 0, fractional_day=value)
    with pytest.raises(ValueError, match="finite"):
        de440_solar.solar_longitude_parts(2451545, value)


def test_split_vector_matches_original_kernel_clenshaw_at_record_boundaries():
    SPK = pytest.importorskip("jplephem.spk").SPK

    kernel = SPK.open(str(ROOT / "ephe/solar-de440.bsp"))
    try:
        for pair in ((0, 3), (3, 399), (0, 10)):
            segment = kernel[pair]
            for day in (2414655.0, 2451545.0, 2488432.0):
                for fraction in (0.5, 0.5000000001, -0.0000000001):
                    expected = segment.compute_and_differentiate(day, fraction)
                    actual = de440_solar.state(
                        pair, day - 2451545.0, fractional_day=fraction
                    )
                    assert (
                        max(abs(a - float(b)) for a, b in zip(actual[0], expected[0]))
                        < 0.000001
                    )
                    assert (
                        max(abs(a - float(b)) for a, b in zip(actual[1], expected[1]))
                        < 0.000001
                    )
    finally:
        kernel.close()
