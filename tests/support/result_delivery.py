"""Private result-store isolation and verified same-run page reconstruction."""

import json
import os
import tempfile
from pathlib import Path

import pytest

import fatebridge.api as api
from fatebridge.application import result_delivery as delivery
from tests.fixtures.mcp_result_delivery import (
    assert_same_run_receipt as assert_same_run_metadata,
)


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
    assert len(text) == page["total_chars"]
    return json.loads(text)


RESULT_CASES = [
    {"id": tool, "tool": tool, "run_id": f"{tool}-run"} for tool in ("canping", "heluo")
]
RESULT_PAYLOADS = {
    case["id"]: {
        "input_normalized": {"gender": "女", "minute": None},
        "numerology_evidence": {
            "birth_clock": {
                "timezone": "Asia/Shanghai",
                "fold": 0,
                "text": "中文🌳" * 800,
            }
        },
        "run_metadata": {"run_id": case["run_id"], "tool_name": case["tool"]},
        "canping_timing": {
            "schedule_basis": {"scope": "synthetic storage fixture"},
            "first_period": [None, True, 0, -0.0, 1.2345678901234567],
            "selected": {"label": "甲子"},
        },
    }
    for case in RESULT_CASES
}


def forbidden(*args, **kwargs):
    raise AssertionError("A verified read attempted a write or writable-temp discovery")


def block_writes(monkeypatch):
    original_open = os.open

    def read_open(path, flags, *args, **kwargs):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            forbidden()
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", read_open)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(Path, "unlink", forbidden)
    monkeypatch.setattr(Path, "chmod", forbidden)
    monkeypatch.setattr(tempfile, "gettempdir", forbidden)


def assert_same_run_receipt(store, shaped, original):
    """Check retained payload integrity and the explicitly deferred receipt."""
    reference = shaped["result_delivery"]
    result_id = reference["result_id"]
    verified = store.verified_page(result_id, shaped["run_metadata"]["run_id"])
    assert verified["verification"]["calculation_repeated"] is False
    retained = reconstruct(store, result_id)
    assert retained == original
    assert json.dumps(retained, sort_keys=True) == json.dumps(original, sort_keys=True)
    assert_same_run_metadata(
        shaped["run_metadata"],
        original["run_metadata"],
        deferred_fields=reference["deferred_fields"],
    )
