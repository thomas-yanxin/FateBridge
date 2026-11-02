"""Historical readers coexist with the stricter current month producer model."""

import pytest
from jsonschema import Draft202012Validator
from jsonschema import ValidationError as SchemaValidationError
from pydantic import ValidationError

from fatebridge.core.output_bazi_evidence import EvidenceStructureProfile
from fatebridge.core.output_candidate_selection import MonthStructureReference


@pytest.mark.parametrize(
    "key",
    [
        "default_support",
        "yang_ren_jia_sha",
        "shi_shen_zhi_sha",
        "sha_yin_xiang_sheng",
        "shang_guan_pei_yin",
        "shang_guan_jian_guan",
    ],
)
def test_historical_structure_labels_remain_readable_without_becoming_current_month_labels(
    key,
):
    old = {"key": key, "useful_elements": ["木"], "priority": 10}
    result = EvidenceStructureProfile.model_validate({"dominant_structure": old})
    assert result.model_dump(exclude_none=True)["dominant_structure"] == old
    with pytest.raises(ValidationError):
        MonthStructureReference.model_validate(old)


def test_current_month_key_cannot_fall_back_to_legacy_to_promote_unadjudicated_elements():
    for field in ["useful_elements", "avoid_elements", "useful_ten_gods"]:
        bad = {"key": "selected_month_reference", field: ["虚构用神"]}
        with pytest.raises(ValidationError):
            EvidenceStructureProfile.model_validate({"dominant_structure": bad})
    with pytest.raises(ValidationError):
        EvidenceStructureProfile.model_validate(
            {"dominant_structure": {"key": "invented_structure"}}
        )


def test_legacy_leaf_projection_still_needs_no_sibling_key():
    projected = {"dominant_structure": {"useful_elements": ["木"]}}
    assert (
        EvidenceStructureProfile.model_validate(projected).model_dump(exclude_none=True)
        == projected
    )


@pytest.mark.parametrize(
    "dominant",
    [
        {"key": "default_support"},
        {"formation_status": "formed"},
        {"key": "selected_month_reference", "useful_elements": ["木"]},
        {"key": "default_support", "useful_elements": ["木"]},
    ],
)
def test_current_source_policy_is_strict_in_both_python_and_json_schema(dominant):
    payload = {
        "resolution_policy": "source_conditions_before_preference_v2",
        "dominant_structure": dominant,
    }
    with pytest.raises(ValidationError):
        EvidenceStructureProfile.model_validate(payload)
    with pytest.raises(SchemaValidationError):
        Draft202012Validator(EvidenceStructureProfile.model_json_schema()).validate(
            payload
        )
