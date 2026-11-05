"""Large runtime inventories remain lossless without crowding out the analysis."""

import copy
import hashlib
import json

import pytest

from fatebridge.application import result_delivery as delivery
from fatebridge.application.examples import suggested_fields
from fatebridge.services import replay_metadata
from tests.fixtures.mcp_receipt import assert_same_run_receipt
from tests.support.result_delivery import reconstruct, store
from tests.support.transports import SPECS, inputs, rest, surface_calls

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


def test_semicolon_directory_inventory_is_equal_across_transports(
    monkeypatch, tmp_path, surface_calls
):
    monkeypatch.chdir(tmp_path)
    for name in ("first", "second"):
        directory = tmp_path / name
        directory.mkdir()
        # Small auxiliary file, tracked by provenance but unused in this chart.
        (directory / "seasnam.txt").write_text(name)
    monkeypatch.setenv("SE_EPHE_PATH", "first;second")
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    expected = replay_metadata.ephemeris_inventory()
    assert set(expected["files"]) == {"0/seasnam.txt", "1/seasnam.txt"}
    spec = SPECS["bazi_career"]
    payload = inputs(spec)
    options = dict(
        fields=[PATH],
        strict_fields=True,
        response_char_limit=0,
        include_snapshot_text=False,
    )
    response, protocol, code, cli = surface_calls(
        spec,
        payload,
        params=options,
        options=options,
        flags=[
            "--fields",
            PATH,
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
        ],
        cli_first=False,
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    for output in (response.json(), protocol.structured_content, cli):
        assert output["run_metadata"]["runtime"]["ephemeris"] == expected


@pytest.mark.parametrize("limit", [4096, 8192])
def test_real_career_stays_readable_with_large_inventory_across_transports(
    monkeypatch, limit, store, surface_calls
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
    response, protocol, code, cli = surface_calls(
        spec, payload, params=params, options=opts, flags=flags, cli_first=False
    )
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
            for path in ref["deferred_fields"]:
                assert path.startswith("run_metadata.")
                key = path.removeprefix("run_metadata.")
                assert (
                    reconstruct(store, ref["result_id"], path)
                    == original["run_metadata"][key]
                )
            assert_same_run_receipt(
                result["run_metadata"],
                original["run_metadata"],
                deferred_fields=ref["deferred_fields"],
            )
        else:
            assert original["career_analysis"]["evidence_chain"]["structure_checks"]
