"""Real REST, MCP and CLI test calls; domain facts stay in their owning suites."""

import asyncio
import json
from functools import lru_cache

import pytest
from fastmcp import Client
from fastmcp.client.client import CallToolResult

AS_OF = "2026-10-12T02:00:00Z"


@lru_cache(maxsize=1)
def _specs():
    from fatebridge.services.tool_catalog import CATALOG

    return {spec.name: spec for spec in CATALOG}


def __getattr__(name: str):
    if name == "SPECS":
        return _specs()
    else:
        pass
    if name in {"REST_POST_CASES", "MCP_CASES"}:
        from tests.fixtures import surface_payloads

        return getattr(surface_payloads, name)
    else:
        pass
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


@lru_cache(maxsize=None)
def cached_mcp_app(families: str | None = None):
    import fatebridge.mcp_server as mcp

    if families is None:
        return mcp.app
    else:
        pass
    return mcp.create_mcp_app(families=families)


async def call_calculation(
    client: Client,
    tool: str,
    values: dict[str, object] | None = None,
    *,
    raise_on_error: bool = True,
) -> CallToolResult:
    controls = {"as_of", "detail", "fields"}
    arguments = {}
    request: dict[str, object] = {
        "tool": tool,
        "arguments": arguments,
        "detail": "audit",
    }
    for name, value in (values or {}).items():
        if name in controls:
            request[name] = value
        else:
            arguments[name] = value
    return await client.call_tool(
        "run_calculation", request, raise_on_error=raise_on_error
    )


async def describe_capability(client: Client, tool: str, *, detail="summary"):
    wire_detail = "summary" if detail == "input" else detail
    result = await client.call_tool(
        "discover_tools", {"tool": tool, "detail": wire_detail}
    )
    assert result.structured_content is not None
    return result.structured_content["tools"][0]


async def discover_capabilities(client: Client):
    result = await client.call_tool("discover_tools", {})
    assert result.structured_content is not None
    return [item["tool"] for item in result.structured_content["tools"]]


async def capability_contracts(client: Client, *, detail="summary"):
    return {
        name: await describe_capability(client, name, detail=detail)
        for name in await discover_capabilities(client)
    }


@lru_cache(maxsize=None)
def cached_output_validator(output_model):
    from jsonschema import Draft202012Validator

    from fatebridge.core.schema_cache import model_schema

    return Draft202012Validator(model_schema(output_model))


def rest_client(monkeypatch):
    from fastapi.testclient import TestClient

    import fatebridge.api as api

    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    return TestClient(api.app)


@pytest.fixture
def rest(monkeypatch):
    return rest_client(monkeypatch)


def inputs(spec):
    from tests.fixtures.surface_payloads import MCP_CASES, REST_POST_CASES

    factory = (
        REST_POST_CASES[spec.rest_path]
        if spec.rest_path
        else MCP_CASES[spec.name][1]
    )
    return spec.request_model.model_validate(factory()).model_dump(exclude_unset=True)


def call_cli(spec, payload, tmp_path, capsys, flags=()):
    from fatebridge.cli import run as cli_run

    request_file = tmp_path / "request.json"
    request_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    extra_flags = list(flags)
    if "--detail" not in extra_flags and not any(
        f.startswith("--detail=") for f in extra_flags
    ):
        extra_flags.extend(["--detail", "audit"])
    capsys.readouterr()
    code = cli_run(
        [
            spec.name,
            "--request-file",
            str(request_file),
            "--as-of",
            AS_OF,
            *extra_flags,
        ]
    )
    return code, json.loads(capsys.readouterr().out)


async def native(spec, payload, **flags):
    from fastmcp import Client

    import fatebridge.mcp_server as mcp

    async with Client(mcp.app) as client:
        return await call_calculation(
            client,
            spec.name,
            {**payload, "as_of": AS_OF, **flags},
            raise_on_error=False,
        )


