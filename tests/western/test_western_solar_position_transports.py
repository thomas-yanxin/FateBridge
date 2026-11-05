"""Nominal-epoch solar model receipts survive actual strict REST/MCP/CLI."""

import asyncio

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import evidence_views
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
)
from tests.evaluation.test_agentic_nested_outputs import rest as rest_fixture
from tests.western.test_western_accuracy import BIRTH

rest = rest_fixture


@pytest.mark.parametrize(
    "key", ["astro_chart", "astro_horary", "astro_hellen", "astro_india"]
)
@pytest.mark.parametrize("published_view", [False, True])
def test_solar_extension_and_physical_error_unknown_are_faithfully_projected(
    key, published_view, rest, tmp_path, capsys
):
    spec = SPECS[key]
    prefix = "horary.calculation_basis" if key == "astro_horary" else "chart_profile"
    if key != "astro_horary":
        inputs = {
            **BIRTH,
            "birth_year": 2022,
            "birth_month": 11,
            "birth_day": 8,
            "birth_hour": 21,
            "birth_minute": 0,
            "birth_timezone": "UTC",
        }
    else:
        inputs = dict(
            question_year=2022,
            question_month=11,
            question_day=8,
            question_hour=21,
            question_minute=0,
            timezone_name="UTC",
            longitude=0,
            latitude=51.5,
            category="career",
        )
    path = prefix + ".apparent_position_policy"
    fields = [
        path + ".bodies.Mercury.position_interpretation",
        path + ".bodies.Mercury.maximum_physical_error_arcseconds",
        path + ".displayed_native_positions_changed",
        path + ".source_model_regularity.axis_continuity_certified",
        path + ".source_model_regularity.unique_rate_at_mass_knots_certified",
    ]
    if published_view:
        fields = evidence_views(spec)["solar_position_model"]["fields"]
    response = rest.post(
        spec.rest_path,
        json=inputs,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", 0),
        ],
    )
    code, cli = call_cli(
        spec,
        inputs,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(
        native(
            spec, inputs, fields=fields, strict_fields=True, include_snapshot_text=False
        )
    )
    assert response.status_code == 200, response.text
    assert code == 0 and not protocol.is_error
    values = [response.json(), cli, protocol.structured_content]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for result in values:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        assert not result.get("projection_warnings")
        basis = (
            result["horary"]["calculation_basis"]
            if key == "astro_horary"
            else result["chart_profile"]
        )
        policy = basis["apparent_position_policy"]
        assert policy["displayed_native_positions_changed"] is False
        assert policy["source_model_regularity"]["axis_continuity_certified"] is False
        assert (
            policy["source_model_regularity"]["unique_rate_at_mass_knots_certified"]
            is False
        )
        mercury = policy["bodies"]["Mercury"]
        assert (
            mercury["position_interpretation"] == "virtual_native_solar_disc_extension"
        )
        assert mercury["maximum_physical_error_arcseconds"] is None
        if not published_view:
            assert set(policy["source_model_regularity"]) == {
                "axis_continuity_certified",
                "unique_rate_at_mass_knots_certified",
            }
            assert set(mercury) == {
                "position_interpretation",
                "maximum_physical_error_arcseconds",
            }
