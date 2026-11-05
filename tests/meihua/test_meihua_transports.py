"""Mei Hua facts, declared conventions and errors agree across REST/MCP/CLI."""

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import suggested_fields
from tests.support.transports import SPECS, business, rest, surface_calls

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
def test_calculation_and_partial_evidence_agree_on_all_surfaces(fields, surface_calls):
    spec = SPECS["meihua_analysis"]
    fields = suggested_fields(spec) if fields == "first_view" else fields
    params = [("response_char_limit", "0")]
    flags = ["--response-char-limit", "0"]
    options = {}
    if fields:
        params += [("fields", f) for f in fields] + [("strict_fields", "true")]
        flags += ["--fields", *fields, "--strict-fields", "true"]
        options = {"fields": fields, "strict_fields": True}
    response, protocol, code, local = surface_calls(
        spec, INPUT, params=params, options=options, flags=flags
    )
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
    changes, surface_calls
):
    spec = SPECS["meihua_analysis"]
    payload = {**INPUT, **changes}
    response, protocol, code, local = surface_calls(spec, payload)
    assert response.status_code == 422 and code != 0 and protocol.is_error
    for output in [response.json(), local, protocol.structured_content]:
        assert output["error_code"] == "validation_error"
        assert output["retryable"] is False


@pytest.mark.parametrize(
    "month,day,expected",
    [(1, 31, (1, 1, False)), (9, 24, (8, 1, True)), (10, 23, (9, 1, False))],
)
def test_primary_1900_calendar_edges_agree_across_surfaces(
    month, day, expected, surface_calls
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
    response, protocol, code, local = surface_calls(
        spec,
        payload,
        params=[("fields", f) for f in fields] + [("strict_fields", "true")],
        options={"fields": fields, "strict_fields": True},
        flags=["--fields", *fields, "--strict-fields", "true"],
    )
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
    surface_calls,
):
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
    response, protocol, code, local = surface_calls(
        spec,
        payload,
        projection={
            **{"fields": fields, "strict_fields": True},
            "response_char_limit": 0,
        },
    )
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
    month, day, lunar_month, code, line, surface_calls
):
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
    response, protocol, exit_code, local = surface_calls(
        spec,
        payload,
        params=[*(("fields", f) for f in fields), ("strict_fields", "true")],
        options={"fields": fields, "strict_fields": True},
        flags=["--fields", *fields, "--strict-fields", "true"],
    )
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
