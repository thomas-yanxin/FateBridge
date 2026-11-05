"""The public chart and its explanation consume one surviving-root receipt."""

import asyncio
from fractions import Fraction as Q

from fatebridge.application.examples import evidence_views
from fatebridge.core.output_root_qualification import RootQualification
from fatebridge.core.root_qualification import root_qualification_snapshot_lines
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
)
from tests.support.bazi_strength_reference_v3 import (
    assert_current_assessment_arithmetic,
)

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
    assert assessment["method_id"] == "season_root_revelation_relations_v12"
    assert assessment["relations"] == []
    values = ["庚午", "辛巳", "庚辰", "辛巳"]
    assert_current_assessment_arithmetic(values, assessment)
    # Independently rebuild the original per-position hidden budgets. The day
    # stem does not vote; three visible non-day metal stems have full root
    # activation. Only hidden 庚 is revealed, with declared factor 5/4.
    hidden = {
        "木": Q(4, 7),
        "火": Q(4, 3) + Q(16, 7) + Q(8, 7),
        "土": Q(2, 3) + Q(4, 7) + Q(8, 7) + Q(2, 7),
        "金": Q(8, 7) + Q(4, 7),
        "水": Q(2, 7),
    }
    energies = {
        "木": hidden["木"],
        "火": hidden["火"] * 2,
        "土": hidden["土"] * Q(3, 2),
        "金": (hidden["金"] * Q(5, 4) + 3) * Q(1, 2),
        "水": hidden["水"] * Q(3, 4),
    }
    support = energies["金"] + energies["土"]
    weaken = energies["木"] + energies["火"] + energies["水"]
    share = support / (support + weaken)
    assert share == Q(276, 709) < Q(2, 5)
    receipt_math = assessment["threshold_arithmetic"]
    assert receipt_math["energies_exact"] == {k: str(v) for k, v in energies.items()}
    assert receipt_math["support_exact"] == str(support)
    assert receipt_math["weaken_exact"] == str(weaken)
    assert receipt_math["share_exact"] == str(share)
    expected_numerical = (
        "弱" if share < Q(2, 5) else "强" if share > Q(3, 5) else "中和"
    )
    assert assessment["structural_decision"]["numerical_label"] == expected_numerical

    assert receipt_math["physical_root_unit_comparison"][
        "effective_classical_root_force"
    ] == ("not_adjudicated")
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
