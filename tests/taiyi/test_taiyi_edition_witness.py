"""Tests for Taiyi Vol. 2 computed arithmetic vs Vol. 3 Siku printed-table policy."""

import pytest

from fatebridge.core.metaphysics.taiyi import (
    VOL3_PRINTED_TABLE_OVERRIDES,
    cyclic_core,
    rotate_shiji,
)


@pytest.mark.parametrize(
    "ju,jishen,wenchang,expected_shiji,addends,expected_guest",
    [
        (37, "申", "寅", "坤", [7, 6, 1, 8, 3], 25),
        (43, "寅", "午", "巳", [1], 1),
        (44, "丑", "未", "坤", [7, 6, 1, 8, 3, 4, 9], 38),
    ],
)
def test_vol2_ring_rotation_and_counting_arithmetic(
    ju: int,
    jishen: str,
    wenchang: str,
    expected_shiji: str,
    addends,
    expected_guest: int,
) -> None:
    ring = "子丑艮寅卯辰巽巳午未坤申酉戌乾亥"
    weights = {"乾": 1, "子": 8, "艮": 3, "卯": 4, "巽": 9, "午": 2, "坤": 7, "酉": 6}
    steps = (ring.index(wenchang) - ring.index(jishen)) % 16
    marker = ring[(ring.index("艮") + steps) % 16]
    assert marker == expected_shiji

    computed = cyclic_core(ju, yin=True, table_policy="computed")
    assert computed["shiji"] == marker
    assert computed["guest_count"] == expected_guest
    assert rotate_shiji(wenchang, jishen)["derived_shiji"] == expected_shiji


@pytest.mark.parametrize(
    "yin,ju,overrides",
    [(y, j, o) for (y, j), o in VOL3_PRINTED_TABLE_OVERRIDES.items()],
)
def test_table_policy_switches_between_computed_and_vol3_printed_table(
    yin: bool, ju: int, overrides: dict
) -> None:
    computed = cyclic_core(ju, yin=yin, table_policy="computed")
    printed = cyclic_core(ju, yin=yin, table_policy="printed_table")
    assert printed["table_policy"] == "printed_table"
    assert computed["table_policy"] == "computed"
    for field, expected_value in overrides.items():
        assert printed[field] == expected_value
    assert printed["main_general"] == (
        printed["main_count"] % 10 or printed["main_count"] // 10
    )
    assert printed["guest_general"] == (
        printed["guest_count"] % 10 or printed["guest_count"] // 10
    )
