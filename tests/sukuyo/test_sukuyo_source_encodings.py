"""Declared encodings keep the full evidence baseline without lossy search."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.sukuyo.check_sukuyo_source_novelty import search_sources

FIXTURE = (
    Path(__file__).parents[1] / "data/sukuyo-source-encodings-before-code-v88.json"
)


def prepared(tmp_path, index=0):
    row = json.loads(FIXTURE.read_bytes())["literal_cases"][index]
    raw = bytes.fromhex(row["raw_hex"])
    path = tmp_path / "captured.html"
    path.write_bytes(raw)
    baseline = {
        "format": "sukuyo_frozen_source_search_baseline_v1",
        "files_sha256": {path.name: hashlib.sha256(raw).hexdigest()},
        "text_encodings": {path.name: row["codec"]},
    }
    candidate = {"candidate_id": "test", "uri": row["uri"], "sha256": "0" * 64}
    return row, baseline, candidate


@pytest.mark.parametrize("index", [0, 1, 2])
def test_complete_precode_text_is_searched_using_explicit_codec(tmp_path, index):
    row, baseline, candidate = prepared(tmp_path, index)
    result = search_sources(tmp_path, baseline, [candidate])
    assert result["verified_files"] == 1
    assert result["candidate_states"]["test"] == row["expected_state"]
    assert result["text_decoding"]["captured.html"]["codec"] == row["codec"]
    assert result["text_decoding"]["captured.html"]["errors"] == "strict"
    assert not result["independent_witness_certified"]
    assert result["independent_observation_count"] is None


def test_legacy_utf8_default_keeps_fail_closed_behavior(tmp_path):
    _, baseline, candidate = prepared(tmp_path)
    baseline.pop("text_encodings")
    with pytest.raises(ValueError, match="baseline text"):
        search_sources(tmp_path, baseline, [candidate])


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        [],
        {"absent.html": "utf-8"},
        {"captured.html": ""},
        {"captured.html": "utf-7"},
        {"captured.html": "base64_codec"},
        {"captured.html": 1},
    ],
)
def test_unknown_or_nontext_metadata_is_rejected_before_search(tmp_path, metadata):
    _, baseline, candidate = prepared(tmp_path, 2)
    baseline["text_encodings"] = metadata
    with pytest.raises(ValueError, match="encoding"):
        search_sources(tmp_path, baseline, [candidate])


def test_binary_files_remain_unexpanded_even_if_caller_declares_text_codec(tmp_path):
    _, baseline, candidate = prepared(tmp_path, 2)
    path = tmp_path / "opaque.zip"
    path.write_bytes(b"opaque")
    baseline["files_sha256"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    baseline["text_encodings"][path.name] = "utf-8"
    with pytest.raises(ValueError, match="encoding"):
        search_sources(tmp_path, baseline, [candidate])


def test_explicit_codec_never_allows_byte_drift_or_replacement_decode(tmp_path):
    _, baseline, candidate = prepared(tmp_path)
    path = tmp_path / "captured.html"
    path.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="changed"):
        search_sources(tmp_path, baseline, [candidate])
    baseline["files_sha256"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="baseline text"):
        search_sources(tmp_path, baseline, [candidate])
