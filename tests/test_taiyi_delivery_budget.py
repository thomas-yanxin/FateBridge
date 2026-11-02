"""Keep actual first-response facts while paging only their original receipt."""

import hashlib
import json
import sys
import types
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.application import result_delivery
from fatebridge.application.result_delivery import ResultStore, bound_response
from fatebridge.core.response_models import RunMetadata
from tests.fixtures.mcp_receipt import assert_same_run_receipt

CORPUS = Path(__file__).parent / "fixtures/taiyi_delivery_v42"
FREEZE = "19319050cf66c4e9cb8fc5871d2645c04a244c343c202a599fa1158c3d5d1527"


def cases():
    assert hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest() == FREEZE
    frozen = json.loads((CORPUS / "freeze.json").read_text())
    for name, sha in frozen["files"].items():
        assert hashlib.sha256((CORPUS / name).read_bytes()).hexdigest() == sha
    return json.loads((CORPUS / "cases.json").read_text())["cases"]


@pytest.mark.parametrize("case", cases())
def test_historical_twelve_payloads_keep_original_inline_policy_and_same_run(
    case, monkeypatch, tmp_path
):
    source = (
        Path(__file__).parent
        / "fixtures/architecture_refactor_v1/taiyi-inline-result-delivery.py"
    )
    raw = source.read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "57025b576c03349a491d16d4c312da50be9b9669fc18da9d388c52b93721cd6a"
    )
    historical = types.ModuleType("fatebridge.application.historical_taiyi_delivery")
    historical.__file__ = result_delivery.__file__
    monkeypatch.setitem(sys.modules, historical.__name__, historical)
    exec(compile(raw, historical.__file__, "exec"), historical.__dict__)
    store = historical.ResultStore(tmp_path / "delivery")
    monkeypatch.setattr(historical, "RESULT_STORE", store)
    payload = deepcopy(case["payload"])
    untouched = deepcopy(payload)
    first = historical.bound_response(payload, response_char_limit=8192)
    RunMetadata.model_validate(first["run_metadata"])
    assert len(json.dumps(first, ensure_ascii=False, separators=(",", ":"))) <= 8192
    assert payload == untouched
    ref = first["result_delivery"]
    assert all(
        path == "run_metadata" or path.startswith("run_metadata.")
        for path in ref["deferred_fields"]
    )
    assert {
        k: v for k, v in first.items() if k not in {"run_metadata", "result_delivery"}
    } == {k: v for k, v in untouched.items() if k != "run_metadata"}
    manifest = store.manifest(ref["result_id"])
    assert manifest["sha256"] == ref["sha256"]
    assert manifest["run_metadata"]["run_id"] == untouched["run_metadata"]["run_id"]
    assert store.get(ref["result_id"]) == untouched
    assert (
        hashlib.sha256(
            json.dumps(untouched, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        == ref["sha256"]
    )
    restored = deepcopy(first["run_metadata"])
    for path in ref["deferred_fields"]:
        if path == "run_metadata":
            assert restored == {key: untouched["run_metadata"][key] for key in restored}
            assert set(restored) == {
                "run_id",
                "trace_id",
                "tool_name",
                "generated_at",
                "engine",
                "engine_is_approximate",
            }
            restored = untouched["run_metadata"]
            continue
        key = path.removeprefix("run_metadata.")
        restored[key] = untouched["run_metadata"][key]
    assert restored == untouched["run_metadata"]


@pytest.mark.parametrize("case", cases())
def test_current_twelve_payloads_keep_essential_receipts_and_exact_same_run(
    case, monkeypatch, tmp_path
):
    store = ResultStore(tmp_path / "delivery")
    monkeypatch.setattr(result_delivery, "RESULT_STORE", store)
    payload = deepcopy(case["payload"])
    untouched = deepcopy(payload)
    first = bound_response(payload, response_char_limit=8192)
    encode = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    assert len(encode(first)) <= 8192 and payload == untouched
    RunMetadata.model_validate(first["run_metadata"])
    ref = first["result_delivery"]
    assert "run_metadata" not in ref["deferred_fields"]
    full = store.get(ref["result_id"])
    assert full == untouched
    assert hashlib.sha256(encode(full).encode()).hexdigest() == ref["sha256"]
    assert_same_run_receipt(
        first["run_metadata"],
        full["run_metadata"],
        deferred_fields=ref["deferred_fields"],
    )
    for key in (
        "run_id",
        "trace_id",
        "input_sha256",
        "contract_sha256",
        "business_output_sha256",
    ):
        assert first["run_metadata"][key] == full["run_metadata"][key]
    business_deferred = {
        p for p in ref["deferred_fields"] if not p.startswith("run_metadata.")
    }
    assert business_deferred == set(full) - set(first)
    for key in set(full) & set(first) - {"run_metadata"}:
        assert first[key] == full[key]
    if business_deferred:
        # Prove that the complete business cannot fit even after removing all
        # permitted supplementary receipt fields and duplicate locators.
        minimal_receipt = {
            k: v
            for k, v in first["run_metadata"].items()
            if k not in {"provenance", "determinism"}
        }
        minimal_reference = {k: ref[k] for k in ("result_id", "sha256", "manifest_uri")}
        assert (
            len(
                encode(
                    {
                        **full,
                        "run_metadata": minimal_receipt,
                        "result_delivery": minimal_reference,
                    }
                )
            )
            > 8192
        )
