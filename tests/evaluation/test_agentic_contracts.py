"""User-visible recovery and schema contracts through all three transports."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

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
from tests.support.transports import call_calculation, capability_contracts

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
        return await call_calculation(
            client, name, {"response_char_limit": 0, **payload}, raise_on_error=False
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
    monkeypatch: pytest.MonkeyPatch, changes, path: str, code: str
) -> None:
    inputs = {**BIRTH, **changes}
    rest = rest_client(monkeypatch).post("/api/bazi/birth-chart", json=inputs)
    protocol = asyncio.run(mcp_call("bazi_birth_chart", inputs))
    cli_code, output = cli("bazi_birth_chart", inputs)
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
        issue = next(item for item in payload["issues"] if item["path"] == path)
        assert issue["code"] == code and issue["message"]
        assert "private-birth-value" not in json.dumps(payload)
    assert all(payload["issues"] == outputs[0]["issues"] for payload in outputs)


def test_relationship_calendar_errors_identify_both_parties(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    party = {
        "birth_year": 2000,
        "birth_month": 2,
        "birth_hour": 12,
        "birth_timezone": "UTC",
        "birth_longitude": 0,
        "birth_latitude": 0,
    }
    response = rest_client(monkeypatch).post(
        "/api/astrology/relationship-chart",
        json={
            f"{side}_{field}": value
            for side, birth in {
                "inner": {**party, "birth_year": 1900, "birth_day": 29},
                "outer": {**party, "birth_day": 30},
            }.items()
            for field, value in birth.items()
        },
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["error_code"] == "validation_error"
    assert payload["retryable"] is False
    assert payload["issues"] == [
        {
            "path": party + "_birth_date",
            "code": "invalid_calendar_date",
            "message": "无效的公历日期，请核对年、月、日及闰年。",
        }
        for party in ("inner", "outer")
    ]


def test_unknown_input_never_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    inputs = {**BIRTH, "birth_mintue": 59}
    rest = rest_client(monkeypatch).post("/api/bazi/birth-chart", json=inputs)
    protocol = asyncio.run(mcp_call("bazi_birth_chart", inputs))
    code, output = cli("bazi_birth_chart", inputs)
    assert rest.status_code == 422 and protocol.is_error and code != 0
    assert output["error_code"] == "usage_error"
    assert (
        rest.json()["issues"]
        == protocol.structured_content["issues"]
        == [
            {
                "path": "birth_mintue",
                "code": "extra_forbidden",
                "message": "Extra inputs are not permitted",
            }
        ]
    )


@pytest.mark.parametrize(
    "name,path,inputs,field,bad",
    [
        (
            "evaluate_election_time",
            "/api/astrology/events/evaluate-election-time",
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
            "horary_chart",
            "/api/astrology/events/horary-chart",
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
    monkeypatch: pytest.MonkeyPatch, name: str, path: str, inputs, field: str, bad: str
) -> None:
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


def test_domain_error_identifies_missing_longitude_without_logging_place(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    place = "private-place-name"
    inputs = {**BIRTH, "birth_place": place, "use_true_solar_time": True}
    client = rest_client(monkeypatch)
    rest = client.post("/api/bazi/birth-chart", json=inputs)
    protocol = asyncio.run(mcp_call("bazi_birth_chart", inputs))
    code, output = cli("bazi_birth_chart", inputs)
    assert rest.status_code == 400 and protocol.is_error and code == 1
    for payload in [rest.json(), protocol.structured_content, output]:
        assert payload["error_code"] == "validation_error" and not payload["retryable"]
        assert payload["issues"] == [
            {"path": "birth_longitude", "code": "longitude_required_for_solar_time"}
        ]
        assert place in payload["error"]
    corrected = {**inputs, "birth_longitude": 116.4}
    assert client.post("/api/bazi/birth-chart", json=corrected).status_code == 200
    assert not asyncio.run(mcp_call("bazi_birth_chart", corrected)).is_error
    assert cli("bazi_birth_chart", corrected)[0] == 0
    assert place not in caplog.text


def test_pair_solar_time_error_names_the_public_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = dict(
        name="Synthetic A",
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=10,
        use_true_solar_time=False,
    )
    second = {**first, "name": "Synthetic B", "use_true_solar_time": True}
    inputs = {
        **{f"person1_{key}": value for key, value in first.items()},
        **{f"person2_{key}": value for key, value in second.items()},
    }
    response = rest_client(monkeypatch).post("/api/bazi/compatibility", json=inputs)
    protocol = asyncio.run(mcp_call("bazi_compatibility", inputs))
    code, output = cli("bazi_compatibility", inputs)
    assert response.status_code == 400 and protocol.is_error and code == 1
    for payload in (response.json(), protocol.structured_content, output):
        assert payload["issues"] == [
            {
                "path": "person2_birth_longitude",
                "code": "longitude_required_for_solar_time",
            }
        ]
        assert "person2_birth_longitude" in payload["error"]


def test_offset_mismatch_returns_the_actual_zone_offsets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = {**BIRTH, "birth_year": 2000, "birth_utc_offset": "+09:00"}
    response = rest_client(monkeypatch).post("/api/bazi/birth-chart", json=inputs)
    protocol = asyncio.run(mcp_call("bazi_birth_chart", inputs))
    code, output = cli("bazi_birth_chart", inputs)
    assert response.status_code == 400 and protocol.is_error and code == 1
    for payload in (response.json(), protocol.structured_content, output):
        assert payload["issues"] == [
            {
                "path": "birth_utc_offset",
                "code": "utc_offset_mismatch",
                "constraints": {"expected": ["+08:00"]},
            }
        ]
        assert "Asia/Shanghai" in payload["error"]


def test_invalid_budget_points_to_one_public_control(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = rest_client(monkeypatch).post(
        "/api/bazi/birth-chart", json=BIRTH, params={"response_char_limit": 100}
    )
    protocol = asyncio.run(
        mcp_call("bazi_birth_chart", {**BIRTH, "response_char_limit": 100})
    )
    assert response.status_code == 422 and protocol.is_error
    expected = {
        "path": "response_char_limit",
        "code": "invalid_response_limit",
        "message": "response_char_limit 须为 0 或 4096–65536",
    }
    assert (
        response.json()["issues"] == protocol.structured_content["issues"] == [expected]
    )


@pytest.mark.parametrize("projected", [False, True])
def test_success_data_schema_and_projection_match_all_transports(
    monkeypatch: pytest.MonkeyPatch, projected: bool
) -> None:
    params = (
        {"fields": "bazi_birth.day_master", "include_snapshot_text": "false"}
        if projected
        else {}
    )
    rest = rest_client(monkeypatch).post(
        "/api/bazi/birth-chart", json=BIRTH, params=params
    )
    flags = (
        {"fields": ["bazi_birth.day_master"], "include_snapshot_text": False}
        if projected
        else {}
    )
    protocol = asyncio.run(mcp_call("bazi_birth_chart", {**BIRTH, **flags}))
    code, output = cli(
        "bazi_birth_chart",
        BIRTH,
        (
            ["--fields", "bazi_birth.day_master", "--no-include-snapshot-text"]
            if projected
            else []
        ),
    )
    assert rest.status_code == 200 and not protocol.is_error and code == 0
    payloads = [rest.json(), protocol.structured_content, output]
    model = next(s.output_model for s in CATALOG if s.key == "bazi_birth")
    for payload in payloads:
        Draft202012Validator(model.model_json_schema()).validate(payload)
    scrubbed = [{k: v for k, v in p.items() if k != "run_metadata"} for p in payloads]
    assert scrubbed[0] == scrubbed[1] == scrubbed[2]


def test_relationship_solar_flags_are_forwarded_through_all_transports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flat = MCP_CASES["relationship_chart"][1]()
    flat["inner_use_true_solar_time"] = True
    rest = rest_client(monkeypatch).post("/api/astrology/relationship-chart", json=flat)
    protocol = asyncio.run(mcp_call("relationship_chart", flat))
    code, output = cli("relationship_chart", flat)
    assert rest.status_code == 200 and not protocol.is_error and code == 0
    payloads = [rest.json(), protocol.structured_content, output]
    for payload in payloads:
        assert payload["inner_chart"]["person_info"]["true_solar"]["applied"]
        assert not payload["outer_chart"]["person_info"]["true_solar"]["applied"]
    scrubbed = [{k: v for k, v in p.items() if k != "run_metadata"} for p in payloads]
    assert scrubbed[0] == scrubbed[1] == scrubbed[2]


def test_all_tools_publish_matching_output_contracts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema = rest_client(monkeypatch).get("/openapi.json").json()
    manifest = rest_client(monkeypatch).get("/api/tools").json()

    async def run():
        async with Client(mcp.create_mcp_app()) as client:
            return await capability_contracts(client, detail="full")

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
            published = tools[spec.tool_name]["output_schema"]
            Draft202012Validator.check_schema(published)
            # FastMCP dereferences schemas at serve time for host compatibility.
            assert set(published["properties"]) == set(advertised["properties"])
        else:
            pass
        if spec.rest_path:
            op = schema["paths"][spec.rest_path]["post"]
            assert op["operationId"] == spec.tool_name
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
        else:
            pass
    described = subprocess.run(
        [sys.executable, "-m", "fatebridge.cli", "describe", "bazi_birth_chart"],
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


def test_output_contract_fault_is_not_user_error() -> None:
    from dataclasses import replace

    spec = next(s for s in CATALOG if s.key == "bazi_birth")
    broken = replace(
        spec, bind=lambda _: (lambda: {"bazi_birth": "invalid-service-output"}, (), {})
    )
    with pytest.raises(OutputContractError):
        execute_spec(broken, spec.request_model(**BIRTH))


def test_all_cli_catalog_commands_accept_profiles_and_match_schemas(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    client = rest_client(monkeypatch)

    def inputs_for(spec):
        factory = (
            REST_POST_CASES[spec.rest_path]
            if spec.rest_path
            else MCP_CASES[spec.tool_name][1]
        )
        return spec.request_model.model_validate(factory()).model_dump(
            mode="json", exclude_unset=True
        )

    async def protocol_outputs():
        async with Client(mcp.app) as protocol:
            outputs = {}
            for spec in CATALOG:
                if spec_is_cli_safe(spec) and spec.mcp_name:
                    result = await call_calculation(
                        protocol,
                        spec.tool_name,
                        {**inputs_for(spec), "response_char_limit": 0},
                    )
                    assert not result.is_error
                    outputs[spec.key] = result.structured_content
                else:
                    pass
            return outputs

    protocols = asyncio.run(protocol_outputs())
    executed = 0
    for spec in CATALOG:
        if not spec_is_cli_safe(spec):
            continue
        else:
            pass
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
        else:
            pass
        if spec.mcp_name:
            payloads.append(protocols[spec.key])
        else:
            pass
        scrubbed = [
            {k: v for k, v in payload.items() if k != "run_metadata"}
            for payload in payloads
        ]
        assert all(payload == scrubbed[0] for payload in scrubbed), spec.key
        executed += 1
    assert executed == sum(spec_is_cli_safe(spec) for spec in CATALOG)


def test_openapi_auth_matches_runtime_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-Test-Key", api_keys={"secret": "id"}),
    )
    schema = api.app.openapi()
    assert schema["components"]["securitySchemes"]["APIKey"]["name"] == "X-Test-Key"
    assert schema["paths"]["/api/bazi/birth-chart"]["post"]["security"] == [
        {"APIKey": []}
    ]
    assert "security" not in schema["paths"]["/health"]["get"]


@pytest.mark.parametrize(
    "exception,expected,status,retryable",
    [
        (None, "internal_error", 500, True),
        (RuntimeError("private-runtime-detail"), "internal_error", 500, True),
        (ImportError("private-import-binding-detail"), "internal_error", 500, True),
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
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    exception,
    expected: str,
    status: int,
    retryable: bool,
) -> None:
    from dataclasses import replace

    from fastapi import FastAPI, HTTPException
    from fastmcp import FastMCP

    import fatebridge.cli as cli_module
    from fatebridge.mcp_server import _register_mcp_tools
    from fatebridge.transports.rest import register_rest

    def fail():
        if exception is None:
            return {"bazi_birth": "private-invalid-output"}
        else:
            pass
        raise exception

    original = next(s for s in CATALOG if s.key == "bazi_birth")
    broken = replace(original, bind=lambda _: (fail, (), {}))
    rest_app = FastAPI()
    rest_app.add_exception_handler(HTTPException, api._http_error_envelope)
    register_rest(rest_app, [broken], execute_service=api._execute_service)
    response = TestClient(rest_app).post(original.rest_path, json=BIRTH)
    mcp_app = FastMCP("failure regression")
    _register_mcp_tools(mcp_app, [broken])

    async def call():
        async with Client(mcp_app) as client:
            return await call_calculation(
                client, "bazi_birth_chart", BIRTH, raise_on_error=False
            )

    protocol = asyncio.run(call())
    monkeypatch.setattr(cli_module, "CATALOG", [broken])
    arguments = [broken.tool_name]
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
