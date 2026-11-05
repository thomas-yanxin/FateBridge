"""New fixed-date source-frozen holdout, kept separate from development data."""

import json
import sys
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core import guolao
from scripts.guolao.audit_guolao_motion import evaluate, load_reference, main
from tests.western import test_other_chart_physical_sources as shared_sources

ephemeris_files = shared_sources.ephemeris_files
restore_configuration = shared_sources.restore_configuration
ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/data/astro/guolao_motion/protocol.json"
REFERENCE = ROOT / "tests/data/astro/guolao_motion/reference.json"


def test_holdout_keeps_predeclared_epochs_and_reference_uncertainty():
    protocol, reference = load_reference(PROTOCOL, REFERENCE)
    assert len(protocol["dates_tt"]) == 12
    assert len(protocol["targets"]) == 7
    assert reference["forbidden_implementation_imports"] == []
    assert reference["versions"] == {"pyerfa": "2.0.1.5", "numpy": "2.5.4"}
    for target in reference["references"]:
        for row in target["rows"]:
            assert row["status"] == "available"
            assert row["missing_probe_epochs"] == []
            assert row["stencil_difference_arcsec_per_day"] <= 0.002
            assert row["frame_step_difference_arcsec_per_day"] <= 0.002


def test_actual_guolao_seven_body_holdout_preserves_the_fixed_line(ephemeris_files):
    _, path = ephemeris_files
    e.swe.close()
    e.configure_ephemeris_path(str(path))
    protocol, reference = load_reference(PROTOCOL, REFERENCE)
    report = evaluate(protocol, reference)
    assert report["requested"] == len(report["rows"]) == 84
    assert report["source_errors"] == report["unresolved_reference"] == 0
    assert report["passed"] == 84
    assert report["numerical_subset_checks_passed"]
    assert {row["actual_model"] for row in report["rows"]} == {"swieph"}
    assert not report["authority_certified"]
    assert not report["all_four_objectives_validated"]


def test_moshier_uses_own_position_derivative_without_swiss_light_time(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    e.swe.close()
    e.configure_ephemeris_path(str(tmp_path))
    raw = guolao.positions(shared_sources.birth(), observer_geometry=False)
    assert raw["models"] == ["moshier"]
    assert "longitude_speed_light_time_correction" not in raw["states"]["Moon"]
    for name in guolao.CN:
        assert "longitude_speed_position_derivative_correction" in raw["states"][name]
    assert (
        raw["longitude_motion"]["lunar_light_time"]["reason"]
        == "unsupported_physical_model"
    )
    assert all(
        value["status"] == "applied"
        and value["method_id"] == "fatebridge_moshier_apparent_position_derivative_v1"
        for value in raw["longitude_motion"]["complete_position_derivatives"].values()
    )


def test_changed_reference_is_not_used_or_reported_as_a_numeric_failure(
    tmp_path, monkeypatch
):
    changed = tmp_path / "changed.json"
    changed.write_bytes(REFERENCE.read_bytes() + b"\n")
    output = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit",
            "--protocol",
            str(PROTOCOL),
            "--reference",
            str(changed),
            "--output",
            str(output),
        ],
    )
    monkeypatch.setattr(
        guolao,
        "positions",
        lambda *a, **k: pytest.fail("Do not use changed oracle bytes"),
    )
    assert main() == 2
    report = json.loads(output.read_text())
    assert "reference_validation_error" in report
    assert not report["numerical_subset_checks_passed"]
