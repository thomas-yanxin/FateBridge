"""Real calculations and native protocol validation retain source context/unknowns."""

import asyncio
import json

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import evidence_views
from fatebridge.cli import run
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_western_horary import QUESTION


@pytest.mark.parametrize("extension", [False, True])
def test_radicality_card_and_leaf_context_on_rest_native_mcp_and_cli(
    extension, rest, tmp_path, capsys
):
    spec = SPECS["astro_horary"]
    context = {
        "figure_origin": "timed_event" if extension else "propounded_question",
        "event_time_certain_reported": True,
        "age_degree_agreement_reported": False,
        "principal_significators_very_strong_reported": False,
    }
    payload = {
        **QUESTION,
        "zodiac_type": "Sidereal" if extension else "Tropic",
        "house_system": "whole_sign" if extension else "R",
        "radicality_context": context,
    }
    fields = list(evidence_views(spec)["lilly_radicality"]["fields"]) + [
        "horary.radicality.clause_count",
        "horary.radicality.real_world_prediction_established",
        "horary.radicality.source_method_scope",
        "horary.rule_profile.radicality_policy",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", 0),
        ],
    )
    request_file = tmp_path / "horary.json"
    request_file.write_text(
        json.dumps({k: v for k, v in payload.items() if k != "radicality_context"})
    )
    # Exercise the public JSON object argument as well as --request-file.
    code = run(
        [
            spec.tool_name,
            "--request-file",
            str(request_file),
            "--radicality-context",
            json.dumps(context),
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    protocol = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert response.status_code == 200, response.text
    assert code == 0 and not protocol.is_error
    assert json.loads(protocol.content[0].text) == protocol.structured_content
    results = [response.json(), cli, protocol.structured_content]
    assert business(results[0]) == business(results[1]) == business(results[2])
    for value in results:
        spec.output_model.model_validate(value)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(value)
        assert not value.get("projection_warnings")
        h = value["horary"]
        r = h["radicality"]
        assert h["verdict"] == "uncertain" and r["safe_to_judge"] is None
        assert len(r["clauses"]) == r["clause_count"] == 12
        assert r["full_original_text_acceptance"] is False
        assert r["full_judgement_accepted"] is False
        assert r["real_world_prediction_established"] is False
        assert r["source_method_scope"] == (
            "other_or_unknown_chart_method_modern_extension"
            if extension
            else "tropical_regiomontanus_declared_review"
        )
        assert r["hour_inputs"]["status"] == "computed"
        assert r["hour_inputs"]["actual_solar_backend_verified"] is False
        assert r["reported_context"]["provided_fields"] == sorted(context)
        assert r["reported_context"]["very_young_querent_reported"] is None
        assert r["ascendant_degree_gate"]["certain_timed_event_exception"] is extension
        assert value["analysis_context"]["radicality_context"] == r["reported_context"]
        assert "C03" in r["unknown_clauses"] and "C11" in r["unknown_clauses"]
        for key, expected in context.items():
            assert r["reported_context"][key] == expected


@pytest.mark.parametrize(
    "context",
    [
        {"event_time_certain_reported": "true"},
        {"event_time_certain_reported": 1},
        {"safe_to_judge": True},
        {"figure_origin": "known_clock"},
    ],
)
def test_context_faults_fail_before_calculation_on_all_protocols(
    context, rest, tmp_path, capsys
):
    spec = SPECS["astro_horary"]
    payload = {**QUESTION, "radicality_context": context}
    http = rest.post(spec.rest_path, json=payload)
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert http.status_code == 422 and code != 0 and protocol.is_error
    assert "horary" not in cli
