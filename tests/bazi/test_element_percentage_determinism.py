"""锁定 ElementAnalysis.convert_to_percentage 的跨版本确定性。

历史 bug：归一化补偿用 ``abs(sum(percentages) - 100) > 0.1`` 这条浮点刀刃判断
是否把残差并入最大项。CPython 3.12 起 ``sum()`` 改用 Neumaier 补偿求和，让
99.9 这类 0.1 倍数的浮点和在 3.11/3.12 间落到刀刃两侧——同一命盘在 3.11 得
金 37.0（总和 99.9，漏补偿），在 3.12+ 得金 37.1（总和 100，正常补偿）。

修复改用 ``round(残差, 1)`` 判断，跨版本确定，且始终把分布凑齐到恰好 100%。
"""

from fatebridge.core.elements import Element, ElementAnalysis


def _counts(**by_name: float) -> dict:
    """按给定中文五行名构造 {Element: weight}（保持插入顺序）。"""
    name_to_element = {e.value: e for e in Element}
    return {name_to_element[name]: weight for name, weight in by_name.items()}


def test_knife_edge_chart_is_deterministic_and_sums_to_100():
    # 庚午/辛巳/庚辰/辛巳：金 5.0 / 火 4.5 / 土 3.0 / 木 0.5 / 水 0.5，总权重 13.5。
    # 各项 round 后和为 99.9，旧逻辑在此刀刃上随 sum() 实现翻转；现固定补到 100。
    counts = _counts(金=5.0, 火=4.5, 土=3.0, 木=0.5, 水=0.5)
    result = ElementAnalysis.convert_to_percentage(counts)
    assert result["金"] == 37.1  # 残差 0.1 并入最大项（金），跨版本一致
    # 各项是 0.1 量化值，其浮点和不会 bit-精确等于 100.0，且 sum() 实现跨版本
    # 不同（正是本 bug 的根源）——故在 0.1 精度上校验总和。
    assert round(sum(result.values()), 1) == 100.0


def test_always_normalizes_to_exactly_100():
    # 不变量：无论权重如何，归一化后总和恰为 100%。
    for counts in (
        _counts(金=5.0, 火=4.5, 土=3.0, 木=0.5, 水=0.5),  # 和偏低 0.1
        _counts(金=1.0, 火=1.0, 土=1.0, 木=1.0, 水=1.0),  # 每项 20.0，正好 100
        _counts(金=2.0, 火=1.0, 土=1.0, 木=1.0, 水=1.0),  # 33.3/16.7×4 → 偏高
        _counts(木=7.0, 火=1.0, 土=1.0, 金=1.0, 水=1.0),  # 单边集中
    ):
        result = ElementAnalysis.convert_to_percentage(counts)
        assert round(sum(result.values()), 1) == 100.0
