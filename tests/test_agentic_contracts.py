"""User-visible recovery and schema contracts through all three transports."""

import asyncio
import json
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
import fatebridge.mcp_server as mcp
from fatebridge.application.description import spec_is_cli_safe
from fatebridge.application.execution import OutputContractError, execute_spec
from fatebridge.cli import run as cli_run
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.surface_payloads import MCP_CASES, REST_POST_CASES

BIRTH = dict(
    birth_year=1990,
    birth_month=5,
    birth_day=15,
    birth_hour=10,
    gender="男",
    birth_place="北京",
    birth_timezone="Asia/Shanghai",
    use_true_solar_time=False,
    analysis_year=2026,
    analysis_month=10,
    analysis_day=12,
)


def cli(tool, inputs, flags=()):
    args = [sys.executable, "-m", "fatebridge.cli", tool]
    for key, value in inputs.items():
        args.extend(
            [
                "--" + key.replace("_", "-"),
                str(value).lower() if isinstance(value, bool) else str(value),
            ]
        )
    result = subprocess.run(
        args + list(flags), text=True, capture_output=True, timeout=30
    )
    return result.returncode, json.loads(result.stdout)


async def mcp_call(name, payload):
    async with Client(mcp.app) as client:
        return await client.call_tool(
            name, {"response_char_limit": 0, **payload}, raise_on_error=False
        )


def rest_client(monkeypatch):
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    return TestClient(api.app)


@pytest.mark.parametrize(
    "changes,path,code",
    [
        ({"birth_month": 13}, "birth_month", "less_than_equal"),
        ({"birth_month": 2, "birth_day": 30}, "birth_date", "invalid_calendar_date"),
        ({"birth_year": "private-birth-value"}, "birth_year", "int_parsing"),
    ],
)
def test_validation_correction_hints_match_all_transports(
    monkeypatch, changes, path, code
):
    inputs = {**BIRTH, **changes}
    rest = rest_client(monkeypatch).post("/api/cn/bazi/birth", json=inputs)
    protocol = asyncio.run(mcp_call("bazi_birth", inputs))
    cli_code, output = cli("bazi_birth", inputs)
    assert rest.status_code == 422
    assert protocol.is_error
    # Argparse catches a non-integer before schema validation; its syntax
    # error remains exit 2. Schema-validation errors are identical (exit 1).
    if changes.get("birth_year") == "private-birth-value":
        assert cli_code == 2
        outputs = [rest.json(), protocol.structured_content]
    else:
        assert cli_code == 1
        outputs = [rest.json(), protocol.structured_content, output]
    for payload in outputs:
        assert payload["error_code"] == "validation_error"
        assert {"path": path, "code": code} in [
            {"path": item["path"], "code": item["code"]} for item in payload["issues"]
        ]
        assert "private-birth-value" not in json.dumps(payload)
    assert json.loads(protocol.content[0].text) == protocol.structured_content


def test_unknown_input_never_succeeds(monkeypatch):
    inputs = {**BIRTH, "birth_mintue": 59}
    rest = rest_client(monkeypatch).post("/api/cn/bazi/birth", json=inputs)
    protocol = asyncio.run(mcp_call("bazi_birth", inputs))
    code, output = cli("bazi_birth", inputs)
    assert rest.status_code == 422 and protocol.is_error and code != 0
    assert output["error_code"] == "usage_error"
    assert (
        rest.json()["issues"]
        == protocol.structured_content["issues"]
        == [{"path": "birth_mintue", "code": "extra_forbidden"}]
    )


@pytest.mark.parametrize(
    "name,path,inputs,field,bad",
    [
        (
            "astro_election",
            "/api/astro/event/election",
            dict(
                candidate_year=2026,
                candidate_month=10,
                candidate_day=12,
                candidate_hour=10,
                longitude=116.4,
                latitude=39.9,
            ),
            "topic_id",
            "contrcat",
        ),
        (
            "astro_horary",
            "/api/astro/event/horary",
            dict(
                question_year=2026,
                question_month=10,
                question_day=12,
                question_hour=10,
                longitude=116.4,
                latitude=39.9,
            ),
            "category",
            "carreer",
        ),
    ],
)
def test_unknown_topic_does_not_change_task(
    monkeypatch, name, path, inputs, field, bad
):
    inputs[field] = bad
    rest = rest_client(monkeypatch).post(path, json=inputs)
    protocol = asyncio.run(mcp_call(name, inputs))
    code, output = cli(name, inputs)
    assert rest.status_code == 422 and protocol.is_error and code == 1
    for payload in [rest.json(), protocol.structured_content, output]:
        assert payload["error_code"] == "validation_error"
        assert payload["issues"][0]["path"] == field
        assert payload["issues"][0]["code"] == "literal_error"
        assert "election" not in payload and "horary" not in payload


