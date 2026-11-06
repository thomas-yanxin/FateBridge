"""Declared receipt paging restores every field; business omissions still fail."""

import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from tests.fixtures.mcp_receipt import verified_inline_business
from tests.fixtures.mcp_result_delivery import assert_same_run_receipt, read_full_result


class Pages:
    def __init__(self, text):
        self.text = text
        self.calls = 0

    async def read_resource(self, uri):
        self.calls += 1
        if uri == "fatebridge://results/unit":
            data = {
                "result_id": "unit",
                "first_page_uri": "fatebridge://results/unit/pages/0",
                "total_chars": len(self.text),
                "run_metadata": json.loads(self.text)["run_metadata"],
            }
        else:
            assert uri == "fatebridge://results/unit/pages/0"
            data = {
                "result_id": "unit",
                "offset": 0,
                "next_offset": None,
                "text": self.text,
                "next_uri": None,
                "total_chars": len(self.text),
            }
        return [SimpleNamespace(text=json.dumps(data))]


def fixture():
    files = ["source.se1"]
    full = {
        "ziwei_birth": {"star": "紫微", "branch": "子"},
        "run_metadata": {
            "run_id": "unit",
            "tool_name": "ziwei_birth",
            "provenance": {"source": "the original source"},
            "determinism": {"scope": "the original scope"},
            "runtime": {
                "ephemeris": {"files": files},
            },
        },
    }
    text = json.dumps(full, ensure_ascii=False, separators=(",", ":"))
    inline = deepcopy(full)
    inline["run_metadata"].pop("provenance")
    inline["run_metadata"].pop("determinism")
    inline["run_metadata"]["runtime"] = {
        "delivery_path": "run_metadata.runtime",
        "ephemeris_files_count": 1,
    }
    inline["result_delivery"] = {
        "mode": "paged",
        "result_id": "unit",
        "manifest_uri": "fatebridge://results/unit",
        "total_chars": len(text),
        "first_page_uri": "fatebridge://results/unit/pages/0",
        "deferred_fields": [
            "run_metadata.runtime",
            "run_metadata.provenance",
            "run_metadata.determinism",
        ],
    }
    return full, inline, Pages(text)


@pytest.mark.parametrize("compact", [False, True])
def test_explicit_metadata_paging_restores_the_exact_original_receipt(compact):
    full, inline, client = fixture()
    if compact:
        inline["result_delivery"].pop("first_page_uri")
        inline["result_delivery"]["compact_reference"] = True
    before = deepcopy(inline)
    restored = asyncio.run(verified_inline_business(client, inline))
    assert restored == full
    assert inline == before
    assert client.calls == 2


@pytest.mark.parametrize(
    "target,field,value",
    [
        ("manifest", "result_id", "different"),
        ("manifest", "total_chars", 0),
        ("manifest", "first_page_uri", "fatebridge://results/different/pages/0"),
        ("page", "result_id", "different"),
        ("page", "total_chars", 0),
        ("page", "offset", 1),
        ("page", "next_offset", 0),
        ("page", "next_uri", "fatebridge://results/unit/pages/0"),
    ],
)
def test_original_readback_rejects_mismatched_manifest_and_page_identity(
    target, field, value
):
    _, inline, client = fixture()

    class CorruptPages(Pages):
        async def read_resource(self, uri):
            response = await super().read_resource(uri)
            if (uri == "fatebridge://results/unit") == (target == "manifest"):
                data = json.loads(response[0].text)
                data[field] = value
                response[0].text = json.dumps(data)
            return response

    with pytest.raises(AssertionError):
        asyncio.run(read_full_result(CorruptPages(client.text), inline))


@pytest.mark.parametrize(
    "change",
    [
        "missing_declaration",
        "extra_declaration",
        "identity",
        "count",
        "boolean_count",
        "boolean_coercion",
    ],
)
def test_receipt_recovery_requires_exact_declarations_and_essential_identity(change):
    full, inline, _ = fixture()
    receipt = inline["run_metadata"]
    deferred = inline["result_delivery"]["deferred_fields"]
    assert_same_run_receipt(receipt, full["run_metadata"], deferred_fields=deferred)
    if change == "missing_declaration":
        deferred[:] = ["run_metadata.runtime"]
    elif change == "extra_declaration":
        deferred.append("run_metadata.unused")
    elif change == "identity":
        receipt.pop("run_id")
        deferred.append("run_metadata.run_id")
    elif change == "count":
        receipt["runtime"]["ephemeris_files_count"] = 2
    elif change == "boolean_count":
        receipt["runtime"]["ephemeris_files_count"] = True
    else:
        full["run_metadata"]["determinism"]["randomness_used"] = False
        receipt["determinism"] = {
            **full["run_metadata"]["determinism"],
            "randomness_used": 0,
        }
        deferred.remove("run_metadata.determinism")
    with pytest.raises(AssertionError):
        assert_same_run_receipt(receipt, full["run_metadata"], deferred_fields=deferred)


@pytest.mark.parametrize(
    "change",
    [
        "business",
        "missing_star",
        "undeclared",
        "forged_provenance",
        "identity",
        "environment",
        "artifact",
        "business_deferral",
        "identity_deferral",
        "duplicate",
    ],
)
def test_receipt_restoration_never_hides_missing_or_changed_facts(change):
    _, p, client = fixture()
    ref = p["result_delivery"]
    if change == "business":
        p["ziwei_birth"]["branch"] = "午"
    elif change == "missing_star":
        p["ziwei_birth"].pop("star")
    elif change == "undeclared":
        ref["deferred_fields"].remove("run_metadata.provenance")
    elif change == "forged_provenance":
        p["run_metadata"]["provenance"] = {"source": "forged"}
    elif change == "identity":
        p["run_metadata"]["run_id"] = "different"
    elif change == "environment":
        p["run_metadata"]["runtime"]["ephemeris_files_count"] = 2
    elif change == "artifact":
        client.text = client.text.replace("紫微", "太阳")
    elif change == "business_deferral":
        ref["deferred_fields"].append("ziwei_birth")
    elif change == "identity_deferral":
        ref["deferred_fields"].append("run_metadata.run_id")
    else:
        ref["deferred_fields"].append("run_metadata.provenance")
    with pytest.raises(AssertionError):
        asyncio.run(verified_inline_business(client, p))
