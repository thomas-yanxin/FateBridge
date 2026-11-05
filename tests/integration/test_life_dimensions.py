"""Unknown inputs remain absent; known zero uses a continuous rule-index scale."""

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
    assert result["love"] is None
    assert all(value is not None for key, value in result.items() if key != "love")


def test_rule_index_has_no_zero_discontinuity_and_preserves_known_anchors():
    normalize = LifeDimensionAnalysis._normalize_to_score
    values = [normalize(raw) for raw in [-1, -1e-9, 0, 1e-9, 0.1, 0.5, 1, 3, 6]]
    assert values == sorted(values)
    assert normalize(1e-9) - normalize(-1e-9) < 1e-6
    assert normalize(0) == pytest.approx(11.920292202211755)
    assert normalize(0.5) == pytest.approx(15.886910488091516)
    assert normalize(3) == 50
