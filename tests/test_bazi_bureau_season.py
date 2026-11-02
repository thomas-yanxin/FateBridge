"""A quarter-membership fact must not silently replace a supplied phase gate."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from fatebridge.core.bureau_season import build_bureau_season_reference
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_bureau_season import BureauSeasonReference

PILLARS = dict(
    zip(("year", "month", "day", "hour"), map(tuple, ("癸卯", "丙辰", "甲辰", "丙寅")))
)


def calculated():
    return ElementAnalysis.analyze_day_master_strength(PILLARS)["assessment"]


def test_source_month_chen_branch_group_keeps_actual_phase_and_unadopted_numeric_result():
    assessment = calculated()
    before = deepcopy(assessment)
    result = build_bureau_season_reference(PILLARS, assessment)
    assert result["month_branch"] == "辰"
    assert result["principal_branch_element"] == "土"
    assert result["branch_seasonal_group"] == "寅卯辰"
    assert result["branch_group_element"] == "木"
    row = result["combination_observations"][0]
    assert row["positions"] == ["year", "month", "day", "hour"]
    assert row["month_in_target_branch_group"] is True
    assert row["calculated_target_phase"] == "死"
    assert row["supplied_season_support_flag"] is False
    assert row["criteria_differ"] is True
    assert row["classical_transformation"] == "not_adjudicated"
    assert result["calculation_effect"] == "none"
    assert assessment == before
    BureauSeasonReference.model_validate(result)


def test_no_supplied_calculation_remains_unknown_and_contested_gate_is_not_false():
    empty = build_bureau_season_reference(PILLARS, {})
    assert empty["combination_observations"] is None
    assert empty["calculated_phases"] is None
    assert empty["combination_gate_basis"] == "method_not_identified"
    state = {
        "method_id": "season_root_revelation_relations_v6",
        "relations": [
            {
                "kind": "三会",
                "positions": ["year", "month", "hour"],
                "target": "木",
                "status": "contested_or_clashed",
            }
        ],
    }
    result = build_bureau_season_reference(PILLARS, state)
    row = result["combination_observations"][0]
    assert row["supplied_season_support_flag"] is None
    assert row["criteria_differ"] is None
    BureauSeasonReference.model_validate(result)


@pytest.mark.parametrize(
    "branch,group,element",
    [
        ("辰", "寅卯辰", "木"),
        ("未", "巳午未", "火"),
        ("戌", "申酉戌", "金"),
        ("丑", "亥子丑", "水"),
    ],
)
def test_four_earth_principal_months_keep_their_different_branch_groups(
    branch, group, element
):
    pillars = {**PILLARS, "month": ("甲", branch)}
    result = build_bureau_season_reference(pillars, {})
    assert result["principal_branch_element"] == "土"
    assert result["branch_seasonal_group"] == group
    assert result["branch_group_element"] == element
    BureauSeasonReference.model_validate(result)


@pytest.mark.parametrize(
    "change",
    [
        "quarter_as_earth",
        "month_member",
        "flip_gate",
        "claim_transformed",
        "invent_phase",
        "invent_comparison",
        "unknown_method",
    ],
)
def test_contract_rejects_conflated_or_invented_seasonal_claims(change):
    result = build_bureau_season_reference(PILLARS, calculated())
    row = result["combination_observations"][0]
    if change == "quarter_as_earth":
        result["branch_group_element"] = "土"
    elif change == "month_member":
        row["month_is_member"] = False
    elif change == "flip_gate":
        row.update(supplied_season_support_flag=True, criteria_differ=False)
    elif change == "claim_transformed":
        row["classical_transformation"] = "formed"
    elif change == "invent_comparison":
        row.update(supplied_season_support_flag=None, criteria_differ=False)
    elif change == "unknown_method":
        result["strength_method_id"] = "unreviewed_new_method"
    else:
        row["calculated_target_phase"] = "旺"
    with pytest.raises(ValidationError):
        BureauSeasonReference.model_validate(result)


def test_present_object_fields_remain_valid_when_projected_alone():
    result = build_bureau_season_reference(PILLARS, calculated())
    for name, value in result.items():
        projected = {name: value}
        assert (
            BureauSeasonReference.model_validate(projected).model_dump(
                exclude_unset=True
            )
            == projected
        )
