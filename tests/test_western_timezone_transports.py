"""Unconfirmed civil zones fail before any western chart is delivered."""

import asyncio
import json

import pytest

from fatebridge.core.requests.birth import AstroBirthRequest
from fatebridge.services.tool_catalog import CATALOG
from tests.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    inputs,
    native,
    rest,
)

# Negative input checks only for the older lifespan-family routes: no natal
# interpretation, duration or individual judgement is requested or delivered.
KEYS = [
    s.key
    for s in CATALOG
    if issubclass(s.request_model, AstroBirthRequest)
    and s.key not in {"astro_guolao", "astro_india", "astro_vimshottari"}
]


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("zone_input", ["omitted", "null", "empty"])
def test_unresolved_western_civil_zone_is_an_error_on_all_adapters(
    key, zone_input, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = inputs(spec)
    payload.pop("birth_timezone", None)
    payload["birth_place"] = "虚构的未知出生地"
    if zone_input != "omitted":
        payload["birth_timezone"] = None if zone_input == "null" else ""
    http = rest.post(spec.rest_path, json=payload, params={"fields": "analysis_type"})
    code, cli = call_cli(spec, payload, tmp_path, capsys, ["--fields", "analysis_type"])
    protocol = asyncio.run(native(spec, payload, fields=["analysis_type"]))
    assert http.status_code == 400 and code == 1 and protocol.is_error
    protocol_error = json.loads(protocol.content[0].text)
    assert cli["status_code"] == protocol_error["status_code"] == 400
    assert protocol_error["operation"] == spec.operation_label_zh
    # HTTP carries status in the response; MCP adds the catalogue operation.
    # Supply only those declared carrier fields; compare every returned field.
    values = [
        {
            "status_code": http.status_code,
            "operation": spec.operation_label_zh,
            **http.json(),
        },
        {"operation": spec.operation_label_zh, **cli},
        protocol_error,
    ]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for result in values:
        assert result["error_code"] == "validation_error"
        assert "birth_timezone" in result["error"]


@pytest.mark.parametrize("party", ["inner", "outer"])
@pytest.mark.parametrize("zone_input", ["omitted", "null", "empty"])
def test_relative_clock_requires_each_partys_zone_on_all_adapters(
    party, zone_input, rest, tmp_path, capsys
):
    spec = SPECS["astro_relative_chart"]
    payload = inputs(spec)
    payload.pop(f"{party}_birth_timezone", None)
    payload[f"{party}_birth_place"] = "虚构的未知出生地"
    if zone_input != "omitted":
        payload[f"{party}_birth_timezone"] = None if zone_input == "null" else ""
    nested = {}
    for role in ["inner", "outer"]:
        prefix = role + "_"
        nested[role] = {
            k.removeprefix(prefix): v
            for k, v in payload.items()
            if k.startswith(prefix)
        }
    http = rest.post(
        SPECS["astro_relative"].rest_path,
        json=nested,
        params={"fields": "analysis_type"},
    )
    code, cli = call_cli(spec, payload, tmp_path, capsys, ["--fields", "analysis_type"])
    protocol = asyncio.run(native(spec, payload, fields=["analysis_type"]))
    assert http.status_code == 400 and code == 1 and protocol.is_error
    protocol_error = json.loads(protocol.content[0].text)
    assert cli["status_code"] == protocol_error["status_code"] == 400
    assert protocol_error["operation"] == spec.operation_label_zh
    # HTTP carries status in the response; MCP adds the catalogue operation.
    # Supply only those declared carrier fields; compare every returned field.
    values = [
        {
            "status_code": http.status_code,
            "operation": spec.operation_label_zh,
            **http.json(),
        },
        {"operation": spec.operation_label_zh, **cli},
        protocol_error,
    ]
    assert business(values[0]) == business(values[1]) == business(values[2])
    assert "birth_timezone" in values[0]["error"]


@pytest.mark.parametrize(
    "key", ["astro_chart", "astro_hellen", "astro_chart13", "astro_germany"]
)
@pytest.mark.parametrize("inferred", [False, True])
def test_confirmed_or_resolved_zone_has_readable_provenance(
    key, inferred, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = inputs(spec)
    payload["birth_place"] = "北京"
    if inferred:
        payload.pop("birth_timezone", None)
    else:
        payload["birth_timezone"] = "Asia/Shanghai"
    path = "base_chart.person_info" if key == "astro_germany" else "person_info"
    fields = [path]
    http = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", path), ("strict_fields", "true")],
    )
    code, cli = call_cli(
        spec, payload, tmp_path, capsys, ["--fields", path, "--strict-fields", "true"]
    )
    protocol = asyncio.run(native(spec, payload, fields=fields, strict_fields=True))
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    values = [http.json(), cli, json.loads(protocol.content[0].text)]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for value in values:
        spec.output_model.model_validate(value)
        person = (
            value["base_chart"]["person_info"]
            if key == "astro_germany"
            else value["person_info"]
        )
        assert person["birth_timezone"] == "Asia/Shanghai"
        assert person["timezone_source"] == (
            "birth_place" if inferred else "birth_timezone"
        )
