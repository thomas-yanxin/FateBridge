"""Environmental policy invariants, fact boundaries and floor exposure scopes."""

from copy import deepcopy
from itertools import product

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.core.fengshui.context import (
    analyze_environmental_context,
    expert_context_provenance,
)
from fatebridge.core.fengshui.context_inputs import EnvironmentalContext


def orientation(**changes):
    return {
        "direction_confirmed": True,
        "north_reference": "magnetic",
        "floorplan_alignment_confirmed": True,
        "center_confirmed": True,
        "evidence": "现场核对参考北、户型旋转及全宅中心",
        **changes,
    }


def member(subject_id, gender="male", generation=1, roles=(), **changes):
    return {
        "subject_id": subject_id,
        "gender_role": gender,
        "generation": generation,
        "family_roles": list(roles),
        "evidence": "用户明确确认本家庭辈分与排行",
        **changes,
    }


def evaluate(**values):
    context = EnvironmentalContext.model_validate(values)
    return analyze_environmental_context(context, ["annual_stars", "jinsuo"])


def test_policy_is_versioned_sourced_and_does_not_change_personal_layer():
    result = analyze_environmental_context(None, ["bazhai", "jinsuo"])
    assert result["status"] == "not_requested"
    assert result["missing_inputs"] == []
    assert (
        result["separation_policy"]["bazhai_personal_matching"]
        == "independent_minggua_layer"
    )
    assert result["separation_policy"]["selected_environmental_methods"] == ["jinsuo"]
    provenance = expert_context_provenance()
    assert provenance["ruleset_id"] == "expert_environment_2026_10_v1"
    assert provenance["version"] == "1.0.0"
    source = provenance["sources"][0]
    assert source["kind"] == "user_supplied_expert_policy"
    assert "2026-10-15" in source["title"]
    provenance["sources"].clear()
    assert expert_context_provenance()["sources"]


@pytest.mark.parametrize(
    "natal_field", ["bazi", "ziwei", "favourable_elements", "other_people_charts"]
)
def test_environment_cannot_accept_or_secretly_merge_natal_chart_data(natal_field):
    with pytest.raises(ValidationError, match="Extra inputs"):
        EnvironmentalContext.model_validate({natal_field: {"wood": True}})


@pytest.mark.parametrize(
    "direction,alignment,center", list(product([False, True], repeat=3))
)
def test_sector_binding_requires_direction_alignment_and_center(
    direction, alignment, center
):
    result = evaluate(
        orientation=orientation(
            direction_confirmed=direction,
            floorplan_alignment_confirmed=alignment,
            center_confirmed=center,
        ),
        household_members=[member("p", roles=["eldest_child"])],
    )
    association = result["household_correspondences"][0]["associations"][0]
    ready = direction and alignment and center
    assert result["orientation_review"]["physical_sector_binding_allowed"] is ready
    assert (association["primary_direction"] == "E") is ready
    assert result["status"] == ("complete" if ready else "partial")


def test_reference_north_is_required_and_true_flags_do_not_accept_strings():
    for values in (
        orientation(north_reference=None),
        orientation(direction_confirmed="yes"),
    ):
        with pytest.raises(ValidationError):
            EnvironmentalContext.model_validate({"orientation": values})


def test_generation_beats_household_decision_power_and_spouse_own_rank():
    result = evaluate(
        orientation=orientation(),
        household_composition_confirmed=True,
        household_members=[
            member("father", generation=0, roles=["parent"]),
            member("mother", gender="female", generation=0, roles=["parent"]),
            member(
                "husband", roles=["parent", "middle_child"], spouse_subject_id="wife"
            ),
            member(
                "wife",
                gender="female",
                roles=["parent", "eldest_child"],
                spouse_subject_id="husband",
                follow_spouse_rank=True,
            ),
        ],
    )
    people = {p["subject_id"]: p for p in result["household_correspondences"]}
    assert [a["primary_palace"] for a in people["father"]["associations"]] == ["乾"]
    assert [a["primary_palace"] for a in people["mother"]["associations"]] == ["坤"]
    assert [a["primary_palace"] for a in people["husband"]["associations"]] == ["坎"]
    assert [a["primary_palace"] for a in people["wife"]["associations"]] == ["离"]
    assert (
        people["wife"]["associations"][0]["rank_basis"]
        == "explicitly_following_spouse_rank"
    )
    assert not any(p["decision_making_power_used"] for p in people.values())


