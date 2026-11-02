"""Real local protocols keep calendar provenance and the same physical instant."""

import asyncio

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import evidence_views
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_western_election import CANDIDATE
from tests.test_western_horary import QUESTION


@pytest.mark.parametrize(
    "tool,prefix,body,inputs",
    [
        ("astro_horary", "question_", "horary", QUESTION),
        ("astro_election", "candidate_", "election", CANDIDATE),
    ],
)
def test_julian_and_gregorian_same_instant_on_rest_native_mcp_cli(
    tool, prefix, body, inputs, rest, tmp_path, capsys
):
    spec = SPECS[tool]
    original = {
        **inputs,
        prefix + "year": 2024,
        prefix + "month": 6,
        prefix + "day": 1,
        prefix + "hour": 14,
        prefix + "minute": 30,
    }
    julian = {
        **original,
        prefix + "month": 5,
        prefix + "day": 19,
        prefix + "calendar": "julian",
    }
    fields = list(evidence_views(spec)["calendar_input"]["fields"]) + (
        [
            "horary.ascendant.longitude",
            "horary.planets.Sun.longitude",
            "horary.moon.sign",
            "horary.verdict",
        ]
        if tool == "astro_horary"
        else [
            "election.axes",
            "election.moon.longitude",
            "election.score",
            "election.verdict",
        ]
    )
    params = [("fields", f) for f in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", 0),
    ]
    reference = rest.post(spec.rest_path, json=original, params=params)
    http = rest.post(spec.rest_path, json=julian, params=params)
    code, cli = call_cli(
        spec,
        julian,
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
            spec, julian, fields=fields, strict_fields=True, include_snapshot_text=False
        )
    )
    assert reference.status_code == http.status_code == 200, http.text
    assert code == 0 and not protocol.is_error
    results = [http.json(), cli, protocol.structured_content]
    assert business(results[0]) == business(results[1]) == business(results[2])
    assert reference.json()[body] == results[0][body]
    assert {
        k: v
        for k, v in reference.json()["analysis_context"].items()
        if k not in {"input_calendar", "input_date"}
    } == {
        k: v
        for k, v in results[0]["analysis_context"].items()
        if k not in {"input_calendar", "input_date"}
    }
    for value in results:
        spec.output_model.model_validate(value)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(value)
        c = value["calendar_conversion"]
        assert c["input_calendar"] == "julian"
        assert c["input_date"] == {"year": 2024, "month": 5, "day": 19}
        assert c["normalized_local_datetime"] == "2024-06-01T14:30:00"
        assert c["same_label_gregorian_offset_days"] == 13
        assert c["automatic_regional_reform_applied"] is False
        assert c["historical_clock_reconstruction_performed"] is False
        assert value[body]["calculation_basis"]["calendar"] == "proleptic_gregorian"
        assert (
            value["analysis_context"][prefix.rstrip("_") + "_datetime"]
            == c["normalized_local_datetime"]
        )
    c = reference.json()["calendar_conversion"]
    assert c["input_calendar"] == "proleptic_gregorian"
    assert c["calendar_conversion_performed"] is False


@pytest.mark.parametrize(
    "tool,prefix,inputs",
    [
        ("astro_horary", "question_", QUESTION),
        ("astro_election", "candidate_", CANDIDATE),
    ],
)
@pytest.mark.parametrize(
    "calendar,year,month,day",
    [
        ("julian", 1700, 2, 30),
        ("proleptic_gregorian", 1700, 2, 29),
        ("auto", 1582, 10, 4),
        ("julian", 1, 1, 1),
    ],
)
def test_calendar_faults_are_rejected_consistently_before_calculation(
    tool, prefix, inputs, calendar, year, month, day, rest, tmp_path, capsys
):
    spec = SPECS[tool]
    payload = {
        **inputs,
        prefix + "calendar": calendar,
        prefix + "year": year,
        prefix + "month": month,
        prefix + "day": day,
    }
    http = rest.post(spec.rest_path, json=payload)
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert http.status_code == 422 and code != 0 and protocol.is_error
    assert "calendar_conversion" not in cli
