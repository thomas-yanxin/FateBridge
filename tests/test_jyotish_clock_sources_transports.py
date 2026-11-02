"""Whole-clock configuration sessions through the three real local surfaces."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import ephemeris_runtime as e
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services import astrology, jyotish
from fatebridge.services.tool_catalog import CATALOG
from tests.test_jyotish_clock_sources import arguments
from tests.test_jyotish_sources import data18, restore_runtime  # noqa: F401


@pytest.mark.native_engine_fault
@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari", "astro_chart"])
def test_clock_to_native_change_is_typed_and_uniform_sources_succeed_on_all_surfaces(
    data18, tmp_path, monkeypatch, capsys, key
):
    _, full = data18
    empty = tmp_path / "empty"
    empty.mkdir()
    module, name = (
        (jyotish, "build_astro_birth_info")
        if key == "astro_vimshottari"
        else (astrology, "_build_birth_info")
    )
    original = getattr(module, name)
    mutate = True

    def changed(*args, **kwargs):
        birth = original(*args, **kwargs)
        if mutate:
            monkeypatch.setenv("SE_EPHE_PATH", str(full))
            e.configure_ephemeris_path(str(full))
        return birth

    monkeypatch.setattr(module, name, changed)
    payload = {"name": "虚构：太阳钟时来源衔接", **arguments()}
    if key == "astro_vimshottari":
        payload["analysis_year"] = 2026
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    spec = next(s for s in CATALOG if s.key == key)
    fields = ["india.profile.clock_context", "india.birth_time_sensitivity"]
    options = {
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
        "as_of": "2026-10-22T00:00:00Z",
    }
    request = tmp_path / "request.json"
    request.write_text(json.dumps(payload))
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )

    def select(directory):
        monkeypatch.setenv("SE_EPHE_PATH", str(directory))
        e.configure_ephemeris_path(str(directory))

    def surfaces(directory):
        params = [("fields", f) for f in fields] + [
            (k, str(v).lower() if isinstance(v, bool) else str(v))
            for k, v in options.items()
            if k != "fields"
        ]
        select(directory)
        rest = TestClient(api.app).post(spec.rest_path, json=payload, params=params)

        async def protocol():
            async with Client(create_mcp_app()) as client:
                return await client.call_tool(
                    spec.tool_name, {**payload, **options}, raise_on_error=False
                )

        select(directory)
        mcp = asyncio.run(protocol())
        capsys.readouterr()
        select(directory)
        code = run(
            [
                spec.tool_name,
                "--subject-file",
                str(request),
                "--fields",
                *fields,
                "--strict-fields",
                "--no-include-snapshot-text",
                "--response-char-limit",
                "0",
                "--as-of",
                options["as_of"],
            ]
        )
        return rest, mcp, code, json.loads(capsys.readouterr().out)

    rest, mcp, code, cli = surfaces(empty)
    assert rest.status_code == 503 and mcp.is_error and code == 1
    for result in [rest.json(), json.loads(mcp.content[0].text), cli]:
        assert result["error_code"] == "ephemeris_source_inconsistent"
        assert result["retryable"] is False
        assert result["issues"] == [
            {"path": "runtime.ephemeris_data", "code": "physical_configuration_changed"}
        ]
        assert str(tmp_path) not in json.dumps(result)

    mutate = False
    for directory, model in [(empty, "moshier"), (full, "swieph")]:
        rest, mcp, code, cli = surfaces(directory)
        assert rest.status_code == 200 and not mcp.is_error and code == 0
        results = [rest.json(), mcp.structured_content, cli]
        assert results[0]["india"] == results[1]["india"] == results[2]["india"]
        for result in results:
            clock = result["india"]["profile"]["clock_context"]
            assert clock["input_clock_conversion"][
                "solar_ephemeris_models_observed"
            ] == [model]
            checked = clock["source_comparison"]
            assert checked["status"] == "compatible_observed_sun_contexts"
            assert checked["physical_instant_shifted"] is False
            assert checked["original_sun_identity_recorded"] is True
            grid = result["india"]["birth_time_sensitivity"]
            assert (
                len(grid["source_comparison"]["sample_source_indices"])
                == grid["sample_count"]
            )