def test_domain_error_is_native_mcp_failure(monkeypatch):
    inputs = {**BIRTH, "birth_place": "未提供", "use_true_solar_time": True}
    rest = rest_client(monkeypatch).post("/api/cn/bazi/birth", json=inputs)
    protocol = asyncio.run(mcp_call("bazi_birth", inputs))
    code, output = cli("bazi_birth", inputs)
    assert rest.status_code == 400 and protocol.is_error and code == 1
    assert {
        p["error_code"] for p in [rest.json(), protocol.structured_content, output]
    } == {"validation_error"}


@pytest.mark.parametrize("projected", [False, True])
def test_success_data_schema_and_projection_match_all_transports(
    monkeypatch, projected
):
    params = (
        {"fields": "bazi_birth.day_master", "include_snapshot_text": "false"}
        if projected
        else {}
    )
    rest = rest_client(monkeypatch).post(
        "/api/cn/bazi/birth", json=BIRTH, params=params
    )
    flags = (
        {"fields": ["bazi_birth.day_master"], "include_snapshot_text": False}
        if projected
        else {}
    )
    protocol = asyncio.run(mcp_call("bazi_birth", {**BIRTH, **flags}))
    code, output = cli(
        "bazi_birth",
        BIRTH,
        (
            ["--fields", "bazi_birth.day_master", "--no-include-snapshot-text"]
            if projected
            else []
        ),
    )
    assert rest.status_code == 200 and not protocol.is_error and code == 0
    assert json.loads(protocol.content[0].text) == protocol.structured_content
    payloads = [rest.json(), protocol.structured_content, output]
    model = next(s.output_model for s in CATALOG if s.key == "bazi_birth")
    for payload in payloads:
        Draft202012Validator(model.model_json_schema()).validate(payload)
    scrubbed = [{k: v for k, v in p.items() if k != "run_metadata"} for p in payloads]
    assert scrubbed[0] == scrubbed[1] == scrubbed[2]


def test_relationship_solar_flags_are_forwarded_through_all_transports(monkeypatch):
    nested = REST_POST_CASES["/api/astro/relative"]()
    nested["inner"]["use_true_solar_time"] = True
    flat = MCP_CASES["astro_relative_chart"][1]()
    flat["inner_use_true_solar_time"] = True
    rest = rest_client(monkeypatch).post("/api/astro/relative", json=nested)
    protocol = asyncio.run(mcp_call("astro_relative_chart", flat))
    code, output = cli("astro_relative_chart", flat)
    assert rest.status_code == 200 and not protocol.is_error and code == 0
    payloads = [rest.json(), protocol.structured_content, output]
    for payload in payloads:
        assert payload["inner_chart"]["person_info"]["true_solar"]["applied"]
        assert not payload["outer_chart"]["person_info"]["true_solar"]["applied"]
    scrubbed = [{k: v for k, v in p.items() if k != "run_metadata"} for p in payloads]
    assert scrubbed[0] == scrubbed[1] == scrubbed[2]