def test_parent_and_birth_order_are_both_retained_when_no_older_generation_resides():
    result = evaluate(
        orientation=orientation(),
        household_composition_confirmed=True,
        household_members=[member("p", roles=["parent", "eldest_child"])],
    )
    associations = result["household_correspondences"][0]["associations"]
    assert {a["primary_palace"] for a in associations} == {"乾", "震"}
    assert {a["opposite_palace"] for a in associations} == {"巽", "兑"}
    assert all(a["opposite_priority"] == "secondary" for a in associations)
    assert all(not p["effects_inferred"] for p in result["household_correspondences"])


def test_incomplete_household_does_not_promote_oldest_supplied_person_to_qian():
    result = evaluate(
        orientation=orientation(),
        household_members=[member("p", roles=["parent", "middle_child"])],
    )
    person = result["household_correspondences"][0]
    assert [a["primary_palace"] for a in person["associations"]] == ["坎"]
    assert person["withheld_roles"][0]["reason"] == "household_composition_unconfirmed"
    assert result["missing_inputs"] == [
        "environmental_context.household_composition_confirmed"
    ]


@pytest.mark.parametrize(
    "zodiac,palace",
    [
        ("鼠", "坎"),
        ("牛", "艮"),
        ("虎", "艮"),
        ("兔", "震"),
        ("龙", "巽"),
        ("蛇", "巽"),
        ("马", "离"),
        ("羊", "坤"),
        ("猴", "坤"),
        ("鸡", "兑"),
        ("狗", "乾"),
        ("猪", "乾"),
    ],
)
def test_confirmed_zodiac_is_separate_index_with_opposite_secondary(zodiac, palace):
    result = evaluate(
        household_members=[member("p", zodiac=zodiac)],
    )
    association = result["household_correspondences"][0]["associations"][0]
    assert association["primary_palace"] == palace
    assert association["opposite_palace"] != palace
    assert association["primary_direction"] is None
    assert association["opposite_priority"] == "secondary"
    assert (
        association["boundary_scope"]
        == "eight_sector_symbolic_index_not_exact_24_mountain"
    )
    assert "SHEN_BRANCHES" in association["source_ids"]


def test_zodiac_is_not_guessed_when_not_provided_and_nonresident_is_not_affected():
    result = evaluate(
        orientation=orientation(),
        household_members=[
            member("p", roles=["eldest_child"]),
            member("outside", roles=["parent"], zodiac="狗", co_resident=False),
        ],
    )
    assert len(result["household_correspondences"][0]["associations"]) == 1
    assert result["household_correspondences"][1]["associations"] == []


@pytest.mark.parametrize(
    "members",
    [
        [member("a", spouse_subject_id="missing")],
        [member("a", spouse_subject_id="a")],
        [member("a", roles=["eldest_child", "middle_child"])],
        [member("a", follow_spouse_rank=True)],
        [
            member("a", "female", spouse_subject_id="b", follow_spouse_rank=True),
            member("b"),
        ],
        [member("a", spouse_subject_id="b"), member("b", generation=2)],
        [
            member("a", spouse_subject_id="b"),
            member("b", spouse_subject_id="c"),
            member("c"),
        ],
        [
            member("a", spouse_subject_id="b"),
            member("c", spouse_subject_id="b"),
            member("b"),
        ],
    ],
)
def test_inconsistent_family_contract_is_rejected(members):
    with pytest.raises(ValidationError):
        EnvironmentalContext.model_validate({"household_members": members})


