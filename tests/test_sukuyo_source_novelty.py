"""Frozen source identity signals never certify a new independent witness."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.check_sukuyo_source_novelty import search_sources

FIXTURE = Path(__file__).parent / "data/sukuyo-novelty-before-code-v85.json"


def prepared(tmp_path):
    reference = json.loads(FIXTURE.read_bytes())
    hashes = {}
    for name, text in reference["actual_selected_baseline_texts"].items():
        q = tmp_path / name
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_text(text)
        hashes[name] = hashlib.sha256(q.read_bytes()).hexdigest()
    baseline = {
        "format": "sukuyo_frozen_source_search_baseline_v1",
        "files_sha256": hashes,
    }
    return reference, baseline


def test_actual_known_sources_match_entire_independent_precode_reference(tmp_path):
    reference, baseline = prepared(tmp_path)
    result = search_sources(tmp_path, baseline, reference["candidates"])
    assert result["match_paths"] == reference["expected_match_paths"]
    assert result["independent_witness_certified"] is False
    assert result["independent_observation_count"] is None
    assert result["rule_adoption_authorized"] is False
    assert result["candidate_states"]["utokyo_t30108"] == (
        "fingerprint_previously_recorded"
    )
    assert result["candidate_states"]["t1509"] == "fingerprint_previously_recorded"
    assert result["candidate_states"]["t2217"] == "not_found_in_this_text_baseline"
    assert result["candidate_states"]["unmei908"] == ("not_found_in_this_text_baseline")


def test_uri_mention_without_byte_fingerprint_is_not_an_acquired_source(tmp_path):
    reference, baseline = prepared(tmp_path)
    candidate = {**reference["candidates"][0], "sha256": "a" * 64}
    result = search_sources(tmp_path, baseline, [candidate])
    assert result["candidate_states"][candidate["candidate_id"]] == (
        "uri_previously_referenced"
    )
    assert not result["match_paths"][candidate["candidate_id"]][
        "fingerprint_text_matches"
    ]
    assert result["independent_witness_certified"] is False


def test_drift_or_missing_baseline_cannot_be_silently_omitted(tmp_path):
    reference, baseline = prepared(tmp_path)
    name = next(iter(baseline["files_sha256"]))
    q = tmp_path / name
    q.write_bytes(q.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="baseline.*changed"):
        search_sources(tmp_path, baseline, reference["candidates"])
    q.unlink()
    with pytest.raises(ValueError, match="baseline.*missing"):
        search_sources(tmp_path, baseline, reference["candidates"])


def test_binary_archive_is_verified_but_not_treated_as_searched_text(tmp_path):
    reference, baseline = prepared(tmp_path)
    candidate = reference["candidates"][-1]
    raw = candidate["uri"].encode() + b"\x00" + candidate["sha256"].encode()
    q = tmp_path / "opaque.zip"
    q.write_bytes(raw)
    baseline["files_sha256"][q.name] = hashlib.sha256(raw).hexdigest()
    result = search_sources(tmp_path, baseline, [candidate])
    assert result["binary_files_not_expanded"] == [q.name]
    assert result["candidate_states"][candidate["candidate_id"]] == (
        "not_found_in_this_text_baseline"
    )
    assert result["archives_expanded"] is False


def test_direct_artifact_bytes_and_candidate_aliases_are_not_independent_votes(
    tmp_path,
):
    reference, baseline = prepared(tmp_path)
    q = tmp_path / "opaque.zip"
    q.write_bytes(b"actual captured object")
    fingerprint = hashlib.sha256(q.read_bytes()).hexdigest()
    baseline["files_sha256"][q.name] = fingerprint
    a = {**reference["candidates"][-1], "sha256": fingerprint}
    b = {**a, "candidate_id": "another_label", "uri": "https://example.org/alias"}
    result = search_sources(tmp_path, baseline, [a, b])
    for candidate in [a, b]:
        assert result["match_paths"][candidate["candidate_id"]][
            "direct_artifact_hash_matches"
        ] == [q.name]
    assert result["identical_candidate_fingerprint_groups"] == [
        sorted([a["candidate_id"], b["candidate_id"]])
    ]
    assert result["independent_observation_count"] is None


@pytest.mark.parametrize("fault", ["duplicate_id", "hash", "uri", "empty"])
def test_invalid_candidate_list_is_rejected_before_search(tmp_path, fault):
    reference, baseline = prepared(tmp_path)
    candidates = deepcopy(reference["candidates"])
    if fault == "duplicate_id":
        candidates.append(candidates[0])
    elif fault == "hash":
        candidates[0]["sha256"] = "not a digest"
    elif fault == "uri":
        candidates[0]["uri"] = "not a source URI"
    else:
        candidates = []
    with pytest.raises(ValueError):
        search_sources(tmp_path, baseline, candidates)


def test_frozen_baseline_paths_cannot_escape_the_declared_root(tmp_path):
    reference, baseline = prepared(tmp_path)
    baseline["files_sha256"]["../elsewhere.json"] = "0" * 64
    with pytest.raises(ValueError, match="path"):
        search_sources(tmp_path, baseline, reference["candidates"])
