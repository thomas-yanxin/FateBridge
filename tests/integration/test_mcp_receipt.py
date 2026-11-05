"""Declared receipt paging restores every field; business omissions still fail."""

import asyncio
import hashlib
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from tests.fixtures.mcp_receipt import verified_inline_business


class Pages:
    def __init__(self, text):
        self.text = text
        self.calls = 0

    async def read_resource(self, uri):
        self.calls += 1
        assert uri == "fatebridge://results/unit/pages/0"
        return [SimpleNamespace(text=json.dumps({"text": self.text, "next_uri": None}))]


def fixture():
    files = {"source.se1": "a" * 64}
    digest = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    full = {
        "ziwei_birth": {"star": "紫微", "branch": "子"},
        "run_metadata": {
            "run_id": "unit",
            "tool_name": "ziwei_birth",
            "business_output_sha256": "c" * 64,
            "provenance": {"source": "the original source"},
            "determinism": {"scope": "the original scope"},
            "runtime": {
                "environment_sha256": "b" * 64,
                "ephemeris": {"files": files, "sha256": digest},
            },
        },
    }
    text = json.dumps(full, ensure_ascii=False, separators=(",", ":"))
    inline = deepcopy(full)
    inline["run_metadata"].pop("provenance")
    inline["run_metadata"].pop("determinism")
    inline["run_metadata"]["runtime"] = {
        "delivery_path": "run_metadata.runtime",
        "environment_sha256": "b" * 64,
        "ephemeris_inventory_sha256": digest,
        "ephemeris_files_count": 1,
    }
    inline["result_delivery"] = {
        "first_page_uri": "fatebridge://results/unit/pages/0",
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "deferred_fields": [
            "run_metadata.runtime",
            "run_metadata.provenance",
            "run_metadata.determinism",
        ],
    }
    return full, inline, Pages(text)


def test_explicit_metadata_paging_restores_the_exact_original_receipt():
    full, inline, client = fixture()
    before = deepcopy(inline)
    restored = asyncio.run(verified_inline_business(client, inline))
    assert restored == full
    assert inline == before
    assert client.calls == 1


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
        p["run_metadata"]["runtime"]["environment_sha256"] = "d" * 64
    elif change == "artifact":
        client.text = client.text.replace("紫微", "太阳")
    elif change == "business_deferral":
        ref["deferred_fields"].append("ziwei_birth")
    elif change == "identity_deferral":
        ref["deferred_fields"].append("run_metadata.business_output_sha256")
    else:
        ref["deferred_fields"].append("run_metadata.provenance")
    with pytest.raises(AssertionError):
        asyncio.run(verified_inline_business(client, p))
