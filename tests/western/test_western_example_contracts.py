"""Fictional Western examples are complete, detached and publicly callable."""

import asyncio
import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastmcp import Client
from jsonschema import validate

from fatebridge.application.description import describe_input_spec, spec_is_cli_safe
from fatebridge.application.examples import example_input
from fatebridge.cli import run as cli_run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.evaluation.test_agentic_nested_outputs import rest
from tests.fixtures.mcp_result_delivery import first_page_uri

KEYS = [
    "astro_chart",
    "astro_chart13",
    "astro_hellen",
    "astro_germany",
    "astro_relative",
    "astro_relative_chart",
    "western_timing_analysis",
    "solarreturn",
    "lunarreturn",
    "transit",
    "solararc",
    "givenyear",
    "profection",
    "pd",
    "pdchart",
    "zr",
    "firdaria",
    "decennials",
    "astro_harmonic",
    "astro_planetary_ages",
    "astro_triplicity_rulers",
    "astro_lunation_phase",
    "astro_distributions",
    "astro_balbillus",
    "astro_keypoints",
    "astro_yearsystem129",
    "astro_planetaryarc",
    "astro_persiandirected",
    "astro_agepoint",
    "astro_vedicprog",
    "astro_jaynesprog",
    "astro_mundane",
    "astro_extrareturns",
    "astro_horary",
    "astro_election",
]
SPECS = {s.key: s for s in CATALOG}
AS_OF = "2026-10-12T12:00:00+08:00"


@pytest.mark.parametrize("key", KEYS)
def test_example_has_explicit_fixture_context_but_does_not_supply_user_defaults(key):
    spec = SPECS[key]
    record = describe_input_spec(spec)
    assert record["example_input"]
    assert record["example_context"] == {
        "fictional": True,
        "purpose": "schema_and_transport_demo",
        "use_as_user_default": False,
    }
    validate(record["example_input"], record["input_schema"])
    with pytest.raises(ValueError):
        spec.request_model.model_validate({})
    with pytest.raises(ValueError):
        spec.request_model.model_validate(
            {**record["example_input"], "example_context": record["example_context"]}
        )


@pytest.mark.parametrize(
    "key,nested", [("astro_relative", "inner"), ("fengshui_assess", "house")]
)
def test_client_nested_mutations_cannot_poison_later_discovery(
    key, nested, monkeypatch
):
    import fatebridge.application.examples as examples

    isolated_registry = copy.deepcopy(examples._examples())
    monkeypatch.setattr(examples, "_examples", lambda: isolated_registry)
    first = example_input(SPECS[key])
    expected = copy.deepcopy(first)
    first[nested]["_fictional_probe_unknown"] = True
    assert example_input(SPECS[key]) == expected
    assert (
        "_fictional_probe_unknown"
        not in describe_input_spec(SPECS[key])["example_input"][nested]
    )
    with pytest.raises(ValueError):
        SPECS[key].request_model.model_validate(first)


def test_missing_unrelated_examples_are_not_filled_with_a_generic_person():
    undeclared = replace(SPECS["astro_chart"], key="_unregistered_example_probe")
    assert example_input(undeclared) is None
    assert "example_context" not in describe_input_spec(undeclared)


def assert_original_facts(actual, original):
    if isinstance(actual, dict):
        for key, value in actual.items():
            if key in {"run_metadata", "result_delivery"}:
                continue
            assert key in original, key
            assert_original_facts(value, original[key])
    elif isinstance(actual, list):
        assert len(actual) == len(original)
        for value, expected in zip(actual, original):
            assert_original_facts(value, expected)
    else:
        assert actual == original


def assert_requested_path(value, field):
    current = value
    for key in field.split("."):
        assert isinstance(current, dict) and key in current, field
        current = current[key]


