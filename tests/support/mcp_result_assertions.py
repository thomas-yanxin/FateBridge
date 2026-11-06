"""Strict bounded first views and original same-run MCP resource proofs."""

import json

from tests.fixtures.mcp_result_delivery import read_full_result


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
    original = await read_full_result(client, body)
    inline_business = {
        k: v for k, v in body.items() if k not in {"run_metadata", "result_delivery"}
    }
    assert inline_business == without_transport(original)
    return original
