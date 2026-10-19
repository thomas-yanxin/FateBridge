"""Scenario generation, native transport replay and isolation contracts."""

import asyncio
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timezone
from pathlib import Path
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator
from pydantic import BaseModel

import fatebridge.api as api
import fatebridge.mcp_server as mcp
from fatebridge.application.discovery import discover_specs
from fatebridge.application.execution import execute_tool
from fatebridge.application.scenarios import (
    definitions,
    discover_scenarios,
    scenario_keys,
)
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.execution_context import ExecutionOptions, current_datetime
from fatebridge.core.reproducibility import ReproducibilityPolicy
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from scripts.build_scenario_manifest import build_manifest
from tests.fixtures.surface_payloads import REST_POST_CASES

BIRTH = REST_POST_CASES["/api/cn/bazi/birth"]()
AS_OF = "2024-02-29T16:30:00Z"
CONTROLS = {
    "as_of": AS_OF,
    "trace_id": "trace-replay-test",
    "parent_run_id": "parent-001",
}


@pytest.fixture
def rest(monkeypatch):
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    return TestClient(api.app)


def cli(tool, inputs, controls=None, flags=None):
    args = [sys.executable, "-m", "fatebridge.cli", tool]
    for key, value in {**inputs, **(controls or {})}.items():
        if value is not None and value != []:
            args += [
                "--" + key.replace("_", "-"),
                (
                    json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (dict, list, bool))
                    else str(value)
                ),
            ]
    result = subprocess.run(
        args + (flags or []), capture_output=True, text=True, timeout=45
    )
    return result.returncode, json.loads(result.stdout)


def native(tool, inputs, controls=None):
    async def call():
        async with Client(mcp.app) as client:
            result = await client.call_tool(
                tool,
                {**inputs, "response_char_limit": 0, **(controls or {})},
                raise_on_error=False,
            )
            assert json.loads(result.content[0].text) == result.structured_content
            return result

    return asyncio.run(call())


def business(payload):
    return {key: value for key, value in payload.items() if key != "run_metadata"}


def test_generated_scenarios_are_current_and_join_live_catalog():
    assert definitions() == build_manifest()
    full = discover_scenarios(CATALOG)
    interfaces = list(
        (Path(__file__).resolve().parents[1] / "skills").glob(
            "onda-*/agents/interface.yaml"
        )
    )
    assert len(full["scenarios"]) == len(interfaces) + 1
    keys = {spec.key for spec in CATALOG}
    for record in full["scenarios"]:
        assert record["availability"]["complete"]
        declared = {tool["key"] for tool in record["tools"]}
        assert declared <= keys
        for route in record["routing"]:
            for group in route["evidence"]:
                assert group["available"]
                assert set(group["alternatives"]) <= declared
                assert group["role"] in {"primary", "supporting", "deep"}
    pair = scenario_keys(CATALOG, "onda-yuanfen")
    assert {"astro_relative", "astro_relative_chart"} <= pair


@pytest.mark.parametrize("detail", ["summary", "full"])
@pytest.mark.parametrize(
    "scenario", ["onda-shiyun", "onda-fengshui", "onda-caiwu", "onda-zige"]
)
def test_scenario_manifest_parity_across_three_interfaces(rest, detail, scenario):
    params = {"scenario": scenario, "surface": "mcp", "detail": detail}
    http = rest.get("/api/scenarios", params=params)
    code, output = cli(
        "scenarios",
        {},
        flags=["--scenario", scenario, "--surface", "mcp", "--detail", detail],
    )

    async def read():
        async with Client(mcp.app) as client:
            uri = (
                "fatebridge://scenarios"
                if detail == "summary"
                else f"fatebridge://scenarios/{scenario}"
            )
            return json.loads((await client.read_resource(uri))[0].text)

    protocol = asyncio.run(read())
    if detail == "summary":
        protocol = {
            **protocol,
            "matched_count": 1,
            "scenarios": [
                record for record in protocol["scenarios"] if record["id"] == scenario
            ],
        }
    assert http.status_code == 200 and code == 0
    assert http.json() == output == protocol


