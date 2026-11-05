"""Confirmed lunar labels stay visible without inventing strength or a date."""

import copy
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from fatebridge.core.meihua_observation import _seed_calendar_values
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.meihua import calculate_meihua_cast
from tests.evaluation.test_agentic_nested_outputs import (  # noqa: F401
    SPECS,
    call_cli,
    rest,
)

FOLDER = Path(__file__).parents[1] / "fixtures/meihua_quiet_calendar_v74"
CASES = json.loads((FOLDER / "confirmed-label-cases24.json").read_bytes())
CASES_SHA = "889b6d70abcabf5691485430c611254e01ae971e8b8a4f14d7c0efea21a0574f"
QUIET = {
    "label": "虚构工程静室声明",
    "quiet_room": True,
    "nothing_heard": True,
    "nothing_seen": True,
}
TOPICS = [
    "general",
    "planning",
    "reputation",
    "wealth",
    "transaction",
    "travel",
    "meeting",
]


def at_path(value, path):
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def check_labels(out, case):
    assert "error" not in out
    layer = out["interpretation"]["observation_context"]
    internal = layer["internal_basis"]
    assert internal["known_seed_calendar_values"] == case["expected_rows"]
    for row in internal["known_seed_calendar_values"]:
        assert at_path(out, row["fact_path"]) == row["value"]
    assert internal["seed_counts_are_year_or_day_strength_calculations"] is False
    assert internal["complete_year_month_day_strength_synthesis"] is None
    assert internal["full_selected_quiet_judgement_established"] is False
    assert (
        layer["event_time"]
        is layer["real_outcome"]
        is layer["casting_eligibility"]
        is None
    )
    assert layer["changes_registered_forecast_eligibility_or_denominators"] is False
    assert out["interpretation"]["day_qi"] is None
    assert out["input_normalized"]["casting"] == case["casting"]


def test_labels_and_source_visual_recheck_were_frozen_before_production_edit():
    assert (
        hashlib.sha256(
            (FOLDER / "confirmed-label-cases24.json").read_bytes()
        ).hexdigest()
        == CASES_SHA
    )
    freeze = json.loads((FOLDER / "reference-freeze.json").read_bytes())
    assert freeze["before_production_modification"]
    assert not freeze["expected_values_from_production"]
    recheck = json.loads((FOLDER / "primary-recheck.json").read_bytes())
    assert (
        recheck["live_pdf_sha256"]
        == recheck["selected_pdf_sha256"]
        == "af608094ab11ae209eae91a9365565e7c9cff604aac3da5e753e04d1cc4598c0"
    )
    for name, row in recheck["images_visually_read"].items():
        assert hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() == row["sha256"]


@pytest.mark.parametrize("case", CASES, ids=lambda row: row["id"])
@pytest.mark.parametrize("context", [None, QUIET])
def test_confirmed_labels_and_actual_paths_are_present_with_or_without_quiet_declaration(
    case, context
):
    out = calculate_meihua_cast(casting=case["casting"], observation_context=context)
    check_labels(out, case)
    assert out["interpretation"]["observation_context"]["status"] == (
        "not_collected" if context is None else "declared_conditions_met"
    )


@pytest.mark.parametrize("topic", TOPICS)
def test_all_human_topics_preserve_reported_labels_without_full_quiet_certification(
    topic,
):
    out = calculate_meihua_cast(
        casting=CASES[0]["casting"],
        interpretation_topic=topic,
        observation_context=QUIET,
    )
    check_labels(out, CASES[0])


@pytest.mark.parametrize(
    "context,status",
    [
        ({"label": "虚构未知静室"}, "pending_declared_conditions"),
        ({"label": "虚构不静室", "quiet_room": False}, "declared_conditions_not_met"),
    ],
)
def test_incomplete_or_false_context_does_not_erase_known_calendar_labels(
    context, status
):
    out = calculate_meihua_cast(
        casting=CASES[0]["casting"], observation_context=context
    )
    check_labels(out, CASES[0])
    assert out["interpretation"]["observation_context"]["status"] == status


