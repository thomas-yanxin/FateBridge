"""Punishment cannot be resolved by a combination which was not completed."""

import pytest

from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.strength import DEFAULT_POLICY, evaluate_strength_policy
from tests.bazi_punishment_reference import (
    GEOMETRIES,
    ORDER,
)


@pytest.mark.parametrize("branches", GEOMETRIES)
def test_eight_first_patterns_cannot_resolve_punishment_with_contested_pairs(branches):
    chart = dict(zip(ORDER, (("甲", b) for b in branches)))
    value = evaluate_strength_policy(
        chart, ElementAnalysis.seasonal_phases(chart["month"][1]), DEFAULT_POLICY
    )
    punishment = next(e for e in value["relations"] if e["kind"] == "刑")
    assert punishment["status"] == "active"
    assert all(
        e["status"] == "contested_or_clashed"
        for e in value["relations"]
        if e["kind"] == "六合"
    )
