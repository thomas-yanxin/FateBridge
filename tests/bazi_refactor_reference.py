"""Exact pre-repair strength bytes for the retained 408 literal inputs."""

import gzip
import hashlib
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def _strength_hashes():
    source = (
        ROOT
        / "docs/validation/bazi-month-command-integrity-files-v1/all408-source-final-first.jsonl.gz"
    )
    manifest = (
        ROOT / "tests/fixtures/architecture_refactor_v1/bazi408-before-manifest.json"
    )
    assert hashlib.sha256(source.read_bytes()).hexdigest() == (
        "81766f95c5e45ba866244d793c1dadcdd1f36470893b2077563da3c4eb8492b8"
    )
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == (
        "bac00f4517a2357188312ab9c325ba8d051dcc224b8f32aee7bf0b6f453b17d8"
    )
    rows = [json.loads(line) for line in gzip.open(source, "rt")]
    frozen = json.loads(manifest.read_bytes())
    assert len(rows) == len(frozen) == 408
    result = {}
    for row, expected in zip(rows, frozen, strict=True):
        key = tuple(row["case"]["pillars"])
        digest = expected["strength_sha256"]
        assert key not in result or result[key] == digest
        result[key] = digest
    return result


def assert_strength_matches_before_repair(pillars, value):
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    expected = _strength_hashes().get(tuple(pillars))
    if expected is None:
        expected = {
            tuple(row["pillars"]): row["strength_sha256"]
            for row in assessment_baseline()["assessment_rows"]
        }[tuple(pillars)]
    assert hashlib.sha256(raw).hexdigest() == expected


@lru_cache(maxsize=1)
def assessment_baseline():
    path = (
        ROOT / "tests/fixtures/architecture_refactor_v1/assessment-before-manifest.json"
    )
    raw = path.read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "f1f8565cbc0f95933fa2b922de85e2dc22542816618c3e854faccd4a533cc92c"
    )
    data = json.loads(raw)
    assert len(data["assessment_rows"]) == 366
    assert len(data["single_end_probes"]) == 3000
    return data


def exact_digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def assert_assessment_matches_before_repair(pillars, value):
    expected = {
        tuple(r["pillars"]): r["assessment_sha256"]
        for r in assessment_baseline()["assessment_rows"]
    }
    assert exact_digest(value) == expected[tuple(pillars)]