def floor_inputs():
    return {
        "orientation": orientation(),
        "household_members": [member("down"), member("up")],
        "floors": [
            {
                "floor_id": "first",
                "level": 1,
                "subject_ids": ["down"],
                "usage_confirmed": True,
                "usage_evidence": "完整核对一层室内住用及日常活动，up不使用一层室内",
                "uses_shared_orientation": True,
                "center_confirmed": True,
                "floorplan_alignment_confirmed": True,
                "evidence": "一层实际使用人已确认",
            },
            {
                "floor_id": "second",
                "level": 2,
                "subject_ids": ["up"],
                "uses_shared_orientation": True,
                "center_confirmed": True,
                "floorplan_alignment_confirmed": True,
                "suitability": "confirmed_suitable",
                "suitability_evidence": "现场专家独立核对二层适宜；不是计算分数",
                "evidence": "二层实际使用人已确认",
            },
            {
                "floor_id": "yard",
                "level": 1,
                "space_kind": "courtyard",
                "usage_confirmed": True,
                "usage_evidence": "独立核对院落全部实际活动范围，up不使用院落；未借用室内名单",
                "uses_shared_orientation": True,
                "center_confirmed": True,
                "floorplan_alignment_confirmed": True,
                "evidence": "一层院落独立记录",
            },
        ],
        "floor_influences": [
            {
                "influence_id": "local",
                "source_floor_id": "yard",
                "extent": "floor_local_confirmed",
                "evidence": "现场确认此项只限一层，不含共用通道等因素",
            }
        ],
    }


def test_courtyard_is_first_floor_and_local_issue_not_transferred_to_suitable_other_floor():
    result = evaluate(**floor_inputs())
    influence = result["floor_review"]["influences"][0]
    assignments = {p["subject_id"]: p["status"] for p in influence["subject_scope"]}
    assert assignments == {
        "down": "local_exposure_review_required",
        "up": "local_exposure_not_assigned_to_other_floor",
    }
    assert influence["shared_factors_cancelled"] is False
    assert result["floor_review"]["overall_review"] == "shared_review_required"
    yard = result["floor_review"]["floors"][2]
    assert yard["analysis_level"] == 1
    assert "planting" in yard["courtyard_review_scope"]
    assert all(
        f["suitability_source"] == "explicit_input_not_engine_calculation"
        for f in result["floor_review"]["floors"]
    )


@pytest.mark.parametrize(
    "field",
    ["center_confirmed", "floorplan_alignment_confirmed", "uses_shared_orientation"],
)
@pytest.mark.parametrize("unconfirmed", [None, False])
def test_global_geometry_does_not_supply_per_floor_geometry(field, unconfirmed):
    inputs = floor_inputs()
    inputs["floors"][1][field] = unconfirmed
    result = evaluate(**inputs)
    floors = {floor["floor_id"]: floor for floor in result["floor_review"]["floors"]}
    assert result["orientation_review"]["physical_sector_binding_allowed"] is True
    assert floors["first"]["direction_frame"] == "shared_confirmed"
    assert floors["second"]["direction_frame"] == "not_confirmed"
    context = EnvironmentalContext.model_validate(inputs)
    assert not context.floors[1].ready_for_sectors()
    if field != "uses_shared_orientation" or unconfirmed is None:
        assert (
            f"environmental_context.floors.second.{field}" in result["missing_inputs"]
        )


def test_courtyard_uses_first_level_but_cannot_borrow_its_confirmed_center():
    inputs = floor_inputs()
    inputs["floors"][2].pop("center_confirmed")
    result = evaluate(**inputs)
    yard = result["floor_review"]["floors"][2]
    assert yard["analysis_level"] == 1
    assert yard["direction_frame"] == "not_confirmed"
    assert (
        "environmental_context.floors.yard.center_confirmed" in result["missing_inputs"]
    )


@pytest.mark.parametrize(
    "change,expected",
    [
        ("unknown_extent", "scope_confirmation_required"),
        ("unknown_suitability", "other_floor_suitability_not_confirmed"),
        ("unsuitable_other_floor", "other_floor_suitability_not_confirmed"),
        ("also_uses_source", "local_exposure_review_required"),
        ("shared", "shared_review_required"),
        ("unknown_usage", "usage_confirmation_required"),
    ],
)
def test_floor_exemption_does_not_extend_past_confirmed_conditions(change, expected):
    inputs = floor_inputs()
    if change == "unknown_extent":
        inputs["floor_influences"][0]["extent"] = "unknown"
    elif change == "unknown_suitability":
        inputs["floors"][1].update(
            suitability="not_assessed", suitability_evidence=None
        )
    elif change == "unsuitable_other_floor":
        inputs["floors"][1]["suitability"] = "requires_review"
    elif change == "also_uses_source":
        inputs["floors"][0]["subject_ids"].append("up")
    elif change == "shared":
        inputs["floor_influences"][0].update(
            extent="shared_confirmed", shared_floor_ids=["second"]
        )
    else:
        inputs["floors"][1]["subject_ids"] = []
    result = evaluate(**inputs)
    assignment = next(
        p
        for p in result["floor_review"]["influences"][0]["subject_scope"]
        if p["subject_id"] == "up"
    )
    assert assignment["status"] == expected


