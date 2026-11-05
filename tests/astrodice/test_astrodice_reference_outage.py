"""A frozen HTTP-200 service error must leave every numerical gate unresolved."""

import json
from pathlib import Path

from scripts.astrodice.audit_astrodice_local_motion import UNRESOLVED, evaluate_layers
from scripts.astrodice.audit_astrodice_local_reference import replay

FIXTURE = (
    Path(__file__).parents[1]
    / "data/astrodice/reference_sets/fixture-grid5-outage-20261026-v1"
)


def test_frozen_source_outage_retains_every_planned_probe_without_comparing_candidate():
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
