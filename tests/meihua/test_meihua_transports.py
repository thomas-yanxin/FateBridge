"""Mei Hua facts, declared conventions and errors agree across REST/MCP/CLI."""

import asyncio

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import suggested_fields
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

INPUT = {
    "analysis_year": 2026,
    "analysis_month": 2,
    "analysis_day": 5,
    "analysis_hour": 12,
    "analysis_timezone": "Asia/Shanghai",
    "question": "项目推进",
}


@pytest.mark.parametrize(
    "fields",
    [
        None,
        "first_view",
        [
            "meihua.ruleset.id",
            "meihua.calendar_policy.day_boundary",
            "meihua.stage_relations",
            "interpretation.classical_text_reference",
        ],
    ],
)
def test_calculation_and_partial_evidence_agree_on_all_surfaces(
    fields, rest, tmp_path, capsys
):
    spec = SPECS["meihua_analysis"]
    fields = suggested_fields(spec) if fields == "first_view" else fields
    params = [("response_char_limit", "0")]
    flags = ["--response-char-limit", "0"]
    options = {}
    if fields:
        params += [("fields", f) for f in fields] + [("strict_fields", "true")]
        flags += ["--fields", *fields, "--strict-fields", "true"]
        options = {"fields": fields, "strict_fields": True}
    response = rest.post(spec.rest_path, json=INPUT, params=params)
    code, local = call_cli(spec, INPUT, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(native(spec, INPUT, **options))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        assert output["meihua"]["ruleset"]["id"] == "meihua_lunar_time_v1"
        assert output["meihua"]["calendar_policy"]["day_boundary"] == "local_midnight"
        assert len(output["meihua"]["stage_relations"]) == 4


@pytest.mark.parametrize(
    "changes",
    [
        {"analysis_year": 1899, "analysis_month": 12, "analysis_day": 31},
        {"analysis_year": 1900, "analysis_month": 2, "analysis_day": 29},
        {"analysis_year": 2101, "analysis_month": 1, "analysis_day": 1},
        {
            "analysis_year": 2026,
            "analysis_month": 11,
            "analysis_day": 1,
            "analysis_hour": 1,
            "analysis_minute": 30,
            "analysis_timezone": "America/New_York",
        },
    ],
)
def test_unsupported_date_and_dst_ambiguity_are_failures_on_all_surfaces(
    changes, rest, tmp_path, capsys
):
    spec = SPECS["meihua_analysis"]
    payload = {**INPUT, **changes}
    response = rest.post(spec.rest_path, json=payload)
    code, local = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert response.status_code == 422 and code != 0 and protocol.is_error
    for output in [response.json(), local, protocol.structured_content]:
        assert output["error_code"] == "validation_error"
        assert output["retryable"] is False


@pytest.mark.parametrize(
    "month,day,expected",
    [(1, 31, (1, 1, False)), (9, 24, (8, 1, True)), (10, 23, (9, 1, False))],
)
def test_primary_1900_calendar_edges_agree_across_surfaces(
    month, day, expected, rest, tmp_path, capsys
):
    spec = SPECS["meihua_analysis"]
    payload = {
        **INPUT,
        "analysis_year": 1900,
        "analysis_month": month,
        "analysis_day": day,
    }
    fields = [
        "calendar_context.lunar_calendar",
        "meihua.seed",
        "meihua.calendar_policy",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields] + [("strict_fields", "true")],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=["--fields", *fields, "--strict-fields", "true"],
    )
    protocol = asyncio.run(native(spec, payload, fields=fields, strict_fields=True))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        lunar = output["calendar_context"]["lunar_calendar"]
        assert lunar["year"] == 1900
        assert (lunar["month"], lunar["day"], lunar["is_leap_month"]) == expected
        seed = output["meihua"]["seed"]
        assert (
            seed["year_branch"],
            seed["lunar_month"],
            seed["lunar_day"],
            seed["hour_branch"],
        ) == ("子", expected[0], expected[1], "午")


def test_new_1900_prefix_keeps_the_former_negative_date_as_a_positive_reference(
    rest, tmp_path, capsys
):
    # TAM1900 prints 十二月初一 on Jan1 and 三十 on Jan30. The current
    # prefix now admits Jan30: 亥12+月12+日30=54, +午7=61 => 坎/巽,动1.
    # Keep this positive probe when moving the out-of-range test to1899-12-31.
    spec = SPECS["meihua_analysis"]
    payload = {
        **INPUT,
        "analysis_year": 1900,
        "analysis_month": 1,
        "analysis_day": 30,
    }
    fields = [
        "calendar_context.lunar_calendar",
        "meihua.seed",
        "meihua.base_hexagram.binary_code",
        "meihua.changed_hexagram.binary_code",
        "meihua.mutual_hexagram.binary_code",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[
            *(("fields", f) for f in fields),
            ("strict_fields", "true"),
            ("response_char_limit", 0),
        ],
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
            "true",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(native(spec, payload, fields=fields, strict_fields=True))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        lunar = output["calendar_context"]["lunar_calendar"]
        assert (
            lunar["year"],
            lunar["month"],
            lunar["day"],
            lunar["is_leap_month"],
        ) == (1899, 12, 30, False)
        seed = output["meihua"]["seed"]
        assert (seed["year_branch"], seed["hour_branch"], seed["moving_line"]) == (
            "亥",
            "午",
            1,
        )
        for kind, expected in [
            ("base", "011010"),
            ("changed", "111010"),
            ("mutual", "110101"),
        ]:
            assert output["meihua"][kind + "_hexagram"]["binary_code"] == expected


@pytest.mark.parametrize(
    "month,day,lunar_month,code,line",
    [(2, 9, 1, "110101", 6), (12, 31, 12, "011010", 5)],
)
def test_normative_2100_extension_keeps_calendar_source_and_actual_time_cast(
    month, day, lunar_month, code, line, rest, tmp_path, capsys
):
    # HKO's two printed month starts; year 申=9, noon 午=7. Manual seeds:
    # 9+1+1=11, +7=18; 9+12+1=22, +7=29. Not independent astronomy.
    spec = SPECS["meihua_analysis"]
    payload = {
        **INPUT,
        "analysis_year": 2100,
        "analysis_month": month,
        "analysis_day": day,
    }
    fields = [
        "calendar_context.lunar_calendar",
        "meihua.seed",
        "meihua.base_hexagram.binary_code",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[*(("fields", f) for f in fields), ("strict_fields", "true")],
    )
    exit_code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=["--fields", *fields, "--strict-fields", "true"],
    )
    protocol = asyncio.run(native(spec, payload, fields=fields, strict_fields=True))
    assert response.status_code == 200 and exit_code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        lunar = output["calendar_context"]["lunar_calendar"]
        assert (
            lunar["year"],
            lunar["month"],
            lunar["day"],
            lunar["is_leap_month"],
        ) == (2100, lunar_month, 1, False)
        assert lunar["conversion_source"]["method_id"] == "hko_2100_month_starts_v1"
        assert lunar["conversion_source"]["publisher"] == "香港天文台"
        assert lunar["conversion_source"]["raw_sha256"]
        seed = output["meihua"]["seed"]
        assert (seed["year_branch"], seed["hour_branch"], seed["moving_line"]) == (
            "申",
            "午",
            line,
        )
        assert output["meihua"]["base_hexagram"]["binary_code"] == code
