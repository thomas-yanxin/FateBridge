"""Moves preserve object identity, static floor facts and operation permissions."""

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.core.fengshui.interior_inputs import RELATION_ROLES
from fatebridge.core.fengshui.output import FengshuiOutput
from fatebridge.services.fengshui import assess


def orientation():
    return dict(
        north_reference="magnetic",
        direction_confirmed=True,
        floorplan_alignment_confirmed=True,
        center_confirmed=True,
        evidence="统一方向、中心与图纸对齐已分别核对",
    )


def floor(floor_id, level, objects, space_kind="interior"):
    return dict(
        floor_id=floor_id,
        level=level,
        space_kind=space_kind,
        object_ids=objects,
        uses_shared_orientation=True,
        center_confirmed=True,
        floorplan_alignment_confirmed=True,
        evidence="该层身份、中心与统一方向已独立确认",
    )


def relation_request(
    *,
    kind="mirror_faces_bed",
    moving="source",
    old_floors=(),
    new_floors=(),
    changes=("location",),
    candidate_present=False,
):
    source_role, target_role = RELATION_ROLES[kind]
    relation = dict(
        relation_id="relation",
        source_object_id="source",
        target_object_id="target",
        kind=kind,
        present=True,
        observation_basis="user_confirmed",
        evidence="现状关系已确认，不按物件名称或位置猜测",
    )
    objects = [
        dict(
            object_id=object_id,
            label=object_id,
            role=role,
            kind="garden_feature" if role == "sharp_corner" else "furniture",
            evidence="对象身份与用途已明确核对",
        )
        for object_id, role in (("source", source_role), ("target", target_role))
    ]
    return dict(
        methods=[],
        scene="home",
        environmental_context=dict(
            orientation=orientation(),
            objects=objects,
            floors=list(old_floors),
            interior_relations=[relation],
        ),
        layout_constraints=[
            dict(
                object_id=object_id,
                can_relocate="location" in changes,
                can_rotate="facing" in changes,
                evidence="搬位与转向许可分别确认；仅列明动作被允许",
            )
            for object_id in ("source", "target")
        ],
        layout_alternatives=[
            dict(
                candidate_id="proposal",
                object_id=moving,
                changes=list(changes),
                physically_feasible=True,
                evidence="明确提交一个独立观察且空间可行的候选",
                environmental_context=dict(
                    orientation=orientation(),
                    floors=list(new_floors),
                    interior_relations=[
                        {
                            **relation,
                            "present": candidate_present,
                            "evidence": "候选位置关系已独立复核",
                        }
                    ],
                ),
            )
        ],
    )


def candidate_result(request):
    result = assess(**request)
    FengshuiOutput.model_validate(result)
    Draft202012Validator(FengshuiOutput.model_json_schema()).validate(result)
    return result["layout_analysis"]["alternatives_analysis"]["findings"][0]


@pytest.mark.parametrize("before,after", [(False, True), (True, False)])
@pytest.mark.parametrize("basis", ["measured", "user_confirmed"])
def test_move_or_turn_cannot_change_confirmed_plant_alive_state(before, after, basis):
    inputs = relation_request(kind="sharp_corner_points_at_desk", changes=("facing",))
    original = dict(
        fact_id="plant",
        object_id="source",
        material="living_plant",
        plant_alive=before,
        element_use="wood_remedy",
        observation_basis=basis,
        evidence="独立核对该盆栽存活状态；候选只搬转同一物件",
    )
    inputs["environmental_context"]["material_facts"] = [original]
    inputs["layout_alternatives"][0]["environmental_context"]["material_facts"] = [
        {**original, "plant_alive": after}
    ]
    with pytest.raises(ValidationError):
        assess(**inputs)


def test_photo_plant_state_may_be_confirmed_without_replacing_the_object():
    inputs = relation_request(kind="sharp_corner_points_at_desk", changes=("facing",))
    original = dict(
        fact_id="plant",
        object_id="source",
        material="living_plant",
        plant_alive=False,
        element_use="wood_remedy",
        observation_basis="image_observed",
        evidence="照片所见存活状态只是候选",
    )
    inputs["environmental_context"]["material_facts"] = [original]
    inputs["layout_alternatives"][0]["environmental_context"]["material_facts"] = [
        {**original, "plant_alive": True, "observation_basis": "user_confirmed"}
    ]
    candidate = candidate_result(inputs)
    assert candidate["status"] == "ready"
    assert candidate["material_analysis"]["findings"][0]["material_eligibility"] == (
        "conditional_material_match"
    )
    assert candidate["material_analysis"]["findings"][0]["placement_suitability"] == (
        "not_assessed"
    )


