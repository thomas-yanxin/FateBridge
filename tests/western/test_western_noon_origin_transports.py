"""Real protocol hour labels preserve raw provenance and the same physical chart."""

import asyncio

import pytest

from fatebridge.application.examples import evidence_views
from tests.evaluation.test_agentic_nested_outputs import SPECS, call_cli, native, rest
from tests.western.test_western_event_clock_transports import surfaces


@pytest.mark.parametrize(
    "tool,prefix,body,source,canonical,expected",
    [
        (
            "astro_horary",
            "question",
            "horary",
            dict(
                year=2024,
                month=5,
                day=31,
                hour=14,
                minute=30,
                calendar="proleptic_gregorian",
            ),
            dict(year=2024, month=6, day=1, hour=2, minute=30),
            "2024-06-01T02:30:00",
        ),
        (
            "astro_election",
            "candidate",
            "election",
            dict(year=1646, month=1, day=3, hour=21, minute=0, calendar="julian"),
            dict(year=1646, month=1, day=14, hour=9, minute=0),
            "1646-01-14T09:00:00",
        ),
        (
            "astro_election",
            "candidate",
            "election",
            dict(year=1, month=1, day=2, hour=12, minute=0, calendar="julian"),
            dict(year=1, month=1, day=1, hour=0, minute=0),
            "0001-01-01T00:00:00",
        ),
    ],
)
def test_noon_origin_and_canonical_midnight_labels_on_rest_mcp_cli(
    tool, prefix, body, source, canonical, expected, rest, tmp_path, capsys
):
    spec = SPECS[tool]
    fields = list(evidence_views(spec)["hour_origin"]["fields"]) + (
        [
            "horary.ascendant.longitude",
            "horary.planets.Sun.longitude",
            "horary.moon.sign",
            "horary.verdict",
        ]
        if body == "horary"
        else [
            "election.axes",
            "election.moon.longitude",
            "election.score",
            "election.verdict",
        ]
    )
    inputs = {prefix + "_" + k: v for k, v in source.items()}
    inputs.update(
        {
            prefix + "_hour_origin": "noon",
            "timezone_name": "UTC",
            "longitude": 0,
            "latitude": 40,
        }
    )
    values = surfaces(tool, inputs, fields, rest, tmp_path, capsys)
    reference = {prefix + "_" + k: v for k, v in canonical.items()}
    reference.update({"timezone_name": "UTC", "longitude": 0, "latitude": 40})
    params = [("fields", f) for f in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", 0),
    ]
    response = rest.post(spec.rest_path, json=reference, params=params)
    assert response.status_code == 200, response.text
    assert values[0][body] == response.json()[body]
    for value in values:
        c = value["clock_conversion"]
        origin = c["hour_origin_conversion"]
        assert c["input_hour_origin"] == "noon"
        assert (
            c["input_wall_datetime"] == origin["normalized_wall_datetime"] == expected
        )
        assert c["converted_utc"] == expected + "+00:00"
        assert origin["day_carry"] == 1
        assert origin["input_clock"]["hour"] == source["hour"]
        assert origin["input_date"] == {k: source[k] for k in ["year", "month", "day"]}
        assert (
            not origin["physical_duration_applied"]
            and not origin["source_clock_identification_performed"]
        )
        assert value["analysis_context"][prefix + "_datetime"] == expected
        assert value["analysis_context"]["input_hour_origin"] == "noon"
        if source["year"] == 1:
            assert value["calendar_conversion"]["normalized_local_datetime"] is None
            assert not origin["source_date_gregorian_representable"]
            assert value[body]["calculation_basis"]["julian_day_ut1"] == 1721425.5


@pytest.mark.parametrize(
    "tool,prefix", [("astro_horary", "question"), ("astro_election", "candidate")]
)
@pytest.mark.parametrize(
    "change",
    [
        dict(hour_origin="auto"),
        dict(hour=24, hour_origin="noon"),
        dict(year=9999, month=12, day=31, hour=12, hour_origin="noon"),
        dict(year=1, month=1, day=1, hour=23, calendar="julian", hour_origin="noon"),
        dict(year=1, month=1, day=2, hour=11, calendar="julian", hour_origin="noon"),
        dict(
            year=1700,
            month=2,
            day=29,
            calendar="proleptic_gregorian",
            hour_origin="noon",
        ),
    ],
)
def test_invalid_origin_or_final_label_is_rejected_before_calculation(
    tool, prefix, change, rest, tmp_path, capsys
):
    values = dict(year=2024, month=1, day=1, hour=0, minute=0)
    values.update(change)
    inputs = {prefix + "_" + k: v for k, v in values.items()}
    inputs.update(longitude=0, latitude=40, timezone_name="UTC")
    spec = SPECS[tool]
    http = rest.post(spec.rest_path, json=inputs)
    code, cli = call_cli(spec, inputs, tmp_path, capsys)
    protocol = asyncio.run(native(spec, inputs))
    assert http.status_code == 422 and code != 0 and protocol.is_error
    assert "clock_conversion" not in cli


def test_deep_origin_projection_omits_unrequested_siblings(rest, tmp_path, capsys):
    fields = [
        "clock_conversion.hour_origin_conversion.input_clock.hour",
        "clock_conversion.hour_origin_conversion.normalized_wall_datetime",
        "calendar_conversion.normalized_date_representable",
    ]
    values = surfaces(
        "astro_election",
        dict(
            candidate_year=1,
            candidate_month=1,
            candidate_day=2,
            candidate_hour=12,
            candidate_calendar="julian",
            candidate_hour_origin="noon",
            longitude=0,
            latitude=40,
            timezone_name="UTC",
        ),
        fields,
        rest,
        tmp_path,
        capsys,
    )
    assert values[0]["clock_conversion"]["hour_origin_conversion"] == {
        "input_clock": {"hour": 12},
        "normalized_wall_datetime": "0001-01-01T00:00:00",
    }
    assert values[0]["calendar_conversion"] == {"normalized_date_representable": False}
