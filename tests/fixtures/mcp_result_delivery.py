"""Read original same-run MCP pages and validate their manifest and receipt."""

import json


def assert_same_run_receipt(inline, full, *, deferred_fields=None):
    # Restore only explicitly declared supplementary receipt fields, then
    # compare every value with the complete retained result.
    restored = dict(inline)
    declared = (
        None
        if deferred_fields is None
        else {path for path in deferred_fields if path.startswith("run_metadata.")}
    )
    restored_paths = set()
    for path in deferred_fields or ():
        if not path.startswith("run_metadata."):
            continue  # whole-result paging is separate from this receipt check
        assert path in {
            "run_metadata.runtime",
            "run_metadata.provenance",
            "run_metadata.determinism",
            "run_metadata.calculation_evidence",
        }, path
        key = path.removeprefix("run_metadata.")
        if key == "calculation_evidence":
            assert inline[key] == {
                "delivery_path": path,
                "coverage": full[key].get("coverage"),
            }
            restored[key] = full[key]
            restored_paths.add(path)
        elif key != "runtime":
            assert key not in inline and key in full, key
            restored[key] = full[key]
            restored_paths.add(path)
    summary = inline.get("runtime", {})
    if summary.get("delivery_path") == "run_metadata.runtime":
        runtime = full["runtime"]
        files = runtime["ephemeris"]["files"]
        assert type(summary["ephemeris_files_count"]) is int
        assert summary["ephemeris_files_count"] == len(files)
        restored["runtime"] = runtime
        restored_paths.add("run_metadata.runtime")
    if declared is not None:
        assert declared == restored_paths
    assert restored == full
    assert json.dumps(restored, sort_keys=True) == json.dumps(full, sort_keys=True)


async def read_full_result(client, payload):
    """Read the original artifact with exact page, manifest and receipt checks."""
    reference = payload.get("result_delivery")
    if reference is None:
        return payload
    result_id = reference["result_id"]
    base_uri = f"fatebridge://results/{result_id}"
    expected_first = f"{base_uri}/pages/0"
    assert reference["mode"] == "paged"
    assert reference["manifest_uri"] == base_uri
    if "first_page_uri" in reference:
        assert reference["first_page_uri"] == expected_first
    else:
        assert reference.get("compact_reference") is True
    manifest = json.loads((await client.read_resource(base_uri))[0].text)
    assert manifest["result_id"] == result_id
    assert manifest["total_chars"] == reference["total_chars"]
    assert manifest["first_page_uri"] == expected_first
    assert manifest["run_metadata"]["run_id"] == payload["run_metadata"]["run_id"]
    uri, offset, pieces = expected_first, 0, []
    while uri is not None:
        assert uri == f"{base_uri}/pages/{offset}"
        page = json.loads((await client.read_resource(uri))[0].text)
        assert page["result_id"] == result_id
        assert page["total_chars"] == reference["total_chars"]
        assert page["offset"] == offset
        assert page["text"]
        pieces.append(page["text"])
        offset += len(page["text"])
        next_offset = offset if offset < reference["total_chars"] else None
        assert page["next_offset"] == next_offset
        assert page["next_uri"] == (
            f"{base_uri}/pages/{next_offset}" if next_offset is not None else None
        )
        uri = page["next_uri"]
    text = "".join(pieces)
    assert len(text) == reference["total_chars"]
    complete = json.loads(text)
    assert complete["run_metadata"] == manifest["run_metadata"]
    assert_same_run_receipt(
        payload["run_metadata"],
        complete["run_metadata"],
        deferred_fields=reference["deferred_fields"],
    )
    return complete
