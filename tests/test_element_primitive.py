"""Hand-counted vectors for the career/health/wealth structural tally.

These fixed expectations do not import the implementation's element or hidden
stem tables. Weights 1 / 0.5 / 0.3 are this tally's engineering convention;
they neither validate day-master strength nor establish a classical constant.
"""

import pytest

from fatebridge.utils.data import Element, count_element_distribution


@pytest.mark.parametrize(
    "branch,expected",
    [
        ("子", {"木": 1, "火": 0, "土": 0, "金": 0, "水": 0.8}),
        ("丑", {"木": 1, "火": 0, "土": 0.8, "金": 0.3, "水": 0.3}),
        ("寅", {"木": 1.8, "火": 0.3, "土": 0.3, "金": 0, "水": 0}),
        ("卯", {"木": 1.8, "火": 0, "土": 0, "金": 0, "水": 0}),
        ("辰", {"木": 1.3, "火": 0, "土": 0.8, "金": 0, "水": 0.3}),
        ("巳", {"木": 1, "火": 0.8, "土": 0.3, "金": 0.3, "水": 0}),
        ("午", {"木": 1, "火": 0.8, "土": 0.3, "金": 0, "水": 0}),
        ("未", {"木": 1.3, "火": 0.3, "土": 0.8, "金": 0, "水": 0}),
        ("申", {"木": 1, "火": 0, "土": 0.3, "金": 0.8, "水": 0.3}),
        ("酉", {"木": 1, "火": 0, "土": 0, "金": 0.8, "水": 0}),
        ("戌", {"木": 1, "火": 0.3, "土": 0.8, "金": 0.3, "水": 0}),
        ("亥", {"木": 1.3, "火": 0, "土": 0, "金": 0, "水": 0.8}),
    ],
)
def test_all_twelve_branches_match_hand_counted_weights(branch, expected):
    actual = count_element_distribution({"day": ("甲", branch)})
    assert {element.value: value for element, value in actual.items()} == pytest.approx(
        expected, rel=0, abs=1e-12
    )


def test_four_pillars_match_hand_counted_weights():
    pillars = {
        "year": ("庚", "午"),
        "month": ("辛", "巳"),
        "day": ("辛", "巳"),
        "hour": ("甲", "午"),
    }
    actual = count_element_distribution(pillars)
    # Three metal stems, one wood stem; 午 has 丁/己 and 巳 has 丙/庚/戊.
    assert {element.value: value for element, value in actual.items()} == pytest.approx(
        {"木": 1, "火": 3.2, "土": 1.2, "金": 3.6, "水": 0}, rel=0, abs=1e-12
    )


@pytest.mark.parametrize(
    "stem,expected",
    [
        ("甲", {"木": 1, "火": 0, "土": 0, "金": 0, "水": 0.8}),
        ("乙", {"木": 1, "火": 0, "土": 0, "金": 0, "水": 0.8}),
        ("丙", {"木": 0, "火": 1, "土": 0, "金": 0, "水": 0.8}),
        ("丁", {"木": 0, "火": 1, "土": 0, "金": 0, "水": 0.8}),
        ("戊", {"木": 0, "火": 0, "土": 1, "金": 0, "水": 0.8}),
        ("己", {"木": 0, "火": 0, "土": 1, "金": 0, "水": 0.8}),
        ("庚", {"木": 0, "火": 0, "土": 0, "金": 1, "水": 0.8}),
        ("辛", {"木": 0, "火": 0, "土": 0, "金": 1, "水": 0.8}),
        ("壬", {"木": 0, "火": 0, "土": 0, "金": 0, "水": 1.8}),
        ("癸", {"木": 0, "火": 0, "土": 0, "金": 0, "水": 1.8}),
    ],
)
def test_all_ten_stems_match_hand_counted_weights(stem, expected):
    actual = count_element_distribution({"day": (stem, "子")})
    assert {element.value: value for element, value in actual.items()} == pytest.approx(
        expected, rel=0, abs=1e-12
    )


def test_empty_input_includes_every_element_zero_initialised():
    assert count_element_distribution({}) == {element: 0.0 for element in Element}
