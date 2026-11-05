"""Current tagged results keep values/types and the original wire bound."""

import json
import math
import struct
from datetime import datetime, timezone

import pytest

from fatebridge.core.astro import native_execution as execution

MODE = execution.RESULT_ENCODING


def wire_roundtrip(value):
    message = {"value": execution.encode_result(value)}
    raw = execution.message_bytes(message)
    return execution.decode_result(json.loads(raw)["value"]), raw


def test_finite_json_result_preserves_colliding_tags_unicode_and_numeric_types():
    value = {
        "map": ["datetime", "not a protocol date", None, 0],
        "json_tree_v1": {"birth": [1, 2]},
        "unicode": "设计原点",
        "none": None,
        "bool": True,
        "numbers": [0, 2**80, -(2**80), 0.0, -0.0, 1.1, 1e-250, 1e250],
    }
    result, raw = wire_roundtrip(value)
    assert result == value
    assert json.loads(raw)["value"][0] == MODE
    for original, actual in zip(value["numbers"], result["numbers"], strict=True):
        assert type(actual) is type(original)
        if type(original) is float:
            assert struct.pack(">d", actual) == struct.pack(">d", original)
    assert isinstance(result["map"], list)


def test_current_typed_result_preserves_tuple_and_datetime():
    value = {"nested": [(1, 2), datetime(2000, 1, 1, tzinfo=timezone.utc)]}
    assert execution.encode_result(value) == [MODE, "typed", execution.encode(value)]
    result, _ = wire_roundtrip(value)
    assert result == value and type(result["nested"][0]) is tuple


def test_non_json_trees_do_not_erase_tuple_dates_or_nonstring_keys():
    value = {1: ("a", datetime(2000, 1, 1, tzinfo=timezone.utc)), "1": [True, None]}
    assert execution.encode_result(value) == [MODE, "typed", execution.encode(value)]
    result, _ = wire_roundtrip(value)
    assert result == value and type(result[1]) is tuple
    assert type(next(iter(result))) is int


@pytest.mark.parametrize(
    "bad",
    [float("nan"), float("inf"), float("-inf"), (1, 2), {1: 2}, datetime(2000, 1, 1)],
)
def test_json_tag_cannot_smuggle_non_json_or_nonfinite_values(bad):
    with pytest.raises(
        execution.NativeExecutionError, match="Invalid native JSON tree"
    ):
        execution.decode_result([MODE, "json", {"bad": bad}])


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        {"a": 1},
        ["map", [["a", 1]]],
        ["json_tree_v1", {"a": 1}],
        [MODE, {"a": 1}],
        [MODE, "invented", {"a": 1}],
    ],
)
def test_result_requires_the_current_explicit_envelope(invalid):
    with pytest.raises(execution.NativeExecutionError, match="Invalid native result"):
        execution.decode_result(invalid)


def test_plain_json_result_cannot_bypass_the_same_message_bound(monkeypatch):
    monkeypatch.setattr(execution, "_MAX_MESSAGE", 128)
    with pytest.raises(execution.NativeExecutionError, match="exceeds limit"):
        execution.message_bytes(
            {"value": execution.encode_result({"large": "x" * 128})}
        )


def test_current_json_tree_keeps_values_under_the_same_64mib_message_bound():
    # Repeated ordinary structured business rows inflate the typed envelope.
    # Keep the actual 64MiB budget: no recorded message or previous wire size.
    row = {"longitude": 1.25, "latitude": -0.0, "body": "Sun", "flags": 258}
    value = [row] * 900_000
    typed = [MODE, "typed", execution.encode(value)]
    with pytest.raises(execution.NativeExecutionError, match="exceeds limit"):
        execution.message_bytes({"value": typed})
    del typed
    wire = execution.message_bytes({"value": execution.encode_result(value)})
    assert len(wire) <= execution._MAX_MESSAGE == 64 * 1024 * 1024
    restored = execution.decode_result(json.loads(wire)["value"])
    assert restored == value
    assert math.copysign(1, restored[-1]["latitude"]) == -1
