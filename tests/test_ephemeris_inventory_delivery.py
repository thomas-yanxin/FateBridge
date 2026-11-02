"""Large runtime inventories remain lossless without crowding out the analysis."""

import asyncio
import copy
import hashlib
import json

import pytest

from fatebridge.application import result_delivery as delivery
from fatebridge.application.examples import suggested_fields
from fatebridge.services import replay_metadata
from tests.fixtures.mcp_receipt import assert_same_run_receipt
from tests.test_agentic_nested_outputs import SPECS, call_cli, inputs, native, rest
from tests.test_result_delivery import reconstruct, store

PATH = "run_metadata.runtime"


def inventory():
    # Transport fixture only; these are not claimed to be installed ephemeris
    # files or reference observations for any astronomical accuracy metric.
    files = {
        f"0/test_{n:03d}.se1": hashlib.sha256(str(n).encode()).hexdigest()
        for n in range(100)
    }
    return {
        "scope": "synthetic delivery fixture, no source or accuracy claim",
        "files": files,
        "sha256": replay_metadata.digest(files),
    }


@pytest.mark.parametrize("compact", [True, False])
def test_large_inventory_keeps_business_and_exact_receipt_in_same_run(store, compact):
    source = inventory()
    original = {
        "analysis": {"conclusion": "测试字段" * 80},
        "run_metadata": {
            "run_id": "original",
            "tool_name": "bazi_career",
            "runtime": {"ephemeris": source},
        },
    }
    before = copy.deepcopy(original)
    result = delivery.bound_response(original, 4096, compact=compact)
    assert len(delivery._json(result, compact)) <= 4096
    assert result["analysis"] == original["analysis"]
    assert result["run_metadata"]["run_id"] == "original"
    projected = result["run_metadata"]["runtime"]
    assert projected["ephemeris_inventory_sha256"] == source["sha256"]
    assert projected["ephemeris_files_count"] == 100
    assert projected["delivery_path"] == PATH
    assert "ephemeris" not in projected  # Never masquerade as an empty inventory.
    ref = result["result_delivery"]
    assert ref["deferred_fields"] == [PATH]
    assert (
        reconstruct(store, ref["result_id"], PATH)
        == original["run_metadata"]["runtime"]
    )
    assert reconstruct(store, ref["result_id"]) == original == before
    assert delivery.bound_response(original, 0) is original


@pytest.mark.parametrize("limit", [4096, 8192])
def test_real_career_stays_readable_with_large_inventory_across_transports(
    monkeypatch, limit, rest, tmp_path, capsys, store
):
    source = inventory()
    monkeypatch.setattr(
        replay_metadata, "ephemeris_inventory", lambda: copy.deepcopy(source)
    )
    spec = SPECS["bazi_career"]
    payload = inputs(spec)
    fields = suggested_fields(spec) if limit == 8192 else None
    opts = {"include_snapshot_text": False, "response_char_limit": limit}
    params = [("include_snapshot_text", "false"), ("response_char_limit", str(limit))]
    flags = [
        "--compact",
        "--include-snapshot-text",
        "false",
        "--response-char-limit",
        str(limit),
    ]
    if fields:
        opts.update(fields=fields, strict_fields=True)
        params += [("fields", f) for f in fields] + [("strict_fields", "true")]
        flags += ["--fields", *fields, "--strict-fields", "true"]
    response = rest.post(spec.rest_path, json=payload, params=params)
    protocol = asyncio.run(native(spec, payload, **opts))
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    for result in (response.json(), protocol.structured_content, cli):
        assert (
            len(json.dumps(result, ensure_ascii=False, separators=(",", ":"))) <= limit
        )
        ref = result["result_delivery"]
        original = reconstruct(store, ref["result_id"])
        assert original["run_metadata"]["run_id"] == result["run_metadata"]["run_id"]
        assert original["run_metadata"]["runtime"]["ephemeris"] == source
        assert (
            reconstruct(store, ref["result_id"], PATH)
            == original["run_metadata"]["runtime"]
        )
        if fields:
            assert result["career_analysis"] == original["career_analysis"]
            assert PATH in ref["deferred_fields"]
            assert set(ref["deferred_fields"]) <= {
                PATH,
                "run_metadata.provenance",
                "run_metadata.determinism",
            }
            assert_same_run_receipt(
                result["run_metadata"],
                original["run_metadata"],
                deferred_fields=ref["deferred_fields"],
            )
        else:
            assert original["career_analysis"]["evidence_chain"]["structure_checks"]
