"""Reversible additive migration from frozen ORIGINAL input, never output digits.

The historical archives and their numeric/narrative assertions stay unchanged.
This helper supplies only the newly introduced lexical receipt and its copies.
"""

import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path

REFERENCE = Path(__file__).parent / "fixtures/numerology_clock_input_v1/reference.json"
_CLOCK_ID = "numerology_explicit_longitude_clock_v1"
_ANCHOR = "年、月及太阳交节用民用时刻的绝对瞬间；日、时柱用所选钟面。"


def _expected(original_time):
    rows = json.loads(REFERENCE.read_bytes())["rows"]
    rows += json.loads((REFERENCE.parent / "migration-reference.json").read_bytes())[
        "rows"
    ]
    return deepcopy(next(r["expected"] for r in rows if r["input"] == original_time))


def upgrade_prior_clock_input(output, original_time):
    out = deepcopy(output)
    evidence = out["numerology_evidence"]
    clock = evidence["birth_clock"]
    traces = [r for r in evidence["rule_trace"] if r["rule_id"] == _CLOCK_ID]
    assert len(traces) == 1 and traces[0]["facts"] == clock
    assert "input_representation" not in clock
    expected = _expected(original_time)
    clock["input_representation"] = deepcopy(expected)
    traces[0]["facts"]["input_representation"] = deepcopy(expected)
    assert out["snapshot_text"].count(_ANCHOR) == 1
    out["snapshot_text"] = out["snapshot_text"].replace(
        _ANCHOR, _ANCHOR + "\n" + expected["statement"]
    )
    assert rewind_prior_clock_input(out, original_time) == output
    return out


def rewind_clock_from_original_first_row_request(output, frozen_output):
    """Find the exact historical output's independently retained request text."""
    reference = json.loads((REFERENCE.parent / "migration-reference.json").read_bytes())
    original = Path(__file__).parent.parent / reference["original_file"]
    assert (
        hashlib.sha256(original.read_bytes()).hexdigest()
        == reference["original_sha256"]
    )
    rows = json.loads(gzip.decompress(original.read_bytes()))
    matching = [r for r in rows if r["output"] == frozen_output]
    assert len(matching) == 1
    return rewind_prior_clock_input(output, matching[0]["arguments"]["time"])


def rewind_prior_clock_input(output, original_time):
    out = deepcopy(output)
    expected = _expected(original_time)
    evidence = out["numerology_evidence"]
    clock = evidence["birth_clock"]
    traces = [r for r in evidence["rule_trace"] if r["rule_id"] == _CLOCK_ID]
    assert len(traces) == 1 and traces[0]["facts"] == clock
    assert clock.pop("input_representation") == expected
    assert traces[0]["facts"].pop("input_representation") == expected
    line = "\n" + expected["statement"]
    assert out["snapshot_text"].count(line) == 1
    out["snapshot_text"] = out["snapshot_text"].replace(line, "")
    return out
