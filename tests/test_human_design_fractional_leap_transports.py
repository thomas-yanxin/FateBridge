"""Exact input labels remain distinct from native TT displays on all adapters."""

import asyncio
import hashlib
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
PLAN = json.loads(
    (ROOT / "tests/fixtures/human_design_fractional_leap_v1/plan.json").read_text()
)


def test_original_one_microsecond_before_birth_misacceptance_is_preserved():
    path = (
        ROOT / "tests/fixtures/human_design_fractional_leap_v1/before-cycle-order.json"
    )
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == "f7ba80db03ea12ed468a7d954ffcaa3a6b0782379aad0341bffa34a83c64b9ed"
    )
    rows = json.loads(path.read_text())
    assert [r["reference_microseconds"] for r in rows] == [8, 9, 10]
    assert [r["before_accepted"] for r in rows] == [True, True, True]
    assert [r["expected_acceptance"] for r in rows] == [False, True, True]


def three_adapters(params, expected_status, monkeypatch, capsys):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as c:
        response = c.post("/api/astro/human-design", json=params)
    assert response.status_code == expected_status, response.text

    async def call():
        async with Client(create_mcp_app(families="astro")) as c:
            v = await c.call_tool(
                "human_design",
                {**params, "response_char_limit": 0},
                raise_on_error=False,
            )
            assert v.is_error == (expected_status != 200)
            return v.structured_content

    mcp = asyncio.run(call())
    assert run(
        [
            "human_design",
            *["--" + k.replace("_", "-") + "=" + str(v) for k, v in params.items()],
        ]
    ) == (0 if expected_status == 200 else 1)
    cli = json.loads(capsys.readouterr().out)
    values = [response.json(), mcp, cli]
    for v in values:
        if expected_status == 200:
            check = verify_human_design_reading(v)
            assert check["status"] == "verified_fixed_template_reading", check
            v.pop("run_metadata")
        else:
            assert v["error_code"] == "validation_error" and v["retryable"] is False
    if expected_status == 200:
        assert _same_value(values[0], values[1]) and _same_value(values[0], values[2])
    return values


@pytest.mark.parametrize("empty_files", [False, True])
@pytest.mark.parametrize("case", PLAN["cases"][-5:], ids=lambda c: c["id"])
def test_all_five_offsets_and_both_backends_on_rest_mcp_cli(
    case, empty_files, monkeypatch, capsys, tmp_path
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path if empty_files else ROOT / "ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    for v in three_adapters(case["input"], 200, monkeypatch, capsys):
        assert v["birth_utc"] == case["expected_utc_label"]
        assert v["time_scales"]["personality"]["utc_is_leap_second"] is True
        assert v["calculation_policy"]["ephemeris_model"] == (
            "moshier" if empty_files else "swieph"
        )


@pytest.mark.parametrize(
    "micros,relation", [(8, "before"), (9, "equal"), (10, "after")]
)
def test_three_adapters_compare_leap_input_microseconds_before_binary64_rounding(
    micros, relation, monkeypatch, capsys
):
    case = next(c for c in PLAN["cases"] if c["id"] == "2016-12-31-9us")
    params = {
        **case["input"],
        "cycle_reference_datetime": f"2016-12-31T23:59:60.{micros:06d}Z",
    }
    values = three_adapters(
        params, 422 if relation == "before" else 200, monkeypatch, capsys
    )
    if relation != "before":
        for v in values:
            assert v["cycle_context"]["reference_ordering"]["relation"] == relation
            assert v["cycle_summary"]["sixth_line"]["current_phase"] is None
