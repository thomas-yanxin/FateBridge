"""Civil seasonal instants and unrounded seconds agree on REST, MCP and CLI."""

import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from tests.support.transports import SPECS, business, call_cli, native
from tests.support.transports import rest as _shared_rest

rest = _shared_rest


@pytest.mark.parametrize("topic", ["birth", "career", "education"])
def test_unrounded_month_window_and_unadjudicated_duty_match_three_transports(
    topic, rest, tmp_path, capsys
):
    spec = SPECS["bazi_" + topic]
    prefix = "bazi_birth" if topic == "birth" else topic + "_analysis"
    evidence = prefix + (
        ".structure_profile.evidence_chain" if topic == "birth" else ".evidence_chain"
    )
    fields = [
        prefix + ".calendar_context.bazi_month_boundary",
        evidence + ".month_command.intra_month_duty",
    ]
    args = {
        "birth_year": 1990,
        "birth_month": 5,
        "birth_day": 15,
        "birth_hour": 10,
        "birth_timezone": "Asia/Shanghai",
        "gender": "男",
        "use_true_solar_time": False,
        "analysis_year": 2026,
        "analysis_month": 10,
        "analysis_day": 22,
    }
    flags = {"fields": fields, "strict_fields": True, "include_snapshot_text": False}
    response = rest.post(spec.rest_path, json=args, params=flags)
    protocol = asyncio.run(native(spec, {**args, **flags}))
    code, local = call_cli(
        spec,
        args,
        tmp_path,
        capsys,
        flags=["--response-char-limit", "0", "--strict-fields", "--fields", *fields],
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    value = outputs[0][prefix]
    window = value["calendar_context"]["bazi_month_boundary"]
    start = datetime.fromisoformat(window["start_term"]["datetime"]).replace(
        tzinfo=ZoneInfo("Asia/Shanghai")
    )
    comparison = datetime.fromisoformat(window["comparison_datetime"])
    assert (
        window["elapsed_seconds_since_start"]
        == (
            comparison.astimezone(timezone.utc) - start.astimezone(timezone.utc)
        ).total_seconds()
    )
    assert window["elapsed_basis"] == "utc_instant_seconds"
    chain = (
        value["structure_profile"]["evidence_chain"]
        if topic == "birth"
        else value["evidence_chain"]
    )
    assert chain["month_command"]["intra_month_duty"]["status"] == "not_adjudicated"
