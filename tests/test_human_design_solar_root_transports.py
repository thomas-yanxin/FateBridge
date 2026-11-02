"""Raw and boundary-sensitive root witnesses on real protocol serializers."""

import asyncio
import json
from fractions import Fraction

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.examples import evidence_views
from fatebridge.cli import run
from fatebridge.core.astro import runtime
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

SPEC = next(s for s in CATALOG if s.key == "human_design")
INPUT = dict(
    birth_year=2000,
    birth_month=1,
    birth_day=1,
    birth_hour=12,
    birth_minute=0,
    birth_timezone="UTC",
)


@pytest.mark.parametrize(
    "synthetic", [False, pytest.param(True, marks=pytest.mark.native_engine_fault)]
)
@pytest.mark.parametrize("empty_files", [False, True])
def test_full_solar_root_witness_and_precision_card_on_actual_three_surfaces(
    monkeypatch, tmp_path, capsys, synthetic, empty_files
):
    if empty_files:
        monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    if synthetic:
        from datetime import datetime, timezone

        birth = ephemeris_time(datetime(2000, 1, 1, 12, tzinfo=timezone.utc)).jd_tt
        original = runtime.ephemeris_call

        def oracle(operation, *args, **kwargs):
            if operation == "calc" and args[1] == runtime.swe.SUN:
                lon = float(
                    (
                        Fraction(131328125, 1000000)
                        + Fraction(51, 50) * (Fraction(args[0]) - Fraction(birth))
                    )
                    % 360
                )
                return (lon, 0, 1, 1.02, 0, 0), args[2]
            return original(operation, *args, **kwargs)

        monkeypatch.setattr(runtime, "ephemeris_call", oracle)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as rest:
        response = rest.post(SPEC.rest_path, json=INPUT)
    assert response.status_code == 200, response.text
    expected = response.json()

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "human_design", {**INPUT, "response_char_limit": 0}
            )
            assert not result.is_error
            card = await client.call_tool(
                "human_design",
                {
                    **INPUT,
                    "fields": evidence_views(SPEC)["precision"]["fields"],
                    "strict_fields": True,
                    "response_char_limit": 0,
                    "include_snapshot_text": False,
                },
            )
            assert not card.is_error
            assert card.structured_content["design_solver"] == expected["design_solver"]
            assert (
                card.structured_content["interpretation"][
                    "design_time_precision_meaning"
                ]
                == expected["interpretation"]["design_time_precision_meaning"]
            )
            return result.structured_content

    native = asyncio.run(call())
    flags = ["human_design"]
    for key, value in INPUT.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run(flags) == 0
    cli = json.loads(capsys.readouterr().out)
    for value in [expected, native, cli]:
        check = verify_human_design_reading(value)
        assert check["status"] == "verified_fixed_template_reading", check
        w = value["design_solver"]["numerical_precision"]
        if synthetic:
            assert w["observed_solar_changed_levels"]
            assert (
                w["solar_subdivision_status"]
                == "observed_variation_at_final_numeric_bracket"
            )
            assert "差异" in value["interpretation"]["design_time_precision_meaning"]
        assert w["physical_time_accuracy_certified"] is False
        value.pop("run_metadata")
    assert expected == native == cli
