"""Verify inline business facts when a large runtime receipt is referenced."""

import hashlib
import json

from fatebridge.utils.json_digest import digest as evidence_digest


def assert_same_run_receipt(inline, full, *, deferred_fields=None):
    # The caller first verifies the complete artifact against the original
    # delivery hash. Only explicitly declared supplementary receipt fields
    # may be restored; identity/hashes or undeclared omissions never pass.
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
                "sha256": evidence_digest(full[key]),
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
        assert summary["environment_sha256"] == runtime["environment_sha256"]
        assert summary["ephemeris_inventory_sha256"] == runtime["ephemeris"]["sha256"]
        files = runtime["ephemeris"]["files"]
        digest = hashlib.sha256(
            json.dumps(
                files, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        assert summary["ephemeris_inventory_sha256"] == digest
        assert type(summary["ephemeris_files_count"]) is int
        assert summary["ephemeris_files_count"] == len(files)
        restored["runtime"] = runtime
        restored_paths.add("run_metadata.runtime")
    if declared is not None:
        assert declared == restored_paths
    assert restored == full
    assert json.dumps(restored, sort_keys=True) == json.dumps(full, sort_keys=True)


async def verified_inline_business(client, payload):
    assert len(json.dumps(payload, ensure_ascii=False, separators=(",", ":"))) <= 8192
    delivery = payload.get("result_delivery")
    if delivery is None:
        return payload
    # This is never permission to hide a star, position, source row or other
    # business result behind pagination in a first-view budget assertion.
    deferred = delivery["deferred_fields"]
    assert deferred and len(deferred) == len(set(deferred)), delivery
    assert set(deferred) <= {
        "run_metadata.runtime",
        "run_metadata.provenance",
        "run_metadata.determinism",
        "run_metadata.calculation_evidence",
    }, delivery
    # The compact manifest may omit the redundant first-page URI.
    text = ""
    uri = delivery.get("first_page_uri")
    if uri is None:
        uri = f"fatebridge://results/{delivery['result_id']}/pages/0"
    while uri:
        page = json.loads((await client.read_resource(uri))[0].text)
        text += page["text"]
        uri = page["next_uri"]
    assert hashlib.sha256(text.encode()).hexdigest() == delivery["sha256"]
    full = json.loads(text)
    assert_same_run_receipt(
        payload["run_metadata"], full["run_metadata"], deferred_fields=deferred
    )
    inline = {
        k: v for k, v in payload.items() if k not in ("run_metadata", "result_delivery")
    }
    stored = {k: v for k, v in full.items() if k != "run_metadata"}
    assert inline == stored
    return {**inline, "run_metadata": full["run_metadata"]}
