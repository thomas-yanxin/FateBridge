"""锁定西占元素 / 模式平衡排除月亮交点（虚点）。

交点是计算虚点，且引擎只排北交、不排南交，计入会造成不对称偏置，故元素 /
模式平衡只统计行星本体；交点仍保留在 planets 列表中，并以 balance_basis
标明统计口径。
"""

from fatebridge.core.astro.parts import _balance
from fatebridge.core.astro.reference import BALANCE_BASIS, NODE_BODIES


def _planet(pid, element, modality):
    return {"id": pid, "element": element, "modality": modality}


def test_balance_excludes_lunar_nodes():
    planets = [
        _planet("Sun", "Fire", "Mutable"),
        _planet("Moon", "Air", "Mutable"),
        _planet("North Node", "Water", "Cardinal"),  # 唯一的水 / 基本，来自虚点
    ]
    element = _balance(planets, "element")
    modality = _balance(planets, "modality")
    assert element == {"Fire": 1, "Air": 1}  # Water 不计入
    assert modality == {"Mutable": 2}  # Cardinal 不计入
    assert "Water" not in element


def test_node_bodies_cover_both_nodes():
    assert "North Node" in NODE_BODIES
    assert "South Node" in NODE_BODIES


def test_balance_basis_is_documented():
    assert "交点" in BALANCE_BASIS and "不计入" in BALANCE_BASIS
