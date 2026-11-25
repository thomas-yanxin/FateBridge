"""Frozen documentary failures remain visible on the three public surfaces."""

import json
from pathlib import Path

import pytest

import scripts.bazi.audit_bazi_authority as authority
from scripts.bazi.audit_bazi_authority import strength_review_axis
from tests.support.transports import AS_OF, SPECS, business
from tests.support.transports import rest as shared_rest
from tests.support.transports import surface_calls

rest = shared_rest
ROOT = Path(__file__).resolve().parents[2]
REVIEW = json.loads(
    (ROOT / "tests/data/bazi_disagreement_review_v1/review.json").read_text()
)
SPEC = SPECS["bazi_source_compare"]
CASES = [
    *REVIEW["disagreements"],
    *REVIEW["constraints"],
    *REVIEW["previously_exposed_controls"],
]


def test_frozen_audit_preserves_failures_and_unadjudicated_denominators():
    report = strength_review_axis()
    assert report["baseline_reproduced"] is True
    assert report["current_denominators"] == REVIEW["frozen_denominators"]
    assert report["authority_certified"] is False
    assert report["independent_human_double_read"] == "not_completed"
    assert report["new_independent_validation_credit"] == 0
    assert report["classical_grade_comparison"] == {
        "known_source_records": 123,
        "compared_records": 0,
        "matching_records": 0,
        "mismatching_records": 0,
        "unadjudicated_records": 123,
        "unadjudicated_is_a_pass": False,
        "scope": "工程旧分歧分母保留；原典未知独立记为未验收，不从样例期望回填裁定。",
    }


@pytest.mark.parametrize(
    "section,field,value",
    [
        ("disagreements", "retained_strength", "弱"),
        ("disagreements", "registered_original_anchor", "invented quotation"),
        ("disagreements", "original_anchor_status", "independently_verified"),
        ("constraints", "constraint_matches", False),
        ("constraints", "retained_anchor", "invented constraint"),
        ("previously_exposed_controls", "engineering_strength", "弱"),
        ("previously_exposed_controls", None, None),
    ],
)
def test_altered_manifest_cannot_claim_baseline_reproduced(
    section, field, value, monkeypatch, tmp_path
):
    manifest = json.loads(json.dumps(REVIEW))
    if field is None:
        manifest[section] = []
    else:
        manifest[section][0][field] = value
    manifest_directory = tmp_path / "tests/data/bazi_disagreement_review_v1"
    manifest_directory.mkdir(parents=True)
    (manifest_directory / "review.json").write_text(json.dumps(manifest))
    (tmp_path / "src").symlink_to(ROOT / "src", target_is_directory=True)
    (tmp_path / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
    monkeypatch.setattr(authority, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="manifest hash mismatch"):
        strength_review_axis()


@pytest.mark.parametrize("projection", [False, True], ids=["full", "strict"])
@pytest.mark.parametrize("record", CASES, ids=lambda record: record["reference_id"])
def test_frozen_cases_do_not_promote_engineering_grades_to_source_judgments(
    record, projection, surface_calls
):
    arguments = dict(
        zip(
            ["year_pillar", "month_pillar", "day_pillar", "hour_pillar"],
            record["pillars"],
            strict=True,
        )
    )
    controls = {
        "include_snapshot_text": False,
        "response_char_limit": 0,
        **(
            {
                "fields": [
                    "current_calculation.strength_level",
                    "current_calculation.classical_adjudication",
                    "source_comparison",
                ],
                "strict_fields": True,
            }
            if projection
            else {}
        ),
    }
    response, protocol, code, cli = surface_calls(
        SPEC, arguments, projection=controls, rest_as_of=AS_OF
    )
    assert response.status_code == 200 and not protocol.is_error and code == 0
    result = business(response.json())
    assert result == business(protocol.structured_content) == business(cli)
    if not projection:
        SPEC.output_model.model_validate(response.json())
    judgment = result["current_calculation"]["classical_adjudication"]
    assert judgment["status"] == "not_adjudicated"
    assert judgment["body_strength"] is None
    assert judgment["ordinary_fuyi_applicable"] is None
    assert (
        result["current_calculation"]["strength_level"]
        == record["engineering_strength"]
    )
    source = next(
        source
        for source in result["source_comparison"]["records"]
        if source["reference_id"] == record["reference_id"]
    )
    assert source["independent_annotation_review"] == "not_certified"


def test_invalid_strict_projection_is_rejected_on_all_surfaces(surface_calls):
    response, protocol, code, cli = surface_calls(
        SPEC,
        dict(
            zip(
                ["year_pillar", "month_pillar", "day_pillar", "hour_pillar"],
                REVIEW["constraints"][1]["pillars"],
                strict=True,
            )
        ),
        projection={
            "fields": ["current_calculation.invented_grade"],
            "strict_fields": True,
        },
        rest_as_of=AS_OF,
    )
    assert response.status_code == 422 and protocol.is_error and code == 1
    assert response.json()["error_code"] == protocol.structured_content["error_code"]
    assert response.json()["error_code"] == cli["error_code"]
