"""Reproduce a failed frozen acceptance; this is not a passing accuracy score."""

import hashlib
import json
from pathlib import Path

from scripts.audit_astrodice_local_reference import replay

FIXTURE = Path(__file__).parent / "fixtures/astrodice-solar-layer-holdout-v1"


def test_frozen_independent_reference_and_first_failures_remain_unchanged():
    manifest_path = FIXTURE / "manifest.json"
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == (
        "69d092198e86044284e65dadb91172aa02955534e138cce19dc59b59b2b7077c"
    )
    manifest = json.loads(manifest_path.read_text())
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    result = replay(
        FIXTURE / "protocol.json",
        FIXTURE / "reference.json",
        FIXTURE / "raw",
        FIXTURE / "reference-seal.json",
        json.loads((FIXTURE / "certificates.json").read_text()),
    )
    assert result == json.loads((FIXTURE / "first-quality.json").read_text())
    assert result["exit_code"] == 2
    assert result["unqualified_case_ids"] == [
        "fresh-solar-8100-Mercury",
        "fresh-solar-8100-Venus",
    ]
    summary = json.loads((FIXTURE / "first-candidate-summary.json").read_text())
    for model, expected in [("swieph", (1, 2, 3)), ("jpl", (2, 2, 2))]:
        record = summary["models"][model]
        assert record["exit_code"] == 1
        counts = record["layer_counts"]
        assert list(counts["position"].values()) == [4, 2, 0, 0]
        assert list(counts["rate"].values()) == [*expected, 0]
        assert len(record["rows"]) == 6
