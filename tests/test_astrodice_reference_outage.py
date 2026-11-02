"""A frozen HTTP-200 service error must leave every numerical gate unresolved."""

import hashlib
import json
from pathlib import Path

from scripts.audit_astrodice_local_motion import UNRESOLVED, evaluate_layers
from scripts.audit_astrodice_local_reference import replay

FIXTURE = Path(__file__).parent / "fixtures/astrodice-grid5-outage-20261026-v1"


def test_frozen_source_outage_retains_every_planned_probe_without_comparing_candidate():
    manifest_path = FIXTURE / "manifest.json"
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == (
        "7df1a27fab43825e3000309af5c8111d497a6387a4231ba3e41753cb4518fd76"
    )
    manifest = json.loads(manifest_path.read_text())
    for name, expected in manifest["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == expected
    result = replay(
        FIXTURE / "protocol.json",
        FIXTURE / "reference.json",
        FIXTURE / "raw",
        FIXTURE / "reference-seal.json",
        json.loads((FIXTURE / "certificates.json").read_text()),
    )
    assert result == json.loads((FIXTURE / "first-quality.json").read_text())
    assert result["exit_code"] == 2 and len(result["unqualified_case_ids"]) == 4
    baseline = result["raw_integrity_and_baseline_quality"]
    assert baseline["position_probes"] == baseline["complete_cases"] == 0
    assert not baseline["candidate_compared"]

    def forbidden_candidate():
        raise AssertionError("Missing independent source invoked the candidate")

    rows = json.loads((FIXTURE / "reference.json").read_text())["rows"]
    assert sum(len(row["samples"]) for row in rows) == 2308
    for row, quality in zip(rows, result["rows"]):
        assert len(row["missing_offsets_seconds"]) == 577
        assert all(point is None for point in row["samples"].values())
        layers = evaluate_layers(row, quality, forbidden_candidate, forbidden_candidate)
        assert layers["status"] == UNRESOLVED
        assert all(v["status"] == UNRESOLVED for v in layers["layers"].values())