@pytest.mark.parametrize(
    "mutation",
    [
        "yard_on_upper",
        "unknown_floor",
        "local_with_shared",
        "shared_without_floors",
        "duplicate_level",
        "blank_evidence",
        "missing_suitability_evidence",
    ],
)
def test_floor_contract_rejects_inconsistent_or_unconfirmed_assertions(mutation):
    inputs = floor_inputs()
    if mutation == "yard_on_upper":
        inputs["floors"][2]["level"] = 2
    elif mutation == "unknown_floor":
        inputs["floor_influences"][0]["source_floor_id"] = "none"
    elif mutation == "local_with_shared":
        inputs["floor_influences"][0]["shared_floor_ids"] = ["second"]
    elif mutation == "shared_without_floors":
        inputs["floor_influences"][0]["extent"] = "shared_confirmed"
    elif mutation == "duplicate_level":
        inputs["floors"][1]["level"] = 1
    elif mutation == "blank_evidence":
        inputs["floors"][0]["evidence"] = "  "
    else:
        inputs["floors"][1]["suitability_evidence"] = None
    with pytest.raises(ValidationError):
        EnvironmentalContext.model_validate(inputs)


def observation_inputs():
    return {
        "objects": [
            {
                "object_id": "kitchen",
                "label": "厨房",
                "kind": "room",
                "evidence": "实际厨房",
            }
        ],
        "observations": [
            {
                "observation_id": "open",
                "object_id": "kitchen",
                "category": "modern_design",
                "feature": "open_kitchen",
                "evidence": "已确认开放式厨房",
            },
            {
                "observation_id": "material",
                "object_id": "kitchen",
                "category": "material",
                "feature": "wood",
                "evidence": "已确认木材，不由照片推断",
            },
            {
                "observation_id": "relation",
                "object_id": "kitchen",
                "category": "room_relationship",
                "feature": "kitchen_bathroom_adjacent",
                "evidence": "确认相邻，其他门线未知",
            },
        ],
    }


def test_no_direction_keeps_modern_reminders_low_and_unsourced_taboos_uncovered():
    context = EnvironmentalContext.model_validate(observation_inputs())
    context.validate_references([], [])
    result = analyze_environmental_context(context, [])
    assert result["status"] == "complete"
    assert result["missing_inputs"] == []
    assert result["rule_coverage_counts"] == {
        "supported": 1,
        "confirmed_unsupported": 2,
        "unknown": 0,
    }
    findings = result["environment_findings"]
    assert findings[0]["finding"] == "low_priority_reminder"
    assert findings[0]["priority"] == "low"
    assert (
        findings[1]["finding"]
        == findings[2]["finding"]
        == "confirmed_fact_without_specific_taboo_rule"
    )
    assert not any(f["direction_inferred"] or f["action_required"] for f in findings)


def test_context_objects_do_not_force_fake_placement_and_reference_checks_cover_every_scope():
    inputs = observation_inputs()
    inputs["household_members"] = [member("person")]
    inputs["floors"] = [
        {
            "floor_id": "f",
            "level": 1,
            "subject_ids": ["person"],
            "object_ids": ["kitchen"],
            "evidence": "确认厨房归属",
        }
    ]
    inputs["observations"][0]["floor_id"] = "f"
    context = EnvironmentalContext.model_validate(inputs)
    context.validate_references([], [])
    bad = deepcopy(inputs)
    bad["floors"][0]["subject_ids"] = ["stranger"]
    with pytest.raises(ValueError, match="未知楼层使用人"):
        EnvironmentalContext.model_validate(bad).validate_references([], [])
    bad = deepcopy(inputs)
    bad["floors"][0]["object_ids"].append("undeclared")
    with pytest.raises(ValueError, match="未知楼层对象"):
        EnvironmentalContext.model_validate(bad).validate_references([], [])
    bad = deepcopy(inputs)
    bad["observations"][0]["floor_id"] = "missing"
    with pytest.raises(ValidationError, match="未知观察楼层"):
        EnvironmentalContext.model_validate(bad)


