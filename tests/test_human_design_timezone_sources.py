"""Timezone-source faults reject the complete reading on every public adapter."""

import asyncio
import hashlib
import json
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services import human_design
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils import timezones
from fatebridge.validation.human_design import verify_human_design_reading

SPEC = next(s for s in CATALOG if s.key == "human_design")
PARAMS = dict(
    birth_year=1980,
    birth_month=7,
    birth_day=1,
    birth_hour=12,
    birth_minute=0,
    birth_timezone="America/New_York",
)


@pytest.mark.native_engine_fault
@pytest.mark.parametrize(
    "fault",
    [
        "changed",
        "changed_and_cache_cleared",
        "changed_and_cache_evicted",
        "unavailable",
        "invalid",
    ],
)
def test_actual_tzif_fault_has_consistent_safe_errors_on_three_surfaces(
    monkeypatch, capsys, fault
):
    original_open = timezones.pytz.open_resource
    with original_open(PARAMS["birth_timezone"]) as stream:
        ny = stream.read()
    with original_open("Etc/UTC") as stream:
        utc = stream.read()
    current = [ny]

    def resource(name):
        if name != PARAMS["birth_timezone"]:
            return original_open(name)
        if isinstance(current[0], Exception):
            raise current[0]
        return BytesIO(current[0])

    monkeypatch.setattr(timezones.pytz, "open_resource", resource)
    original_evidence = human_design.evidence

    def evidence(chart):
        result = original_evidence(chart)
        if fault.startswith("changed"):
            current[0] = utc
            if fault.endswith("cache_cleared"):
                timezones._parse_timezone_name_cached.cache_clear()
            elif fault.endswith("cache_evicted"):
                for minute in range(129):
                    timezones.parse_timezone_name(
                        f"+02:{minute % 60:02}:{minute // 60:02}"
                    )
        return result

    monkeypatch.setattr(human_design, "evidence", evidence)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )

    def reset():
        timezones._parse_timezone_name_cached.cache_clear()
        current[0] = {
            "invalid": b"invalid TZif",
            "unavailable": FileNotFoundError("private/source/path"),
        }.get(fault, ny)

    reset()
    with TestClient(api.app) as client:
        response = client.post(SPEC.rest_path, json=PARAMS)
    assert response.status_code == 503, response.text
    rest = response.json()

    async def call():
        reset()
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "human_design", PARAMS, raise_on_error=False
            )
            assert result.is_error
            return result.structured_content

    native = asyncio.run(call())
    reset()
    flags = ["human_design"]
    for key, value in PARAMS.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run(flags) == 1
    cli = json.loads(capsys.readouterr().out)
    for result in (rest, native, cli):
        assert result["error_code"] == "ephemeris_source_inconsistent"
        assert result["retryable"] is False
        assert result["issues"] == [
            {
                "path": "runtime.ephemeris_data",
                "code": "timezone_rules_"
                + ("changed" if fault.startswith("changed") else fault),
            }
        ]
        assert "private/source/path" not in json.dumps(result)
        assert "activations" not in result and "interpretation" not in result


def test_valid_named_zone_still_has_a_complete_verified_reading():
    value = execute_tool(SPEC, SPEC.request_model(**PARAMS))
    assert value["native_execution_context"]["mechanism"] == "fresh_exec_process"
    assert value["birth_utc"] == "1980-07-01T16:00:00+00:00"
    with timezones.pytz.open_resource(PARAMS["birth_timezone"]) as stream:
        expected = hashlib.sha256(stream.read()).hexdigest()
    assert value["clock_evidence"]["timezone_rules"]["tzif_sha256"] == expected
    check = verify_human_design_reading(value)
    assert check["status"] == "verified_fixed_template_reading", check
