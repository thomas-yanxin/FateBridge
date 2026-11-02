"""Execute frozen v62 request bytes with a selected fixed implementation tree."""

import asyncio
import contextlib
import hashlib
import importlib
import importlib.util
import io
import json
import sys
from pathlib import Path

source = Path(sys.argv[1]).resolve()
original = Path(sys.argv[2]).resolve()
sys.path[:0] = [str(source), str(source.parent)]
import fatebridge

assert Path(fatebridge.__file__).resolve().parent == source / "fatebridge"
package = importlib.import_module("fatebridge.core.requests")
name = "fatebridge.core.requests.divination"
spec = importlib.util.spec_from_file_location(name, original)
module = importlib.util.module_from_spec(spec)
sys.modules[name] = module
spec.loader.exec_module(module)
setattr(package, "MeihuaAnalysisRequest", module.MeihuaAnalysisRequest)
from fatebridge.services.tool_catalog import CATALOG

spec = next(s for s in CATALOG if s.key == "meihua_analysis")
assert spec.request_model is module.MeihuaAnalysisRequest
assert spec.request_model.model_fields["analysis_minute"].default == 0
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.execution import execute_tool
from fatebridge.cli import run as cli_run
from fatebridge.mcp_server import app as mcp_app

api._reset_runtime_state_for_tests()
api.API_KEY_AUTHENTICATOR = api.ApiKeyAuthenticator(
    header_name="X-API-Key", api_keys={}
)
args = dict(
    analysis_year=2000,
    analysis_month=1,
    analysis_day=6,
    analysis_hour=9,
    analysis_timezone="+08:00",
)
fields = [
    "analysis_context",
    "meihua.calendar_policy.civil_clock_resolution",
    "summary",
]
rows = []


def retain(surface, kind, value):
    assert "error" not in value, (surface, kind, value)
    clock = value["meihua"]["calendar_policy"]["civil_clock_resolution"]
    rows.append(
        {
            "surface": surface,
            "kind": kind,
            "input_sha256": value["run_metadata"]["input_sha256"],
            "clock": clock,
            "summary": value["summary"],
        }
    )


with TestClient(api.app) as client:
    for kind, extra in [("omitted", {}), ("zero", {"analysis_minute": 0})]:
        response = client.post(
            spec.rest_path,
            json={**args, **extra},
            params=[
                *(("fields", f) for f in fields),
                ("strict_fields", "true"),
                ("response_char_limit", "0"),
            ],
        )
        assert response.status_code == 200, response.text
        retain("REST", kind, response.json())
for kind, extra in [("omitted", []), ("zero", ["--analysis-minute", "0"])]:
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        code = cli_run(
            [
                "meihua_analysis",
                "--analysis-year",
                "2000",
                "--analysis-month",
                "1",
                "--analysis-day",
                "6",
                "--analysis-hour",
                "9",
                "--analysis-timezone=+08:00",
                *extra,
                "--fields",
                *fields,
                "--strict-fields",
                "true",
                "--response-char-limit",
                "0",
            ]
        )
    assert code == 0, capture.getvalue()
    retain("CLI", kind, json.loads(capture.getvalue()))


async def mcp():
    async with Client(mcp_app) as client:
        tools = {t.name: t for t in await client.list_tools()}
        schema = tools["meihua_analysis"].input_schema
        assert schema["properties"]["analysis_minute"]["default"] == 0
        for kind, extra in [("omitted", {}), ("zero", {"analysis_minute": 0})]:
            response = await client.call_tool(
                "meihua_analysis",
                {
                    **args,
                    **extra,
                    "fields": fields,
                    "strict_fields": True,
                    "response_char_limit": 0,
                },
                raise_on_error=False,
            )
            assert not response.is_error, response
            retain("MCP", kind, response.structured_content)


asyncio.run(mcp())
print(
    json.dumps(
        {
            "package": str(fatebridge.__file__),
            "original_request_sha256": hashlib.sha256(
                original.read_bytes()
            ).hexdigest(),
            "original_request_default_minute": 0,
            "rows": rows,
        },
        ensure_ascii=False,
    )
)
