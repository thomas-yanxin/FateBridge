"""Material symbolism is not a universal taboo, chart need, or feasible action."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.fengshui.context_inputs import EnvironmentalContext
from fatebridge.core.fengshui.material_inputs import MaterialShapeFact
from fatebridge.core.fengshui.materials import (
    analyze_material_facts,
    material_reference,
)
from fatebridge.services.fengshui import assess

AFSI_COLOURS = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/fengshui-material-colours-afsi-2004.json"
    ).read_text(encoding="utf-8")
)["colours"]


def fact(**values):
    return {
        "fact_id": "f",
        "object_id": "item",
        "material": "processed_wood",
        "observation_basis": "user_confirmed",
        "evidence": "确认对象实际属性，不按物名猜测",
        **values,
    }


def material_request(**values):
    return dict(
        methods=[],
        scene="shared_rental",
        environmental_context=dict(
            orientation=dict(
                direction_confirmed=False, evidence="只审查材料属性，方位未知"
            ),
            objects=[
                dict(
                    object_id="item",
                    label="待审物件",
                    kind="material_object",
                    evidence="物件身份已确认",
                )
            ],
            material_facts=[fact(**values)],
        ),
    )


@pytest.mark.parametrize(
    "shape,element",
    [
        ("columnar", "木"),
        ("triangular", "火"),
        ("square", "土"),
        ("round", "金"),
        ("wavy", "水"),
    ],
)
def test_shapes_are_separate_source_references_not_pointing_geometry(shape, element):
    result = analyze_material_facts(
        [MaterialShapeFact.model_validate(fact(shape=shape))]
    )
    finding = result["findings"][0]
    assert finding["shape_reference"]["element"] == element
    assert finding["shape_reference"]["source_ids"] == ["M_FSI"]
    assert finding["finding"] == "reference_only_no_general_taboo"
    assert not finding["shape_used_as_afsi_remedy"]
    assert result["rule_coverage_counts"]["supported"] == 0
    assert result["action_options"] == []


@pytest.mark.parametrize(
    "material,goal,extra",
    [
        ("living_plant", "wood_remedy", {"plant_alive": True}),
        ("metal", "metal_remedy", {}),
        ("stone", "earth_remedy", {}),
        ("ceramic", "earth_remedy", {}),
        ("water", "water_remedy", {}),
    ],
)
def test_registered_material_use_stays_conditional_and_unplaced(material, goal, extra):
    value = fact(element_use=goal)
    value.update(material=material, **extra)
    result = analyze_material_facts([MaterialShapeFact.model_validate(value)])
    finding = result["findings"][0]
    assert finding["material_eligibility"] == "conditional_material_match"
    assert finding["placement_suitability"] == "not_assessed"
    assert not finding["action_required"]
    assert (
        finding["requested_element_basis"]
        == "explicit_representation_question_not_natal_or_environmental_need"
    )


def test_processed_wood_exclusion_is_not_global_bad_furniture_or_colour_exclusion():
    request = material_request(
        element_use="wood_remedy", colour="green", shape="columnar"
    )
    result = assess(**request)
    finding = result["layout_analysis"]["material_analysis"]["findings"][0]
    assert finding["material_eligibility"] == "excluded_by_selected_author"
    assert finding["colour_eligibility"] == "colour_substitute_match"
    assert finding["finding"] == "colour_substitute_only"
    assert result["coverage"]["analysis_progress"]["assessment_complete"] is True
    assert not result["layout_analysis"]["missing_inputs"]
    assert result["layers"] == {}


@pytest.mark.parametrize(
    "attribute,value",
    [("material", "glass"), ("material", "plastic"), ("shape", "irregular")],
)
def test_unregistered_attributes_are_not_invented_cures(attribute, value):
    record = fact(element_use="wood_remedy")
    record.update({attribute: value})
    finding = analyze_material_facts([MaterialShapeFact.model_validate(record)])[
        "findings"
    ][0]
    assert finding["material_eligibility"] != "conditional_material_match"
    assert finding["placement_suitability"] == "not_assessed"


@pytest.mark.parametrize("basis", ["measured", "user_confirmed", "image_observed"])
def test_living_plant_question_requires_actual_alive_fact(basis):
    record = fact(element_use="wood_remedy")
    record.update(material="living_plant", observation_basis=basis)
    result = analyze_material_facts([MaterialShapeFact.model_validate(record)])
    assert result["status"] == "partial"
    assert (
        "environmental_context.material_facts.f.plant_alive" in result["missing_inputs"]
    )
    assert result["findings"][0]["candidate_only"]


def test_shape_alone_does_not_supply_afsi_material_or_colour():
    record = fact(shape="triangular", element_use="fire_remedy")
    record.pop("material")
    result = analyze_material_facts([MaterialShapeFact.model_validate(record)])
    assert (
        "environmental_context.material_facts.f.material_or_colour"
        in result["missing_inputs"]
    )
    assert result["status"] == "partial"
    assert result["findings"][0]["material_eligibility"] == "not_provided"
    assert (
        result["findings"][0]["reference_finding"]
        == "not_determined_from_supplied_attributes"
    )


def test_separate_attributes_can_ask_same_use_without_promoting_photo_confirmation():
    request = material_request(element_use="wood_remedy")
    request["environmental_context"]["material_facts"].append(
        dict(
            fact_id="colour",
            object_id="item",
            colour="green",
            element_use="wood_remedy",
            observation_basis="image_observed",
            evidence="颜色仅照片候选，独立于已确认木材",
        )
    )
    findings = assess(**request)["layout_analysis"]["material_analysis"]["findings"]
    assert findings[0]["material_eligibility"] == "excluded_by_selected_author"
    assert not findings[0]["candidate_only"]
    assert findings[1]["material_eligibility"] == "not_provided"
    assert findings[1]["colour_eligibility"] == "colour_substitute_match"
    assert findings[1]["candidate_only"]


def test_different_attribute_bases_stay_independent_and_duplicate_attributes_reject():
    records = [
        fact(),
        {
            **fact(shape="round"),
            "fact_id": "shape",
            "material": None,
            "observation_basis": "image_observed",
        },
    ]
    context = material_request()["environmental_context"]
    context["material_facts"] = records
    result = assess(methods=[], environmental_context=context)
    findings = result["layout_analysis"]["material_analysis"]["findings"]
    assert not findings[0]["candidate_only"] and findings[1]["candidate_only"]
    context["material_facts"][1]["material"] = "glass"
    with pytest.raises(ValidationError, match="同一物件属性"):
        EnvironmentalContext.model_validate(context)


@pytest.mark.parametrize(
    "bad",
    [
        {"plant_alive": True},
        {"material": None},
        {"observation_basis": "guessed"},
        {"element_use": "bazi_favourite"},
        {"evidence": " "},
    ],
)
def test_material_schema_rejects_inferred_or_empty_facts(bad):
    with pytest.raises(ValidationError):
        MaterialShapeFact.model_validate({**fact(), **bad})


def test_material_reference_is_isolated_and_has_source_version_and_locations():
    one = material_reference()
    two = deepcopy(one)
    one["shapes"]["round"]["element"] = "changed"
    assert material_reference() == two
    for source in two["ruleset"]["sources"]:
        assert (
            source["url"]
            and source["title"]
            and source["source_version"]
            and source["locator"]
        )


@pytest.mark.parametrize("source_colour", AFSI_COLOURS, ids=lambda row: row["colour"])
@pytest.mark.parametrize(
    "requested_use",
    ["wood_remedy", "fire_remedy", "earth_remedy", "metal_remedy", "water_remedy"],
)
def test_afsi_published_palette_against_each_requested_element(
    source_colour, requested_use
):
    finding = analyze_material_facts(
        [
            MaterialShapeFact.model_validate(
                fact(
                    material=None,
                    colour=source_colour["colour"],
                    element_use=requested_use,
                )
            )
        ]
    )["findings"][0]
    assert finding["colour_reference"] == source_colour["element"]
    assert finding["colour_eligibility"] == (
        "colour_substitute_match"
        if source_colour["element_use"] == requested_use
        else "no_matching_colour_substitute"
    )
    assert finding["source_ids"] == ["M_AFSI"]
    assert finding["material_eligibility"] == "not_provided"
    assert finding["placement_suitability"] == "not_assessed"
    assert not finding["action_required"]


def test_afsi_reference_keeps_the_complete_published_colour_vocabulary():
    assert material_reference()["colours"] == {
        row["colour"]: row["element"] for row in AFSI_COLOURS
    }


def test_broad_brown_observation_does_not_establish_published_tan():
    finding = analyze_material_facts(
        [
            MaterialShapeFact.model_validate(
                fact(material=None, colour="brown", element_use="earth_remedy")
            )
        ]
    )["findings"][0]
    assert finding["colour"] == "brown"
    assert finding["colour_reference"] is None
    assert finding["colour_eligibility"] == "no_matching_colour_substitute"
    assert finding["finding"] == "not_determined_from_supplied_attributes"


def test_published_tan_in_a_photo_keeps_candidate_status():
    result = analyze_material_facts(
        [
            MaterialShapeFact.model_validate(
                fact(
                    material=None,
                    colour="tan",
                    element_use="earth_remedy",
                    observation_basis="image_observed",
                )
            )
        ]
    )
    finding = result["findings"][0]
    assert result["status"] == "partial"
    assert finding["colour_reference"] == "土"
    assert finding["colour_eligibility"] == "colour_substitute_match"
    assert finding["candidate_only"]
    assert finding["finding"] == "needs_confirmation"
    assert finding["placement_suitability"] == "not_assessed"
