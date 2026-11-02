"""Original-text counterexamples must not become false global absence claims."""

from copy import deepcopy
from itertools import product

import pytest
from pydantic import ValidationError

from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.element_presence import build_element_presence
from fatebridge.core.output_element_presence import ElementPresence

ORDER = ("year", "month", "day", "hour")


def chart(*values):
    return dict(zip(ORDER, map(tuple, values)))


def test_source_no_metal_context_keeps_actual_hidden_xin_without_fabricating_absence():
    pillars = chart("癸未", "乙卯", "甲戌", "乙亥")
    before = deepcopy(pillars)
    result = build_element_presence(pillars)
    assert "金" in result["visible_stems"]["absent_elements"]
    assert "金" in result["principal_hidden_stems"]["absent_elements"]
    assert "金" in result["all_hidden_stems"]["present_elements"]
    assert [
        o for o in result["all_hidden_stems"]["occurrences"] if o["element"] == "金"
    ] == [
        {
            "pillar": "day",
            "stem": "辛",
            "branch": "戌",
            "hidden_rank": 1,
            "element": "金",
        }
    ]
    assert result["absent_from_all_listed"] == []
    assert result["source_phrase_scope"] == "not_adjudicated"
    assert result["calculation_effect"] == "none"
    assert pillars == before
    ElementPresence.model_validate(result)
    assert build_natal_evidence(pillars)["element_presence"] == result


def test_day_stem_is_an_occurrence_and_principal_hidden_is_not_a_fifth_layer_vote():
    result = build_element_presence(chart("庚午", "辛巳", "庚辰", "辛巳"))
    assert result["visible_stems"]["present_elements"] == ["金"]
    assert len(result["visible_stems"]["occurrences"]) == 4
    assert result["visible_stems"]["occurrences"][2] == {
        "pillar": "day",
        "stem": "庚",
        "element": "金",
    }
    assert result["principal_hidden_stems"]["present_elements"] == ["火", "土"]
    assert set(result["all_hidden_stems"]["present_elements"]) == {
        "木",
        "火",
        "土",
        "金",
        "水",
    }
    assert result["principal_hidden_stems"]["occurrences"] == [
        o for o in result["all_hidden_stems"]["occurrences"] if o["hidden_rank"] == 0
    ]


@pytest.mark.parametrize(
    "plane", ["visible_stems", "principal_hidden_stems", "all_hidden_stems"]
)
def test_each_object_projection_keeps_only_requested_siblings(plane):
    result = build_element_presence(chart("癸未", "乙卯", "甲戌", "乙亥"))
    for field in ("present_elements", "absent_elements", "occurrences"):
        projected = {plane: {field: result[plane][field]}}
        validated = ElementPresence.model_validate(projected)
        assert validated.model_dump(exclude_unset=True) == projected


@pytest.mark.parametrize(
    "corruption",
    ["element", "absent", "rank", "principal", "union", "duplicate", "verdict"],
)
def test_contract_rejects_fabricated_element_or_plane_claims(corruption):
    result = build_element_presence(chart("癸未", "乙卯", "甲戌", "乙亥"))
    if corruption == "element":
        result["visible_stems"]["occurrences"][0]["element"] = "金"
    elif corruption == "absent":
        result["all_hidden_stems"]["absent_elements"] = ["金"]
    elif corruption == "rank":
        result["all_hidden_stems"]["occurrences"][0]["hidden_rank"] = 1
    elif corruption == "principal":
        result["principal_hidden_stems"]["occurrences"][0] = result["all_hidden_stems"][
            "occurrences"
        ][1]
    elif corruption == "union":
        result["all_listed_elements"] = ["木"]
    elif corruption == "duplicate":
        result["visible_stems"]["occurrences"].append(
            result["visible_stems"]["occurrences"][0].copy()
        )
    else:
        result["source_phrase_scope"] = "formed"
    with pytest.raises(ValidationError):
        ElementPresence.model_validate(result)


def test_twelve_branch_position_permutations_do_not_erase_physical_hidden_elements():
    # Exercise every branch in every position, including repeated identical
    # branches. This is a fact invariant, not a force or classical accuracy test.
    for position, branch in product(ORDER, "子丑寅卯辰巳午未申酉戌亥"):
        pillars = chart("甲子", "丙寅", "戊辰", "壬戌")
        pillars[position] = (pillars[position][0], branch)
        result = build_element_presence(pillars)
        ElementPresence.model_validate(result)
        assert len(result["principal_hidden_stems"]["occurrences"]) == 4
