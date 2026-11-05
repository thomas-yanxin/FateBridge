"""Strict bounded first views and original same-run MCP resource proofs."""

import hashlib
import json


def without_transport(result):
    return {k: v for k, v in result.items() if k != "run_metadata"}


async def same_run_projected_response(client, result):
    """Prove complete inline business facts and read the exact original receipt.

    The default wire budget stays unchanged. Supplementary run metadata may be
    paged; business facts may not disappear from these first-view tests. Never
    recompute a tool call to obtain a purported full response.
    """
    assert not result.is_error
    assert len(result.content[0].text) <= 8192
    body = result.structured_content
    assert json.loads(result.content[0].text) == body
    if "result_delivery" not in body:
        return body
    ref = body["result_delivery"]
    assert ref["mode"] == "paged"
    assert ref["deferred_fields"]
    assert all(path.startswith("run_metadata.") for path in ref["deferred_fields"])
    manifest = json.loads((await client.read_resource(ref["manifest_uri"]))[0].text)
    assert manifest["sha256"] == ref["sha256"]
    assert manifest["run_metadata"]["run_id"] == body["run_metadata"]["run_id"]
    uri, offset, chunks = manifest["first_page_uri"], 0, []
    while uri is not None:
        assert uri == f"fatebridge://results/{ref['result_id']}/pages/{offset}"
        page = json.loads((await client.read_resource(uri))[0].text)
        assert page["result_id"] == ref["result_id"]
        assert page["sha256"] == ref["sha256"]
        assert page["total_chars"] == ref["total_chars"]
        assert page["offset"] == offset
        assert page["text"]
        chunks.append(page["text"])
        expected_offset = offset + len(page["text"])
        assert page["next_offset"] == (
            expected_offset if expected_offset < ref["total_chars"] else None
        )
        offset, uri = expected_offset, page["next_uri"]
    text = "".join(chunks)
    assert len(text) == ref["total_chars"]
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == ref["sha256"]
    original = json.loads(text)
    assert original["run_metadata"] == manifest["run_metadata"]
    inline_business = {
        k: v for k, v in body.items() if k not in {"run_metadata", "result_delivery"}
    }
    assert inline_business == without_transport(original)
    return original
