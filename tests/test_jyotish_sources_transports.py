"""Source-coherent grids through actual REST, native MCP and CLI calls."""

import asyncio
import json
import shutil

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import ephemeris_runtime as e
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.test_jyotish_sources import data18, edge_birth, restore_runtime  # noqa: F401


@pytest.mark.parametrize(
    "key,variant",
    [
        ("astro_india", None),
        ("astro_vimshottari", None),
        ("astro_chart", "india_chart"),
    ],
)
def test_source_grid_boundary_errors_and_complete_files_across_surfaces(
    data18, monkeypatch, tmp_path, capsys, key, variant
):
    root, directory = data18
    center = edge_birth().utc_datetime
    monkeypatch.setenv("SE_EPHE_PATH", str(directory))
    payload = {
        "name": "虚构：印占文件覆盖边界",
        "birth_year": center.year,
        "birth_month": center.month,
        "birth_day": center.day,
        "birth_hour": center.hour,
        "birth_minute": center.minute,
        "birth_second": center.second,
        "birth_timezone": "UTC",
        "birth_longitude": 0.0,
        "birth_latitude": 0.0,
        "birth_time_uncertainty_minutes": 1.0,
        "divisions": [],
    }
    if key == "astro_vimshottari":
        payload["analysis_year"] = center.year + 1
    if variant:
        payload["chart_variant"] = variant
    spec = next(s for s in CATALOG if s.key == key)
    fields = ["india.profile.physical_ephemeris_source", "india.birth_time_sensitivity"]
    options = {
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
        "as_of": "2026-10-22T00:00:00Z",
    }
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    request = tmp_path / "request.json"
    request.write_text(json.dumps(payload))

    def surfaces():
        params = [("fields", field) for field in fields] + [
            (k, str(v).lower() if isinstance(v, bool) else str(v))
            for k, v in options.items()
            if k != "fields"
        ]
        rest = TestClient(api.app).post(spec.rest_path, json=payload, params=params)

        async def protocol():
            async with Client(create_mcp_app()) as client:
                return await client.call_tool(
                    spec.tool_name, {**payload, **options}, raise_on_error=False
                )

        mcp = asyncio.run(protocol())
        capsys.readouterr()
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

    rest, mcp, code, cli = surfaces()
    assert rest.status_code == 503 and mcp.is_error and code == 1
    # Chart derivatives and the native birth grid must both retain an actual
    # missing-file model transition. Restoring coverage must compute the same
    # original birth epoch; a neighbor cannot substitute for this assertion.
    reason = "model_changed"
    for error in [rest.json(), json.loads(mcp.content[0].text), cli]:
        assert error["error_code"] == "ephemeris_source_inconsistent"
        assert error["issues"] == [{"path": "runtime.ephemeris_data", "code": reason}]
        assert error["retryable"] is False
        assert str(directory) not in json.dumps(error)
    for name in ("sepl_24.se1", "semo_24.se1"):
        shutil.copy2(root / name, directory / name)
    e.configure_ephemeris_path(str(directory))
    rest, mcp, code, cli = surfaces()
    assert rest.status_code == 200 and not mcp.is_error and code == 0
    bodies = [rest.json(), mcp.structured_content, cli]
    assert bodies[0]["india"] == bodies[1]["india"] == bodies[2]["india"]
    grid = bodies[0]["india"]["birth_time_sensitivity"]
    assert grid["sample_count"] == 5
    assert len(grid["source_comparison"]["sample_source_indices"]) == 5
    assert grid["sampled_ephemeris_fallback_bodies"] == []
