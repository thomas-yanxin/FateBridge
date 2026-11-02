"""Rotation provenance and precision limits survive strict public projections."""

import asyncio

import pytest
from jsonschema import Draft202012Validator

from fatebridge.core.astro_models import POLICY_ID
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_western_accuracy import BIRTH


@pytest.mark.parametrize(
    "year,expected",
    [
        (2099, "IERS2010_expression_Swiss_nutation"),
        (2300, "Swiss_longterm_with_boundary_phase_alignment"),
    ],
)
def test_epoch_policy_and_limits_on_real_rest_mcp_cli(
    year, expected, rest, tmp_path, capsys
):
    spec = SPECS["astro_chart"]
    payload = {**BIRTH, "birth_year": year}
    prefix = "chart_profile.earth_rotation"
    fields = [
        prefix + ".policy_id",
        prefix + ".sidereal_time_model",
        prefix + ".longterm_phase_alignment",
        prefix + ".measured_eop_applied",
        prefix + ".precision_scope",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
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
        policy = result["chart_profile"]["earth_rotation"]
        assert policy["policy_id"] == POLICY_ID
        assert policy["sidereal_time_model"] == expected
        assert policy["measured_eop_applied"] is False
        if year == 2300:
            assert (
                policy["longterm_phase_alignment"]["absolute_accuracy_certified"]
                is False
            )
            assert (
                policy["longterm_phase_alignment"]["derivative_continuity_certified"]
                is False
            )
        else:
            assert policy["longterm_phase_alignment"] is None
        assert not result.get("projection_warnings")
