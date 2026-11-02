"""Negotiated JSON results keep values/types and the original wire bound."""

import gzip
import json
import math
import struct
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.core.astro import native_execution as execution
from scripts.gen_human_design_timezone_history import read, sha

E = (
    Path(__file__).resolve().parents[1]
    / "docs/validation/human-design-cycle-origin-comparison-v1/evidence"
)
MODE = execution.JSON_TREE_ENCODING


def wire_roundtrip(value, encoding):
    message = {"value": execution.encode_result(value, encoding)}
    raw = execution.message_bytes(message)
    return execution.decode_result(json.loads(raw)["value"], encoding), raw


def test_finite_json_result_preserves_colliding_tags_unicode_and_numeric_types():
    value = {
        "map": ["datetime", "not a protocol date", None, 0],
        "json_tree_v1": {"birth": [1, 2]},
        "unicode": "设计原点",
        "none": None,
        "bool": True,
        "numbers": [0, 2**80, -(2**80), 0.0, -0.0, 1.1, 1e-250, 1e250],
    }
    result, raw = wire_roundtrip(value, MODE)
    assert result == value
    assert json.loads(raw)["value"][0] == MODE
    for original, actual in zip(value["numbers"], result["numbers"], strict=True):
        assert type(actual) is type(original)
        if type(original) is float:
            assert struct.pack(">d", actual) == struct.pack(">d", original)
    assert isinstance(result["map"], list)


def test_legacy_request_retains_exact_typed_codec_and_accepts_old_replies():
    value = {"nested": [(1, 2), datetime(2000, 1, 1, tzinfo=timezone.utc)]}
    assert execution.encode_result(value) == execution.encode(value)
    result, _ = wire_roundtrip(value, None)
    assert result == value and type(result["nested"][0]) is tuple
    assert execution.decode_result(execution.encode(value), MODE) == value


def test_non_json_trees_do_not_erase_tuple_dates_or_nonstring_keys():
    value = {1: ("a", datetime(2000, 1, 1, tzinfo=timezone.utc)), "1": [True, None]}
    assert execution.encode_result(value, MODE) == execution.encode(value)
    result, _ = wire_roundtrip(value, MODE)
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
        execution.decode_result([MODE, {"bad": bad}], MODE)


def test_new_result_tag_requires_explicit_negotiation():
    encoded = execution.encode_result({"a": 1}, MODE)
    with pytest.raises(execution.NativeExecutionError, match="Unnegotiated"):
        execution.decode_result(encoded)
    with pytest.raises(execution.NativeExecutionError, match="Unsupported"):
        execution.encode_result({"a": 1}, "invented")


def test_plain_json_result_cannot_bypass_the_same_message_bound(monkeypatch):
    monkeypatch.setattr(execution, "_MAX_MESSAGE", 128)
    with pytest.raises(execution.NativeExecutionError, match="exceeds limit"):
        execution.message_bytes(
            {"value": execution.encode_result({"large": "x" * 128}, MODE)}
        )


def test_captured_overflow_reencodes_every_value_without_changing_bound():
    plan = read(E / "json-wire-plan.json")
    path = E / "oversized-original-native-frame.json.gz"
    assert sha(path) == plan["old_frame_sha256"]
    old_wire = gzip.decompress(path.read_bytes())
    old_message = json.loads(old_wire)
    original = execution.decode(old_message["value"])
    message = {**old_message, "value": execution.encode_result(original, MODE)}
    new_wire = execution.message_bytes(message)
    restored = execution.decode_result(json.loads(new_wire)["value"], MODE)
    assert original == restored
    assert len(old_wire) == plan["old_wire_bytes"] > execution._MAX_MESSAGE
    assert (
        len(new_wire)
        == plan["candidate_wire_bytes"]
        <= execution._MAX_MESSAGE
        == plan["bound"]
        == 64 * 1024 * 1024
    )
    assert old_message["clock_reads"] == json.loads(new_wire)["clock_reads"]
