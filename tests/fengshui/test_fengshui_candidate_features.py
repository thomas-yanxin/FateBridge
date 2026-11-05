"""Moving/turning a feature must not reuse its old sand/water assessment."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from fatebridge.core.fengshui.models import AssessRequest
from fatebridge.services.fengshui import assess
from tests.fengshui.test_fengshui_context import orientation
from tests.fengshui.test_fengshui_planning import observation, proposal_request


def feature(object_id="furniture", direction="N", classification="sand"):
    return {
        "object_id": object_id,
        "direction": direction,
        "classification": classification,
        "classification_basis": "user_confirmed",
        "evidence": "本次位置与砂水分类独立确认，不按物品名称推断",
    }


def inputs(*, fresh=False, facing_only=False):
    values = proposal_request()
    values["methods"] = ["jinsuo", "annual_stars"]
    values["features"] = [feature(), feature("fixed_wall", "NW", "sand")]
    candidate = values["layout_alternatives"][0]
    if facing_only:
        candidate["changes"] = ["facing"]
        candidate["placement"]["location_direction"] = "N"
    if fresh:
        candidate["features"] = [
            feature(direction=candidate["placement"]["location_direction"])
        ]
    return values


def proposal(values):
    return assess(**values)["layout_analysis"]["alternatives_analysis"]["findings"][0]


@pytest.mark.parametrize("facing_only", [False, True])
def test_old_target_feature_is_removed_and_missing_fresh_confirmation_prevents_ready(
    facing_only,
):
    result = proposal(inputs(facing_only=facing_only))
    assert result["status"] == "candidate_only"
    assert result["calculation_status"] == "partial"
    assert "layout_alternatives.proposal.features" in result["missing_inputs"]
    assert not result["old_target_feature_reused"]
    assert {f["object_id"] for f in result["environment_adjustments"]} == {"fixed_wall"}
    assert {
        f["object_id"] for f in result["rule_comparisons"] if f["method"] == "jinsuo"
    } == {"fixed_wall"}


@pytest.mark.parametrize("facing_only", [False, True])
def test_independent_feature_confirmation_recalculates_target_and_retains_static_features(
    facing_only,
):
    values = inputs(fresh=True, facing_only=facing_only)
    # N prefers sand, while E likewise prefers sand. Use confirmed water to
    # ensure a complete proposal need not match a traditional preference.
    values["layout_alternatives"][0]["features"][0]["classification"] = "water"
    result = proposal(values)
    assert result["status"] == "ready"
    assert result["missing_inputs"] == []
    environments = {f["object_id"]: f for f in result["environment_adjustments"]}
    target = environments["furniture"]
    assert target["direction"] == ("N" if facing_only else "E")
    assert target["classification"] == "water"
    assert target["finding"] == "opposes_preference"
    assert target["feature_observation_scope"] == "independent_candidate_confirmation"
    assert environments["fixed_wall"]["direction"] == "NW"
    assert (
        environments["fixed_wall"]["feature_observation_scope"]
        == "unchanged_environment_feature"
    )
    comparisons = [f for f in result["rule_comparisons"] if f["method"] == "jinsuo"]
    assert len(comparisons) == 2
    assert all(
        f["rule_id"] == "jinsuo_basic_fixed_v1.palace_preference" for f in comparisons
    )


@pytest.mark.parametrize("classification", ["mixed", "unknown"])
def test_fresh_feature_with_unconfirmed_single_classification_remains_partial(
    classification,
):
    values = inputs(fresh=True)
    values["layout_alternatives"][0]["features"][0]["classification"] = classification
    result = proposal(values)
    assert result["status"] == "candidate_only"
    assert (
        "features.furniture.single_confirmed_classification" in result["missing_inputs"]
    )
    target = next(
        f for f in result["environment_adjustments"] if f["object_id"] == "furniture"
    )
    assert target["finding"] == "undetermined"


@pytest.mark.parametrize(
    "violation",
    [
        "unselected_method",
        "other_id",
        "duplicate",
        "wrong_direction",
        "wrong_current_direction",
    ],
)
def test_features_cannot_switch_identity_direction_or_method_scope(violation):
    values = inputs(fresh=True)
    candidate = values["layout_alternatives"][0]
    if violation == "unselected_method":
        values["methods"] = ["annual_stars"]
    elif violation == "other_id":
        candidate["features"][0]["object_id"] = "fixed_wall"
    elif violation == "duplicate":
        candidate["features"].append(deepcopy(candidate["features"][0]))
    elif violation == "wrong_direction":
        candidate["features"][0]["direction"] = "S"
    else:
        values["features"][0]["direction"] = "S"
    with pytest.raises(ValidationError):
        AssessRequest.model_validate(values)


def form_only_candidate():
    return {
        "methods": ["jinsuo"],
        "form_observations": [observation()],
        "features": [feature("fixed_wall")],
        "layout_constraints": [
            {"object_id": "furniture", "can_rotate": True, "evidence": "允许转向"}
        ],
        "layout_alternatives": [
            {
                "candidate_id": "form_only",
                "object_id": "furniture",
                "changes": ["facing"],
                "form_observation": observation(),
                "features": [feature(direction="E")],
                "physically_feasible": True,
                "evidence": "独立确认新形态和砂水；无家具落宫占位",
            }
        ],
    }


@pytest.mark.parametrize(
    "context_location", ["current", "candidate", "candidate_omits_orientation"]
)
def test_feature_only_physical_claim_cannot_bypass_unknown_global_orientation(
    context_location,
):
    values = form_only_candidate()
    unknown = {"orientation": {"evidence": "未确认方位"}}
    if context_location == "current":
        values["environmental_context"] = unknown
    elif context_location == "candidate":
        values["layout_alternatives"][0]["environmental_context"] = unknown
    else:
        values["environmental_context"] = unknown
        values["layout_alternatives"][0]["environmental_context"] = {
            "observations": [
                {
                    "observation_id": "wood",
                    "object_id": "furniture",
                    "category": "material",
                    "feature": "wood",
                    "evidence": "只确认材质，不等于确认方位",
                }
            ],
        }
    # The current fixed feature must not mask the candidate-only gate.
    values["features"] = []
    with pytest.raises(ValidationError):
        AssessRequest.model_validate(values)


@pytest.mark.parametrize("context_location", ["current", "candidate"])
@pytest.mark.parametrize(
    "missing_flag",
    ["center_confirmed", "floorplan_alignment_confirmed", "uses_shared_orientation"],
)
def test_new_feature_without_placement_still_requires_its_floor_geometry(
    context_location, missing_flag
):
    values = form_only_candidate()
    floor = {
        "floor_id": "upper",
        "level": 2,
        "object_ids": ["furniture"],
        "center_confirmed": True,
        "floorplan_alignment_confirmed": True,
        "uses_shared_orientation": True,
        "evidence": "逐层核对",
    }
    floor.pop(missing_flag)
    context = {"orientation": orientation(), "floors": [floor]}
    if context_location == "current":
        values["environmental_context"] = context
    else:
        values["layout_alternatives"][0]["environmental_context"] = context
    with pytest.raises(ValidationError, match="楼层"):
        AssessRequest.model_validate(values)


def test_feature_only_candidate_can_be_reviewed_without_faking_furniture_location():
    result = proposal(form_only_candidate())
    assert result["status"] == "ready"
    assert result["placement_findings"] == []
    assert any(
        f["object_id"] == "furniture" and f["direction"] == "E"
        for f in result["environment_adjustments"]
    )


def test_cross_floor_candidate_uses_new_feature_and_new_frame_together():
    values = inputs(fresh=True)
    for key, level in [("environmental_context", 1), ("candidate", 2)]:
        context = {
            "orientation": orientation(),
            "floors": [
                {
                    "floor_id": f"floor-{level}",
                    "level": level,
                    "object_ids": ["furniture"],
                    "center_confirmed": True,
                    "floorplan_alignment_confirmed": True,
                    "uses_shared_orientation": True,
                    "evidence": "各层独立核对中心、对齐与方向",
                }
            ],
        }
        if key == "candidate":
            values["layout_alternatives"][0]["environmental_context"] = context
        else:
            values[key] = context
    result = proposal(values)
    assert result["status"] == "ready"
    target = next(
        f for f in result["environment_adjustments"] if f["object_id"] == "furniture"
    )
    assert target["direction"] == "E"
    assert target["floor_id"] == "floor-2" and target["floor_level"] == 2
    assert (
        target["location_reference"]
        == "independently_confirmed_floor_center_shared_orientation"
    )