async def read_complete(client, result):
    value = result.structured_content
    if "result_delivery" not in value:
        return value
    reference = value["result_delivery"]
    uri = await first_page_uri(client, reference)
    pieces = []
    while uri:
        page = json.loads((await client.read_resource(uri))[0].text)
        pieces.append(page["text"])
        uri = page["next_uri"]
    raw = "".join(pieces)
    assert hashlib.sha256(raw.encode()).hexdigest() == reference["sha256"]
    complete = json.loads(raw)
    assert complete["run_metadata"]["run_id"] == value["run_metadata"]["run_id"]
    return complete


@pytest.mark.parametrize(
    "changed", ["result_id", "sha256", "first_page_uri", "total_chars"]
)
def test_compact_readback_rejects_a_different_result_or_document(changed):
    from types import SimpleNamespace

    reference = {
        "result_id": "fixture-result",
        "sha256": "a" * 64,
        "total_chars": 2,
        "manifest_uri": "fatebridge://results/fixture-result",
        "compact_reference": True,
    }
    manifest = {
        "result_id": reference["result_id"],
        "sha256": reference["sha256"],
        "total_chars": 2,
        "first_page_uri": "fatebridge://results/fixture-result/pages/0",
    }
    manifest[changed] = {
        "result_id": "different",
        "sha256": "b" * 64,
        "first_page_uri": "fatebridge://results/different/pages/0",
        "total_chars": 3,
    }[changed]

    class Client:
        async def read_resource(self, uri):
            assert uri == reference["manifest_uri"]
            return [SimpleNamespace(text=json.dumps(manifest))]

    with pytest.raises(AssertionError):
        asyncio.run(first_page_uri(Client(), reference))


@pytest.mark.parametrize("key", KEYS)
def test_public_descriptor_drives_each_available_adapter_without_private_input_defaults(
    key, rest, tmp_path, capsys
):
    spec = SPECS[key]

    async def public_call():
        async with Client(create_mcp_app()) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            if spec.mcp_name:
                record = json.loads(
                    (
                        await client.read_resource(
                            f"fatebridge://tools/{spec.tool_name}/input"
                        )
                    )[0].text
                )["tools"][0]
            else:
                described = rest.get("/api/tools").json()
                record = next(item for item in described["tools"] if item["key"] == key)
            assert record["example_context"]["fictional"] is True
            assert record["example_context"]["use_as_user_default"] is False
            data = record["example_input"]
            fields = record.get("suggested_fields")
            values = []
            if spec.mcp_name:
                assert spec.tool_name in tools
                params = {
                    **data,
                    "as_of": AS_OF,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                }
                validate(params, tools[spec.tool_name].input_schema)
                result = await client.call_tool(
                    spec.tool_name, params, raise_on_error=False
                )
                assert not result.is_error
                values.append(("mcp", await read_complete(client, result)))
            return record, values

    record, values = asyncio.run(public_call())
    data = record["example_input"]
    fields = record.get("suggested_fields")
    if spec.rest_path:
        params = {
            "as_of": AS_OF,
            "strict_fields": "true",
            "include_snapshot_text": "false",
            "response_char_limit": 0,
        }
        if fields is not None:
            params["fields"] = fields
        response = rest.post(spec.rest_path, json=data, params=params)
        assert response.status_code == 200
        values.append(("rest", response.json()))
    if spec_is_cli_safe(spec):
        assert cli_run(["describe", spec.tool_name]) == 0
        description = json.loads(capsys.readouterr().out)
        assert description["example_input"] == data
        assert description["example_context"] == record["example_context"]
        flags = ["--include-snapshot-text", "false", "--response-char-limit", "0"]
        if fields is not None:
            flags += ["--fields", *fields, "--strict-fields", "true"]
        subject = tmp_path / "published-example.json"
        subject.write_text(json.dumps(data))
        code = cli_run(
            [spec.tool_name, "--subject-file", str(subject), "--as-of", AS_OF, *flags]
        )
        value = json.loads(capsys.readouterr().out)
        assert code == 0
        values.append(("cli", value))
    assert values
    for surface, value in values:
        assert "error" not in value
        if fields:
            for field in fields:
                assert_requested_path(value, field)
        (tmp_path / f"{key}-{surface}.json").write_text(json.dumps(value))
    for _, value in values[1:]:
        assert_original_facts(value, values[0][1])
