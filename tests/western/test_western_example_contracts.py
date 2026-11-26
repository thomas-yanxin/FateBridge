"""Fictional Western examples are complete, detached and publicly callable."""

import asyncio
import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastmcp import Client
from jsonschema import validate

from fatebridge.application.description import describe_input_spec
from fatebridge.application.examples import example_input
from fatebridge.cli import run as cli_run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.support.transports import call_calculation, describe_capability

KEYS = [
    "astrology_chart",
    "thirteen_sector_chart",
    "hellenistic_chart",
    "hamburg_midpoint_chart",
    "relationship_chart",
    "western_timing",
    "solar_return",
    "lunar_return",
    "transit_chart",
    "solar_arc",
    "chart_for_year",
    "profection",
    "primary_directions",
    "primary_directions_chart",
    "zodiacal_releasing",
    "firdaria",
    "decennials",
    "harmonic_chart",
    "planetary_ages",
    "triplicity_ruler_periods",
    "lunar_phase_progressions",
    "bounds_directions",
    "balbillus_periods",
    "numeric_aspect_periods",
    "planetary_periods_129_years",
    "planetary_arc_directions",
    "persian_directions",
    "age_point",
    "sidereal_progressions",
    "declination_progressions",
    "mundane_ingress_chart",
    "planetary_returns",
    "horary_chart",
    "evaluate_election_time",
]
SPECS = {s.name: s for s in CATALOG}
AS_OF = "2026-10-12T12:00:00+08:00"
# Pruned prose/policy paths still referenced by shared data/agent_examples.json until Wave 3 refreshes it.
_PRUNED_SUGGESTED_FIELDS = frozenset(
    {
        "summary",
        "midpoint_analysis.reading_guide",
        "midpoint_analysis.limitations",
        "midpoint_analysis.original_text_conformance",
        "midpoint_analysis.interpretations",
        "midpoint_analysis.time_sensitivity.status",
        "midpoint_analysis.time_sensitivity.uncertainty_minutes",
        "election.solar_condition_policy",
        "election.condition_policy",
    }
)


def _active_suggested_fields(record: dict) -> list[str] | None:
    fields = record.get("suggested_fields")
    if fields is None:
        return None
    return [f for f in fields if f not in _PRUNED_SUGGESTED_FIELDS]


@pytest.mark.parametrize("key", KEYS)
def test_example_has_explicit_fixture_context_but_does_not_supply_user_defaults(
    key,
) -> None:
    spec = SPECS[key]
    record = describe_input_spec(spec)
    assert record["example_input"]
    assert "example_context" not in record
    validate(record["example_input"], record["input_schema"])
    with pytest.raises(ValueError):
        spec.request_model.model_validate({})
    with pytest.raises(ValueError):
        spec.request_model.model_validate(
            {**record["example_input"], "example_context": {"fictional": True}}
        )


def test_client_nested_mutations_cannot_poison_later_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fatebridge.application.examples as examples

    key, nested = "fengshui_assess", "house"
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


def test_missing_unrelated_examples_are_not_filled_with_a_generic_person() -> None:
    undeclared = replace(SPECS["astrology_chart"], name="_unregistered_example_probe")
    assert example_input(undeclared) is None
    assert "example_context" not in describe_input_spec(undeclared)


def assert_original_facts(actual, original):
    if isinstance(actual, dict):
        for key, value in actual.items():
            if key == "run_metadata":
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


@pytest.mark.parametrize("key", KEYS)
def test_public_descriptor_drives_each_available_adapter_without_private_input_defaults(
    key, rest, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = SPECS[key]

    async def public_call():
        async with Client(create_mcp_app()) as client:
            if spec.expose_mcp:
                record = await describe_capability(client, spec.name)
            else:
                described = rest.get(
                    "/api/tools", params={"tool": spec.name, "detail": "full"}
                ).json()
                record = next(
                    item for item in described["tools"] if item["tool"] == key
                )
            assert record["example_input"]
            data = record["example_input"]
            fields = _active_suggested_fields(record)
            values = []
            if spec.expose_mcp:
                validate(data, record["input_schema"])
                params = {
                    "tool": spec.name,
                    "arguments": data,
                    "detail": "audit",
                    "as_of": AS_OF,
                    **({"fields": fields} if fields is not None else {}),
                }
                result = await call_calculation(
                    client,
                    spec.name,
                    {
                        **data,
                        "as_of": AS_OF,
                        "detail": "audit",
                        **({"fields": fields} if fields is not None else {}),
                    },
                    raise_on_error=False,
                )
                assert not result.is_error, params
                values.append(("mcp", result.structured_content))
            return record, values

    record, values = asyncio.run(public_call())
    data = record["example_input"]
    fields = _active_suggested_fields(record)
    if spec.rest_path:
        params: dict[str, object] = {"as_of": AS_OF, "detail": "audit"}
        if fields is not None:
            params["fields"] = fields
        response = rest.post(spec.rest_path, json=data, params=params)
        assert response.status_code == 200
        values.append(("rest", response.json()))
    assert cli_run(["discover", "--tool", spec.name, "--detail", "full"]) == 0
    description = json.loads(capsys.readouterr().out)["tools"][0]
    assert description["example_input"] == data
    assert "example_context" not in description
    flags = ["--detail", "audit"]
    if fields is not None:
        flags += ["--fields", *fields]
    subject = tmp_path / "published-example.json"
    subject.write_text(json.dumps(data))
    code = cli_run(
        [spec.name, "--request-file", str(subject), "--as-of", AS_OF, *flags]
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
        else:
            pass
        (tmp_path / f"{key}-{surface}.json").write_text(json.dumps(value))
    for _, value in values[1:]:
        assert_original_facts(value, values[0][1])
