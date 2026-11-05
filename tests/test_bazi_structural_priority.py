"""A sourced root override must not depend on the proxy it overrides."""

from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.strength import (
    DEFAULT_POLICY,
    STRUCTURAL_PRIORITY_METHOD_ID,
    _evaluate,
)


def evaluate(text):
    pillars = dict(zip(("year", "month", "day", "hour"), map(tuple, text.split())))
    return _evaluate(
        pillars, ElementAnalysis.seasonal_phases(pillars["month"][1]), DEFAULT_POLICY
    )


def test_original_gs12_root_capacity_is_not_vetoed_by_weighted_share():
    # 1947 Ren commentary, PDF209: 火長夏天，旺之極矣. The retained
    # source label and four pillars are unchanged; no biography is scored.
    result = evaluate("癸丑 戊午 丙午 壬辰")
    assert result["threshold_arithmetic"]["numerical_label"] == "中和"
    assert result["threshold_arithmetic"]["support_above_half"] is False
    assert result["structural_decision"]["vigorous_roots"] == ["month", "day"]
    assert result["structural_decision"]["method_id"] == STRUCTURAL_PRIORITY_METHOD_ID
    assert result["structural_decision"]["rule"] == "in_command_multiple_vigorous_roots"
    assert result["strength_level"] == "强"


def test_root_override_really_requires_command_and_multiple_surviving_roots():
    for control in ("癸丑 辛酉 丙午 壬辰", "癸丑 戊午 丙子 壬辰"):
        result = evaluate(control)
        assert (
            result["structural_decision"]["rule"]
            != "in_command_multiple_vigorous_roots"
        )


def test_month_command_alone_does_not_override_a_controlling_front():
    result = evaluate("辛酉 辛卯 甲申 辛酉")
    assert result["strength_level"] != "强"
