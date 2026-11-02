"""Stable geometry may resolve cancellation; exact knots still remain unknown."""

from decimal import Decimal as D

import pytest

from fatebridge.core.astro.solar_decimal import stable_interpolation_cell
from fatebridge.utils.errors import EphemerisSourceError


@pytest.mark.parametrize("impact,cell", [("0.5099999999", 50), ("0.5100000001", 51)])
def test_stable_cross_product_cell_resolves_the_ill_conditioned_dot_margin(
    impact, cell
):
    radius = D("0.00465")
    ratio = D("0.8")
    result = stable_interpolation_cell(D(impact), radius, ratio)
    assert result["cell"] == cell
    assert result["status"] == "interior_sampled_cell"
    old_margin = 64 * D.from_float(2.0**-52) / (radius * radius * D(impact))
    assert old_margin > abs(D(impact) - D("0.51"))
    assert D.from_float(result["arithmetic_margin_fraction"]) < abs(
        D(impact) - D("0.51")
    )


@pytest.mark.parametrize("impact", ["0", "0.51", "0.5100000000001", "1"])
def test_a_knot_or_unresolved_margin_does_not_authorize_a_fit(impact):
    result = stable_interpolation_cell(D(impact), D("0.00465"), D("0.8"))
    assert result["cell"] is None and result["status"] == "boundary_ambiguous"


def test_invalid_geometry_cannot_become_a_source_cell():
    with pytest.raises(EphemerisSourceError):
        stable_interpolation_cell(D("-0.1"), D("0.00465"), D("0.8"))
