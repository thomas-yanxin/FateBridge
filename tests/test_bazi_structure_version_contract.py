"""Historical projections remain readable without weakening current semantics."""

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaError
from pydantic import ValidationError

from fatebridge.core.output_bazi_evidence import EvidenceStructureProfile


@pytest.mark.parametrize(
    "payload",
    [
        {
            "resolution_policy": "layered_conflict_review_v1",
            "dominant_structure": {"key": "default_support", "useful_elements": ["火"]},
        },
        {"dominant_structure": {"key": "default_support"}},
        {"dominant_structure": {"useful_elements": ["火"]}},
        {
            "resolution_policy": "source_conditions_before_preference_v2",
            "dominant_structure": {
                "key": "selected_month_reference",
                "formation_status": "not_adjudicated",
                "useful_elements": [],
            },
        },
        {"resolution_policy": "source_conditions_before_preference_v2"},
    ],
)
def test_old_and_current_values_are_projection_compatible_without_rewriting(payload):
    before = repr(payload)
    EvidenceStructureProfile.model_validate(payload)
    Draft202012Validator(EvidenceStructureProfile.model_json_schema()).validate(payload)
    assert repr(payload) == before


@pytest.mark.parametrize(
    "dominant",
    [
        {"key": "default_support"},
        {"key": "default_support", "useful_elements": ["火"]},
        {"useful_elements": ["火"]},
        {"key": "selected_month_reference", "formation_status": "formed"},
        {"key": "selected_month_reference", "useful_elements": ["火"]},
    ],
)
def test_current_policy_cannot_accept_legacy_promotion_or_unadjudicated_preferences(
    dominant,
):
    payload = {
        "resolution_policy": "source_conditions_before_preference_v2",
        "dominant_structure": dominant,
    }
    with pytest.raises(ValidationError):
        EvidenceStructureProfile.model_validate(payload)
    with pytest.raises(SchemaError):
        Draft202012Validator(EvidenceStructureProfile.model_json_schema()).validate(
            payload
        )
