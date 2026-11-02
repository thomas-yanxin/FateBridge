"""New source identity must not displace the old complete8192-character card."""

import copy
import json

from fatebridge.application import result_delivery as delivery


def test_duplicate_page_locator_never_displaces_complete_receipt_provenance(
    tmp_path, monkeypatch
):
    store = delivery.ResultStore(tmp_path)
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    original = {
        "cycle_summary": {"reading": ""},
        "run_metadata": {
            "run_id": "same-original-run",
            "tool_name": "human_design",
            "provenance": {
                "method_id": ["source-bound-mechanics"],
                "record": "p" * 500,
            },
            "runtime": {
                "environment_sha256": "b" * 64,
                "ephemeris": {
                    "files": {f"reference-{i}.se1": "a" * 64 for i in range(120)},
                    "sha256": "c" * 64,
                },
            },
        },
    }
    # Fixed budget; vary only synthetic filler to exercise the actual boundary.
    prototype = delivery.bound_response(original, 8192)
    ref = {
        k: v
        for k, v in prototype["result_delivery"].items()
        if k
        not in ("available_fields", "total_bytes", "page_chars", "rest_manifest_path")
    }
    ref["compact_reference"] = True
    size = len(delivery._json({**prototype, "result_delivery": ref}))
    original["cycle_summary"]["reading"] = "中" * (8192 + 50 - size)
    before = copy.deepcopy(original)
    shaped = delivery.bound_response(original, 8192)
    ref = shaped["result_delivery"]
    assert len(delivery._json(shaped)) <= 8192
    assert ref["deferred_fields"] == ["run_metadata.runtime"]
    assert shaped["run_metadata"]["provenance"] == before["run_metadata"]["provenance"]
    assert shaped["cycle_summary"] == before["cycle_summary"]
    assert "first_page_uri" not in ref
    manifest = store.manifest(ref["result_id"])
    assert manifest["first_page_uri"] == ref["manifest_uri"] + "/pages/0"
    assert ref["sha256"] == manifest["sha256"]
    assert store.get(ref["result_id"]) == before == original
    file_record = json.loads(open(ref["file_path"]).read())
    assert file_record[ref["file_payload_path"]] == original
