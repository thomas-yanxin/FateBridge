"""锁定西占行星本质尊贵（庙旺落陷）判定。

仅古典七曜（日月水金火木土）有本质尊贵：入庙(domicile)、入旺(exaltation)、
落陷(detriment=庙之对宫)、失势(fall=旺之对宫)。此星座级摘要不计算三分、界、面，
不能将其余情况称为peregrine。天王 /
海王 / 冥王及交点无古典本质尊贵，记为 None。
"""

import pytest

from fatebridge.core.astro.parts import _essential_dignity
from fatebridge.core.astrology_tables import _opposite_sign


@pytest.mark.parametrize(
    "planet, sign, expected",
    [
        ("Sun", "Leo", "rulership"),
        ("Sun", "Aquarius", "detriment"),
        ("Sun", "Aries", "exaltation"),
        ("Sun", "Libra", "fall"),
        ("Moon", "Cancer", "rulership"),
        ("Moon", "Taurus", "exaltation"),
        ("Mars", "Aries", "rulership"),
        ("Mars", "Scorpio", "rulership"),
        ("Mars", "Libra", "detriment"),  # 命主火星天秤
        ("Mars", "Capricorn", "exaltation"),
        ("Mars", "Cancer", "fall"),
        ("Mercury", "Sagittarius", "detriment"),  # 命主水星射手
        ("Jupiter", "Gemini", "detriment"),  # 命主木星双子
        ("Saturn", "Taurus", "no_major_dignity"),
        ("Venus", "Aquarius", "no_major_dignity"),
    ],
)
def test_classical_dignities(planet, sign, expected):
    result = _essential_dignity(planet, sign)
    assert result is not None
    assert result["dignity"] == expected


@pytest.mark.parametrize("planet", ["Uranus", "Neptune", "Pluto", "North Node"])
def test_non_classical_bodies_have_no_dignity(planet):
    assert _essential_dignity(planet, "Aquarius") is None


def test_status_zh_labels():
    assert _essential_dignity("Mars", "Libra")["status_zh"] == "陷"
    assert _essential_dignity("Sun", "Leo")["status_zh"] == "庙"
    assert _essential_dignity("Sun", "Aries")["status_zh"] == "旺"
    assert _essential_dignity("Mars", "Cancer")["status_zh"] == "弱"


def test_opposite_sign():
    assert _opposite_sign("Aries") == "Libra"
    assert _opposite_sign("Libra") == "Aries"
    assert _opposite_sign("Pisces") == "Virgo"
