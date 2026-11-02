"""Actual local transports retain instantaneous motion evidence and its limits."""

import asyncio

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import evidence_views
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_western_accuracy import BIRTH
from tests.test_western_angular_predicates import reference_phase


@pytest.mark.parametrize(
    "key",
    ["astro_chart", "astro_chart13", "astro_hellen", "astro_india", "astro_germany"],
)
def test_published_motion_card_reads_conditions_with_instantaneous_evidence(key, rest):
    spec = SPECS[key]
    card = evidence_views(spec)["aspect_motion"]
    response = rest.post(
        spec.rest_path,
        json=BIRTH,
        params=[("fields", p) for p in card["fields"]]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", 0),
        ],
    )
    assert response.status_code == 200
    payload = response.json()
    assert not payload.get("projection_warnings")
    result = payload["base_chart"] if key == "astro_germany" else payload
    assert result["classical_patterns"]["aspect_motion"]
    assert (
        result["classical_patterns"]["application_policy"]["rule_id"]
        == "instantaneous_longitude_phase_v1"
    )
    assert "no future perfection" in card["purpose"].lower()


@pytest.mark.parametrize("key", ["astro_chart", "astro_hellen", "astro_india"])
@pytest.mark.parametrize("project", [False, True])
def test_motion_facts_and_limits_agree_across_rest_native_mcp_and_cli(
    key, project, rest, tmp_path, capsys
):
    spec = SPECS[key]
    fields = [
        "classical_patterns.aspect_motion",
        "classical_patterns.application_policy",
    ]
    query = [("response_char_limit", 0)]
    flags = ["--response-char-limit", "0"]
    protocol_flags = {}
    if project:
        query += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        protocol_flags = {
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        }
    response = rest.post(spec.rest_path, json=BIRTH, params=query)
    code, local = call_cli(spec, BIRTH, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(native(spec, BIRTH, **protocol_flags))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        assert not result.get("projection_warnings")
        patterns = result["classical_patterns"]
        assert (
            patterns["application_policy"]["rule_id"]
            == "instantaneous_longitude_phase_v1"
        )
        assert "not_future_perfection" in patterns["application_policy"]["scope"]
        assert patterns["aspect_motion"]
        if project:
            assert "snapshot_text" not in result
            continue
        planets = {p["id"]: p for p in result["planets"]}
        for row in patterns["aspect_motion"]:
            # Only relative speed is needed by the independent gap derivative.
            expected = reference_phase(
                planets[row["planet_a"]]["longitude"],
                0.0,
                planets[row["planet_b"]]["longitude"],
                row["relative_longitude_speed"],
                row["exact_angle"],
            )
            assert row["phase"] == expected
        assert "未检验未来成相及完整原典条件" in result["snapshot_text"]
