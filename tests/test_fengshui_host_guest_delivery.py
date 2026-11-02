"""Read the complete original host/guest result under the unchanged MCP budget."""

import asyncio
import hashlib
import json
from copy import deepcopy

import pytest
from fastmcp import Client

from fatebridge.mcp_server import create_mcp_app
from fatebridge.validation.fengshui_reading import verify_fengshui_reading


@pytest.mark.parametrize("tool", ["xuankong_natal", "assess"])
def test_default_budget_reads_the_same_run_and_keeps_source_difference(tool):
    value = {
        "house": {"facing_degrees": 135, "north_reference": "magnetic"},
        "period": {
            "basis": "expert_confirmed",
            "period_number": 6,
            "evidence": "Synthetic pagination audit, not a real dwelling",
        },
        "interpretation": {"host_guest_ruleset_id": "shen_2011_host_guest_v1"},
    }
    if tool == "assess":
        value = {"methods": ["xuankong_natal"], "xuankong": value}

    async def read_original():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool("fengshui_" + tool, value)
            assert not result.is_error
            assert len(result.content[0].text) <= 8192
            inline = result.structured_content
            ref = inline["result_delivery"]
            manifest = json.loads(
                (await client.read_resource(ref["manifest_uri"]))[0].text
            )
            assert manifest["sha256"] == ref["sha256"]
            chunks, uri, offset = [], ref["first_page_uri"], 0
            while uri is not None:
                page = json.loads((await client.read_resource(uri))[0].text)
                assert page["sha256"] == ref["sha256"]
                assert page["offset"] == offset
                chunks.append(page["text"])
                offset += len(page["text"])
                assert page["next_offset"] == (
                    offset if offset < ref["total_chars"] else None
                )
                uri = page["next_uri"]
            raw = "".join(chunks)
            assert len(raw) == ref["total_chars"]
            assert hashlib.sha256(raw.encode()).hexdigest() == ref["sha256"]
            original = json.loads(raw)
            assert original["run_metadata"] == manifest["run_metadata"]
            assert (
                original["run_metadata"]["run_id"] == inline["run_metadata"]["run_id"]
            )
            checked = verify_fengshui_reading(
                original, trusted_run_metadata=deepcopy(manifest["run_metadata"])
            )
            assert checked["status"] == "verified_served_fixed_reading"
            assert checked["host_guest_relation_count"] == 8
            assert checked["host_guest_literal_source_differences"] == 1
            assert checked["host_guest_coverage_verified"] is True
            assert checked["whole_book_conformity_established"] is False

    asyncio.run(read_original())
