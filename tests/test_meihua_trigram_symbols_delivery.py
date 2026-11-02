"""All public casting shapes and bounded same-run delivery; no model calls."""

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic import TypeAdapter

import fatebridge
from fatebridge.core.requests.meihua import MeihuaCasting
from fatebridge.services.meihua import calculate_meihua_cast

METHODS = [
    {"method": "existing", "hexagram_code": "010111", "moving_line": 4},
    {
        "method": "sound_groups",
        "first_count": 11,
        "second_count": 1,
        "hour_branch": "子",
    },
    {"method": "object_count", "count": 9, "hour_branch": "酉"},
    {
        "method": "observed_trigrams",
        "upper_trigram": "离",
        "lower_trigram": "兑",
        "hour_branch": "辰",
    },
    {
        "method": "observed_categories",
        "subject_category": "elder_person",
        "subject_description": "虚构工程诊断的单一已报类别",
        "single_subject_confirmed": True,
        "direction": "southeast",
        "direction_role": "toward",
        "hour_branch": "卯",
    },
    {"method": "length_zhang_chi", "zhang": 1, "chi": 8, "cun": 3},
    {"method": "length_chi_cun", "chi": 1, "cun": 8, "fen": 3, "hour_branch": "卯"},
    {"method": "text_tones", "tones": [1, 4, 3, 3, 1, 1]},
    {"method": "text_strokes", "strokes": [6, 8]},
    {
        "method": "single_character_strokes",
        "script_style": "regular",
        "left_strokes": 7,
        "right_strokes": 4,
        "total_strokes": 11,
    },
    {"method": "text_count", "character_count": 11},
    {
        "method": "lunar_time_added_count",
        "year_branch": "子",
        "lunar_month": 12,
        "lunar_day": 30,
        "hour_branch": "午",
        "added_count": 7,
    },
]
FIELD = "interpretation.trigram_relation_symbols"


def test_diagnostics_cover_every_public_method_without_claiming_an_unseen_holdout():
    schema = TypeAdapter(MeihuaCasting).json_schema()
    assert set(schema["discriminator"]["mapping"]) == {p["method"] for p in METHODS}
    expected = os.environ.get("MEIHUA_V41_EXPECTED_PACKAGE_ROOT")
    if expected:
        assert (
            Path(fatebridge.__file__).resolve().is_relative_to(Path(expected).resolve())
        )


@pytest.mark.parametrize("casting", METHODS, ids=lambda p: p["method"])
@pytest.mark.parametrize("topic", ["general", "wealth", "weather"])
def test_each_valid_public_method_retains_symbol_evidence_or_weather_null(
    casting, topic
):
    TypeAdapter(MeihuaCasting).validate_python(casting)
    result = calculate_meihua_cast(casting=casting, interpretation_topic=topic)
    assert "error" not in result, result
    layer = result["interpretation"]["trigram_relation_symbols"]
    if topic == "weather":
        assert layer is None
    else:
        assert layer["selected"]["body"] == result["meihua"]["body_trigram"]["name"]
        assert len(layer["selected"]["role_evaluations"]) == 4
        assert layer["effective_role_or_global_synthesis"] == "not_computed"
        assert (
            layer["event_time"]
            is layer["real_outcome"]
            is layer["success_probability"]
            is None
        )


@pytest.mark.asyncio
async def test_bounded_stdio_read_restores_complete_same_run_field(tmp_path):
    package_root = Path(
        os.environ.get(
            "MEIHUA_V41_EXPECTED_PACKAGE_ROOT",
            str(Path(__file__).resolve().parents[1] / "src"),
        )
    )
    root = Path(__file__).resolve().parents[1]
    expected = calculate_meihua_cast(casting=METHODS[0])["interpretation"][
        "trigram_relation_symbols"
    ]
    assert len(json.dumps(expected, ensure_ascii=False)) > 4096
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "fatebridge.mcp_server"],
        cwd=str(root),
        env={
            "PYTHONPATH": str(package_root),
            "FATEBRIDGE_MCP_SCENARIOS": "onda-zhanbu",
            "FATEBRIDGE_MCP_TOOL_SCOPE": "topic",
        },
        log_file=tmp_path / "stdio.log",
    )
    async with Client(transport) as client:
        reply = await client.call_tool(
            "meihua_cast",
            {
                "casting": METHODS[0],
                "fields": [FIELD],
                "strict_fields": True,
                "include_snapshot_text": False,
                "response_char_limit": 4096,
            },
            raise_on_error=False,
        )
        assert not reply.is_error
        result = reply.structured_content
        delivery = result["result_delivery"]
        run = result["run_metadata"]["run_id"]
        uri = f"fatebridge://results/{delivery['result_id']}/verified/{run}/{delivery['sha256']}/fields/{FIELD}/0"
        fragments = []
        offset = 0
        checksum = None
        while uri:
            reply = await client.read_resource(uri)
            page = json.loads(reply[0].text)
            assert (
                page["offset"] == offset and page["result_id"] == delivery["result_id"]
            )
            assert page["path"] == FIELD
            assert page["verification"]["run_id"] == run
            assert page["verification"]["payload_sha256"] == delivery["sha256"]
            assert page["verification"]["calculation_repeated"] is False
            checksum = page["sha256"] if checksum is None else checksum
            assert checksum == page["sha256"]
            fragments.append(page["text"])
            offset += len(page["text"])
            following = page["next_offset"]
            assert following is None or following == offset
            uri = (
                uri.rsplit("/", 1)[0] + "/" + str(following)
                if following is not None
                else None
            )
    text = "".join(fragments)
    assert hashlib.sha256(text.encode()).hexdigest() == checksum
    assert json.loads(text) == expected
