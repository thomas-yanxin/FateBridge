"""锁定西占元素 / 模式平衡排除月亮交点（虚点）。

交点是计算虚点，且引擎只排北交、不排南交，计入会造成不对称偏置，故元素 /
模式平衡只统计行星本体；交点仍保留在 planets 列表中，并以 balance_basis
标明统计口径。
"""

from fatebridge.core.astro.parts import _balance


def test_balance_excludes_lunar_nodes():
    planets = [
        {"id": "Sun", "element": "Fire", "modality": "Mutable"},
        {"id": "Moon", "element": "Air", "modality": "Mutable"},
        {"id": "North Node", "element": "Water", "modality": "Cardinal"},
        {"id": "South Node", "element": "Earth", "modality": "Fixed"},
    ]
    element = _balance(planets, "element")
    modality = _balance(planets, "modality")
    assert element == {"Fire": 1, "Air": 1}  # Water 不计入
    assert modality == {"Mutable": 2}  # Cardinal 不计入
