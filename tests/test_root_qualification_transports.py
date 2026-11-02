"""The public chart and its explanation consume one surviving-root receipt."""

import asyncio

from fatebridge.application.examples import evidence_views
from fatebridge.core.output_root_qualification import RootQualification
from fatebridge.core.root_qualification import root_qualification_snapshot_lines
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

PAYLOAD = {
    "name": "虚构阳长生根回归",
    "birth_year": 1990,
    "birth_month": 5,
    "birth_day": 15,
    "birth_hour": 10,
    "birth_minute": 30,
    "birth_timezone": "Asia/Shanghai",
    "use_true_solar_time": False,
    "gender": "男",
    "analysis_year": 2026,
    "analysis_month": 10,
    "analysis_day": 12,
}


def test_public_root_qualification_receipt_text_and_claims_match_on_all_transports(
    rest, tmp_path, capsys
):
    spec = SPECS["bazi_birth"]
    response = rest.post(
        spec.rest_path, json=PAYLOAD, params={"response_char_limit": 0}
    )
    code, local = call_cli(
        spec, PAYLOAD, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    protocol = asyncio.run(native(spec, PAYLOAD))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    result = response.json()
    assert business(result) == business(local) == business(protocol.structured_content)
    birth = result["bazi_birth"]
    assert [p["stem"] + p["branch"] for p in birth["four_pillars"].values()] == [
        "庚午",
        "辛巳",
        "庚辰",
        "辛巳",
    ]
    assessment = birth["day_master"]["assessment"]
    assert birth["day_master"]["strength"] == "强"
    assert assessment["method_id"] == "season_root_revelation_relations_v10"
    assert assessment["structural_decision"]["numerical_label"] == "中和"
    assert assessment["structural_decision"]["vigorous_roots"] == ["month", "hour"]
    shared = birth["structure_profile"]["evidence_chain"]["strength_context"]
    assert shared["root_qualifications"] == assessment["root_qualifications"]
    for row in shared["root_qualifications"]:
        RootQualification.model_validate(row)
    for line in root_qualification_snapshot_lines(assessment):
        assert line in result["snapshot_text"]
    receipt = result["run_metadata"]
    claim = CalculationClaim(
        path="bazi_birth.structure_profile.evidence_chain.strength_context.root_qualifications.1.qualified_for_structural_rule",
        value=True,
        run_id=receipt["run_id"],
        business_output_sha256=receipt["business_output_sha256"],
    )
    assert (
        verify_calculation_claims(result, [claim])["status"]
        == "verified_structured_facts"
    )
    assert (
        verify_calculation_claims(result, [claim.model_copy(update={"value": False})])[
            "status"
        ]
        == "rejected"
    )


def test_published_root_qualification_view_preserves_facts_and_rejects_array_descent(
    rest,
):
    spec = SPECS["bazi_birth"]
    fields = evidence_views(spec)["root_qualification"]["fields"]
    response = rest.post(
        spec.rest_path,
        json=PAYLOAD,
        params={
            "fields": fields,
            "strict_fields": "true",
            "include_snapshot_text": "false",
        },
    )
    assert response.status_code == 200, response.text
    context = response.json()["bazi_birth"]["structure_profile"]["evidence_chain"][
        "strength_context"
    ]
    assert context["root_qualifications"][1]["kind"] == "yang_growth_root"
    response = rest.post(
        spec.rest_path,
        json=PAYLOAD,
        params={
            "fields": [
                "bazi_birth.structure_profile.evidence_chain.strength_context.root_qualifications.qualified_for_structural_rule"
            ],
            "strict_fields": "true",
            "include_snapshot_text": "false",
        },
    )
    # Public projection descends objects, not array items. Request the receipt
    # array as a whole; a non-object path must fail visibly, never erase facts.
    assert response.status_code == 422, response.text
    assert response.json()["issues"][0]["code"] == "non_object_projection_path"
