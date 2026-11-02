"""The published chapter card keeps the selected actor across three adapters."""

import asyncio

import pytest

from fatebridge.application.examples import evidence_views
from tests.meihua_qualified_motion_reference import expected_summary, load, path_get
from tests.test_agentic_nested_outputs import SPECS, call_cli, native, rest

GEOMETRY, COUNTING, READING, TEMPLATES = load()
FIELD = "interpretation.topic_reading.chapter_qualifications.qualitative_motion"
ATOMS = []
for topic in ["travel", "traveler"]:
    for name in ["乾", "兑", "离", "震", "巽", "坎", "艮", "坤"]:
        row = next(
            c
            for c in GEOMETRY
            if c["topic"] == topic
            and c["selected_trigram"] == name
            and c["body"] != c["use"]
        )
        ATOMS.append(row)


def run_three(tool, payload, rest, tmp_path, capsys):
    spec = SPECS[tool]
    fields = evidence_views(spec)["chapter_qualitative_motion"]["fields"]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[
            *(("fields", f) for f in fields),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
            ("include_snapshot_text", "false"),
        ],
    )
    reply = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    flags = ["--fields", *fields] + [
        "--strict-fields",
        "true",
        "--response-char-limit",
        "0",
        "--include-snapshot-text",
        "false",
    ]
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    assert response.status_code == 200, response.text
    assert not reply.is_error and code == 0
    values = [response.json(), reply.structured_content, cli]
    assert all("result_delivery" not in v for v in values)
    return values


def check(layer, expected, result, prefix):
    role = expected["selected_role"]
    assert layer["selected_role"] == role
    assert layer["selected_trigram"] == expected["selected_trigram"]
    assert layer["trigram_fact_path"] == f"{prefix}.{role}_trigram.name"
    if prefix == "meihua":
        assert (
            path_get(result, layer["trigram_fact_path"]) == expected["selected_trigram"]
        )
    assert layer["qualified_predicates"] == expected["qualified_predicates"]
    assert layer["matched_clause_ids"] == expected["matched_clause_ids"]
    assert layer["summary"] == expected_summary(expected, READING, TEMPLATES)
    assert layer["success_probability"] is None and layer["real_outcome"] is None


@pytest.mark.parametrize("case", ATOMS, ids=lambda c: c["id"])
def test_all16_actor_categories_use_the_published_card(case, rest, tmp_path, capsys):
    args = {
        "casting": {
            "method": "existing",
            "hexagram_code": case["code"],
            "moving_line": case["moving_line"],
        },
        "interpretation_topic": case["topic"],
    }
    for result in run_three("meihua_cast", args, rest, tmp_path, capsys):
        layer = path_get(result, FIELD)
        check(layer, case, result, "meihua")
        assert layer["summary"] in result["summary"]


@pytest.mark.parametrize("case", COUNTING, ids=lambda c: str(c["arguments"]))
def test_counting_candidates_are_not_replaced_with_primary_actor(
    case, rest, tmp_path, capsys
):
    topic = case["arguments"]["interpretation_topic"]
    for result in run_three("meihua_cast", case["arguments"], rest, tmp_path, capsys):
        expected = {**case["expected_primary"], "topic": topic}
        check(path_get(result, FIELD), expected, result, "meihua")
        readings = result["interpretation"]["casting_readings"]
        assert len(readings) == len(case["expected_candidates"])
        for index, (row, expected) in enumerate(
            zip(readings, case["expected_candidates"])
        ):
            check(
                row["topic_clause"]["chapter_qualifications"]["qualitative_motion"],
                {**expected, "topic": topic},
                result,
                f"meihua.counting_variants.{index}",
            )


@pytest.mark.parametrize("topic", ["travel", "traveler"])
def test_calendar_tool_publishes_primary_card_without_casting_readings(
    topic, rest, tmp_path, capsys
):
    args = {
        "analysis_year": 2000,
        "analysis_month": 1,
        "analysis_day": 6,
        "analysis_hour": 12,
        "analysis_minute": 0,
        "analysis_second": 0,
        "analysis_timezone": "+08:00",
        "interpretation_topic": topic,
    }
    fields = evidence_views(SPECS["meihua_analysis"])["chapter_qualitative_motion"][
        "fields"
    ]
    assert "interpretation.casting_readings" not in fields
    for result in run_three("meihua_analysis", args, rest, tmp_path, capsys):
        role = "body" if topic == "travel" else "use"
        name = result["meihua"][role + "_trigram"]["name"]
        expected = next(
            c for c in GEOMETRY if c["topic"] == topic and c["selected_trigram"] == name
        )
        check(path_get(result, FIELD), expected, result, "meihua")
