"""Actual REST/native MCP/CLI accept the same declared clock and provenance."""

import asyncio
from datetime import datetime

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import evidence_views
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_western_event_clocks import REFERENCE


def surfaces(tool, inputs, fields, rest, tmp_path, capsys):
    spec = SPECS[tool]
    params = [("fields", f) for f in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", 0),
    ]
    http = rest.post(spec.rest_path, json=inputs, params=params)
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
    mcp = asyncio.run(
        native(
            spec, inputs, fields=fields, strict_fields=True, include_snapshot_text=False
        )
    )
    assert http.status_code == 200, http.text
    assert code == 0 and not mcp.is_error
    values = [http.json(), cli, mcp.structured_content]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for value in values:
        spec.output_model.model_validate(value)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(value)
    return values


def test_julian_historical_lmt_horary_matches_the_same_civil_epoch(
    rest, tmp_path, capsys
):
    tool = "astro_horary"
    fields = list(evidence_views(SPECS[tool])["clock_input"]["fields"]) + [
        "horary.ascendant.longitude",
        "horary.planets.Sun.longitude",
        "horary.moon.sign",
        "horary.verdict",
    ]
    inputs = dict(
        question_year=1634,
        question_month=7,
        question_day=16,
        question_hour=11,
        question_calendar="julian",
        question_clock_basis="local_mean_solar",
        longitude=10,
        latitude=40,
    )
    values = surfaces(tool, inputs, fields, rest, tmp_path, capsys)
    c = values[0]["clock_conversion"]
    assert c["input_wall_datetime"] == "1634-07-26T11:00:00"
    assert c["converted_utc"] == "1634-07-26T10:20:00+00:00"
    assert values[0]["calendar_conversion"]["input_date"]["day"] == 16
    assert values[0]["analysis_context"]["timezone"] is None
    params = [("fields", f) for f in fields] + [
        ("strict_fields", "true"),
        ("response_char_limit", 0),
    ]
    reference = rest.post(
        SPECS[tool].rest_path,
        json={
            **inputs,
            "question_day": 26,
            "question_calendar": "proleptic_gregorian",
            "question_clock_basis": "civil",
            "question_hour": 10,
            "question_minute": 20,
            "timezone_name": "UTC",
        },
        params=params,
    )
    assert reference.status_code == 200, reference.text
    # Solar sunrise weekday metadata explicitly differs; the selected physical
    # geometry and actual TT/UT1 match the reference civil UTC epoch exactly.
    assert reference.json()["horary"] == values[0]["horary"]


def test_jpl_lat_election_physical_axis_on_all_surfaces(rest, tmp_path, capsys):
    row = REFERENCE["apparent_inverse_controls"][0]
    tool = "astro_election"
    fields = list(evidence_views(SPECS[tool])["clock_input"]["fields"]) + [
        "election.axes",
        "election.moon.longitude",
        "election.score",
        "election.verdict",
    ]
    values = surfaces(
        tool,
        dict(
            candidate_year=2000,
            candidate_month=1,
            candidate_day=1,
            candidate_hour=1,
            candidate_clock_basis="local_apparent_solar",
            longitude=row["longitude"],
            latitude=40,
        ),
        fields,
        rest,
        tmp_path,
        capsys,
    )
    for value in values:
        c = value["clock_conversion"]
        basis = value["election"]["calculation_basis"]
        assert c["julian_day_tt"] == basis["julian_day_tt"]
        assert c["julian_day_ut1"] == basis["julian_day_ut1"]
        assert (
            abs(
                (
                    datetime.fromisoformat(c["converted_utc"])
                    - datetime.fromisoformat(row["utc"])
                ).total_seconds()
            )
            < REFERENCE["apparent_utc_tolerance_seconds"]
        )
        assert not c["source_clock_identification_performed"]
        assert not c["input_clock_accuracy_certified"]


@pytest.mark.parametrize(
    "tool,prefix", [("astro_horary", "question"), ("astro_election", "candidate")]
)
@pytest.mark.parametrize(
    "basis,zone",
    [("local_mean_solar", "UTC"), ("local_apparent_solar", "+08:00"), ("auto", None)],
)
def test_invalid_clock_contract_rejected_before_calculation_on_all_surfaces(
    tool, prefix, basis, zone, rest, tmp_path, capsys
):
    inputs = {
        prefix + "_year": 2000,
        prefix + "_month": 1,
        prefix + "_day": 1,
        prefix + "_hour": 1,
        prefix + "_clock_basis": basis,
        "timezone_name": zone,
        "longitude": 15,
        "latitude": 40,
    }
    spec = SPECS[tool]
    http = rest.post(spec.rest_path, json=inputs)
    code, cli = call_cli(spec, inputs, tmp_path, capsys)
    mcp = asyncio.run(native(spec, inputs))
    assert http.status_code == 422 and code != 0 and mcp.is_error
    assert "clock_conversion" not in cli


def test_deep_solar_clock_projection_has_optional_siblings(rest, tmp_path, capsys):
    fields = [
        "clock_conversion.solar_conversion.equation_of_time_seconds",
        "clock_conversion.input_clock_accuracy_certified",
        "clock_conversion.clock_chart_source_comparison.chart_sun_source.by_factor.Sun.model",
    ]
    values = surfaces(
        "astro_election",
        dict(
            candidate_year=2000,
            candidate_month=1,
            candidate_day=1,
            candidate_hour=1,
            candidate_clock_basis="local_apparent_solar",
            longitude=15,
            latitude=40,
        ),
        fields,
        rest,
        tmp_path,
        capsys,
    )
    c = values[0]["clock_conversion"]
    assert "converted_utc" not in c and "input_clock_basis" not in c
    assert set(c["solar_conversion"]) == {"equation_of_time_seconds"}
