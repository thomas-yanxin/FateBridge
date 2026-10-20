"""Missing dimension signals remain neutral without changing nonzero weights."""

import math

import pytest

from fatebridge.analysis.life_dimensions import LifeDimensionAnalysis

PILLARS = {
    "year": ("庚", "午"),
    "month": ("辛", "巳"),
    "day": ("庚", "辰"),
    "hour": ("辛", "巳"),
}


@pytest.mark.parametrize("gender", [None, "未知", "unspecified"])
def test_unknown_gender_does_not_become_a_low_love_score(gender):
    result = LifeDimensionAnalysis.calculate_life_dimensions(PILLARS, gender=gender)
    assert result["love"] == 50


def test_zero_is_neutral_and_nonzero_scores_keep_the_existing_scale():
    assert LifeDimensionAnalysis._normalize_to_score(0) == 50
    for raw in [-1, 0.5, 3, 6]:
        assert LifeDimensionAnalysis._normalize_to_score(raw) == pytest.approx(
            50 + 50 * math.tanh((raw - 3) / 3)
        )