def test_all_tools_publish_matching_output_contracts(monkeypatch):
    schema = rest_client(monkeypatch).get("/openapi.json").json()
    manifest = rest_client(monkeypatch).get("/api/tools").json()

    async def run():
        async with Client(mcp.app) as client:
            return {tool.name: tool for tool in await client.list_tools()}

    tools = asyncio.run(run())
    assert len(tools) == sum(spec.mcp_name is not None for spec in CATALOG)
    for spec in CATALOG:
        advertised = spec.output_model.model_json_schema()
        Draft202012Validator.check_schema(advertised)
        assert "properties" in advertised and "run_metadata" in advertised["properties"]
        assert (
            next(t for t in manifest["tools"] if t["tool"] == spec.tool_name)[
                "output_schema"
            ]
            == advertised
        )
        if spec.mcp_name:
            published = tools[spec.tool_name].model_dump(by_alias=True)["outputSchema"]
            Draft202012Validator.check_schema(published)
            # FastMCP dereferences schemas at serve time for host compatibility.
            assert set(published["properties"]) == set(advertised["properties"])
        if spec.rest_path:
            op = schema["paths"][spec.rest_path]["post"]
            assert op["operationId"] == spec.key
            assert set(op["responses"]) >= {
                "200",
                "400",
                "401",
                "422",
                "500",
                "503",
                "504",
            }
            reference = op["responses"]["200"]["content"]["application/json"]["schema"][
                "$ref"
            ]
            assert reference.startswith("#/components/schemas/")
    described = subprocess.run(
        [sys.executable, "-m", "fatebridge.cli", "describe", "bazi_birth"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert described.returncode == 0
    spec = next(s for s in CATALOG if s.key == "bazi_birth")
    assert (
        json.loads(described.stdout)["output_schema"]
        == spec.output_model.model_json_schema()
    )


def test_output_contract_fault_is_not_user_error():
    from dataclasses import replace

    spec = next(s for s in CATALOG if s.key == "bazi_birth")
    broken = replace(
        spec, bind=lambda _: (lambda: {"bazi_birth": "invalid-service-output"}, (), {})
    )
    with pytest.raises(OutputContractError):
        execute_spec(broken, spec.request_model(**BIRTH))


def test_all_cli_catalog_commands_accept_profiles_and_match_schemas(
    tmp_path, capsys, monkeypatch
):
    client = rest_client(monkeypatch)

    def inputs_for(spec):
        factory = (
            REST_POST_CASES[spec.rest_path]
            if spec.rest_path
            else MCP_CASES[spec.tool_name][1]
        )
        return spec.request_model.model_validate(factory()).model_dump(
            exclude_unset=True
        )

    async def protocol_outputs():
        async with Client(mcp.app) as protocol:
            outputs = {}
            for spec in CATALOG:
                if spec_is_cli_safe(spec) and spec.mcp_name:
                    result = await protocol.call_tool(
                        spec.tool_name,
                        {**inputs_for(spec), "response_char_limit": 0},
                    )
                    assert not result.is_error
                    outputs[spec.key] = result.structured_content
            return outputs

    protocols = asyncio.run(protocol_outputs())
    executed = 0
    for spec in CATALOG:
        if not spec_is_cli_safe(spec):
            continue
        # Subject files use canonical model names, independent of REST aliases.
        inputs = inputs_for(spec)
        subject = tmp_path / "subject.json"
        subject.write_text(json.dumps(inputs, ensure_ascii=False))
        code = cli_run([spec.tool_name, "--subject-file", str(subject)])
        output = json.loads(capsys.readouterr().out)
        assert code == 0, (spec.key, output)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        payloads = [output]
        if spec.rest_path:
            response = client.post(spec.rest_path, json=inputs)
            assert response.status_code == 200, spec.key
            payloads.append(response.json())
        if spec.mcp_name:
            payloads.append(protocols[spec.key])
        scrubbed = [
            {k: v for k, v in payload.items() if k != "run_metadata"}
            for payload in payloads
        ]
        assert all(payload == scrubbed[0] for payload in scrubbed), spec.key
        executed += 1
    assert executed == sum(spec_is_cli_safe(spec) for spec in CATALOG)


def test_openapi_auth_matches_runtime_configuration(monkeypatch):
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-Test-Key", api_keys={"secret": "id"}),
    )
    schema = api.app.openapi()
    assert schema["components"]["securitySchemes"]["APIKey"]["name"] == "X-Test-Key"
    assert schema["paths"]["/api/cn/bazi/birth"]["post"]["security"] == [{"APIKey": []}]
    assert "security" not in schema["paths"]["/health"]["get"]


@pytest.mark.parametrize(
    "exception,expected,status,retryable",
    [
        (None, "internal_error", 500, True),
        (RuntimeError("private-runtime-detail"), "internal_error", 500, True),
        (
            ModuleNotFoundError("private-dependency-detail"),
            "dependency_missing",
            503,
            False,
        ),
        (TimeoutError("private-timeout-detail"), "timeout", 504, True),
    ],
)
def test_execution_failures_agree_and_do_not_leak(
    monkeypatch, capsys, exception, expected, status, retryable
):
    from dataclasses import replace

    from fastapi import FastAPI, HTTPException
    from fastmcp import FastMCP

    import fatebridge.cli as cli_module
    from fatebridge.transports.mcp import register_mcp
    from fatebridge.transports.rest import register_rest

    def fail():
        if exception is None:
            return {"bazi_birth": "private-invalid-output"}
        raise exception

    original = next(s for s in CATALOG if s.key == "bazi_birth")
    broken = replace(original, bind=lambda _: (fail, (), {}))
    rest_app = FastAPI()
    rest_app.add_exception_handler(HTTPException, api._http_error_envelope)
    register_rest(rest_app, [broken], execute_service=api._execute_service)
    response = TestClient(rest_app).post(original.rest_path, json=BIRTH)
    mcp_app = FastMCP("failure regression")
    register_mcp(
        mcp_app,
        [broken],
        render_response=mcp._render_protocol_response,
        render_error=mcp._render_protocol_error,
    )

    async def call():
        async with Client(mcp_app) as client:
            return await client.call_tool("bazi_birth", BIRTH, raise_on_error=False)

    protocol = asyncio.run(call())
    monkeypatch.setattr(cli_module, "CATALOG", [broken])
    arguments = ["bazi_birth"]
    for key, value in BIRTH.items():
        arguments += [
            "--" + key.replace("_", "-"),
            str(value).lower() if isinstance(value, bool) else str(value),
        ]
    assert cli_module.run(arguments) == 1
    output = json.loads(capsys.readouterr().out)
    assert response.status_code == status and protocol.is_error
    for payload in [response.json(), protocol.structured_content, output]:
        assert payload["error_code"] == expected
        assert payload["retryable"] is retryable
        assert "private-" not in json.dumps(payload)
