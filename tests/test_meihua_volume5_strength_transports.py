"""Attributed source-table facts through actual REST, native MCP and CLI."""

import asyncio
from copy import deepcopy

import pytest

from tests.meihua_volume5_strength_reference import load
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

CELLS, _ = load()
LOOKUP = {(r["column"], r["element"]): r["expected_state"] for r in CELLS}
BASE = {"casting": {"method": "existing", "hexagram_code": "010000", "moving_line": 1}}
CASES = [
    ("meihua_cast", {**BASE, "season_month_branch": m})
    for m in [None, "寅", "巳", "申", "亥", "丑"]
] + [
    (
        "meihua_cast",
        {
            "casting": {
                "method": "sound_groups",
                "first_count": 11,
                "second_count": 1,
                "hour_branch": "子",
            },
            "season_month_branch": "申",
        },
    ),
    (
        "meihua_analysis",
        {
            "analysis_year": 2000,
            "analysis_month": 1,
            "analysis_day": 6,
            "analysis_hour": 12,
            "analysis_minute": 0,
            "analysis_second": 0,
            "analysis_timezone": "+08:00",
        },
    ),
]
FIELDS = [
    "interpretation.seasonal_qualification.volume5_table_comparison",
    "interpretation.casting_readings",
]


def check_layer(layer):
    assert layer["ruleset_id"] == "meihua_volume5_four_state_nlc1925_v1"
    assert set(layer["ruleset"]["rows"]) == {"旺", "相", "休", "囚"}
    assert layer["complete_year_month_day_strength_synthesis"] is None
    assert layer["used_to_override_primary_strength"] is False
    for row in layer["roles"]:
        column = layer["table_column"]
        assert row["table_state"] == (
            LOOKUP[column, row["element"]] if column is not None else None
        )


def across_transports(key, arguments, fields, rest, tmp_path, capsys):
    spec = SPECS[key]
    payload = deepcopy(arguments)
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[
            *(("fields", f) for f in fields),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
        ],
    )
    assert response.status_code == 200, response.text
    reply = asyncio.run(native(spec, payload, fields=fields, strict_fields=True))
    assert not reply.is_error, reply
    code, cli = call_cli(
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
    assert code == 0, cli
    actual = business(response.json())
    assert actual == business(reply.structured_content) == business(cli)
    return actual


@pytest.mark.parametrize("key,arguments", CASES)
def test_source_scope_cells_and_candidate_evidence_agree_on_three_transports(
    key, arguments, rest, tmp_path, capsys
):
    fields = FIELDS if key == "meihua_cast" else FIELDS[:1]
    actual = across_transports(key, arguments, fields, rest, tmp_path, capsys)
    check_layer(
        actual["interpretation"]["seasonal_qualification"]["volume5_table_comparison"]
    )
    for candidate in actual["interpretation"].get("casting_readings", []):
        layer = candidate["seasonal_qualification"]["volume5_table_comparison"]
        check_layer(layer)
        assert layer["roles"][0]["trigram"] == candidate["body"]


def test_weather_keeps_its_existing_null_body_use_qualification(rest, tmp_path, capsys):
    payload = {**BASE, "season_month_branch": "申", "interpretation_topic": "weather"}
    actual = across_transports(
        "meihua_cast",
        payload,
        ["interpretation.seasonal_qualification"],
        rest,
        tmp_path,
        capsys,
    )
    assert actual == {"interpretation": {"seasonal_qualification": None}}
