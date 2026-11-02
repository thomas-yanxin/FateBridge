"""Same-run disclosure faults remain source errors before any projection."""

from copy import deepcopy

import pytest

from tests.test_agentic_nested_outputs import rest as shared_rest
from tests.test_canping_receipt_binding_transports import return_frozen_output
from tests.test_canping_scope_rendering import REFERENCE, SPEC, _synchronize
from tests.test_canping_scope_rendering import generated as shared_generated
from tests.test_heluo_poem_transports import run_three

rest = shared_rest
generated = shared_generated


@pytest.mark.parametrize("fault", REFERENCE["live_faults"])
@pytest.mark.parametrize("unrelated", [False, True])
def test_disclosure_faults_are_nonretryable_source_errors_on_three_surfaces(
    fault, unrelated, generated, rest, tmp_path, capsys, monkeypatch
):
    output = deepcopy(generated[0])
    receipt = output["canping_timing"]["schedule_basis"]
    if fault == "legacy_consistent_copies":
        old = "generic_regional_caveat_v1"
        receipt["scope_statement"] = REFERENCE["revisions"][old]
        receipt["scope_rendering"] = deepcopy(REFERENCE["receipts"][old])
    elif fault == "unknown_text":
        receipt["scope_statement"] = "全书与现实预测均已验证。"
    elif fault == "wrong_revision":
        receipt["scope_rendering"]["revision"] = "generic_regional_caveat_v1"
    elif fault == "wrong_digest":
        receipt["scope_rendering"]["text_sha256"] = "0" * 64
    elif fault == "wrong_layer":
        receipt["scope_rendering"]["layer"] = "original_book_quote"
    elif fault == "missing_receipt":
        del receipt["scope_rendering"]
    elif fault == "original_book_hash":
        receipt["sources"]["heluo_najda"]["pdf_sha256"] = "0" * 64
    elif fault == "quote_rewrite":
        receipt["clauses"][0]["text"] += "原典已认证"
    _synchronize(output)
    return_frozen_output(monkeypatch, output)
    fields = (
        ["benming.numShun"]
        if unrelated
        else ["canping_timing.schedule_basis.scope_rendering"]
    )
    response, code, cli, mcp = run_three(
        SPEC,
        {
            **REFERENCE["engineering_payload"],
            "zone": REFERENCE["clocks"][0],
            "dayun_method": REFERENCE["profiles"][0],
        },
        fields,
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 503 and code == 1 and mcp.is_error
    for result in [response.json(), cli, mcp.structured_content]:
        assert result["error_code"] == "numerology_source_inconsistent"
        assert result["retryable"] is False
        assert (
            result["issues"][0]["code"] == "runtime_canping_schedule_binding_conflict"
        )
