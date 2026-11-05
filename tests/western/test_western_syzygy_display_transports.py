"""Solved historical points and display limits agree across actual adapters."""

import json

import pytest

from tests.support.transports import SPECS, business, rest, surface_calls


@pytest.mark.parametrize("key", ["astro_chart", "astro_hellen", "astro_chart13"])
@pytest.mark.parametrize("year,day", [(1, 1), (1, 5), (1, 10), (2026, 4)])
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_extended_syzygy_point_and_summary_on_rest_mcp_cli(
    key, year, day, zodiacal, surface_calls
):
    spec = SPECS[key]
    payload = dict(
        birth_year=year,
        birth_month=1,
        birth_day=day,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=40,
        use_true_solar_time=False,
        zodiacal=zodiacal,
    )
    fields = ["classical.syzygy", "classical.almuten_figuris", "snapshot_text"]
    http, protocol, code, cli = surface_calls(
        spec,
        payload,
        projection={
            **{"fields": fields, "strict_fields": True, "include_snapshot_text": True},
            "response_char_limit": 0,
        },
    )
    assert http.status_code == 200, http.text
    assert code == 0 and not protocol.is_error
    values = [http.json(), cli, json.loads(protocol.content[0].text)]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for result in values:
        spec.output_model.model_validate(result)
        syzygy = result["classical"]["syzygy"]
        assert syzygy is not None
        assert "syzygy" in result["classical"]["almuten_figuris"]["points"]
        representation = syzygy["utc_representation"]
        if year == 1:
            assert representation["datetime_representable"] is False
            assert syzygy["event_datetime_utc"].startswith("0000-")
            assert "Python日期表示受限" in result["snapshot_text"]
        else:
            assert representation["datetime_representable"] is True
            assert "Python日期表示受限" not in result["snapshot_text"]


@pytest.mark.parametrize(
    "fields",
    [
        ["classical.syzygy.utc_representation.datetime_representable"],
        [
            "classical.syzygy.event_datetime_utc",
            "classical.almuten_figuris.points.syzygy.winner",
        ],
    ],
)
def test_new_partial_paths_are_faithfully_projected(fields, surface_calls):
    spec = SPECS["astro_chart"]
    payload = dict(
        birth_year=1,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=40,
        use_true_solar_time=False,
    )
    http, protocol, code, cli = surface_calls(
        spec,
        payload,
        params=[("fields", f) for f in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
        options={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ],
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    values = [http.json(), cli, json.loads(protocol.content[0].text)]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for value in values:
        spec.output_model.model_validate(value)
