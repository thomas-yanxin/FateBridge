"""Method selection, orientation and source boundaries for Feng Shui."""

import pytest
from pydantic import ValidationError

from fatebridge.core.fengshui.models import AssessRequest
from fatebridge.services.fengshui import calculate_fengshui_assessment as _assess
from tests.fixtures.fengshui import payload
from tests.unit_test.fixtures.fengshui_layout import (
    form,
)


def assess(**kwargs):
    return _assess(AssessRequest.model_validate(kwargs))


def unknown_orientation(**updates):
    return {
        "direction_confirmed": False,
        "floorplan_alignment_confirmed": False,
        "center_confirmed": False,
        "evidence": "尚未测量或核对户型方向",
        **updates,
    }


@pytest.mark.parametrize("methods", [[], ["bazhai"]])
def test_unselected_environment_methods_are_references_without_findings(
    methods,
) -> None:
    result = assess(
        scene="shared_rental",
        methods=methods,
        environmental_context={"orientation": unknown_orientation()},
        occupants=[
            {
                "subject_id": "user",
                "effective_birth_year": 1990,
                "gender_convention": "male",
            }
        ],
        form_observations=[form()],
    )
    assert list(result["layers"]) == methods
    assert set(result["method_details"]["methods"]) == set(methods)
    assert result["layout_analysis"]["placement_findings"] == []
    assert result["layout_analysis"]["environment_adjustments"] == []
    context = result["layout_analysis"]["environmental_context"]
    assert context["separation_policy"]["selected_environmental_methods"] == []
    for entry in result["method_policy"]["method_priority"][:2]:
        assert entry["selection_status"] == "reference_only_not_selected"
        assert entry["selected_engine_layers"] == []
        assert entry["judgment_scope"] == "no_calculation_or_physical_judgment"


def test_empty_environment_context_is_rejected() -> None:
    with pytest.raises(ValidationError):
        assess(environmental_context={})


@pytest.mark.parametrize("conflict", ["location", "facing", "jinsuo", "external_form"])
def test_explicit_unknown_orientation_cannot_be_bypassed_by_any_physical_layer(
    conflict: str,
) -> None:
    inputs = {
        "scene": "workstation",
        "environmental_context": {"orientation": unknown_orientation()},
        "form_observations": [form()],
    }
    if conflict == "location":
        inputs["placements"] = [
            {"object_id": "desk", "purpose": "desk", "location_direction": "N"}
        ]
    elif conflict == "facing":
        inputs["placements"] = [
            {
                "object_id": "desk",
                "purpose": "desk",
                "facing_direction": "N",
                "facing_role": "desk_facing",
            }
        ]
    elif conflict == "jinsuo":
        inputs["features"] = [
            {
                "object_id": "feature",
                "direction": "N",
                "classification": "sand",
                "classification_basis": "user_confirmed",
                "evidence": "与未确认方位矛盾的落宫声明",
            }
        ]
    else:
        inputs["xuankong"] = {
            **payload("xuankong_natal"),
            "interpretation": {
                "external_forms": [
                    {
                        "direction": "N",
                        "mountain_present": True,
                        "observation_basis": "user_confirmed",
                        "evidence": "与未确认方位矛盾的外局分宫",
                    }
                ]
            },
        }
    with pytest.raises(ValidationError):
        AssessRequest.model_validate(inputs)


def test_confirmed_facing_remains_distinct_from_unconfirmed_house_sector_geometry() -> (
    None
):
    result = assess(
        scene="workstation",
        methods=["annual_stars"],
        effective_year=2026,
        environmental_context={
            "orientation": unknown_orientation(
                direction_confirmed=True, north_reference="magnetic"
            )
        },
        placements=[
            {
                "object_id": "desk",
                "purpose": "desk",
                "facing_direction": "N",
                "facing_role": "desk_facing",
            }
        ],
    )
    assert result["layers"]["annual_stars"]["status"] == "complete"
    assert result["layout_analysis"]["placement_findings"] == []
    assert (
        "placements.desk.location_direction"
        in result["layout_analysis"]["missing_inputs"]
    )
    context = result["layout_analysis"]["environmental_context"]
    assert context["orientation_review"]["physical_sector_binding_allowed"] is False


def test_candidate_cannot_erase_known_unknown_orientation_by_supplying_other_context() -> (
    None
):
    inputs = {
        "scene": "workstation",
        "methods": ["annual_stars"],
        "effective_year": 2026,
        "form_observations": [form()],
        "environmental_context": {"orientation": unknown_orientation()},
        "layout_constraints": [
            {"object_id": "desk", "can_relocate": True, "evidence": "允许移动"}
        ],
        "layout_alternatives": [
            {
                "candidate_id": "move",
                "object_id": "desk",
                "changes": ["location"],
                "placement": {
                    "object_id": "desk",
                    "purpose": "desk",
                    "location_direction": "N",
                },
                "form_observation": form(),
                "environmental_context": {
                    "observations": [
                        {
                            "observation_id": "material",
                            "object_id": "desk",
                            "category": "material",
                            "feature": "wood",
                            "evidence": "独立确认材质，未确认任何新方向",
                        }
                    ]
                },
                "physically_feasible": True,
                "evidence": "候选新位置",
            }
        ],
    }
    with pytest.raises(ValidationError):
        AssessRequest.model_validate(inputs)


def test_all_composed_source_ids_are_resolved_by_published_rulesets() -> None:
    result = assess(
        scene="home",
        methods=["annual_stars", "jinsuo", "bazhai"],
        effective_year=2026,
        house={"sitting_trigram": "坎"},
        features=[
            {
                "object_id": "feature",
                "direction": "N",
                "classification": "sand",
                "classification_basis": "user_confirmed",
                "evidence": "已确认环境分类与方位",
            }
        ],
        environmental_context={
            "orientation": {
                "direction_confirmed": True,
                "north_reference": "magnetic",
                "floorplan_alignment_confirmed": True,
                "center_confirmed": True,
                "evidence": "已测量方向并确认中心和户型对齐",
            }
        },
    )
    sources = result["source_catalog"].keys()
    rulesets = {r["ruleset_id"]: r for r in result["rulesets"]}
    annual_ruleset = result["layers"]["annual_stars"]["ruleset"]["ruleset_id"]
    annual_citation = rulesets[annual_ruleset]["source_citations"]["S4"]
    method_citation = rulesets["expert_fengshui_methods_v1"]["source_citations"]["S4"]
    assert annual_citation["scope"] != method_citation["scope"]
    assert "九宫挨星掌诀" in method_citation["locator"]
    assert result["source_catalog"]["S4"]["title"] == "沈氏玄空学卷四转录"

    def inspect(value):
        if isinstance(value, dict):
            if "source_ids" in value:
                assert set(value["source_ids"]) <= sources
            else:
                pass
            for item in value.values():
                inspect(item)
        elif isinstance(value, list):
            for item in value:
                inspect(item)
        else:
            pass

    inspect(result)
    for trace in result["rule_trace"]:
        record = rulesets[trace["ruleset_id"]]
        assert trace["source_ids"] == record["source_ids"]
