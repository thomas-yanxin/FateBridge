"""Private result-store isolation and verified same-run page reconstruction."""

import hashlib
import json

import pytest

import fatebridge.api as api
from fatebridge.application import result_delivery as delivery


@pytest.fixture
def store(tmp_path, monkeypatch):
    result = delivery.ResultStore(tmp_path / "private")
    monkeypatch.setattr(delivery, "RESULT_STORE", result)
    monkeypatch.setattr(api, "RESULT_STORE", result)
    return result


def reconstruct(store, result_id, path=None):
    parts = []
    offset = 0
    while True:
        page = store.page(result_id, offset, path)
        assert len(page["text"]) <= delivery.PAGE_CHARS
        # Each envelope is valid JSON even when its text is a document fragment.
        assert json.loads(json.dumps(page, ensure_ascii=False)) == page
        parts.append(page["text"])
        offset = page["next_offset"]
        if offset is None:
            break
    text = "".join(parts)
    assert hashlib.sha256(text.encode()).hexdigest() == page["sha256"]
    return json.loads(text)
