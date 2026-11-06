"""Source-position paths are the same structured facts in all public surfaces."""

import asyncio
import json

import pytest

from fatebridge.application.examples import suggested_fields
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.support.result_delivery import reconstruct, store
from tests.support.transports import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
    surface_calls,
)

PAYLOAD = {
    "name": "虚构通路传输回归",
    "birth_year": 1993,
    "birth_month": 12,
    "birth_day": 12,
    "birth_hour": 12,
    "birth_minute": 0,
    "birth_timezone": "Asia/Shanghai",
    "use_true_solar_time": False,
    "gender": "男",
    "analysis_year": 2026,
    "analysis_month": 10,
    "analysis_day": 12,
}


@pytest.mark.parametrize(
    "topic",
    [
        "birth",
        "career",
        "wealth",
        "health",
        "children",
        "education",
        "personality",
        "relatives",
        "marriage",
        "romance",
    ],
)
def test_passage_view_matches_rest_native_mcp_and_cli(
    topic, rest, store, surface_calls
):
    spec = SPECS["bazi_" + topic]
    fields = suggested_fields(spec, view="passage")
    response, protocol, code, local = surface_calls(
        spec,
        PAYLOAD,
        params={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
        options={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
            "response_char_limit": 8192,
        },
        flags=["--response-char-limit", "0", "--strict-fields", "--fields", *fields],
        cli_first=False,
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    result = response.json()
    inline = dict(protocol.structured_content)
    reference = inline.pop("result_delivery", None)
    assert business(result) == business(inline) == business(local)
    if reference is not None:
        # Every business field remains inline at the unchanged8192 budget.
        # Only supplementary receipt details may use exact same-run readback.
        assert reference["deferred_fields"]
        assert set(reference["deferred_fields"]) <= {
            "run_metadata.runtime",
            "run_metadata.provenance",
            "run_metadata.determinism",
            "run_metadata.calculation_evidence",
        }
        restored = reconstruct(store, reference["result_id"])
        assert business(restored) == business(result)
        assert restored["run_metadata"]["run_id"] == inline["run_metadata"]["run_id"]
    assert (
        len(
            json.dumps(
                protocol.structured_content, ensure_ascii=False, separators=(",", ":")
            )
        )
        <= 8192
    )
    chain = (
        result["bazi_birth"]["structure_profile"]["evidence_chain"]
        if topic == "birth"
        else result[topic + "_analysis"]["evidence_chain"]
    )
    facts = chain["classical_passage"]
    assert facts["visible_paths"][0]["positions"] == ["year", "month", "day"]
    assert facts["summary"]["effective_passage"] == "not_adjudicated"
    spec.output_model.model_validate(result)
    metadata = result["run_metadata"]
    prefix = fields[0].removesuffix(".source")
    claim = CalculationClaim(
        path=prefix + ".summary.effective_passage",
        value="not_adjudicated",
        run_id=metadata["run_id"],
    )
    # Quotation checking alone cannot authenticate the complete original.
    quoted = verify_calculation_claims(result, [claim])
    assert quoted["status"] == "verified_structured_facts"
    assert quoted["original_payload_compared"] is False
    complete = rest.post(
        spec.rest_path, json=PAYLOAD, params={"response_char_limit": 0}
    ).json()
    receipt = complete["run_metadata"]
    claim = claim.model_copy(
        update={
            "run_id": receipt["run_id"],
        }
    )
    assert (
        verify_calculation_claims(complete, [claim])["status"]
        == "verified_structured_facts"
    )
    assert (
        verify_calculation_claims(
            complete, [claim.model_copy(update={"value": "effective"})]
        )["status"]
        == "rejected"
    )


@pytest.mark.parametrize(
    "view", ["passage_hidden", "passage_mixed", "star_occurrences"]
)
def test_secondary_arrays_and_physical_counts_match_complete_business_result(
    view, rest
):
    spec = SPECS["bazi_birth"]
    full = rest.post(
        spec.rest_path, json=PAYLOAD, params={"response_char_limit": 0}
    ).json()
    fields = suggested_fields(spec, view=view)
    response = rest.post(
        spec.rest_path,
        json=PAYLOAD,
        params={
            "response_char_limit": 0,
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
    )
    assert response.status_code == 200
    for path in fields:
        expected, actual = full, response.json()
        for name in path.split("."):
            expected, actual = expected[name], actual[name]
        assert expected == actual


def test_native_destiny_alias_publishes_paths_and_counts_on_mcp_and_cli(
    tmp_path, capsys
):
    spec = SPECS["analyze_destiny"]
    payload = {k: v for k, v in PAYLOAD.items() if not k.startswith("analysis_")}
    fields = suggested_fields(spec, view="passage") + suggested_fields(
        spec, view="star_occurrences"
    )
    protocol = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=["--response-char-limit", "0", "--strict-fields", "--fields", *fields],
    )
    assert code == 0 and not protocol.is_error
    assert business(local) == business(protocol.structured_content)
    chain = local["structure_profile"]["evidence_chain"]
    assert chain["classical_passage"]["summary"]["calculation_effect"] == "none"
    assert (
        chain["star_occurrences"]["quantity_kind"]
        == "physical_occurrences_not_force_or_weighted_score"
    )