def run_three(spec, payload, fields, rest, tmp_path, capsys):
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields] + [("detail", "audit")],
    )
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=["--fields", *fields, "--detail", "audit"],
    )
    mcp = asyncio.run(
        native(
            spec,
            {**payload, "fields": fields, "detail": "audit"},
        )
    )
    return response, code, cli, mcp


def business(payload):
    return {k: v for k, v in payload.items() if k != "run_metadata"}


def projected_outputs(spec, payload, fields, rest, tmp_path, capsys):
    """Call the same strict projection on REST, CLI and native MCP."""
    options = dict(fields=fields, detail="audit")
    params = [("fields", f) for f in fields] + [("detail", "audit")]
    flags = ["--fields", *fields, "--detail", "audit"]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=params,
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=flags,
    )
    protocol = asyncio.run(
        native(
            spec,
            {**payload, **options},
        )
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    return [response.json(), local, protocol.structured_content]


@pytest.fixture
def surface_calls(rest, tmp_path, capsys):
    """Keep each caller's exact controls and original CLI/MCP execution order."""

    def call(
        spec,
        payload,
        *,
        params=None,
        options=None,
        flags=(),
        cli_first=True,
        projection=None,
        rest_as_of=None,
    ):
        if projection is not None:
            options = projection
            params = dict(projection)
            if rest_as_of is not None:
                params["as_of"] = rest_as_of
            else:
                pass
            flags = []
            for name, value in projection.items():
                flags.append("--" + name.replace("_", "-"))
                if name == "fields":
                    flags.extend(value)
                else:
                    flags.append(
                        str(value).lower() if isinstance(value, bool) else str(value)
                    )
        else:
            pass
        if params is None:
            params = {"detail": "audit"}
        elif isinstance(params, dict) and "detail" not in params:
            params = {**params, "detail": "audit"}
        elif isinstance(params, list) and not any(k == "detail" for k, _ in params):
            params = [*params, ("detail", "audit")]
        http = rest.post(
            spec.rest_path,
            json=payload,
            params=params,
        )
        if cli_first:
            code, local = call_cli(spec, payload, tmp_path, capsys, flags=flags)
        else:
            pass
        protocol = asyncio.run(native(spec, payload, **(options or {})))
        if not cli_first:
            code, local = call_cli(spec, payload, tmp_path, capsys, flags=flags)
        else:
            pass
        return http, protocol, code, local

    return call


def three_surfaces(spec, payload, fields, as_of, tmp_path, monkeypatch, capsys):
    from fastmcp import Client

    from fatebridge.cli import run as cli_run

    rest = rest_client(monkeypatch)
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[
            ("as_of", as_of),
            ("detail", "audit"),
            *[("fields", f) for f in fields],
        ],
    )

    async def native_call():
        async with Client(cached_mcp_app()) as client:
            return await call_calculation(
                client,
                spec.name,
                {
                    **payload,
                    "as_of": as_of,
                    "fields": fields,
                    "detail": "audit",
                },
                raise_on_error=False,
            )

    protocol = asyncio.run(native_call())
    request = tmp_path / "request.json"
    request.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    capsys.readouterr()
    code = cli_run(
        [
            spec.name,
            "--request-file",
            str(request),
            "--as-of",
            as_of,
            "--detail",
            "audit",
            "--fields",
            *fields,
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200, response.text
    assert not protocol.is_error, protocol.content
    assert code == 0, cli
    validator = cached_output_validator(spec.output_model)
    bodies = []
    for label, body in [
        ("rest", response.json()),
        ("mcp", protocol.structured_content),
        ("cli", cli),
    ]:
        validator.validate(body)
        (tmp_path / f"{label}.json").write_text(
            json.dumps(
                body, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
            ),
            encoding="utf-8",
        )
        body = dict(body)
        body.pop("run_metadata")
        bodies.append(body)
    assert bodies[0] == bodies[1] == bodies[2]
    return bodies[0]
