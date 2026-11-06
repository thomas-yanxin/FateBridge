"""Actual MCP replies can be reviewed without starting any model or sub-agent."""

import asyncio
import json
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from fatebridge.validation.agent_capture import CaptureJournal, read_capture


def test_journal_refuses_existing_paths_and_detects_modified_payload(tmp_path):
    p = tmp_path / "capture.jsonl"
    journal = CaptureJournal(p)
    asyncio.run(
        journal.append({"event": "tool_call", "tool": "meihua_cast", "value": 1})
    )
    journal.close()
    assert read_capture(p)[0]["value"] == 1
    with pytest.raises(FileExistsError):
        CaptureJournal(p)
    record = json.loads(p.read_text())
    record["value"] = 2
    p.write_text(json.dumps(record) + "\n")
    with pytest.raises(ValueError, match="bytes changed"):
        read_capture(p)


def test_journal_refuses_existing_symlink(tmp_path):
    original = tmp_path / "original"
    original.write_text("preserve")
    link = tmp_path / "link"
    link.symlink_to(original)
    with pytest.raises(FileExistsError):
        CaptureJournal(link)
    assert original.read_text() == "preserve"


@pytest.mark.asyncio
async def test_independent_stdio_logs_actual_projected_reply_and_same_run_resource(
    tmp_path,
):
    root = Path(__file__).resolve().parents[2]
    path = tmp_path / "actual-mcp.jsonl"
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "fatebridge.validation.agent_capture"],
        cwd=str(root),
        env={
            "PYTHONPATH": str(root / "src"),
            "FATEBRIDGE_EVALUATION_LOG": str(path),
            "FATEBRIDGE_MCP_FAMILIES": "divination",
        },
        log_file=tmp_path / "stderr.log",
    )
    arguments = {
        "casting": {"method": "object_count", "count": 9, "hour_branch": "酉"},
        "fields": ["meihua.seed", "meihua.counting_variants"],
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 8192,
    }
    async with Client(transport) as client:
        names = {tool.name for tool in await client.list_tools()}
        assert "meihua_cast" in names and "bazi_birth" not in names
        result = await client.call_tool("meihua_cast", arguments, raise_on_error=False)
        assert not result.is_error
        data = result.structured_content
        uri = data["result_delivery"]["first_page_uri"]
        page = await client.read_resource(uri)
        assert page
        bad = await client.call_tool(
            "meihua_cast",
            {"casting": {"method": "object_count", "count": True, "hour_branch": "酉"}},
            raise_on_error=False,
        )
        assert bad.is_error
    records = read_capture(path)
    catalogs = [r for r in records if r["event"] == "tool_list"]
    assert catalogs and "meihua_cast" in catalogs[0]["tool_names"]
    assert "bazi_birth" not in catalogs[0]["tool_names"]
    assert len(catalogs[0]["tool_schema_sha256"]["meihua_cast"]) == 64
    calls = [r for r in records if r["event"] == "tool_call"]
    assert len(calls) == 2
    assert calls[0]["arguments"] == arguments
    assert calls[0]["result"]["structured_content"] == data
    assert (
        calls[0]["result"]["structured_content"]["run_metadata"]["run_id"]
        == data["run_metadata"]["run_id"]
    )
    assert any(r["event"] == "resource_read" and r["uri"] == uri for r in records)
    assert calls[1]["outcome"] == "raised_error" or calls[1]["result"]["is_error"]
