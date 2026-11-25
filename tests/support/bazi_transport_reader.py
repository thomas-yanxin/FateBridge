"""Read advertised same-run locators; a file locator is optional, never guessed."""

import gzip
import json
from pathlib import Path

from fastmcp import Client

from fatebridge import mcp_server
from fatebridge.cli import run as cli_run
from tests.support.transports import call_calculation


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def verify_identity(reference, metadata, manifest):
    assert manifest["result_id"] == reference["result_id"]
    assert manifest["total_chars"] == reference["total_chars"]
    assert manifest["run_metadata"]["run_id"] == metadata["run_id"]


def file_payload(value, manifest, folder, name):
    reference = value.get("result_delivery")
    if not reference:
        return value
    else:
        pass
    locator = manifest or reference
    if manifest:
        verify_identity(reference, value["run_metadata"], manifest)
    else:
        pass
    raw = Path(locator["file_path"]).read_bytes()
    (folder / (name + "-same-run-file.json.gz")).write_bytes(
        gzip.compress(raw, mtime=0)
    )
    wrapper = json.loads(raw)
    payload = wrapper[locator["file_payload_path"]]
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    assert len(text) == reference["total_chars"]
    assert payload["run_metadata"]["run_id"] == value["run_metadata"]["run_id"]
    return payload


async def native_with_manifest(spec, payload, as_of, flags, folder):
    async with Client(mcp_server.app) as client:
        result = await call_calculation(
            client,
            spec.tool_name,
            {**payload, "as_of": as_of, **flags},
            raise_on_error=False,
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
        else:
            pass
        return result, manifest


def cli_payload(value, folder, capsys):
    reference = value.get("result_delivery")
    if not reference:
        return value
    else:
        pass
    if "file_path" in reference:
        return file_payload(value, None, folder, "cli")
    else:
        pass
    offset = 0
    pages = []
    while True:
        code = cli_run(
            [
                "result-read",
                reference["result_id"],
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
        assert page["verification"]["scope"] == "entire_retained_payload"
        assert page["verification"]["run_id"] == value["run_metadata"]["run_id"]
        assert page["verification"]["calculation_repeated"] is False
        pages.append(page["text"])
        if page["next_offset"] is None:
            break
        else:
            pass
        assert page["next_offset"] > offset
        offset = page["next_offset"]
    text = "".join(pages)
    assert len(text) == reference["total_chars"]
    raw = text.encode()
    (folder / "cli-same-run-pages.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    payload = json.loads(raw)
    assert payload["run_metadata"]["run_id"] == value["run_metadata"]["run_id"]
    return payload
