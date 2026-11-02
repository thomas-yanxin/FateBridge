"""Real production workers reject auxiliary changes on all public adapters."""

import asyncio
import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application import result_delivery as delivery
from fatebridge.cli import run
from fatebridge.core.astro import native_execution, runtime
from fatebridge.mcp_server import create_mcp_app
from fatebridge.validation.human_design import verify_human_design_reading


@pytest.mark.parametrize(
    "filename", ["swe_deltat.txt", "sedeltat.txt", "seleapsec.txt"]
)
def test_actual_child_auxiliary_change_keeps_safe_three_surface_source_error(
    tmp_path, monkeypatch, capsys, filename
):
    params = dict(
        birth_year=1900,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        birth_timezone="UTC",
    )
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    original = native_execution._receive
    changes = []
    current = None

    def receive(*args):
        result = original(*args)
        if result.get("kind") == "ready":
            (current / filename).write_text(
                "# Auxiliary candidate created after worker ready\n"
            )
            changes.append(True)
        return result

    monkeypatch.setattr(native_execution, "_receive", receive)
    outputs = []
    current = tmp_path / "rest"
    current.mkdir()
    monkeypatch.setenv("SE_EPHE_PATH", str(current))
    with TestClient(api.app) as client:
        response = client.post("/api/astro/human-design", json=params)
    assert response.status_code == 503, response.text
    outputs.append(response.json())

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "human_design", params, raise_on_error=False
            )
            assert result.is_error
            return result.structured_content

    current = tmp_path / "mcp"
    current.mkdir()
    monkeypatch.setenv("SE_EPHE_PATH", str(current))
    outputs.append(asyncio.run(call()))
    current = tmp_path / "cli"
    current.mkdir()
    monkeypatch.setenv("SE_EPHE_PATH", str(current))
    flags = ["human_design"]
    for key, value in params.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run(flags) == 1
    outputs.append(json.loads(capsys.readouterr().out))
    assert len(changes) == 3
    for result in outputs:
        assert result["error_code"] == "ephemeris_source_inconsistent"
        assert result["retryable"] is False
        assert result["issues"][0]["code"] == "auxiliary_changed_during"
        assert str(tmp_path) not in json.dumps(result)


def test_same_run_pages_forbid_private_dispatch_as_well_as_parent_native_calls(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        delivery, "RESULT_STORE", delivery.ResultStore(tmp_path / "results")
    )

    async def check():
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "human_design",
                dict(
                    birth_year=1900,
                    birth_month=4,
                    birth_day=6,
                    birth_hour=9,
                    birth_minute=33,
                    birth_timezone="UTC",
                    birth_time_uncertainty_minutes=2,
                    fields=None,
                    include_snapshot_text=False,
                    response_char_limit=8192,
                ),
            )
            assert not result.is_error
            shaped = result.structured_content
            reference = shaped["result_delivery"]
            assert shaped["run_metadata"]["run_id"]

            def forbidden(*args, **kwargs):
                raise AssertionError(
                    "Paged original run cannot dispatch a private calculation or call native code"
                )

            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(runtime, "ephemeris_call", forbidden)
                patch.setattr(native_execution, "calculate", forbidden)
                parts = []
                offset = 0
                while offset is not None:
                    page = json.loads(
                        (
                            await client.read_resource(
                                f"fatebridge://results/{reference['result_id']}/pages/{offset}"
                            )
                        )[0].text
                    )
                    parts.append(page["text"])
                    offset = page["next_offset"]
                text = "".join(parts)
                assert (
                    hashlib.sha256(text.encode()).hexdigest()
                    == reference["sha256"]
                    == page["sha256"]
                )
                original = json.loads(text)
                assert (
                    original["run_metadata"]["run_id"]
                    == shaped["run_metadata"]["run_id"]
                )
                verified = verify_human_design_reading(original)
                assert verified["status"] == "verified_fixed_template_reading", verified
                assert (
                    original["native_execution_context"]["mechanism"]
                    == "fresh_exec_process"
                )

    asyncio.run(check())
