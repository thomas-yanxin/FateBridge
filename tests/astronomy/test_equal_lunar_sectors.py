"""Exact supplied-longitude sector identity, independent of physical accuracy.

Equal27 and equal28 overlays are numerical partitions. They do not replace
Guolao's separately named unequal right-ascension mansion boundaries.
"""

import math
from decimal import Decimal, localcontext

import pytest

from fatebridge.core.astro import chart as core_chart
from fatebridge.core.astro.geometry import _nakshatra, _su28
from fatebridge.core.astro.reference import NAKSHATRAS, SU28
from fatebridge.core.jyotish import jyotish
from fatebridge.core.sukuyo.astronomy import apply_equatorial_mansions


@pytest.mark.parametrize("count", [27, 28])
def test_every_equal_sector_boundary_and_neighbor_has_the_exact_input_identity(
    count: int,
) -> None:
    with localcontext() as context:
        context.prec = 1200  # Also retain the subnormal neighbor just below0.
        for boundary in range(count + 1):
            value = 360 * boundary / count
            for longitude in (
                math.nextafter(value, -math.inf),
                value,
                math.nextafter(value, math.inf),
            ):
                reduced = Decimal.from_float(longitude) % 360
                if reduced < 0:
                    reduced += 360
                else:
                    pass
                index = int(reduced * count // 360)
                if count == 27:
                    assert _nakshatra(longitude) == NAKSHATRAS[index]
                    assert _nakshatra(longitude) == jyotish.nakshatra(longitude)["name"]
                else:
                    assert _su28(longitude) == SU28[index]


@pytest.mark.parametrize("longitude", [40, 80, 120, 160, 200, 240, 280, 320])
def test_exact_forty_degree_multiples_enter_the_next_nakshatra(longitude: int) -> None:
    assert _nakshatra(longitude) == NAKSHATRAS[longitude * 27 // 360]


@pytest.mark.parametrize("longitude", [90, 180, 270])
def test_exact_quarter_turns_enter_the_next_equal28_mansion(longitude: int) -> None:
    assert _su28(longitude) == SU28[longitude * 28 // 360]


def test_modern_unequal_projection_replaces_equal_degrees_and_clears_unassigned_points() -> (
    None
):
    chart = {
        "objects": [
            {"id": "Sun", "su28": "斗", "su28_degree": 0},
            {"id": "South Node", "su28": "井", "su28_degree": 0},
        ]
    }
    astronomy = {
        "bodies": [
            {
                "id": "Sun",
                "right_ascension": 123,
                "declination": 4,
                "mansion": {
                    "su28": "井宿",
                    "degree_in_mansion": 32.2,
                    "mansion_width": 40,
                    "boundary_distance": 7.8,
                },
            }
        ]
    }
    apply_equatorial_mansions(chart, astronomy)
    assert chart["objects"][0]["su28"] == "井"
    assert chart["objects"][0]["su28_degree"] == 32.2
    assert chart["objects"][0]["su28_width"] == 40
    assert "su28" not in chart["objects"][1]
    assert "su28_degree" not in chart["objects"][1]
