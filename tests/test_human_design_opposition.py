"""Exact opposition arithmetic; synthetic probes do not certify astronomy."""

import asyncio
import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from fractions import Fraction

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.examples import example_input
from fatebridge.application.execution import execute_tool
from fatebridge.cli import run as cli_run
from fatebridge.core.astro import runtime
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.human_design import (
    GATE_ORDER,
    activation_longitude_fraction,
    chart_at,
    longitude_activation,
    opposite_activation,
    positions_at_tt,
)
from fatebridge.core.human_design_evidence import source_activation_impacts
from fatebridge.core.human_design_precision import compare_node_backends
from fatebridge.core.human_design_sensitivity import assess_birth_interval
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

LEVELS = ("gate", "line", "color", "tone", "base")


def test_all_base_boundary_neighbors_preserve_exact_opposition_subdivisions():
    # The independent invariant is a half-wheel shift (32 gates), preserving
    # every finer subdivision. This is conditional arithmetic, not sky truth.
    checked = 0
    for index in range(69120):
        boundary = float((Fraction(302) + Fraction(index, 192)) % 360)
        for direction in (-math.inf, math.inf):
            source = math.nextafter(boundary, direction)
            if not 0 <= source < 360:
                continue
            first = longitude_activation(source)
            other = opposite_activation(source)
            assert (
                other["gate"] == GATE_ORDER[(GATE_ORDER.index(first["gate"]) + 32) % 64]
            )
            for key in (
                "line",
                "color",
                "tone",
                "base",
                "tone_orientation",
                "line_boundary_distance_degrees",
                "base_boundary_distance_arcseconds",
            ):
                assert other[key] == first[key], (source.hex(), key)
            assert 0 <= other["longitude"] < 360
            assert (
                activation_longitude_fraction({"derived_from": "Sun", **other})
                == (Fraction(source) + 180) % 360
            )
            checked += 1
    assert checked == 138239


@pytest.mark.parametrize("boundary", [0.0, 180.0, 332.078125, 43.25])
def test_display_float_does_not_replace_the_exact_classification_coordinate(boundary):
    source = math.nextafter(boundary, math.inf if boundary == 0 else -math.inf)
    expected = longitude_activation(source)
    opposite = opposite_activation(source)
    assert all(opposite[k] == expected[k] for k in ("line", "color", "tone", "base"))
    assert opposite["derivation_source_longitude"] == source
    if boundary in {180.0, 43.25}:
        rounded = longitude_activation(opposite["longitude"])
        assert any(rounded[k] != opposite[k] for k in LEVELS)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_nonfinite_opposition_source_is_rejected(bad):
    with pytest.raises(ValueError, match="有限"):
        opposite_activation(bad)


def test_actual_position_assembly_retains_the_same_source_for_both_oppositions(
    monkeypatch,
):
    source = math.nextafter(43.328125, -math.inf)

    def positions(operation, jd, body, flags):
        assert operation == "calc"
        return (source, 0, 1, -0.1, 0, 0), flags

    monkeypatch.setattr(runtime, "ephemeris_call", positions)
    result = positions_at_tt(2451545, "true")
    for derived, original in (("Earth", "Sun"), ("SouthNode", "NorthNode")):
        assert result[derived]["derived_from"] == original
        assert (
            result[derived]["derivation_source_longitude"]
            == result[original]["longitude"]
        )
        assert result[derived]["longitude"] == float((Fraction(source) + 180) % 360)