def test_scenario_tool_filter_and_invalid_ids_are_explicit(rest):
    params = {"scenario": "onda-xingpan", "surface": "mcp", "detail": "summary"}
    code, output = cli(
        "discover", {}, flags=["--scenario", "onda-xingpan", "--surface", "mcp"]
    )
    assert code == 0 and output == rest.get("/api/tools", params=params).json()
    for endpoint, command in [
        ("/api/tools", "discover"),
        ("/api/scenarios", "scenarios"),
    ]:
        response = rest.get(endpoint, params={"scenario": "onda-xingpan,typo"})
        code, error = cli(command, {}, flags=["--scenario", "onda-xingpan,typo"])
        assert response.status_code == 422 and code == 1
        assert error["issues"] == response.json()["issues"]
        assert error["issues"][0]["code"] == "unknown_scenario"


def test_mcp_scenario_profiles_and_family_intersection_do_not_invent_routes():
    app = mcp.create_mcp_app(families="bazi", scenarios="onda-jiankang")
    expected = {
        spec.tool_name
        for spec in CATALOG
        if spec.key in scenario_keys(CATALOG, "onda-jiankang")
        and spec.family == "bazi"
        and spec.mcp_name
    }

    async def check():
        async with Client(app) as client:
            assert {tool.name for tool in await client.list_tools()} == expected
            manifest = json.loads(
                (await client.read_resource("fatebridge://scenarios/onda-jiankang"))[
                    0
                ].text
            )
            record = manifest["scenarios"][0]
            assert not record["availability"]["complete"]
            assert {tool["tool"] for tool in record["tools"]} == expected
            assert any(
                not group["available"]
                for row in record["routing"]
                for group in row["evidence"]
            )

    asyncio.run(check())
    with pytest.raises(ValueError):
        mcp.create_mcp_app(scenarios="typo")


@pytest.mark.parametrize("scenario", ["onda-jiankang", "onda-fengshui"])
def test_actual_process_uses_mcp_scenario_configuration(scenario):
    env = {
        **os.environ,
        "FATEBRIDGE_MCP_FAMILIES": "",
        "FATEBRIDGE_MCP_SCENARIOS": scenario,
    }
    code = "import asyncio,json; from fatebridge.mcp_server import app; print(json.dumps([t.name for t in asyncio.run(app.list_tools(run_middleware=False))]))"
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0
    expected = {
        spec.tool_name
        for spec in CATALOG
        if spec.mcp_name and spec.key in scenario_keys(CATALOG, scenario)
    }
    assert set(json.loads(result.stdout)) == expected


@pytest.mark.parametrize(
    "path,tool,inputs",
    [
        ("/api/cn/bazi/birth", "bazi_birth", BIRTH),
        (
            "/api/cn/liuri_analysis",
            "liuri_analysis",
            REST_POST_CASES.get("/api/cn/liuri_analysis", lambda: BIRTH)(),
        ),
    ],
)
def test_fixed_clock_replay_and_metadata_match_three_transports(
    rest, path, tool, inputs
):
    # Use the actual catalog route rather than assuming older route spellings.
    spec = next(spec for spec in CATALOG if spec.key == tool)
    inputs = {
        key: value for key, value in inputs.items() if not key.startswith("analysis_")
    }
    http = rest.post(spec.rest_path, json=inputs, params=CONTROLS)
    protocol = native(tool, inputs, CONTROLS)
    code, output = cli(tool, inputs, CONTROLS)
    assert http.status_code == 200 and not protocol.is_error and code == 0
    payloads = [http.json(), protocol.structured_content, output]
    assert business(payloads[0]) == business(payloads[1]) == business(payloads[2])
    if tool == "bazi_birth":
        assert payloads[0]["bazi_birth"]["analysis_date"] == "2024-03-01"
    for payload in payloads:
        metadata = payload["run_metadata"]
        assert metadata["trace_id"] == CONTROLS["trace_id"]
        assert metadata["parent_run_id"] == CONTROLS["parent_run_id"]
        assert metadata["effective_time"]["as_of"] == AS_OF
        assert metadata["determinism"]["uses_current_time"]
        assert metadata["duration_ms"] >= 0
        assert metadata["business_output_sha256"] == digest(business(payload))
        Draft202012Validator(spec.output_model.model_json_schema()).validate(payload)
    for key in (
        "input_sha256",
        "contract_sha256",
        "business_output_sha256",
        "runtime",
        "replay",
    ):
        assert (
            payloads[0]["run_metadata"][key]
            == payloads[1]["run_metadata"][key]
            == payloads[2]["run_metadata"][key]
        )
    replay = rest.post(
        spec.rest_path,
        json=inputs,
        params={"as_of": payloads[0]["run_metadata"]["replay"]["as_of"]},
    )
    assert business(replay.json()) == business(payloads[0])
    assert (
        replay.json()["run_metadata"]["run_id"] != payloads[0]["run_metadata"]["run_id"]
    )