@pytest.mark.parametrize("moving", ["source", "target"])
def test_horizontal_relation_cannot_erase_static_other_endpoint_floor(moving):
    inputs = relation_request(
        moving=moving,
        old_floors=[floor("upstairs", 2, ["source", "target"])],
        new_floors=[floor("downstairs", 1, [moving])],
        candidate_present=True,
    )
    # The other endpoint is still on the known second floor. Omitting its
    # floor from the proposal must not permit a confirmed horizontal relation.
    with pytest.raises(ValidationError, match="不能跨"):
        assess(**inputs)


@pytest.mark.parametrize("moving,new_level", [("source", 0), ("target", 3)])
def test_vertical_relation_cannot_erase_static_other_endpoint_floor(moving, new_level):
    inputs = relation_request(
        kind="bed_above_stove",
        moving=moving,
        old_floors=[
            floor("bed-level", 2, ["source"]),
            floor("stove-level", 1, ["target"]),
        ],
        new_floors=[floor("new-level", new_level, [moving])],
        candidate_present=True,
    )
    with pytest.raises(ValidationError, match="必须高于"):
        assess(**inputs)


@pytest.mark.parametrize(
    "new_floor",
    [
        floor("other-room-frame", 1, ["source"]),
        floor("upstairs", 2, ["source"]),
        floor("courtyard", 1, ["source"], "courtyard"),
    ],
    ids=["different-floor-id", "different-level", "different-space-kind"],
)
def test_facing_only_proposal_cannot_change_known_floor_identity(new_floor):
    inputs = relation_request(
        old_floors=[floor("original", 1, ["source", "target"])],
        new_floors=[deepcopy(new_floor)],
        changes=("facing",),
    )
    # Only rotation is permitted; floor changes require the independent
    # relocation operation even without a compass Placement record.
    assert inputs["layout_constraints"][0]["can_relocate"] is False
    with pytest.raises(ValidationError):
        assess(**inputs)


def test_facing_only_floor_change_is_also_rejected_for_legacy_form_proposals():
    observation = dict(
        object_id="desk",
        purpose="desk",
        entrance_visible=True,
        entrance_direct_line=False,
        solid_backing=True,
        observation_basis="user_confirmed",
        evidence="该候选座位形态已独立确认",
    )
    inputs = dict(
        methods=[],
        scene="workstation",
        form_observations=[observation],
        environmental_context=dict(
            orientation=orientation(), floors=[floor("original", 1, ["desk"])]
        ),
        layout_constraints=[
            dict(
                object_id="desk",
                can_relocate=False,
                can_rotate=True,
                evidence="桌子只允许转向，不允许换层搬位",
            )
        ],
        layout_alternatives=[
            dict(
                candidate_id="rotate-but-move-floor",
                object_id="desk",
                changes=["facing"],
                form_observation=observation,
                physically_feasible=True,
                evidence="声称仅转向，实际提交不同楼层",
                environmental_context=dict(
                    orientation=orientation(), floors=[floor("new", 2, ["desk"])]
                ),
            )
        ],
    )
    with pytest.raises(ValidationError):
        assess(**inputs)


@pytest.mark.parametrize("moving", ["source", "target"])
def test_location_move_can_remove_horizontal_relation_without_moving_static_endpoint(
    moving,
):
    inputs = relation_request(
        moving=moving,
        old_floors=[floor("original", 2, ["source", "target"])],
        new_floors=[floor("new", 1, [moving])],
    )
    candidate = candidate_result(inputs)
    assert candidate["status"] == "ready"
    assert candidate["changes"] == ["location"]
    assert candidate["interior_analysis"]["findings"][0]["status"] == "not_present"
    assert candidate["missing_inputs"] == []


def test_valid_vertical_location_move_uses_static_floor_only_for_validation():
    inputs = relation_request(
        kind="bed_above_stove",
        old_floors=[
            floor("bed-level", 2, ["source"]),
            floor("stove-level", 1, ["target"]),
        ],
        new_floors=[floor("new-bed-level", 3, ["source"])],
        candidate_present=True,
    )
    candidate = candidate_result(inputs)
    assert candidate["status"] == "ready"
    assert candidate["interior_analysis"]["findings"][0]["status"] == "authored_caution"
    # Readiness records permission and feasibility, not that the relation is
    # favourable or that the retained author caution has been solved.
    assert candidate["decision_scope"].startswith("executable_proposal_not_universal_")


def test_generic_mirror_candidate_keeps_static_action_permissions():
    inputs = relation_request(changes=("facing",), candidate_present=True)
    candidate = candidate_result(inputs)
    actions = candidate["interior_analysis"]["action_options"]
    assert candidate["status"] == "ready"
    assert {a["operation"]: a["status"] for a in actions} == {
        "location": "blocked",
        "facing": "conditional_option",
    }
    assert {a["object_id"] for a in actions} == {"source"}
    assert candidate["layer_statuses"] == {}
