"""A restored real event window and nullable diagnostics through all protocols."""

import asyncio

from jsonschema import Draft202012Validator

from fatebridge.application.examples import evidence_views
from tests.ephemeris_case_runtime import native_ephemeris_files
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_western_horary import QUESTION


def test_restored_swiss_history_and_v5_receipts_survive_strict_three_protocols(
    rest, tmp_path, capsys, native_ephemeris_files
):
    spec = SPECS["astro_horary"]
    inputs = {**QUESTION, "category": "career"}
    fields = evidence_views(spec)["reference_points"]["fields"]
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
    results = [response.json(), cli, protocol.structured_content]
    assert business(results[0]) == business(results[1]) == business(results[2])
    for value in results:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(value)
        assert not value.get("projection_warnings")
        h = value["horary"]
        history = h["perfection"]["event_history"]
        assert h["calculation_basis"]["ephemeris_model"] == "swieph"
        assert history["status"] == "computed"
        assert history["unavailable_reason"] is None
        assert history["unavailable_code"] is None and history["failed_sample"] is None
        policies = history["longitude_motion"]["complete_position_derivatives"]
        assert {
            f"{planet}:tropical" for planet in ("Sun", "Mercury", "Venus", "Mars")
        } <= policies.keys()
        for policy in policies.values():
            assert policy["method_id"] == "fatebridge_complete_position_derivative_v8"
            assert policy["convergence_line_arcsec_per_day"] == 0.0002
            if policy["directional_checks"]:
                assert policy["directional_checks"][-1]["passed"]
        assert h["verdict"] == "uncertain" and h["perfection"]["perfects"] is None
