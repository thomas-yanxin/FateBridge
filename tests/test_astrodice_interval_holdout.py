"""Frozen new reference keeps all eight cases and its rejected epoch."""

import hashlib
import json
from pathlib import Path

from scripts.audit_astrodice_local_reference import replay

FIXTURE = (
    Path(__file__).parent
    / "data/astrodice/reference_sets/fixture-local-interval-holdout-v1"
)


def test_independent_frozen_holdout_replays_exactly_without_a_solver():
    result = replay(
        FIXTURE / "protocol.json",
        FIXTURE / "reference.json",
        FIXTURE / "raw",
        FIXTURE / "reference-seal.json",
        json.loads((FIXTURE / "certificates.json").read_text()),
    )
    assert result == json.loads((FIXTURE / "first-quality.json").read_text())
    assert result["exit_code"] == 2 and len(result["rows"]) == 8
    assert result["unqualified_case_ids"] == ["fresh-local-7750-Venus"]
    row = next(
        v
        for v in json.loads((FIXTURE / "reference.json").read_text())["rows"]
        if v["id"] == "fresh-local-7750-Venus"
    )
    assert row["missing_offsets_seconds"] == ["-1140"]
    assert row["samples"]["-1140"] is None