def test_existing_object_purpose_cannot_be_reassigned_by_environmental_definition():
    context = EnvironmentalContext.model_validate(
        {
            "orientation": orientation(),
            "objects": [
                {
                    "object_id": "x",
                    "label": "床",
                    "kind": "furniture",
                    "purpose": "bed",
                    "evidence": "用户确认",
                }
            ],
        }
    )
    context.validate_references(["x"], [], {"x": "bed"})
    with pytest.raises(ValueError, match="已有用途不一致"):
        context.validate_references(["x"], [], {"x": "desk"})
    wrong_kind = EnvironmentalContext.model_validate(
        {
            "orientation": orientation(),
            "objects": [
                {
                    "object_id": "x",
                    "label": "房间",
                    "kind": "room",
                    "evidence": "用户确认",
                }
            ],
        }
    )
    with pytest.raises(ValueError, match="已有类型不一致"):
        wrong_kind.validate_references(["x"], [], {"x": "desk"})


@pytest.mark.parametrize(
    "values",
    [
        {},
        {
            "objects": [
                {
                    "object_id": "x",
                    "label": "厨房",
                    "kind": "room",
                    "evidence": "确认名称",
                }
            ]
        },
    ],
)
def test_empty_context_or_definitions_alone_are_not_a_complete_review(values):
    with pytest.raises(ValidationError, match="至少提供"):
        EnvironmentalContext.model_validate(values)


def test_declared_person_without_roles_or_floor_use_remains_partial():
    result = evaluate(orientation=orientation(), household_members=[member("p")])
    assert result["status"] == "partial"
    assert result["missing_inputs"] == [
        "environmental_context.household_members.p.family_roles"
    ]


def test_nested_schema_forbids_extra_chart_inputs_and_valid_request_matches_schema():
    schema = EnvironmentalContext.model_json_schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(observation_inputs())
    assert schema["additionalProperties"] is False
    assert all(
        value.get("additionalProperties") is False
        for value in schema["$defs"].values()
        if value.get("type") == "object"
    )
    bad = observation_inputs()
    bad["observations"][0]["bazi_favourable_element"] = "木"
    assert list(Draft202012Validator(schema).iter_errors(bad))


@pytest.mark.parametrize("space_index", [0, 2])
@pytest.mark.parametrize("positive_list_omitted", [False, True])
def test_local_exemption_requires_complete_usage_of_each_affected_level_space(
    space_index, positive_list_omitted
):
    values = floor_inputs()
    floor = values["floors"][space_index]
    floor.pop("usage_confirmed")
    floor.pop("usage_evidence")
    if positive_list_omitted:
        floor.pop("subject_ids", None)
    result = evaluate(**values)
    person = next(
        p
        for p in result["floor_review"]["influences"][0]["subject_scope"]
        if p["subject_id"] == "up"
    )
    assert person["status"] == "usage_confirmation_required"
    assert (
        f"environmental_context.floors.{floor['floor_id']}.usage_confirmed"
        in result["missing_inputs"]
    )
    assert result["status"] == "partial"


@pytest.mark.parametrize("space_index", [0, 2])
def test_shared_scope_cannot_exclude_other_floor_user_without_complete_affected_usage(
    space_index,
):
    values = floor_inputs()
    values["floor_influences"][0].update(
        extent="shared_confirmed", shared_floor_ids=["first"]
    )
    values["floors"][space_index].pop("usage_confirmed")
    values["floors"][space_index].pop("usage_evidence")
    result = evaluate(**values)
    assignments = {
        p["subject_id"]: p["status"]
        for p in result["floor_review"]["influences"][0]["subject_scope"]
    }
    assert assignments["down"] == "shared_review_required"
    assert assignments["up"] == "usage_confirmation_required"


def test_confirmed_shared_usage_can_exclude_scope_without_asking_where_person_lives():
    values = floor_inputs()
    values["floor_influences"][0].update(
        extent="shared_confirmed", shared_floor_ids=["first"]
    )
    values["floors"][1]["subject_ids"] = []
    values["household_members"][1]["family_roles"] = ["middle_child"]
    result = evaluate(**values)
    person = next(
        p
        for p in result["floor_review"]["influences"][0]["subject_scope"]
        if p["subject_id"] == "up"
    )
    assert person["status"] == "outside_declared_shared_scope"
    assert not any("floor_usage" in path for path in result["missing_inputs"])


