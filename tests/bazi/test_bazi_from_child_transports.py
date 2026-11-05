"""Source-scoped from-child facts agree on REST, native MCP and CLI."""

import asyncio

import pytest

from fatebridge.application.examples import suggested_fields
from fatebridge.core.classical_from_child import from_child_snapshot_lines
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.bazi.test_bazi_year_contract import TOPICS
from tests.support.transports import SPECS, business, call_cli, native
from tests.support.transports import rest as _shared_rest

# A fabricated protocol subject, chosen to reproduce the literal SJ07 pillars.
# This does not authenticate the historical author's birth date or biography.
INPUT = {
    "name": "虚构从儿路径验证",
    "gender": "男",
    "birth_year": 1900,
    "birth_month": 4,
    "birth_day": 5,
    "birth_hour": 18,
    "birth_minute": 0,
    "birth_timezone": "Asia/Shanghai",
    "use_true_solar_time": False,
}


def walk(value, path):
    for part in path.split("."):
        value = value[part]
    return value


rest = _shared_rest


@pytest.mark.parametrize(
    "name", ["bazi_" + topic for topic in TOPICS] + ["analyze_destiny"]
)
def test_published_path_and_source_agree_on_all_three_transports(
    name, rest, tmp_path, capsys
):
    spec = SPECS[name]
    fields = suggested_fields(spec, view="from_child")
    controls = {
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    rest_fields = fields if spec.rest_path else ["bazi_birth." + f for f in fields]
    response = rest.post(
        spec.rest_path or SPECS["bazi_birth"].rest_path,
        json=INPUT,
        params={**controls, "fields": rest_fields},
    )
    protocol = asyncio.run(native(spec, INPUT, **controls))
    code, cli = call_cli(
        spec,
        INPUT,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    # analyze_destiny has MCP/CLI only. Its root profile must agree with the
    # same profile exposed by the existing bazi_birth REST service.
    comparable = business(response.json())
    if not spec.rest_path:
        comparable = comparable["bazi_birth"]
    assert comparable == business(protocol.structured_content) == business(cli)
    ref = walk(comparable, fields[0])
    assert ref["ordinary_fuyi_requires_review"]
    assert ref["formation_status"] == "not_adjudicated"
    assert ref["observed_conditions"][0]["occurrence_ids"] == ["month.stem"]
    assert ref["source"]["id"] == "ditian_ren_shunju_from_child_v1"
    assert ref["conditional_direction"]["if_route_is_formed"]["useful_elements"] == [
        "金",
        "水",
    ]


def test_same_run_snapshot_and_claim_verification_cannot_promote_formation(rest):
    spec = SPECS["bazi_birth"]
    response = rest.post(spec.rest_path, json=INPUT, params={"response_char_limit": 0})
    assert response.status_code == 200
    result = response.json()
    profile = result["bazi_birth"]["structure_profile"]
    for line in from_child_snapshot_lines(profile):
        assert line in result["snapshot_text"]
    assert not result["bazi_birth"]["favorable_elements"]
    assert (
        profile["from_child_reference"]
        == profile["evidence_chain"]["from_child_reference"]
    )
    run = result["run_metadata"]
    claim = CalculationClaim(
        path="bazi_birth.structure_profile.from_child_reference.formation_status",
        value="not_adjudicated",
        run_id=run["run_id"],
        business_output_sha256=run["business_output_sha256"],
    )
    assert (
        verify_calculation_claims(result, [claim])["status"]
        == "verified_structured_facts"
    )
    assert (
        verify_calculation_claims(
            result, [claim.model_copy(update={"value": "formed"})]
        )["status"]
        == "rejected"
    )
    # Existing object projection rules continue to forbid descent into arrays.
    invalid = rest.post(
        spec.rest_path,
        json=INPUT,
        params={
            "fields": [
                "bazi_birth.structure_profile.from_child_reference.occurrences.stem"
            ],
            "strict_fields": True,
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["issues"][0]["code"] == "non_object_projection_path"