@pytest.mark.parametrize(
    "casting",
    [
        {"method": "object_count", "count": 12, "hour_branch": "酉"},
        {
            "method": "sound_groups",
            "first_count": 12,
            "second_count": 5,
            "hour_branch": "酉",
        },
        {"method": "existing", "hexagram_code": "100111", "moving_line": 1},
        {"method": "length_zhang_chi", "zhang": 12, "chi": 5},
    ],
)
def test_other_counts_question_and_day_branch_do_not_become_lunar_calendar_labels(
    casting,
):
    out = calculate_meihua_cast(
        casting=casting,
        question="虚构问题中写寅年十二月初一午时",
        season_month_branch="寅",
        day_qi_context={"label": "虚构寅日", "day_branch": "寅"},
    )
    assert "error" not in out
    rows = out["interpretation"]["observation_context"]["internal_basis"][
        "known_seed_calendar_values"
    ]
    assert all(r["value"] is None and r["fact_path"] is None for r in rows[:3])
    assert rows[3]["value"] == casting.get("hour_branch")


@pytest.mark.parametrize(
    "field", ["year_branch", "lunar_month", "lunar_day", "hour_branch", "method"]
)
def test_contradictory_internal_seed_is_rejected_instead_of_silently_rebound(field):
    seed = {
        "casting_method": "lunar_time_added_count",
        "parameters": copy.deepcopy(CASES[0]["casting"]),
        "hour_branch": CASES[0]["casting"]["hour_branch"],
    }
    if field == "method":
        seed["parameters"]["method"] = "object_count"
    else:
        seed[field] = "亥" if field.endswith("branch") else 9
    with pytest.raises(ValueError, match="Quiet-context"):
        _seed_calendar_values(seed)


@pytest.mark.parametrize("field", ["year_branch", "lunar_month", "lunar_day"])
def test_reported_labels_remain_required_no_defaults(field):
    casting = copy.deepcopy(CASES[0]["casting"])
    del casting[field]
    assert "error" in calculate_meihua_cast(casting=casting, observation_context=QUIET)


@pytest.mark.asyncio
async def test_rest_native_mcp_and_cli_preserve_the_actual_nested_fact_paths(
    rest, capsys, tmp_path
):
    arguments = {"casting": CASES[-1]["casting"], "observation_context": QUIET}
    expected = calculate_meihua_cast(**arguments)
    fields = [
        "input_normalized",
        "meihua.seed",
        "interpretation.observation_context",
        "interpretation.day_qi",
        "summary",
    ]
    params = [("fields", f) for f in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", "0"),
    ]
    response = rest.post(SPECS["meihua_cast"].rest_path, json=arguments, params=params)
    assert response.status_code == 200, response.text
    async with Client(create_mcp_app()) as client:
        reply = await client.call_tool(
            "meihua_cast",
            {
                **arguments,
                "fields": fields,
                "strict_fields": True,
                "include_snapshot_text": False,
                "response_char_limit": 0,
            },
            raise_on_error=False,
        )
    assert not reply.is_error
    code, cli = call_cli(
        SPECS["meihua_cast"],
        arguments,
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
    assert code == 0
    for out in [response.json(), reply.structured_content, cli]:
        check_labels(out, CASES[-1])
        assert out["interpretation"] == {
            k: expected["interpretation"][k] for k in ["observation_context", "day_qi"]
        }
        assert out["summary"] == expected["summary"]


@pytest.mark.asyncio
async def test_fresh_stdio_reads_published_quiet_fields_with_corrected_labels(tmp_path):
    root = Path(__file__).resolve().parents[2]
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "fatebridge.mcp_server"],
        cwd=str(root),
        env={
            "PYTHONPATH": os.environ.get("PYTHONPATH", str(root / "src")),
            "FATEBRIDGE_MCP_SCENARIOS": "onda-zhanbu",
            "FATEBRIDGE_MCP_TOOL_SCOPE": "topic",
        },
        log_file=tmp_path / "stdio.log",
    )
    from fatebridge.application.examples import suggested_fields

    fields = suggested_fields(SPECS["meihua_cast"], view="quiet")
    async with Client(transport) as client:
        reply = await client.call_tool(
            "meihua_cast",
            {
                "casting": CASES[0]["casting"],
                "observation_context": QUIET,
                "fields": fields,
                "strict_fields": True,
                "include_snapshot_text": False,
                "response_char_limit": 0,
            },
            raise_on_error=False,
        )
    assert not reply.is_error
    check_labels(reply.structured_content, CASES[0])
