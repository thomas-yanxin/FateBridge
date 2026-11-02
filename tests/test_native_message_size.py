"""Lossless private serialization retains its actual64MiB byte boundary."""

import json
from datetime import datetime, timezone

import pytest

from fatebridge.core.astro import native_execution as execution


def test_compact_typed_json_preserves_unicode_envelopes_and_numeric_values():
    original = {
        "文本": "完整见证\n不删样本",
        "map": ["datetime", "not an envelope"],
        "numbers": [0, -1, 0.0000000000000001, -0.0, True, None],
        "moment": datetime(2000, 1, 1, tzinfo=timezone.utc),
        "tuple": ("中文", 2),
    }
    message = {"kind": "result", "value": execution.encode(original)}
    old = json.dumps(message, ensure_ascii=True, allow_nan=False).encode() + b"\n"
    compact = execution.message_bytes(message)
    assert len(compact) < len(old)
    assert json.loads(compact) == json.loads(old)
    assert execution.decode(json.loads(compact)["value"]) == original
    assert compact.endswith(b"\n") and compact.count(b"\n") == 1


def test_actual_message_limit_still_accepts_exactly64mib_and_rejects_one_extra_byte():
    limit = 64 * 1024 * 1024
    assert execution._MAX_MESSAGE == limit
    assert len(execution.message_bytes({"x": "a" * (limit - 9)})) == limit
    with pytest.raises(execution.NativeExecutionError, match="exceeds limit"):
        execution.message_bytes({"x": "a" * (limit - 8)})


@pytest.mark.parametrize("invalid", [float("inf"), float("-inf"), float("nan")])
def test_size_optimization_does_not_allow_nonfinite_json(invalid):
    with pytest.raises(ValueError):
        execution.message_bytes({"x": invalid})