def sixyao_inputs():
    spec = next(spec for spec in CATALOG if spec.key == "sixyao")
    return spec.request_model.model_validate(
        REST_POST_CASES[spec.rest_path]()
    ).model_dump(mode="json", exclude_unset=True)


def test_random_coin_receipt_can_be_replayed_in_rest_mcp_and_cli(rest):
    spec = next(spec for spec in CATALOG if spec.key == "sixyao")
    inputs = {
        **sixyao_inputs(),
        "method": "coin",
        "coins": None,
        "lines": [],
        "gua_code": None,
        "changed_code": None,
        "seed": None,
    }
    initial = rest.post(spec.rest_path, json=inputs, params=CONTROLS)
    assert initial.status_code == 200
    receipt = initial.json()["run_metadata"]
    assert receipt["determinism"]["seed_generated"]
    assert receipt["determinism"]["randomness_used"]
    inputs.update(receipt["replay"]["overrides"])
    replay = rest.post(spec.rest_path, json=inputs, params=CONTROLS)
    protocol = native("sixyao", inputs, CONTROLS)
    code, output = cli("sixyao", inputs, CONTROLS)
    assert replay.status_code == 200 and not protocol.is_error and code == 0
    for payload in [replay.json(), protocol.structured_content, output]:
        assert business(payload) == business(initial.json())
        assert payload["run_metadata"]["input_sha256"] == receipt["input_sha256"]
        assert not payload["run_metadata"]["determinism"]["seed_generated"]


@pytest.mark.parametrize(
    "override",
    [
        {"method": "time"},
        {"coins": [6, 7, 8, 9, 7, 8]},
        {"gua_code": "111111", "changed_code": "111111"},
    ],
)
def test_manual_or_time_casting_does_not_generate_a_seed(rest, override):
    spec = next(spec for spec in CATALOG if spec.key == "sixyao")
    inputs = {**sixyao_inputs(), "method": "coin", "seed": None, **override}
    result = rest.post(spec.rest_path, json=inputs, params={"as_of": AS_OF}).json()
    assert not result["run_metadata"]["determinism"]["seed_generated"]
    assert not result["run_metadata"]["determinism"]["randomness_used"]
    assert result["run_metadata"]["replay"]["overrides"] == {}


def test_normalized_blank_hexagrams_still_capture_the_random_seed(rest):
    spec = next(spec for spec in CATALOG if spec.key == "sixyao")
    inputs = {
        **sixyao_inputs(),
        "method": " COIN ",
        "coins": None,
        "lines": [],
        "gua_code": "  ",
        "changed_code": "abc",
        "seed": None,
    }
    result = rest.post(spec.rest_path, json=inputs, params={"as_of": AS_OF}).json()
    assert result["run_metadata"]["determinism"]["seed_generated"]
    replay = rest.post(
        spec.rest_path,
        json={**inputs, **result["run_metadata"]["replay"]["overrides"]},
        params={"as_of": AS_OF},
    ).json()
    assert business(replay) == business(result)


def test_pinned_partial_date_uses_existing_month_clamping_and_timezone_rules(rest):
    inputs = {**BIRTH, "analysis_year": 2024, "analysis_month": 2}
    result = rest.post(
        "/api/cn/bazi/birth", json=inputs, params={"as_of": "2024-01-31T00:00:00+08:00"}
    ).json()
    assert result["bazi_birth"]["analysis_date"] == "2024-02-29"
    assert result["run_metadata"]["effective_time"]["as_of"] == "2024-01-30T16:00:00Z"


