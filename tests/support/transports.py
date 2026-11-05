"""Real REST, MCP and CLI test calls; domain facts stay in their owning suites."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import fatebridge.mcp_server as mcp
from fatebridge.cli import run as cli_run
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.surface_payloads import MCP_CASES, REST_POST_CASES

SPECS = {spec.key: spec for spec in CATALOG}
AS_OF = "2026-10-12T02:00:00Z"


@pytest.fixture
def rest(monkeypatch):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    return TestClient(api.app)


def inputs(spec):
    factory = (
        REST_POST_CASES[spec.rest_path]
        if spec.rest_path
        else MCP_CASES[spec.tool_name][1]
    )
    return spec.request_model.model_validate(factory()).model_dump(exclude_unset=True)


def rest_spec(spec):
    return SPECS["astro_relative"] if spec.key == "astro_relative_chart" else spec


def call_cli(spec, payload, tmp_path, capsys, flags=()):
    subject = tmp_path / "subject.json"
    subject.write_text(json.dumps(payload, ensure_ascii=False))
    prefix = ["--no-metadata"] if "--no-metadata" in flags else []
    flags = [flag for flag in flags if flag != "--no-metadata"]
    code = cli_run(
        [
            *prefix,
            spec.tool_name,
            "--subject-file",
            str(subject),
            "--as-of",
            AS_OF,
            *flags,
        ]
    )
    return code, json.loads(capsys.readouterr().out)


async def native(spec, payload, **flags):
    async with Client(mcp.app) as client:
        return await client.call_tool(
            spec.tool_name,
            {**payload, "as_of": AS_OF, "response_char_limit": 0, **flags},
            raise_on_error=False,
        )


def business(payload):
    return {k: v for k, v in payload.items() if k != "run_metadata"}


def projected_outputs(
    spec, payload, fields, rest, tmp_path, capsys, *, include_snapshot_text=None
):
    """Call the same strict projection on REST, CLI and native MCP."""
    options = dict(fields=fields, strict_fields=True, response_char_limit=0)
    params = [("fields", f) for f in fields] + [
        ("strict_fields", "true"),
        ("response_char_limit", "0"),
    ]
    flags = [
        "--fields",
        *fields,
        "--strict-fields",
        "true",
        "--response-char-limit",
        "0",
    ]
    if include_snapshot_text is not None:
        options["include_snapshot_text"] = include_snapshot_text
        text_flag = str(include_snapshot_text).lower()
        params.append(("include_snapshot_text", text_flag))
        flags.extend(["--include-snapshot-text", text_flag])
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
            flags = []
            for name, value in projection.items():
                flags.append("--" + name.replace("_", "-"))
                if name == "fields":
                    flags.extend(value)
                else:
                    flags.append(
                        str(value).lower() if isinstance(value, bool) else str(value)
                    )
        http = rest.post(
            spec.rest_path,
            json=payload,
            **({"params": params} if params is not None else {}),
        )
        if cli_first:
            code, local = call_cli(spec, payload, tmp_path, capsys, flags=flags)
        protocol = asyncio.run(native(spec, payload, **(options or {})))
        if not cli_first:
            code, local = call_cli(spec, payload, tmp_path, capsys, flags=flags)
        return http, protocol, code, local

    return call
