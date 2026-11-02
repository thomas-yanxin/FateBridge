"""Read advertised same-run locators; a file locator is optional, never guessed."""

import gzip
import hashlib
import json
from pathlib import Path

from fastmcp import Client

from fatebridge import mcp_server
from fatebridge.cli import run as cli_run


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def verify_identity(reference, metadata, manifest):
    assert manifest["result_id"] == reference["result_id"]
    assert manifest["sha256"] == reference["sha256"]
    assert manifest["run_metadata"]["run_id"] == metadata["run_id"]


def file_payload(value, manifest, folder, name):
    reference = value.get("result_delivery")
    if not reference:
        return value
    locator = manifest or reference
    if manifest:
        verify_identity(reference, value["run_metadata"], manifest)
    raw = Path(locator["file_path"]).read_bytes()
    (folder / (name + "-same-run-file.json.gz")).write_bytes(
        gzip.compress(raw, mtime=0)
    )
    wrapper = json.loads(raw)
    payload = wrapper[locator["file_payload_path"]]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    assert hashlib.sha256(encoded).hexdigest() == reference["sha256"]
    assert payload["run_metadata"]["run_id"] == value["run_metadata"]["run_id"]
    return payload


async def native_with_manifest(spec, payload, as_of, flags, folder):
    async with Client(mcp_server.app) as client:
        result = await client.call_tool(
            spec.tool_name, {**payload, "as_of": as_of, **flags}, raise_on_error=False
        )
        value = result.structured_content
        save_json(folder / "mcp-original-response.json", value)
        manifest = None
        if not result.is_error and value.get("result_delivery"):
            blocks = await client.read_resource(
                value["result_delivery"]["manifest_uri"]
            )
            manifest = json.loads(blocks[0].text)
            save_json(folder / "mcp-manifest.json", manifest)
            verify_identity(value["result_delivery"], value["run_metadata"], manifest)
        return result, manifest


def cli_payload(value, folder, capsys):
    reference = value.get("result_delivery")
    if not reference:
        return value
    if "file_path" in reference:
        return file_payload(value, None, folder, "cli")
    offset = 0
    pages = []
    while True:
        code = cli_run(
            [
                "result-read",
                reference["result_id"],
                "--sha256",
                reference["sha256"],
                "--run-id",
                value["run_metadata"]["run_id"],
                "--offset",
                str(offset),
            ]
        )
        captured = capsys.readouterr()
        (folder / ("cli-page-" + str(offset) + "-stdout.json")).write_text(captured.out)
        (folder / ("cli-page-" + str(offset) + "-stderr.txt")).write_text(captured.err)
        assert code == 0
        page = json.loads(captured.out)
        assert page["verification"]["payload_sha256"] == reference["sha256"]
        assert page["verification"]["run_id"] == value["run_metadata"]["run_id"]
        assert page["verification"]["calculation_repeated"] is False
        pages.append(page["text"])
        if page["next_offset"] is None:
            break
        assert page["next_offset"] > offset
        offset = page["next_offset"]
    raw = "".join(pages).encode()
    assert hashlib.sha256(raw).hexdigest() == reference["sha256"]
    (folder / "cli-same-run-pages.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    payload = json.loads(raw)
    assert payload["run_metadata"]["run_id"] == value["run_metadata"]["run_id"]
    return payload
