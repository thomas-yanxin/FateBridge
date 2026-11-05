"""The selected analysis instant survives public protocols and calendar edges."""

import asyncio
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import suggested_fields
from fatebridge.core.reproducibility import BAZI_ANALYSIS_CLOCK_TOOLS
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
)
from tests.evaluation.test_agentic_nested_outputs import rest as _shared_rest

rest = _shared_rest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/bazi_analysis_instant_v1"
PROTOCOL = json.loads((FIXTURE / "protocol.json").read_text())
WITNESSES = json.loads((FIXTURE / "date-side-witnesses.json").read_text())
BIRTH = PROTOCOL["cases"][0]["input"]
STAMP = "2025-02-04T04:37:49.123456Z"


@pytest.mark.parametrize("tool", sorted(BAZI_ANALYSIS_CLOCK_TOOLS))
def test_current_instant_and_published_clock_view_match_on_three_protocols(
    tool, rest, tmp_path, capsys
):
    spec = SPECS[tool]
    fields = suggested_fields(spec, view="analysis_clock")
    assert fields == ["analysis_reference"]
    opts = {
        "as_of": STAMP,
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    http = rest.post(spec.rest_path, json=BIRTH, params=opts)
    protocol = asyncio.run(native(spec, BIRTH, **opts))
    code, cli = call_cli(
        spec,
        BIRTH,
        tmp_path,
        capsys,
        flags=[
            "--as-of",
            STAMP,
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
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [http.json(), protocol.structured_content, cli]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for value in outputs:
        ref = value["analysis_reference"]
        assert ref["analysis_datetime"] == "2025-02-04T12:37:49.123456+08:00"
        assert ref["utc_datetime"] == "2025-02-04T04:37:49.123456+00:00"
        assert value["run_metadata"]["determinism"][
            "current_time_fields_defaulted"
        ] == [
            "analysis_year",
            "analysis_month",
            "analysis_day",
            "analysis_hour",
            "analysis_minute",
        ]
        Draft202012Validator(spec.output_model.model_json_schema()).validate(value)


@pytest.mark.parametrize(
    "tool", ["timing_analysis", "liuyue_analysis", "liuri_analysis", "liushi_analysis"]
)
@pytest.mark.parametrize("case", WITNESSES["term_side_cases"])
def test_implicit_clock_keeps_both_sides_of_a_known_subminute_lichun(tool, case, rest):
    response = rest.post(
        SPECS[tool].rest_path,
        json=BIRTH,
        params={"as_of": case["as_of"], "response_char_limit": 0},
    )
    assert response.status_code == 200
    value = response.json()
    month = value["analysis_calendar"]["analysis_date_context"]["bazi_month_boundary"]
    assert month["branch"] == case["expected_month_branch"]
    assert (
        month["comparison_datetime"] == value["analysis_reference"]["analysis_datetime"]
    )
    if tool == "timing_analysis":
        assert value["liunian_analysis"]["pillar"] == (
            "甲辰" if case["expected_bazi_year"] == 2024 else "乙巳"
        )


def test_current_latezi_uses_the_next_printed_day_without_changing_civil_date(rest):
    case = WITNESSES["late_zi_case"]
    response = rest.post(
        SPECS["liuri_analysis"].rest_path,
        json=BIRTH,
        params={"as_of": case["as_of"], "response_char_limit": 0},
    )
    assert response.status_code == 200
    value = response.json()
    assert value["personal_info"]["analysis_date"] == case["expected_civil_date"]
    assert value["liuri_info"]["pillar"] == case["expected_day_pillar"]
    assert (
        value["analysis_reference"]["analysis_datetime"] == "2025-03-01T23:30:00+08:00"
    )


@pytest.mark.parametrize("tool", sorted(BAZI_ANALYSIS_CLOCK_TOOLS))
@pytest.mark.parametrize(
    "month,day,hour,token", [(3, 9, 2, "nonexistent"), (11, 2, 1, "ambiguous")]
)
def test_every_timing_endpoint_rejects_invalid_explicit_analysis_clocks(
    tool, month, day, hour, token, rest
):
    payload = {
        **BIRTH,
        "birth_timezone": "America/New_York",
        "analysis_year": 2025,
        "analysis_month": month,
        "analysis_day": day,
        "analysis_hour": hour,
        "analysis_minute": 30,
    }
    response = rest.post(SPECS[tool].rest_path, json=payload)
    assert response.status_code == 400
    value = response.json()
    assert value["error_code"] == "validation_error" and value["retryable"] is False
    assert token in value["error"] and "分析钟时" in value["error"]
    assert "勿改出生时区" in value["error"]


def test_ambiguous_target_has_the_same_nonretryable_error_on_three_protocols(
    rest, tmp_path, capsys
):
    spec = SPECS["liushi_analysis"]
    payload = {
        **BIRTH,
        "birth_timezone": "America/New_York",
        "analysis_year": 2025,
        "analysis_month": 11,
        "analysis_day": 2,
        "analysis_hour": 1,
        "analysis_minute": 30,
    }
    http = rest.post(spec.rest_path, json=payload)
    protocol = asyncio.run(native(spec, payload))
    code, cli = call_cli(
        spec, payload, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    assert http.status_code == 400 and protocol.is_error and code != 0
    # HTTP carries status in its response, while MCP/CLI retain execution
    # envelope fields. The shared domain error facts must still agree exactly.
    keys = ("error", "error_code", "retryable")
    assert (
        {k: http.json()[k] for k in keys}
        == {k: protocol.structured_content[k] for k in keys}
        == {k: cli[k] for k in keys}
    )
    assert protocol.structured_content["status_code"] == 400
    assert protocol.structured_content["operation"] == "流时分析"


def test_explicit_age_has_no_invented_calendar_instant_and_projection_needs_no_siblings(
    rest,
):
    spec = SPECS["dayun_analysis"]
    response = rest.post(
        spec.rest_path,
        json={**BIRTH, "analysis_age": 35},
        params={
            "as_of": STAMP,
            "fields": ["analysis_reference"],
            "strict_fields": True,
        },
    )
    assert response.status_code == 200
    value = response.json()
    assert value["analysis_reference"]["basis"] == "explicit_age_reference"
    assert "analysis_datetime" not in value["analysis_reference"]
    assert not value["run_metadata"]["determinism"]["uses_current_time"]
    response = rest.post(
        SPECS["liuyue_analysis"].rest_path,
        json=BIRTH,
        params={
            "as_of": STAMP,
            "fields": ["analysis_reference.utc_datetime"],
            "strict_fields": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["analysis_reference"] == {
        "utc_datetime": "2025-02-04T04:37:49.123456+00:00"
    }


@pytest.mark.parametrize("tool", sorted(BAZI_ANALYSIS_CLOCK_TOOLS))
def test_known_utc_fold_instants_are_not_rejected_or_reinterpreted_by_http(tool, rest):
    fields = ["analysis_reference"]
    if tool != "dayun_analysis":
        fields.append("analysis_calendar.analysis_date_context.bazi_month_boundary")
    results = []
    for stamp in ["2025-11-02T05:30:00Z", "2025-11-02T06:30:00Z"]:
        response = rest.post(
            SPECS[tool].rest_path,
            json={**BIRTH, "birth_timezone": "America/New_York"},
            params={
                "as_of": stamp,
                "fields": fields,
                "strict_fields": True,
                "response_char_limit": 0,
            },
        )
        assert response.status_code == 200
        results.append(response.json())
    assert [r["analysis_reference"]["fold"] for r in results] == [0, 1]
    assert [r["analysis_reference"]["analysis_datetime"] for r in results] == [
        "2025-11-02T01:30:00-04:00",
        "2025-11-02T01:30:00-05:00",
    ]
    if tool != "dayun_analysis":
        windows = [
            r["analysis_calendar"]["analysis_date_context"]["bazi_month_boundary"]
            for r in results
        ]
        assert (
            windows[1]["elapsed_seconds_since_start"]
            - windows[0]["elapsed_seconds_since_start"]
            == 3600
        )
