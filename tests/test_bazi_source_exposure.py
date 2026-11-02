"""Standalone prior corpora count as exposed even when a directory glob missed them."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_exposure_addendum_keeps_first_unknown_and_removes_legacy_chart_from_fresh_gate():
    spec = importlib.util.spec_from_file_location(
        "exposure_audit", ROOT / "scripts/audit_bazi_source_exposure.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = ROOT / "docs/validation/bazi-clash-source-exposure-addendum-v1.json"
    expected = json.loads(path.read_text())
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    assert module.audit() == expected
    assert expected["corrected_case_ids"] == ["XX-13"]
    assert expected["nonoverlap_new_chapter_cases"] == 29
    assert expected["nonoverlap_adjudicated"] == 8
    assert expected["nonoverlap_unknown"] == 21
    row = next(r for r in expected["rows"] if r["id"] == "XX-13")
    assert row["all_prior_exact_overlaps"] == [
        {
            "source": "tests/fixtures/bazi-strength-reference.json",
            "id": "ditian_shuaiwang_14",
        }
    ]
    assert row["expected_strength"] is None  # Never fill it from legacy labels.
    assert row["first_recorded_fresh_gate_eligible"] is True
    assert row["corrected_fresh_gate_eligible"] is False
    assert expected["all_numeric_results_unchanged"] is True
    assert expected["candidate_adopted"] is False
