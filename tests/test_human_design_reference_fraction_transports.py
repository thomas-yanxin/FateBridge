"""Actual adapters keep hour/minute fractions, prebirth decisions and leap clocks."""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.validation.claims import _same_value
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[1]
BASIC = dict(
    birth_year=1980,
    birth_month=9,
    birth_day=9,
    birth_hour=12,
    birth_minute=15,
    birth_timezone="UTC",
)
CASES = [
    (
        "hour",
        {**BASIC, "cycle_reference_datetime": "1980-09-09T12.5Z"},
        200,
        "1980-09-09T12:30:00+00:00",
        "after",
    ),
    (
        "minute",
        {**BASIC, "cycle_reference_datetime": "1980-09-09T12:15.5Z"},
        200,
        "1980-09-09T12:15:30+00:00",
        "after",
    ),
    (
        "false-leap-guard",
        {
            **BASIC,
            "birth_minute": 0,
            "cycle_reference_datetime": "1980-09-09T12.123600Z",
        },
        200,
        "1980-09-09T12:07:24.960000+00:00",
        "after",
    ),
    (
        "offset-microsecond",
        {
            **BASIC,
            "birth_minute": 0,
            "cycle_reference_datetime": "1980-09-09T1230,000001-00:00:00.000001",
        },
        200,
        "1980-09-09T12:30:00.000061+00:00",
        "after",
    ),
    (
        "before",
        {**BASIC, "cycle_reference_datetime": "1980-09-09T12.1Z"},
        422,
        None,
        None,
    ),
    (
        "ordinary",
        {**BASIC, "cycle_reference_datetime": "1980-09-09T12:30:00.000001Z"},
        200,
        "1980-09-09T12:30:00.000001+00:00",
        "after",
    ),
    (
        "true-leap",
        dict(
            birth_year=2016,
            birth_month=12,
            birth_day=31,
            birth_hour=23,
            birth_minute=59,
            birth_second=60,
            birth_timezone="-0.0000000025",
            cycle_reference_datetime="2016-12-31T23:59:60.000009Z",
        ),
        200,
        "2016-12-31T23:59:60.000009+00:00",
        "equal",
    ),
]


@pytest.mark.parametrize("empty", [False, True])
@pytest.mark.parametrize(
    "cid,params,status,reference,relation", CASES, ids=[c[0] for c in CASES]
)
def test_fixed_fraction_semantics_and_original_rejections_on_three_surfaces(
    cid, params, status, reference, relation, empty, monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path if empty else ROOT / "ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as c:
        response = c.post("/api/astro/human-design", json=params)
    assert response.status_code == status, response.text

    async def call():
        async with Client(create_mcp_app(families="astro")) as c:
            v = await c.call_tool(
                "human_design",
                {**params, "response_char_limit": 0},
                raise_on_error=False,
            )
            assert v.is_error == (status != 200)
            return v.structured_content

    mcp = asyncio.run(call())
    assert run(
        [
            "human_design",
            *["--" + k.replace("_", "-") + "=" + str(v) for k, v in params.items()],
        ]
    ) == (0 if status == 200 else 1)
    values = [response.json(), mcp, json.loads(capsys.readouterr().out)]
    for v in values:
        if status == 200:
            check = verify_human_design_reading(v)
            assert check["status"] == "verified_fixed_template_reading", check
            assert v["cycle_context"]["reference_utc"] == reference
            assert v["cycle_context"]["reference_ordering"]["relation"] == relation
            assert v["cycle_summary"]["sixth_line"]["current_phase"] is None
            assert v["calculation_policy"]["ephemeris_model"] == (
                "moshier" if empty else "swieph"
            )
            v.pop("run_metadata")
        else:
            assert v["error_code"] == "validation_error" and v["retryable"] is False
    if status == 200:
        assert _same_value(values[0], values[1]) and _same_value(values[0], values[2])