def test_ephemeris_inventory_has_content_fingerprints_without_server_paths(
    monkeypatch, tmp_path
):
    from fatebridge.core import ephemeris_runtime
    from fatebridge.services import replay_metadata

    data = tmp_path / "test.se1"
    data.write_bytes(b"test-ephemeris")
    monkeypatch.setattr(
        ephemeris_runtime, "configured_ephemeris_path", lambda: str(tmp_path)
    )
    replay_metadata._ephemeris_inventory.cache_clear()
    inventory = replay_metadata.ephemeris_inventory()
    assert len(inventory["files"]["0/test.se1"]) == 64
    assert str(tmp_path) not in json.dumps(inventory)
    old = inventory["sha256"]
    data.write_bytes(b"changed-ephemeris")
    replay_metadata._ephemeris_inventory.cache_clear()
    assert replay_metadata.ephemeris_inventory()["sha256"] != old


def test_rule_versions_and_actual_time_policy_survive_projection(rest):
    from fatebridge.services.replay_metadata import provenance_values

    assert provenance_values(
        {
            "layers": [{"ruleset": {"ruleset_id": "zhongzhou", "version": "1.0"}}],
            "name": "PrivateIdentity",
        }
    ) == {"ruleset": ["zhongzhou@1.0"], "ruleset_id": ["zhongzhou"]}
    response = rest.post(
        "/api/cn/bazi/birth",
        json=BIRTH,
        params={**CONTROLS, "fields": "bazi_birth.day_master"},
    ).json()
    assert response["run_metadata"]["provenance"]["time_algorithm"] == ["直接时间"]


@pytest.mark.parametrize(
    "invalid",
    [
        {"as_of": "2026-10-12"},
        {"as_of": "private-invalid-time"},
        {"trace_id": "private invalid\ntrace"},
        {"parent_run_id": "x" * 129},
    ],
)
def test_execution_controls_fail_safely_and_consistently(rest, invalid):
    http = rest.post("/api/cn/bazi/birth", json=BIRTH, params=invalid)
    protocol = native("bazi_birth", BIRTH, invalid)
    code, output = cli("bazi_birth", BIRTH, invalid)
    assert http.status_code == 422 and protocol.is_error and code == 1
    assert (
        http.json()["issues"]
        == protocol.structured_content["issues"]
        == output["issues"]
    )
    for payload in [http.json(), protocol.structured_content, output]:
        assert "private" not in json.dumps(payload)


@pytest.mark.parametrize("case", ["model", "domain", "projection"])
def test_caller_correlation_survives_failure_paths(rest, case):
    inputs = dict(BIRTH)
    query = dict(CONTROLS)
    flags = []
    if case == "model":
        inputs["birth_day"] = 0
    elif case == "domain":
        inputs.update(
            birth_place="未提供", birth_longitude=None, use_true_solar_time=True
        )
    else:
        query.update(fields=["typo"], strict_fields=True)
        flags = ["--fields", "typo", "--strict-fields"]
    http = rest.post("/api/cn/bazi/birth", json=inputs, params=query)
    protocol = native("bazi_birth", inputs, query)
    code, output = cli("bazi_birth", inputs, CONTROLS, flags)
    assert http.status_code in {400, 422} and protocol.is_error and code == 1
    for payload in [http.json(), protocol.structured_content, output]:
        assert payload["trace_id"] == CONTROLS["trace_id"]
        assert payload["parent_run_id"] == CONTROLS["parent_run_id"]


def test_projection_and_no_metadata_keep_business_output_compatible(rest):
    full = rest.post("/api/cn/bazi/birth", json=BIRTH, params=CONTROLS).json()
    projected = rest.post(
        "/api/cn/bazi/birth",
        json=BIRTH,
        params={
            **CONTROLS,
            "fields": "bazi_birth.day_master",
            "strict_fields": "true",
            "include_snapshot_text": "false",
        },
    ).json()
    assert projected["bazi_birth"]["day_master"] == full["bazi_birth"]["day_master"]
    assert (
        projected["run_metadata"]["business_output_sha256"]
        == full["run_metadata"]["business_output_sha256"]
    )
    code, output = cli("bazi_birth", BIRTH, CONTROLS)
    args = [sys.executable, "-m", "fatebridge.cli", "--no-metadata", "bazi_birth"]
    for key, value in {**BIRTH, **CONTROLS}.items():
        if value is not None:
            args += [
                "--" + key.replace("_", "-"),
                str(value).lower() if isinstance(value, bool) else str(value),
            ]
    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    assert code == result.returncode == 0
    assert json.loads(result.stdout) == business(output)


