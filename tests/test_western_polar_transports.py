"""Polar axis branches and their interpretation qualifications on real APIs."""

import asyncio

import pytest
from jsonschema import Draft202012Validator

from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_western_house_reference import separation
from tests.test_western_polar_axes import POLAR_BIRTH


@pytest.mark.parametrize("hsys", [2, 6])
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_polar_house_branch_and_common_mc_across_rest_native_mcp_cli(
    hsys, zodiacal, rest, tmp_path, capsys
):
    spec = SPECS["astro_chart"]
    payload = {**POLAR_BIRTH, "hsys": hsys, "zodiacal": zodiacal}
    fields = [
        "chart_profile.house_axis_convention",
        "angles.midheaven",
        "houses",
        "summary",
        "interpretation_evidence.social_style.source_paths",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", p) for p in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
    )
    code, local = call_cli(
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
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        note = result["chart_profile"]["house_axis_convention"]
        assert result["angles"]["midheaven"]["longitude"] == note["public_midheaven"]
        assert note["note_zh"] in result["summary"]
        assert (
            "chart_profile.house_axis_convention"
            in result["interpretation_evidence"]["social_style"]["source_paths"]
        )
        assert (
            separation(
                result["houses"][9]["cusp_longitude"], note["native_house_midheaven"]
            )
            < 1e-6
        )
        assert not result.get("projection_warnings")


def test_predictive_axis_convention_is_strictly_projectable(rest, tmp_path, capsys):
    spec = SPECS["transit"]
    payload = {
        **POLAR_BIRTH,
        "house_system": "R",
        "analysis_year": 1900,
        "analysis_month": 1,
        "analysis_day": 1,
        "analysis_hour": 0,
        "analysis_minute": 30,
        "return_timezone": "UTC",
        "return_longitude": 0.0,
        "return_latitude": -80.0,
    }
    fields = [
        "natal_reference.calculation_basis.house_axis_convention",
        "transit.calculation_basis.house_axis_convention",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", p) for p in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
    )
    code, local = call_cli(
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
    assert response.status_code == 200 and code == 0 and not protocol.is_error, (
        response.json(),
        local,
        protocol.structured_content,
    )
    assert (
        business(response.json())
        == business(local)
        == business(protocol.structured_content)
    )
    for layer in ["natal_reference", "transit"]:
        note = local[layer]["calculation_basis"]["house_axis_convention"]
        assert note["meridian_branch_separation_degrees"] == pytest.approx(180)


@pytest.mark.parametrize(
    "key,extra",
    [
        ("astro_chart", {"hsys": 3}),
        ("astro_chart", {"hsys": 4}),
        (
            "transit",
            {
                "house_system": "P",
                "analysis_year": 1900,
                "analysis_month": 1,
                "analysis_day": 1,
                "analysis_hour": 0,
                "analysis_minute": 30,
            },
        ),
    ],
)
def test_undefined_polar_house_request_is_not_misreported_as_missing_dependency(
    key, extra, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = {**POLAR_BIRTH, **extra}
    response = rest.post(spec.rest_path, json=payload)
    code, local = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert response.status_code == 400 and code == 1 and protocol.is_error
    for result in [response.json(), local, protocol.structured_content]:
        assert result["error_code"] == "validation_error"
        assert result["retryable"] is False
        assert "依赖缺失" not in result["error"]
