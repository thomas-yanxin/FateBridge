"""Build scored charts from literal pillars used by BaZi regression tests."""

from pydantic import JsonValue

from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.strength import (
    DEFAULT_POLICY,
    StrengthPolicy,
    evaluate_strength_policy,
)


def bazi_pillars(pillar_text: str) -> dict[str, tuple[str, str]]:
    return {
        position: (stem, branch)
        for position, (stem, branch) in zip(
            ("year", "month", "day", "hour"), pillar_text.split(), strict=True
        )
    }


def evaluate_pillar_strength(
    pillar_text: str, *, policy: StrengthPolicy = DEFAULT_POLICY
) -> dict[str, JsonValue]:
    pillars = bazi_pillars(pillar_text)
    return evaluate_strength_policy(
        pillars, ElementAnalysis.seasonal_phases(pillars["month"][1]), policy
    )
