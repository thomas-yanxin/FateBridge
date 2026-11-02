"""Exact circular arithmetic and the documented Equal-MC anchor."""

import math
from decimal import Decimal, localcontext

import pytest

from fatebridge.core.astro.parts import _build_houses
from fatebridge.utils.house_systems import house_system_fields, normalize_house_system


@pytest.mark.parametrize(
    "anchor",
    [
        math.nextafter(240.0, 0),
        math.nextafter(360.0, 0),
        math.nextafter(0.0, -math.inf),
        0.0,
        15.0,
    ],
)
def test_equal_house_rotation_preserves_the_exact_input_side_of_zero(anchor):
    result = _build_houses(anchor, "equal")
    with localcontext() as ctx:
        ctx.prec = 1100
        for i, record in enumerate(result):
            exact = (Decimal.from_float(anchor) + Decimal(30 * i)) % Decimal(360)
            if exact < 0:
                exact += 360
            value = record["cusp_longitude"]
            assert 0 <= value < 360
            assert abs(value - float(exact)) <= math.ulp(float(exact))
            assert int(Decimal.from_float(value) // 30) == int(exact // 30)


def test_frozen_half_ulp_counterexample_retains_pisces_not_aries():
    record = _build_houses(math.nextafter(240.0, 0), "equal")[4]
    assert record["cusp_longitude"] == math.nextafter(360.0, 0)
    assert record["sign"] == "Pisces"


def test_whole_sign_does_not_underflow_a_tiny_negative_ascendant_to_aries():
    assert (
        _build_houses(math.nextafter(0.0, -math.inf), "whole_sign")[0]["cusp_longitude"]
        == 330
    )


@pytest.mark.parametrize("mc", [0.0, 17.0, 150.125, 270.0, math.nextafter(240.0, 0)])
def test_equal_mc_anchors_the_tenth_cusp_rather_than_the_house_center(mc):
    houses = _build_houses(77.0, "equal_mc", midheaven=mc)
    assert houses[9]["cusp_longitude"] == mc
    assert houses[0]["cusp_longitude"] != 77.0
    assert (
        house_system_fields("D")["house_system_label_zh"] == "天顶为第10宫宫头的等宫制"
    )


def test_historical_mislabel_is_input_compatible_but_never_the_canonical_name():
    assert normalize_house_system("天顶为10宫中点等宫制") == "D"
    assert normalize_house_system("天顶为第10宫宫头的等宫制") == "D"
    assert "宫头" in house_system_fields("D")["house_system_label_zh"]
