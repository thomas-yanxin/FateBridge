"""Observed natal file sources survive real projection and lossless paging."""

import asyncio
import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
from fatebridge.application import result_delivery as delivery
from fatebridge.application.examples import evidence_views
from fatebridge.cli import run
from fatebridge.core.astro import runtime
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

SPEC = next(s for s in CATALOG if s.key == "human_design")
INPUT = dict(
    birth_year=2024,
    birth_month=3,
    birth_day=20,
    birth_hour=6,
    birth_minute=30,
    birth_timezone="UTC",
    birth_time_uncertainty_minutes=2,
)


@pytest.mark.parametrize("node_mode", ["true", "mean"])
@pytest.mark.parametrize("empty", [False, True])
def test_file_sources_card_and_full_three_surface_readings_match_with_lossless_paging(
    monkeypatch, tmp_path, capsys, node_mode, empty
):
    if empty:
        monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty"))
    store = delivery.ResultStore(tmp_path / "result_store")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    params = {**INPUT, "node_mode": node_mode}
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as rest:
        response = rest.post(SPEC.rest_path, json=params)
    assert response.status_code == 200, response.text
    expected = response.json()
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:

            async def restore(shaped):
                reference = shaped["result_delivery"]

                def forbidden(*args, **kwargs):
                    raise AssertionError(
                        "resource pages must not recalculate positions"
                    )

                parts = []
                offset = 0
                with pytest.MonkeyPatch.context() as patch:
                    patch.setattr(runtime, "ephemeris_call", forbidden)
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
                    == page["sha256"]
                    == reference["sha256"]
                )
                original = json.loads(text)
                assert (
                    original["run_metadata"]["run_id"]
                    == shaped["run_metadata"]["run_id"]
                )
                return original

            card = await client.call_tool(
                "human_design",
                {
                    **params,
                    "fields": evidence_views(SPEC)["source_files"]["fields"],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 8192,
                },
            )
            assert not card.is_error
            assert len(card.content[0].text) <= 8192
            assert json.loads(card.content[0].text) == card.structured_content
            assert (
                card.structured_content["ephemeris_source_summary"]
                == expected["ephemeris_source_summary"]
            )
            assert "ephemeris_source_evidence" not in card.structured_content
            if "result_delivery" in card.structured_content:
                assert card.structured_content["result_delivery"][
                    "deferred_fields"
                ] == ["run_metadata.runtime"]
                await restore(card.structured_content)
            context_card = await client.call_tool(
                "human_design",
                {
                    **params,
                    "fields": evidence_views(SPEC)["native_context"]["fields"],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 8192,
                },
            )
            assert not context_card.is_error
            assert len(context_card.content[0].text) <= 8192
            assert (
                context_card.structured_content["native_execution_context"]
                == expected["native_execution_context"]
            )
            if "result_delivery" in context_card.structured_content:
                await restore(context_card.structured_content)
            bounded = await client.call_tool(
                "human_design",
                {
                    **params,
                    "fields": None,
                    "include_snapshot_text": False,
                    "response_char_limit": 8192,
                },
            )
            assert not bounded.is_error
            return await restore(bounded.structured_content)

    native = asyncio.run(call())
    flags = ["human_design"]
    for k, v in params.items():
        flags.extend(["--" + k.replace("_", "-"), str(v)])
    assert run(flags) == 0
    cli = json.loads(capsys.readouterr().out)
    for result in (expected, native, cli):
        assert result["native_execution_context"]["mechanism"] == "fresh_exec_process"
        assert (
            result["native_execution_context"]["lifetime"]
            == "one_outer_human_design_operation"
        )
        check = verify_human_design_reading(result)
        assert check["status"] == "verified_fixed_template_reading", check
        assert (
            check["checked_node_report_count"] == 2
            and check["checked_statement_count"] == 10
        )
        assert check["checked_nominal_native_source_count"] == 22
        assert check["checked_interval_evaluation_count"] == 25
        assert len(result["time_sensitivity"]["evaluation_witnesses"]["samples"]) == 25
        assert (
            result["time_sensitivity"]["summary"]["continuous_interval_certified"]
            is False
        )
        assert result["ephemeris_source_summary"]["accuracy_certified"] is False
        result.pop("run_metadata")
    assert expected == native == cli


@pytest.mark.parametrize(
    "kind", ["file_bytes", "temporary_path", "slot_edition", "late_file_bytes"]
)
@pytest.mark.native_engine_fault
def test_actual_source_change_has_safe_errors_on_all_three_surfaces(
    tmp_path, monkeypatch, capsys, kind
):
    from scripts.check_human_design_natal_sources import (
        PLAN_PATH,
        isolated_source_change,
    )

    params = json.loads(PLAN_PATH.read_text())["birth_input"]
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    outputs = []
    directory = tmp_path / "rest"
    directory.mkdir()
    with isolated_source_change(kind, directory) as state:
        with TestClient(api.app) as client:
            response = client.post(SPEC.rest_path, json=params)
        assert state["mutation_performed"] and response.status_code == 503
        outputs.append(response.json())

    async def native_call():
        directory = tmp_path / "mcp"
        directory.mkdir()
        with isolated_source_change(kind, directory) as state:
            async with Client(create_mcp_app(families="astro")) as client:
                result = await client.call_tool(
                    "human_design", params, raise_on_error=False
                )
                assert state["mutation_performed"] and result.is_error
                return result.structured_content

    outputs.append(asyncio.run(native_call()))
    directory = tmp_path / "cli"
    directory.mkdir()
    flags = ["human_design"]
    for k, v in params.items():
        flags.extend(["--" + k.replace("_", "-"), str(v)])
    with isolated_source_change(kind, directory) as state:
        assert run(flags) == 1 and state["mutation_performed"]
        outputs.append(json.loads(capsys.readouterr().out))
    for output in outputs:
        assert output["error_code"] == "ephemeris_source_inconsistent"
        assert output["retryable"] is False
        assert output["issues"][0]["code"] in {
            "changed_during",
            "edition_changed",
            "physical_configuration_changed",
        }
        assert str(tmp_path) not in json.dumps(output)
