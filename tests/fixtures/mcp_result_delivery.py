"""Resolve a same-result page locator; never replace a calculation by a rerun."""

import json


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
