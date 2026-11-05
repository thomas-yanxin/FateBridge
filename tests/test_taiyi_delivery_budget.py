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
FREEZE = "aaed95d90967e06b9afb420c0200c0c999d2d461031167405eb8e20de11dfc96"


def cases():
    assert hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest() == FREEZE
    frozen = json.loads((CORPUS / "freeze.json").read_text())
    for name, sha in frozen["files"].items():
        assert hashlib.sha256((CORPUS / name).read_bytes()).hexdigest() == sha
    return json.loads((CORPUS / "cases.json").read_text())["cases"]


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
