"""Compact locators must restore the same run, with every integrity check kept."""

import asyncio
import hashlib
import json
from types import SimpleNamespace

import pytest

from scripts.validate_bazi_source_input_revision_stdio import read_full_payload


class Resources:
    def __init__(self, values):
        self.values = values
        self.calls = []

    async def read_resource(self, uri):
        self.calls.append(uri)
        return [SimpleNamespace(text=json.dumps(self.values[uri], ensure_ascii=False))]


def sample(compact):
    payload = {
        "text": "同一回执中文😀",
        "run_metadata": {
            "run_id": "original-run",
            "business_output_sha256": "business",
        },
    }
    text = json.dumps(payload, ensure_ascii=False)
    digest = hashlib.sha256(text.encode()).hexdigest()
    result_id = "same-result"
    chunks = [text[:19], text[19:]]
    values = {
        "manifest": {
            "result_id": result_id,
            "sha256": digest,
            "first_page_uri": "page0",
        }
    }
    offset = 0
    for i, chunk in enumerate(chunks):
        values[f"page{i}"] = {
            "result_id": result_id,
            "sha256": digest,
            "offset": offset,
            "text": chunk,
            "next_offset": offset + len(chunk) if i == 0 else None,
            "next_uri": "page1" if i == 0 else None,
        }
        offset += len(chunk)
    delivery = {"result_id": result_id, "sha256": digest, "manifest_uri": "manifest"}
    if not compact:
        delivery["first_page_uri"] = "page0"
    return (
        payload,
        {"run_metadata": payload["run_metadata"].copy(), "result_delivery": delivery},
        values,
    )


@pytest.mark.parametrize("compact", [False, True])
def test_inline_or_manifest_locator_restores_same_unicode_payload_and_receipt(compact):
    expected, envelope, values = sample(compact)
    client = Resources(values)
    actual, pages, manifest = asyncio.run(read_full_payload(client, envelope))
    assert actual == expected
    assert len(pages) == 2
    assert client.calls == (
        ["manifest", "page0", "page1"] if compact else ["page0", "page1"]
    )
    assert (manifest is not None) == compact


@pytest.mark.parametrize(
    "fault", ["manifest_hash", "result_id", "page_hash", "offset", "receipt", "bytes"]
)
def test_compact_locator_cannot_bypass_hash_identity_offsets_or_original_receipt(fault):
    _, envelope, values = sample(True)
    if fault == "manifest_hash":
        values["manifest"]["sha256"] = "different"
    elif fault == "result_id":
        values["page1"]["result_id"] = "different"
    elif fault == "page_hash":
        values["page1"]["sha256"] = "different"
    elif fault == "offset":
        values["page1"]["offset"] += 1
    elif fault == "receipt":
        envelope["run_metadata"]["run_id"] = "different"
    else:
        values["page1"]["text"] += "tamper"
    with pytest.raises(AssertionError):
        asyncio.run(read_full_payload(Resources(values), envelope))


def test_explicit_whole_receipt_deferral_retains_hash_bound_business_check():
    expected, envelope, values = sample(True)
    envelope["run_metadata"].pop("business_output_sha256")
    envelope["result_delivery"]["deferred_fields"] = ["run_metadata"]
    actual, _, _ = asyncio.run(
        read_full_payload(Resources(values), envelope, "business")
    )
    assert actual == expected
    with pytest.raises(AssertionError):
        asyncio.run(
            read_full_payload(
                Resources(values), envelope, "wrong frozen expected business hash"
            )
        )


def test_missing_inline_hash_without_explicit_whole_receipt_deferral_is_rejected():
    _, envelope, values = sample(True)
    envelope["run_metadata"].pop("business_output_sha256")
    envelope["result_delivery"]["deferred_fields"] = ["run_metadata.runtime"]
    with pytest.raises(AssertionError):
        asyncio.run(read_full_payload(Resources(values), envelope, "business"))
