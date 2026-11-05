"""A paged receipt is valid only after same-run integrity and business checks."""

import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from fatebridge.application.result_delivery import ResultStore
from tests.fengshui.test_fengshui_surfaces import same_run_projected_response


def fixture(tmp_path, corruption=None):
    store = ResultStore(tmp_path / "results")
    original = {
        "layers": {"directions": {"north_reference": "true"}},
        "run_metadata": {
            "run_id": "same-original-run",
            "tool_name": "fengshui_directions",
            "runtime": {"ephemeris": {"files": {}, "sha256": "original"}},
        },
    }
    ref = store.put(original)
    body = deepcopy(original)
    body["run_metadata"]["runtime"] = {"delivery_path": "run_metadata.runtime"}
    body["result_delivery"] = {**ref, "deferred_fields": ["run_metadata.runtime"]}
    if corruption == "missing_business":
        body.pop("layers")
    result = SimpleNamespace(
        is_error=False,
        structured_content=body,
        content=[SimpleNamespace(text=json.dumps(body))],
    )

    class Reader:
        reads = 0

        async def read_resource(self, uri):
            self.reads += 1
            if uri == ref["manifest_uri"]:
                data = store.manifest(ref["result_id"])
            else:
                offset = int(uri.rsplit("/", 1)[1])
                data = store.page(ref["result_id"], offset)
                if corruption == "page_text":
                    data["text"] = "[" + data["text"][1:]
                if corruption == "next_offset":
                    data["next_offset"] = 0
            return [SimpleNamespace(text=json.dumps(data))]

    return Reader(), result, original


def test_original_same_run_receipt_is_reconstructed_without_tool_recalculation(
    tmp_path,
):
    reader, response, original = fixture(tmp_path)
    assert asyncio.run(same_run_projected_response(reader, response)) == original
    assert reader.reads == 2  # Manifest plus the single complete original page.


@pytest.mark.parametrize("corruption", ["page_text", "next_offset", "missing_business"])
def test_delivery_metadata_cannot_hide_corrupt_or_missing_evidence(
    tmp_path, corruption
):
    reader, response, _ = fixture(tmp_path, corruption)
    with pytest.raises(AssertionError):
        asyncio.run(same_run_projected_response(reader, response))
