"""Verify reviewed/retired inputs and full same-run MCP delivery in one package."""

import argparse
import asyncio
import gzip
import hashlib
import json
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

BOOT = """import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import fatebridge.core.source_annotations as module
assert Path(module.__file__).resolve()==Path(sys.argv[1]).resolve()/'fatebridge/core/source_annotations.py'
from fatebridge.mcp_server import main
main()
"""


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def read_full_payload(client, payload, expected_business_hash=None):
    delivery = payload.get("result_delivery")
    if not delivery:
        return payload, [], None
    manifest = None
    uri = delivery.get("first_page_uri")
    if uri is None:
        manifest = json.loads(
            (await client.read_resource(delivery["manifest_uri"]))[0].text
        )
        assert manifest["result_id"] == delivery["result_id"]
        assert manifest["sha256"] == delivery["sha256"]
        uri = manifest["first_page_uri"]
    text, pages = "", []
    while uri:
        assert len(pages) < 128
        page = json.loads((await client.read_resource(uri))[0].text)
        assert page["result_id"] == delivery["result_id"]
        assert page["sha256"] == delivery["sha256"]
        assert page["offset"] == len(text)
        text += page["text"]
        if page["next_offset"] is not None:
            assert page["next_offset"] == len(text)
        pages.append(page)
        uri = page["next_uri"]
    assert hashlib.sha256(text.encode()).hexdigest() == delivery["sha256"]
    full = json.loads(text)
    inline, restored = payload["run_metadata"], full["run_metadata"]
    assert restored["run_id"] == inline["run_id"]
    for field in (
        "trace_id",
        "tool_name",
        "generated_at",
        "engine",
        "engine_is_approximate",
        "business_output_sha256",
    ):
        if field in inline:
            assert restored[field] == inline[field]
    if "business_output_sha256" not in inline:
        assert "run_metadata" in delivery["deferred_fields"]
    if expected_business_hash is not None:
        assert restored["business_output_sha256"] == expected_business_hash
    return full, pages, manifest


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), "Preserve the first transport result"
    assert not args.output.with_suffix(
        ".receipts.jsonl"
    ).exists(), "Preserve failed call receipts"
    assert (
        sha(args.expected)
        == args.expected.with_suffix(".gz.sha256").read_text().strip()
    )
    expected = json.loads(gzip.decompress(args.expected.read_bytes()))
    package = args.package.resolve()
    index_file = expected.get("index_file", "bazi-source-annotations-v6.json")
    assert index_file in {
        "bazi-source-annotations-v6.json",
        "bazi-source-annotations-v7.json",
    }
    index_path = package / "fatebridge/data/reference" / index_file
    assert sha(index_path) == expected["index_sha256"]
    assert (
        sha(package / "fatebridge/core/source_annotations.py")
        == expected["source_loader_sha256"]
    )
    assert (
        sha(package / "fatebridge/core/output_source_annotations.py")
        == expected["output_schema_sha256"]
    )
    examples = json.loads((package / "fatebridge/data/agent_examples.json").read_text())
    fields = examples["evidence_views"]["bazi_source_compare"]["source_strength"][
        "fields"
    ]
    transport = StdioTransport(
        command=sys.executable,
        args=["-I", "-c", BOOT, str(package)],
        cwd="/tmp",
        env={
            "FATEBRIDGE_MCP_SCENARIOS": "onda-xingpan",
            "FATEBRIDGE_MCP_FAMILIES": "bazi",
            "FATEBRIDGE_MCP_TOOL_SCOPE": "topic",
        },
        log_file=args.output.with_suffix(".stderr.log"),
    )
    records, pages_total = [], 0
    async with Client(transport, timeout=300) as client:
        definitions = {t.name: t for t in await client.list_tools()}
        assert set(definitions["bazi_source_compare"].inputSchema["required"]) == {
            "year_pillar",
            "month_pillar",
            "day_pillar",
            "hour_pillar",
        }
        calls = [(c, project) for c in expected["cases"] for project in (False, True)]
        calls.append((expected["cases"][0], False))
        for case, project in calls:
            values = dict(
                zip(
                    ("year_pillar", "month_pillar", "day_pillar", "hour_pillar"),
                    case["pillars"],
                )
            )
            values.update(
                as_of="2026-10-12T00:00:00Z",
                response_char_limit=4096,
                include_snapshot_text=False,
            )
            if project:
                values.update(fields=fields, strict_fields=True)
            response = await client.call_tool(
                "bazi_source_compare", values, raise_on_error=False
            )
            assert not response.is_error, response
            payload = response.structured_content
            envelope = payload
            with args.output.with_suffix(".receipts.jsonl").open("a") as journal:
                journal.write(
                    json.dumps(
                        {
                            "case_id": case["case_id"],
                            "projected": project,
                            "envelope": envelope,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            wanted = case["result"]
            wanted_hash = hashlib.sha256(
                json.dumps(
                    wanted,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode()
            ).hexdigest()
            payload, pages, manifest = await read_full_payload(
                client, payload, wanted_hash
            )
            business = {k: v for k, v in payload.items() if k != "run_metadata"}
            if project:
                assert set(business) == {
                    "four_pillars",
                    "input_context",
                    "current_calculation",
                    "source_comparison",
                    "summary",
                }
                for field in (
                    "four_pillars",
                    "input_context",
                    "source_comparison",
                    "summary",
                ):
                    assert business[field] == wanted[field]
                assert business["current_calculation"] == {
                    "strength_level": wanted["current_calculation"]["strength_level"]
                }
            else:
                assert business == wanted
            records.append(
                {
                    "case_id": case["case_id"],
                    "projected": project,
                    "envelope": envelope,
                    "full_payload": payload,
                    "delivery_pages": pages,
                    "manifest": manifest,
                }
            )
            pages_total += len(pages)
        invalid = await client.call_tool(
            "bazi_source_compare", {"year_pillar": "甲子"}, raise_on_error=False
        )
        assert invalid.is_error
    result = {
        "package": str(package),
        "runner_sha256": sha(Path(__file__)),
        "expected_sha256": sha(args.expected),
        "index_sha256": sha(index_path),
        "valid_calls": len(records),
        "invalid_calls": 1,
        "same_run_pages": pages_total,
        "records": records,
        "new_model_executions": 0,
        "full_goal_complete": False,
    }
    args.output.open("x").write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    args.output.with_suffix(".sha256").open("x").write(sha(args.output) + "\n")
    print(
        json.dumps(
            {k: result[k] for k in ("valid_calls", "invalid_calls", "same_run_pages")}
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