def test_clocks_are_isolated_between_threads_and_reset_after_error():
    class Empty(BaseModel):
        pass

    barrier = Barrier(2)

    def service():
        before = current_datetime(timezone.utc)
        barrier.wait(timeout=5)
        after = current_datetime(timezone.utc)
        return {"clock": [before.isoformat(), after.isoformat()]}

    spec = ToolSpec(
        key="isolation",
        bind=lambda request: (service, (), {}),
        request_model=Empty,
        summary="Clock isolation",
        operation_label_zh="Clock isolation",
        family="test",
        reproducibility=ReproducibilityPolicy(implicit_current_time=True),
    )
    dates = ["2000-01-01T00:00:00Z", "2030-01-01T00:00:00Z"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda date: execute_tool(
                    spec, Empty(), options=ExecutionOptions(as_of=date)
                ),
                dates,
            )
        )
    for date, result in zip(dates, results):
        assert result["clock"] == [date.replace("Z", "+00:00")] * 2
    broken = replace(
        spec,
        bind=lambda request: (
            lambda: (_ for _ in ()).throw(RuntimeError("internal-secret")),
            (),
            {},
        ),
    )
    error = execute_tool(
        broken, Empty(), options=ExecutionOptions(as_of=dates[0], trace_id="isolation")
    )
    assert error["error_code"] == "internal_error" and error["trace_id"] == "isolation"
    assert current_datetime(timezone.utc).year not in {2000, 2030}


def test_metadata_fingerprint_and_privacy(rest):
    first = rest.post(
        "/api/cn/bazi/birth",
        json={**BIRTH, "name": "PrivateIdentityMarker"},
        params=CONTROLS,
    ).json()["run_metadata"]
    assert "PrivateIdentityMarker" not in json.dumps(first)
    assert first["runtime"]["package_version"] == first["package_version"]
    for key in ("implementation_sha256", "bundled_data_sha256", "environment_sha256"):
        assert len(first["runtime"][key]) == 64
    second = rest.post(
        "/api/cn/bazi/birth",
        json={**BIRTH, "name": "DifferentIdentityMarker"},
        params=CONTROLS,
    ).json()["run_metadata"]
    assert second["input_sha256"] != first["input_sha256"]
    assert second["runtime"] == first["runtime"]


def test_discovery_declares_replay_conditions_and_keeps_hints_separate():
    descriptions = {
        tool["tool"]: tool
        for tool in discover_specs(CATALOG, detail="summary")["tools"]
    }
    assert descriptions["sixyao"]["reproducibility"]["requires_seed_for_replay"]
    assert descriptions["sixyao"]["annotations"]["idempotentHint"]
    assert descriptions["bazi_birth"]["reproducibility"]["may_use_current_time"]
    assert not descriptions["knowledge_read"]["reproducibility"]["may_use_current_time"]


def test_profile_children_share_clock_and_correlate_to_parent():
    code, output = cli("profile", BIRTH, CONTROLS, ["--systems", "bazi,ziwei"])
    assert code == 0
    root = output["run_metadata"]
    assert (
        root["trace_id"] == CONTROLS["trace_id"]
        and root["parent_run_id"] == CONTROLS["parent_run_id"]
    )
    for result in output["profile"].values():
        metadata = result["run_metadata"]
        assert metadata["parent_run_id"] == root["run_id"]
        assert metadata["trace_id"] == root["trace_id"]
        assert metadata["effective_time"]["as_of"] == AS_OF


def test_receipt_generation_failure_is_internal_and_keeps_correlation(
    rest, monkeypatch
):
    from fatebridge.services import replay_metadata

    def fail(*args, **kwargs):
        raise ValueError("private-server-error")

    monkeypatch.setattr(replay_metadata, "execution_receipt", fail)
    http = rest.post("/api/cn/bazi/birth", json=BIRTH, params=CONTROLS)
    protocol = native("bazi_birth", BIRTH, CONTROLS)
    assert http.status_code == 500 and protocol.is_error
    for payload in [http.json(), protocol.structured_content]:
        assert payload["error_code"] == "internal_error"
        assert payload["trace_id"] == CONTROLS["trace_id"]
        assert "private" not in json.dumps(payload)
