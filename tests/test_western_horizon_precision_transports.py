"""Actual local REST/native MCP/CLI projection of a repaired grazing chart."""

import asyncio
import json

import pytest
from jsonschema import Draft202012Validator

from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_western_horizon_precision import EXPECTED, PUBLIC, separation


@pytest.mark.parametrize("hsys", [0, 2, 6])
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_precision_receipt_and_coordinates_survive_all_local_surfaces(
    hsys, zodiacal, rest, tmp_path, capsys
):
    case = PUBLIC[0]
    spec = SPECS["astro_chart"]
    payload = dict(
        birth_year=case["year"],
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=30,
        birth_timezone="UTC",
        birth_longitude=case["longitude"],
        birth_latitude=case["latitude"],
        hsys=hsys,
        zodiacal=zodiacal,
    )
    fields = [
        "chart_profile.house_axis_convention.eastern_direction_precision",
        "angles",
        "houses",
        "summary",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", path) for path in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
    )
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), cli, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        p = result["chart_profile"]["house_axis_convention"][
            "eastern_direction_precision"
        ]
        assert p["delivered_ascendant"] == result["angles"]["ascendant"]["longitude"]
        assert p["delivered_cusps"] == [h["cusp_longitude"] for h in result["houses"]]
        assert p["ascendant_action"] == "antipodal_endpoint"
        assert not result.get("projection_warnings")
        if zodiacal == 0:
            assert (
                separation(p["delivered_ascendant"], EXPECTED[case["id"]]["ascendant"])
                <= 1
            )


def test_unresolved_endpoint_rejects_even_an_unrelated_projection_on_all_surfaces(
    monkeypatch, rest, tmp_path, capsys
):
    from fatebridge.core.astro import house_axes

    def unresolved(*args, **kwargs):
        raise ArithmeticError("injected unresolved endpoint")

    monkeypatch.setattr(house_axes, "horizon_geometry", unresolved)
    case = PUBLIC[0]
    spec = SPECS["astro_chart"]
    payload = dict(
        birth_year=case["year"],
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=30,
        birth_timezone="UTC",
        birth_longitude=case["longitude"],
        birth_latitude=case["latitude"],
        hsys=0,
    )
    flags = dict(
        fields=["person_info.name"], strict_fields=True, include_snapshot_text=False
    )
    http = rest.post(
        spec.rest_path,
        json=payload,
        params=[
            ("fields", "person_info.name"),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ],
    )
    protocol = asyncio.run(native(spec, payload, **flags))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            "person_info.name",
            "--strict-fields",
            "--no-include-snapshot-text",
        ],
    )
    assert http.status_code == 503 and protocol.is_error and code == 1
    for value in [http.json(), json.loads(protocol.content[0].text), cli]:
        assert value["error_code"] == "ephemeris_source_inconsistent"
        assert value["retryable"] is False
        assert value["issues"] == [
            {
                "path": "runtime.ephemeris_data",
                "code": "horizon_direction_precision_unavailable",
            }
        ]
        assert "person_info" not in value and "angles" not in value
