"""Native local protocols expose the same printed terms and source qualifiers."""

import asyncio

import pytest
from jsonschema import Draft202012Validator

from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_western_accuracy import BIRTH


@pytest.mark.parametrize("key", ["astro_chart", "astro_hellen"])
def test_terms_and_faithful_interpretation_across_real_local_protocols(
    key, rest, tmp_path, capsys
):
    spec = SPECS[key]
    fields = [
        "classical.ptolemy.ruleset_id",
        "classical.ptolemy.planets.Sun",
        "classical.ptolemy.term_policy",
        "classical.ptolemy.term_source_url",
        "classical.ptolemy.term_transcription_note",
        "classical.sect",
        "interpretation.original_text_terms",
        "interpretation_evidence.original_text_terms",
    ]
    query = [("fields", field) for field in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", 0),
    ]
    response = rest.post(spec.rest_path, json=BIRTH, params=query)
    code, local = call_cli(
        spec,
        BIRTH,
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
            spec, BIRTH, fields=fields, strict_fields=True, include_snapshot_text=False
        )
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        assert not result.get("projection_warnings")
        assert "snapshot_text" not in result
        layer = result["classical"]["ptolemy"]
        assert layer["ruleset_id"].endswith("bounded_v4")
        assert set(layer["planets"]["Sun"]["terms"]) == {
            "egyptian",
            "chaldaean",
            "ptolemaic",
        }
        assert (
            "printed" in layer["term_policy"]
            and "Libra" in layer["term_transcription_note"]
        )
        assert (
            result["interpretation_evidence"]["original_text_terms"]["policy_id"]
            == "ptolemy_robbins_printed_terms_v1"
        )
        assert "纸本表" in result["interpretation"]["original_text_terms"]
