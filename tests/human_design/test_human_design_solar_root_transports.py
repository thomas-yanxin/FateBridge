"""Raw and boundary-sensitive root witnesses on real protocol serializers."""

import asyncio
import json
import math
from fractions import Fraction
from pathlib import Path

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
from tests.support.transports import AS_OF, three_surfaces

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
    "synthetic",
    [
        False,
        pytest.param(True, marks=pytest.mark.native_engine_fault),
        pytest.param("plateau", marks=pytest.mark.native_engine_fault),
    ],
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
                origin = Fraction(131328125, 1000000)
                rate = Fraction(1) if synthetic == "plateau" else Fraction(51, 50)
                lon = float(
                    (origin + rate * (Fraction(args[0]) - Fraction(birth))) % 360
                )
                if synthetic == "plateau" and abs(
                    Fraction(args[0]) - Fraction(birth - 88)
                ) <= 3 * Fraction(math.ulp(birth - 88)):
                    lon = float((origin - 88) % 360)
                return (lon, 0, 1, float(rate), 0, 0), args[2]
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
        if synthetic is True:
            assert w["observed_solar_changed_levels"]
            assert (
                w["solar_subdivision_status"]
                == "observed_variation_at_final_numeric_bracket"
            )
            assert "差异" in value["interpretation"]["design_time_precision_meaning"]
        elif synthetic == "plateau":
            lattice = w["local_solar_lattice"]
            assert lattice["selection_changed_by_lattice"] is True
            assert len(lattice["observed_exact_zero_indices"]) == 7
            assert w["selected"]["jd_tt"] < lattice["initial_lower_jd_tt"]
            assert w["lower"] == w["upper"] == w["selected"]
            assert w["selected"]["exact_residual"]["numerator"] == "0"
        assert w["physical_time_accuracy_certified"] is False
        value.pop("run_metadata")
    assert expected == native == cli


@pytest.mark.parametrize(
    "empty_files", [pytest.param(False, marks=pytest.mark.local_data), True]
)
def test_original_neptune_birth_window_keeps_candidates_and_method_on_three_surfaces(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    empty_files: bool,
) -> None:
    root = Path(__file__).resolve().parents[2]
    reference = json.loads(
        (root / "tests/fixtures/human-design-disc-clock-observations.json").read_text()
    )
    case = next(
        case
        for case in reference["cases"]
        if case["id"] == "disc-full-21-neptune-184002020325"
    )
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path if empty_files else root / "ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    reading = three_surfaces(
        SPEC,
        {**case["birth_input"], "birth_time_uncertainty_minutes": 1},
        [
            "activations",
            "design_solver",
            "time_sensitivity",
            "calculation_policy",
            "ephemeris_source_summary",
        ],
        AS_OF,
        tmp_path,
        monkeypatch,
        capsys,
    )
    models = {
        activation["ephemeris_model"]
        for column in reading["activations"].values()
        for activation in column
        if activation["body"] not in ("Earth", "NorthNode", "SouthNode")
    }
    assert models == {"moshier" if empty_files else "swieph"}
    precision = reading["design_solver"]["numerical_precision"]
    assert precision["method_id"] == "human_design_observed_contact_solar_root_v2"
    assert precision["physical_time_accuracy_certified"] is False
    lattice = precision["local_solar_lattice"]
    assert lattice["unique_physical_root_certified"] is False
    endpoints = precision["design_body_endpoint_assessment"]
    assert {row["jd_tt"] for row in endpoints["evaluations"]} == {
        precision["lower"]["jd_tt"],
        precision["upper"]["jd_tt"],
    }
    selected = endpoints["evaluations"][endpoints["selected_evaluation_index"]]
    assert selected["jd_tt"] == reading["design_solver"]["design_jd_tt"]
    design_sun = next(
        activation
        for activation in reading["activations"]["design"]
        if activation["body"] == "Sun"
    )
    assert selected["native_positions"][0][0] == design_sun["longitude"]
    family = precision["local_root_family"]
    if lattice["multiple_numeric_contacts_observed"]:
        assert {row["jd_tt"] for row in family["candidates"]} == {
            lattice["samples"][index]["jd_tt"]
            for index in lattice["candidate_epoch_indices"]
        }
        assert family["continuous_root_count_certified"] is False
    else:
        assert family is None
    window = reading["time_sensitivity"]
    assert window["sampling"]["grid_sample_count"] == 13
    assert window["sampling"]["continuous_interval_certified"] is False
    assert window["evaluation_witnesses"]["samples"]
    assert reading["ephemeris_source_summary"]["accuracy_certified"] is False
