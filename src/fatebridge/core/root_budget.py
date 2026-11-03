"""Exact initial physical hidden-stem budgets shared by natal and time models."""

from fractions import Fraction
from typing import Mapping

from fatebridge.utils.data import BRANCH_HIDDEN_STEMS, STEM_ELEMENTS, Element


def initial_hidden_budgets(
    branches: Mapping[str, str], budgets: Mapping[str, Fraction]
) -> dict[str, list[tuple[str, Element, Fraction]]]:
    """Allocate each supplied branch budget once; reveal no extra root mass."""
    result = {}
    for position, branch in branches.items():
        hidden = BRANCH_HIDDEN_STEMS[branch]
        weights = [2**rank for rank in reversed(range(len(hidden)))]
        result[position] = [
            (
                stem,
                STEM_ELEMENTS[stem][0],
                budgets[position] * Fraction(weight, sum(weights)),
            )
            for stem, weight in zip(hidden, weights)
        ]
    return result
