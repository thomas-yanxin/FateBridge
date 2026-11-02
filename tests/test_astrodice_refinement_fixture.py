"""The independent holdout keeps its first unresolved result and fixed line."""

import hashlib
import json
import math
import shutil
from pathlib import Path

import pytest

from scripts.audit_astrodice_reference_refinement import reference_report

FIXTURE = Path(__file__).parent / "fixtures/astrodice-reference-refinement-v1"


def test_raw_holdout_replays_first_quality_report_without_host_trigonometry(
    monkeypatch,
):
    def forbidden(*args):
        raise AssertionError("Reference replay must avoid platform sin/cos")

    monkeypatch.setattr(math, "sin", forbidden)
    monkeypatch.setattr(math, "cos", forbidden)
    manifest = json.loads((FIXTURE / "fixture-manifest.json").read_text())
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    assert (
        manifest["files"]["reference.json"]
        == "2ade55e10342f9534e5534c164f8f148b241d84621ae6527c1a20baa367ab15f"
    )
    result = reference_report(
        FIXTURE / "protocol.json",
        FIXTURE / "reference.json",
        FIXTURE / "raw",
        FIXTURE / "reference-seal.json",
    )
    assert result == json.loads((FIXTURE / "first-reference-quality.json").read_text())
    assert result["exit_code"] == 2
    assert result["unqualified_case_ids"] == ["fresh-nearsolar-2500-Mercury-Mercury"]


def test_resealing_with_relaxed_reference_line_does_not_regrade_the_fixture(tmp_path):
    material = tmp_path / "material"
    shutil.copytree(FIXTURE, material)
    protocol = json.loads((material / "protocol.json").read_text())
    protocol["fixed_reference_convergence_arcsec_per_day"] = 1.0
    (material / "protocol.json").write_text(json.dumps(protocol))
    protocol_hash = hashlib.sha256(
        (material / "protocol.json").read_bytes()
    ).hexdigest()
    reference = json.loads((material / "reference.json").read_text())
    reference["protocol_sha256"] = protocol_hash
    (material / "reference.json").write_text(json.dumps(reference))
    seal = json.loads((material / "reference-seal.json").read_text())
    seal.update(
        protocol_sha256=protocol_hash,
        reference_sha256=hashlib.sha256(
            (material / "reference.json").read_bytes()
        ).hexdigest(),
    )
    (material / "reference-seal.json").write_text(json.dumps(seal))
    with pytest.raises(ValueError, match="refinement contract changed"):
        reference_report(
            material / "protocol.json",
            material / "reference.json",
            material / "raw",
            material / "reference-seal.json",
        )
