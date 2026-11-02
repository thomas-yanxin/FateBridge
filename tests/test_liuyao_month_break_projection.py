"""Nested selectors on the new evidence object remain strict and consistent."""

import asyncio

import pytest

from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest


@pytest.mark.parametrize("valid", [True, False])
def test_month_break_nested_projection_accepts_facts_and_rejects_typos(
    valid, rest, tmp_path, capsys
):
    spec = SPECS["sixyao"]
    payload = dict(
        date="2004-10-03",
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code="000001",
        changed_code="000001",
        focus_line=3,
    )
    root = "liuyao_evidence.conditional_analysis.month_break_conditions.focus."
    fields = (
        [
            root + field
            for field in [
                "raw_month_break",
                "day_value_exception",
                "calendar_month_opposition",
            ]
        ]
        if valid
        else [root + "day_value_excpetion"]
    )
    params = [("fields", field) for field in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", 0),
    ]
    flags = [
        "--fields",
        *fields,
        "--strict-fields",
        "true",
        "--include-snapshot-text",
        "false",
        "--response-char-limit",
        "0",
    ]
    http = rest.post(spec.rest_path, json=payload, params=params)
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    if not valid:
        assert http.status_code == 422 and code == 1 and protocol.is_error
        for body in [http.json(), cli, protocol.structured_content]:
            assert "liuyao_evidence" not in body
            assert body["issues"] == [
                {"path": fields[0], "code": "unknown_projection_path"}
            ]
        return
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    bodies = [http.json(), cli, protocol.structured_content]
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    for body in bodies:
        fact = body["liuyao_evidence"]["conditional_analysis"][
            "month_break_conditions"
        ]["focus"]
        assert fact == dict(
            raw_month_break=True,
            day_value_exception=True,
            calendar_month_opposition=False,
        )
        assert not body.get("projection_warnings")