@pytest.fixture
def synthetic_solar_boundary(monkeypatch):
    # Keep actual TT conversion and other physical factors. Only the Sun is a
    # synthetic linear oracle so its nominal value is one float below a Tone
    # boundary, while the 88-degree root and full orchestration still execute.
    birth = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)
    birth_tt = ephemeris_time(birth).jd_tt
    source = math.nextafter(43.328125, -math.inf)
    original = runtime.ephemeris_call

    def call(operation, *args, **kwargs):
        if operation == "calc" and args[1] == runtime.swe.SUN:
            return ((source + (args[0] - birth_tt)) % 360, 0, 1, 1, 0, 0), args[2]
        return original(operation, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", call)
    return birth, source


@pytest.mark.native_engine_fault
def test_complete_run_and_fixed_reading_use_exact_source_before_display(
    synthetic_solar_boundary,
):
    birth, source = synthetic_solar_boundary
    spec = next(s for s in CATALOG if s.key == "human_design")
    run = execute_tool(
        spec,
        spec.request_model(
            **{
                **example_input(spec),
                "birth_year": 2000,
                "birth_month": 1,
                "birth_day": 1,
                "birth_hour": 12,
                "birth_minute": 0,
                "birth_timezone": "UTC",
            }
        ),
    )
    assert "error" not in run
    side = {a["body"]: a for a in run["activations"]["personality"]}
    assert side["Sun"]["longitude"] == source
    assert (side["Earth"]["tone"], side["Earth"]["base"]) == (3, 5)
    assert run["variables"]["status"] == "computed"
    assert (
        verify_human_design_reading(run)["status"] == "verified_fixed_template_reading"
    )
    # Even a fresh hash cannot make the rounded display's old wrong sector valid.
    forged = deepcopy(run)
    earth = next(
        a for a in forged["activations"]["personality"] if a["body"] == "Earth"
    )
    earth.update(longitude_activation(earth["longitude"]))
    forged["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in forged.items() if k != "run_metadata"}
    )
    assert verify_human_design_reading(forged)["status"] == "rejected"


def test_interval_derived_witnesses_retain_source_for_independent_replay(
    synthetic_solar_boundary,
):
    birth, _ = synthetic_solar_boundary
    nominal = chart_at(birth)
    interval = assess_birth_interval(nominal, 1, "true")
    earth = next(
        v
        for v in interval["activation_variants"]
        if v["side"] == "personality" and v["body"] == "Earth"
    )
    for witness in earth["first_observed_witness_per_state"]:
        assert witness["derived_from"] == "Sun"
        expected = opposite_activation(witness["derivation_source_longitude"])
        assert all(expected[k] == witness[k] for k in LEVELS)


@pytest.mark.native_engine_fault
def test_synthetic_boundary_survives_all_three_actual_transport_serializers(
    synthetic_solar_boundary, monkeypatch, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    params = {
        "birth_year": 2000,
        "birth_month": 1,
        "birth_day": 1,
        "birth_hour": 12,
        "birth_minute": 0,
        "birth_timezone": "UTC",
    }
    with TestClient(api.app) as client:
        result = client.post("/api/astro/human-design", json=params)
    assert result.status_code == 200, result.text

    async def protocol():
        async with Client(create_mcp_app(families="astro")) as client:
            value = await client.call_tool(
                "human_design", {**params, "response_char_limit": 0}
            )
            assert not value.is_error
            return value.structured_content

    payloads = [result.json(), asyncio.run(protocol())]
    flags = ["human_design", "--response-char-limit", "0"]
    for key, value in params.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert cli_run(flags) == 0
    payloads.append(json.loads(capsys.readouterr().out))
    for payload in payloads:
        earth = next(
            a for a in payload["activations"]["personality"] if a["body"] == "Earth"
        )
        assert earth["longitude"] == 223.328125
        assert (earth["tone"], earth["base"]) == (3, 5)
        assert earth["derivation_source_longitude"] == synthetic_solar_boundary[1]
        assert (
            verify_human_design_reading(payload)["status"]
            == "verified_fixed_template_reading"
        )
        payload.pop("run_metadata")
    assert payloads[0] == payloads[1] == payloads[2]


@pytest.mark.parametrize(
    "tamper", ["source_body", "source_value", "source_boolean", "physical_metadata"]
)
@pytest.mark.native_engine_fault
def test_fresh_hash_cannot_rebind_a_derived_activation(
    synthetic_solar_boundary, tamper
):
    spec = next(s for s in CATALOG if s.key == "human_design")
    payload = execute_tool(
        spec,
        spec.request_model(
            **{
                **example_input(spec),
                "birth_year": 2000,
                "birth_month": 1,
                "birth_day": 1,
                "birth_hour": 12,
                "birth_minute": 0,
                "birth_timezone": "UTC",
            }
        ),
    )
    side = {a["body"]: a for a in payload["activations"]["personality"]}
    if tamper == "source_body":
        side["Earth"]["derived_from"] = "NorthNode"
    elif tamper == "source_value":
        side["Earth"]["derivation_source_longitude"] = math.nextafter(
            side["Sun"]["longitude"], math.inf
        )
    elif tamper == "source_boolean":
        side["Earth"]["derivation_source_longitude"] = True
    else:
        side["Moon"]["derived_from"] = "Sun"
        side["Moon"]["derivation_source_longitude"] = side["Sun"]["longitude"]
    payload["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in payload.items() if k != "run_metadata"}
    )
    assert verify_human_design_reading(payload)["status"] == "rejected"


def test_node_backend_reference_classifies_the_opposite_before_display(monkeypatch):
    chart = chart_at(datetime(2000, 1, 1, 12, tzinfo=timezone.utc))
    source = math.nextafter(332.078125, -math.inf)

    def node(operation, jd, body, flags):
        assert operation == "calc" and body == runtime.swe.TRUE_NODE
        return (source, 0, 1, -0.1, 0, 0), flags

    monkeypatch.setattr(runtime, "ephemeris_call", node)
    report = compare_node_backends(chart, "true")
    for row in report["rows"]:
        assert (row["reference"]["tone"], row["reference"]["base"]) == (3, 5)


def test_printed_source_impact_uses_exact_derived_coordinate():
    source = math.nextafter(43.25, -math.inf)
    earth = {"body": "Earth", "derived_from": "Sun", **opposite_activation(source)}
    assert earth["longitude"] == 223.25
    assert earth["gate"] == 44
    report = source_activation_impacts({"activations": {"personality": [earth]}})
    assert report["status"] == "no_line_discrepancy_at_returned_longitudes"
