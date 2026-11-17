"""Publisher conditions cover every registered material and keep observed uncertainty."""

import json
from pathlib import Path

import pytest

from fatebridge.core.fengshui.material_inputs import MaterialShapeFact
from fatebridge.core.fengshui.materials import analyze_material_facts

SOURCE = json.loads(
    (
        Path(__file__).parents[1]
        / "fixtures/fengshui-material-application-afsi-2006.json"
    ).read_text(encoding="utf-8")
)


@pytest.mark.parametrize(
    "case,value,basis,application_status,condition_status",
    [
        ("omitted", None, None, "needs_confirmation", "needs_confirmation"),
        ("null", None, "user_confirmed", "needs_confirmation", "needs_confirmation"),
        (
            "measured_false",
            False,
            "measured",
            "conditions_not_met",
            "does_not_match_condition",
        ),
        (
            "confirmed_true",
            True,
            "user_confirmed",
            "conditions_reviewed",
            "matches_condition",
        ),
        ("photo_true", True, "image_observed", "needs_confirmation", "candidate_only"),
        (
            "photo_false",
            False,
            "image_observed",
            "needs_confirmation",
            "candidate_only",
        ),
        (
            "photo_null",
            None,
            "image_observed",
            "needs_confirmation",
            "needs_confirmation",
        ),
    ],
    ids=lambda value: str(value),
)
@pytest.mark.parametrize(
    "source_material", SOURCE["materials"], ids=lambda row: row["material"]
)
def test_published_application_proportion_condition_for_every_registered_material(
    source_material, case, value, basis, application_status, condition_status
):
    application = {
        "ruleset_id": "afsi_application_conditions_v1",
        **{
            criterion: {
                "value": True,
                "observation_basis": "user_confirmed",
                "evidence": "工程样本：其余作者条件独立确认，隔离尺度变量",
            }
            for criterion in source_material["criteria"]
            if criterion != "proportionate_to_space"
        },
    }
    if basis is not None:
        application["proportionate_to_space"] = {
            "value": value,
            "observation_basis": basis,
            "evidence": "工程样本：记录原作者定性尺度观察，不计算足量",
        }
    record = {
        "fact_id": "source-application",
        "object_id": "item",
        "material": source_material["material"],
        "element_use": source_material["element_use"],
        "observation_basis": "user_confirmed",
        "evidence": "工程样本：只确认实际代表物身份，不由身份补尺度",
        "application": application,
    }
    if source_material["material"] == "living_plant":
        record["plant_alive"] = True
    finding = analyze_material_facts([MaterialShapeFact.model_validate(record)])[
        "findings"
    ][0]
    review = finding["application_analysis"]
    assert finding["material_eligibility"] == "conditional_material_match"
    assert review["status"] == application_status
    assert {check["criterion"] for check in review["application_conditions"]} == set(
        source_material["criteria"]
    )
    proportion = next(
        check
        for check in review["application_conditions"]
        if check["criterion"] == "proportionate_to_space"
    )
    assert proportion["status"] == condition_status
    assert proportion["source_ids"] == ["A2"]
    assert bool(review["missing_inputs"]) == (
        application_status == "needs_confirmation"
    )
    assert review["placement_suitability"] == "not_assessed"
    assert review["action_status"] != "ready"
    assert "quantitative_dosage_or_sufficiency" in review["unassessed_dimensions"]
