"""Actual consumed solar model policy survives full and projected delivery."""

import asyncio

import pytest

from tests.evaluation.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    inputs,
    native,
)
from tests.evaluation.test_agentic_nested_outputs import rest as _shared_rest

rest = _shared_rest


@pytest.mark.parametrize("key", ["bazi_birth", "dayun_analysis"])
@pytest.mark.parametrize("project", [False, True])
def test_actual_model_components_are_identical_on_three_transports(
    key, project, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = inputs(spec)
    options = dict(as_of=AS_OF, include_snapshot_text=False, response_char_limit=0)
    flags = [
        "--as-of",
        AS_OF,
        "--include-snapshot-text",
        "false",
        "--response-char-limit",
        "0",
    ]
    calendar_path = (
        "bazi_birth.calendar_context" if key == "bazi_birth" else "calendar_context"
    )
    if project:
        fields = [calendar_path + ".current_solar_term.solar_model_details"]
        options.update(fields=fields, strict_fields=True)
        flags += ["--fields", *fields, "--strict-fields", "true"]
    response = rest.post(spec.rest_path, json=payload, params=options)
    mcp = asyncio.run(native(spec, payload, **options))
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    assert response.status_code == 200, response.text
    assert not mcp.is_error and code == 0
    results = [response.json(), mcp.structured_content, cli]
    for result in results:
        assert business(result) == business(results[0])
        spec.output_model.model_validate(result)
        calendar = (
            result["bazi_birth"]["calendar_context"]
            if key == "bazi_birth"
            else result["calendar_context"]
        )
        details = calendar["current_solar_term"]["solar_model_details"]
        policy = details["apparent_direction_model"]
        assert details["accuracy_certified"] is False
        assert policy["physical_accuracy_certified"] is False
        assert policy["solar_gravitational_potential_in_aberration"] is True
        assert policy["finite_distance_light_deflection"] == "not_applied"
        assert policy["tdb"] == "fatebridge_geocentric_erfa_dtdb_v1"
        assert policy["tdb_observer_u_v_km"] == [0, 0]
        assert policy["aberration"] == "ERFA_ab"
        assert policy["precession"] == "IAU2006_P03"
        assert policy["nutation"] == "IAU2000B"
