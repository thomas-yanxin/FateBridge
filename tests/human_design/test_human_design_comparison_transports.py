"""Native node witnesses and explanations survive projection and real paging."""

import asyncio
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
from tests.fixtures.mcp_receipt import verified_inline_business

SPEC = next(s for s in CATALOG if s.key == "human_design")
INPUT = dict(
    birth_year=1990,
    birth_month=4,
    birth_day=6,
    birth_hour=9,
    birth_minute=33,
    birth_timezone="Asia/Shanghai",
)


@pytest.mark.parametrize("node_mode", ["true", "mean"])
@pytest.mark.parametrize("empty", [False, True])
def test_nodes_card_and_full_three_surface_readings_match_with_lossless_paging(
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
                assert len(text) == reference["total_chars"]
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
                    "fields": evidence_views(SPEC)["nodes"]["fields"],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 8192,
                },
            )
            assert not card.is_error
            assert len(card.content[0].text) <= 8192
            assert json.loads(card.content[0].text) == card.structured_content
            assert (
                card.structured_content["interpretation"]["node_comparison_meaning"]
                == expected["interpretation"]["node_comparison_meaning"]
            )
            assert (
                card.structured_content["node_backend_comparison"]["rows"]
                == expected["node_backend_comparison"]["rows"]
            )
            assert (
                card.structured_content["node_convention_comparison"][
                    "reference_node_positions"
                ]
                == expected["node_convention_comparison"]["reference_node_positions"]
            )
            assert (
                card.structured_content["node_convention_comparison"][
                    "changed_activations"
                ]
                == expected["node_convention_comparison"]["changed_activations"]
            )
            if "result_delivery" in card.structured_content:
                await verified_inline_business(client, card.structured_content)
                original_card = await restore(card.structured_content)
                for key in (
                    "node_convention_comparison",
                    "node_backend_comparison",
                    "interpretation",
                    "validation",
                ):
                    assert original_card[key] == card.structured_content[key]
                assert (
                    original_card["run_metadata"]["runtime"]
                    == expected["run_metadata"]["runtime"]
                )
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
        check = verify_human_design_reading(result)
        assert check["status"] == "verified_fixed_template_reading", check
        assert (
            check["checked_node_report_count"] == 2
            and check["checked_statement_count"] == 10
        )
        assert "reference_node_positions" in result["node_convention_comparison"]
        result.pop("run_metadata")
    assert expected == native == cli
