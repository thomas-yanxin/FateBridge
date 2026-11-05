"""Resolve a same-result page locator; never replace a calculation by a rerun."""

import hashlib
import json

from tests.fixtures.mcp_receipt import assert_same_run_receipt


async def first_page_uri(client, reference):
    expected = f"fatebridge://results/{reference['result_id']}/pages/0"
    if "first_page_uri" in reference:
        assert reference["first_page_uri"] == expected
        return expected
    # The published compact-reference contract permits this duplicate URI to
    # be omitted. The immutable manifest still identifies the same document.
    assert reference.get("compact_reference") is True
    assert reference["manifest_uri"] == f"fatebridge://results/{reference['result_id']}"
    manifest = json.loads(
        (await client.read_resource(reference["manifest_uri"]))[0].text
    )
    assert manifest["result_id"] == reference["result_id"]
    assert manifest["sha256"] == reference["sha256"]
    if "total_chars" in reference:
        assert manifest["total_chars"] == reference["total_chars"]
    assert manifest["first_page_uri"] == expected
    return expected


async def read_full_result(client, payload):
    """Read the original artifact and verify its hash and declared receipt fields."""
    reference = payload.get("result_delivery")
    if reference is None:
        return payload
    pieces = []
    uri = await first_page_uri(client, reference)
    while uri:
        page = json.loads((await client.read_resource(uri))[0].text)
        pieces.append(page["text"])
        uri = page["next_uri"]
    text = "".join(pieces)
    assert hashlib.sha256(text.encode()).hexdigest() == reference["sha256"]
    complete = json.loads(text)
    assert_same_run_receipt(
        payload["run_metadata"],
        complete["run_metadata"],
        deferred_fields=reference["deferred_fields"],
    )
    return complete
