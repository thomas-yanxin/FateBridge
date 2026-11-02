"""Internal source-definition faults must not blame otherwise valid inputs."""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import fatebridge.mcp_server as mcp
from fatebridge.cli import run as cli_run
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import NumerologySourceError, calculation_guard

W = Path(__file__).parent
CONTRACT = json.loads(
    (W / "fixtures/numerology_source_reason_v1/contract.json").read_bytes()
)
SPECS = {s.key: s for s in CATALOG}


@pytest.mark.parametrize("reason", ["future_source_reason", "/private/source_reason"])
def test_unregistered_reason_is_rejected_as_programming_fault(reason):
    with pytest.raises(
        RuntimeError, match="Unknown numerology source consistency reason"
    ):
        NumerologySourceError(reason)


@pytest.mark.parametrize("reason", CONTRACT["known_messages"])
def test_every_registered_source_reason_keeps_its_exact_existing_contract(reason):
    assert NumerologySourceError(reason).as_result() == {
        "error": CONTRACT["known_messages"][reason],
        "error_code": "numerology_source_inconsistent",
        "status_code": 503,
        "retryable": False,
        "issues": [{"path": "runtime.numerology_sources", "code": reason}],
    }


def test_registry_itself_is_unchanged_by_the_repair():
    assert NumerologySourceError.MESSAGES == CONTRACT["known_messages"]


def test_plain_input_error_text_cannot_impersonate_an_internal_fault():
    @calculation_guard("测试")
    def plain():
        raise ValueError("Unknown numerology source consistency reason")

    result = plain()
    assert result["status_code"] == 400 and result["error_code"] == "validation_error"


@pytest.mark.parametrize("tool", ["heluo", "canping", "knowledge_read"])
@pytest.mark.parametrize("fault", ["unknown_reason", "known_source", "input"])
def test_actual_three_adapters_keep_source_definition_and_input_faults_distinct(
    tool, fault, monkeypatch, capsys, tmp_path
):
    def fail(*args, **kwargs):
        if fault == "unknown_reason":
            raise NumerologySourceError("/private/future_source_reason")
        if fault == "known_source":
            raise NumerologySourceError("invalid_source_data")
        raise ValueError("explicitly invalid clock")

    if tool in {"heluo", "canping"}:
        import importlib

        module = importlib.import_module("fatebridge.core.local_techniques." + tool)
        monkeypatch.setattr(module, "_build_metaphysics_seed", fail)
        payload = CONTRACT["fictional_valid_request"]
    else:
        from fatebridge.core import numerology_knowledge

        monkeypatch.setattr(numerology_knowledge, "read_reference", fail)
        payload = {"domain": "heluo", "key": "風地觀:4"}
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as http:
        response = http.post(SPECS[tool].rest_path, json=payload)
    subject = tmp_path / "subject.json"
    subject.write_text(json.dumps(payload, ensure_ascii=False))
    code = cli_run([tool, "--subject-file", str(subject)])
    cli = json.loads(capsys.readouterr().out)

    async def native():
        async with Client(mcp.app) as client:
            return await client.call_tool(tool, payload, raise_on_error=False)

    protocol = asyncio.run(native())
    expected_status, expected_code = {
        "unknown_reason": (500, "internal_error"),
        "known_source": (503, "numerology_source_inconsistent"),
        "input": (400, "validation_error"),
    }[fault]
    outputs = [response.json(), cli, protocol.structured_content]
    # Save each first set before assertions; stdout/caplog remain diagnostic.
    (tmp_path / "three-adapter-results.json").write_text(
        json.dumps(
            {
                "tool": tool,
                "fault": fault,
                "HTTP_status": response.status_code,
                "CLI_exit": code,
                "MCP_is_error": protocol.is_error,
                "outputs": outputs,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    assert response.status_code == expected_status and code == 1 and protocol.is_error
    for out in outputs:
        assert out["error_code"] == expected_code
        assert "chart" not in out and "four_pillars" not in out
        assert "/private" not in json.dumps(out)
        if fault == "unknown_reason":
            assert "Unknown numerology" not in out["error"]
    normalize = lambda out: {
        k: v for k, v in out.items() if k not in {"status_code", "operation"}
    }
    assert normalize(outputs[0]) == normalize(outputs[1]) == normalize(outputs[2])