@pytest.mark.parametrize("influence", ["none", "positive", "unsuitable_elsewhere"])
def test_usage_completion_is_not_requested_when_it_cannot_change_scope_or_exemption(
    influence,
):
    values = floor_inputs()
    for floor in values["floors"]:
        floor.pop("usage_confirmed", None)
        floor.pop("usage_evidence", None)
    if influence == "none":
        values["floor_influences"] = []
    elif influence == "positive":
        values["floors"][0]["subject_ids"].append("up")
    else:
        values["floors"][1]["suitability"] = "requires_review"
    result = evaluate(**values)
    assert not any("usage_confirmed" in path for path in result["missing_inputs"])


@pytest.mark.parametrize(
    "confirmed,evidence", [(True, None), (False, "未经确认的依据"), (True, "  ")]
)
def test_complete_usage_requires_explicit_nonblank_basis(confirmed, evidence):
    values = floor_inputs()
    values["floors"][0].update(usage_confirmed=confirmed, usage_evidence=evidence)
    with pytest.raises(ValidationError):
        EnvironmentalContext.model_validate(values)


@pytest.mark.parametrize(
    "methods,selected",
    [
        ([], []),
        (["bazhai"], []),
        (["jinsuo"], ["jinsuo"]),
        (["monthly_stars", "bazhai"], ["monthly_stars"]),
        (
            ["annual_stars", "bazhai", "xuankong_natal"],
            ["annual_stars", "xuankong_natal"],
        ),
    ],
)
def test_household_and_zodiac_indices_are_explicitly_separate_from_bazhai_minggua(
    methods, selected
):
    context = EnvironmentalContext.model_validate(
        {
            "orientation": orientation(),
            "household_composition_confirmed": True,
            "household_members": [member("p", roles=["parent"], zodiac="狗")],
        }
    )
    result = analyze_environmental_context(context, methods)
    person = result["household_correspondences"][0]
    for entry in [person, *person["associations"]]:
        assert (
            entry["scope"] == "environmental_palace_symbolic_index_not_bazhai_minggua"
        )
        assert entry["applicable_methods"] == [
            "annual_stars",
            "monthly_stars",
            "xuankong_natal",
            "jinsuo",
        ]
        assert entry["selected_applicable_methods"] == selected
        assert entry["application_status"] == (
            "symbolic_index_for_selected_environmental_methods"
            if selected
            else "symbolic_reference_only"
        )
    assert all(a["primary_palace"] == "乾" for a in person["associations"])


@pytest.mark.parametrize("with_orientation", [False, True])
def test_explicit_symbolic_household_query_finishes_without_physical_binding(
    with_orientation,
):
    values = {
        "household_scope": "symbolic_reference",
        "household_composition_confirmed": True,
        "household_members": [member("father", roles=["parent"], zodiac="狗")],
    }
    if with_orientation:
        values["orientation"] = orientation()
    result = analyze_environmental_context(
        EnvironmentalContext.model_validate(values), []
    )
    assert result["status"] == "complete"
    assert result["missing_inputs"] == []
    person = result["household_correspondences"][0]
    for association in person["associations"]:
        assert association["primary_palace"] == "乾"
        assert association["primary_direction"] is None
        assert association["opposite_direction"] is None
        assert association["physical_sector_binding"] == "not_confirmed"
        assert association["application_status"] == "symbolic_reference_only"


def test_default_physical_household_query_still_needs_geometry_and_symbolic_scope_does_not_clear_floor_requirements():
    values = {
        "household_composition_confirmed": True,
        "household_members": [member("father", roles=["parent"])],
    }
    physical = evaluate(**values)
    assert physical["status"] == "partial"
    assert (
        "environmental_context.orientation.center_confirmed"
        in physical["missing_inputs"]
    )
    values.update(
        household_scope="symbolic_reference",
        floors=[
            {
                "floor_id": "first",
                "level": 1,
                "subject_ids": ["father"],
                "evidence": "实际使用一层，尚未确认坐标",
            }
        ],
    )
    with_floor = evaluate(**values)
    assert with_floor["status"] == "partial"
    assert (
        "environmental_context.floors.first.center_confirmed"
        in with_floor["missing_inputs"]
    )
