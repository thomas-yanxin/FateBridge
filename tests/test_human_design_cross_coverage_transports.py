"""Expanded source names and conflicts agree across the three real protocols."""

import asyncio
import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
from fatebridge.application.examples import evidence_views
from fatebridge.cli import run
from fatebridge.core.astro import runtime
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

SPEC = next(s for s in CATALOG if s.key == "human_design")
INPUT = dict(
    birth_year=1980,
    birth_month=5,
    birth_day=31,
    birth_hour=15,
    birth_minute=0,
    birth_timezone="Europe/London",
)


@pytest.mark.parametrize("empty_files", [False, True])
def test_expanded_source_and_complete_reading_match_actual_three_surfaces(
    monkeypatch, tmp_path, capsys, empty_files
):
    if empty_files:
        monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
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
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)

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
                    "fields": evidence_views(SPEC)["cross_sources"]["fields"],
                    "strict_fields": True,
                    "response_char_limit": 8192,
                    "include_snapshot_text": False,
                },
            )
            assert not card.is_error
            assert card.structured_content["incarnation_cross"]["gates"] == [
                16,
                9,
                63,
                64,
            ]
            assert (
                card.structured_content["source_consistency"][
                    "expanded_cross_name_comparison"
                ]
                == expected["source_consistency"]["expanded_cross_name_comparison"]
            )
            assert (
                card.structured_content["interpretation"]["expanded_cross_name_meaning"]
                == expected["interpretation"]["expanded_cross_name_meaning"]
            )
            if "result_delivery" in card.structured_content:
                # The published delivery contract can defer only runtime
                # metadata while every requested business fact stays inline.
                reference = card.structured_content["result_delivery"]
                assert reference["deferred_fields"] == ["run_metadata.runtime"]
                parts = []
                offset = 0

                def forbidden(*args, **kwargs):
                    raise AssertionError("Metadata paging recalculated the sky")

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
                    == reference["sha256"]
                    == page["sha256"]
                )
                restored = json.loads(text)
                assert (
                    restored["run_metadata"]["run_id"]
                    == card.structured_content["run_metadata"]["run_id"]
                )
                assert {k: v for k, v in restored.items() if k != "run_metadata"} == {
                    k: v
                    for k, v in card.structured_content.items()
                    if k not in {"run_metadata", "result_delivery"}
                }
            assert len(card.content[0].text) <= 8192
            return result.structured_content

    native = asyncio.run(call())
    flags = ["human_design"]
    for key, value in INPUT.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run(flags) == 0
    cli = json.loads(capsys.readouterr().out)
    for result in (expected, native, cli):
        check = verify_human_design_reading(result)
        assert check["status"] == "verified_fixed_template_reading", check
        assert check["checked_expanded_cross_observation_count"] == 1
        assert (
            result["source_consistency"]["expanded_cross_name_comparison"][
                "course_list_disagreement"
            ]["resolved"]
            is False
        )
        result.pop("run_metadata")
    assert expected == native == cli
