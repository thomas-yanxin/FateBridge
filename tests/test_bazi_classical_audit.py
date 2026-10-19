"""Integrity and scope checks for source-case acceptance, not efficacy tests."""

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "audit_bazi_classical", ROOT / "scripts/audit_bazi_classical.py"
)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def test_frozen_reference_has_disjoint_cases_and_unknown_labels():
    data = audit.load_frozen_corpus()
    development = {c["id"] for c in data["cases"] if c["split"] == "development"}
    reserved = {c["id"] for c in data["cases"] if c["split"] == "reserved"}
    assert len(development) == 6 and len(reserved) == 4
    assert development.isdisjoint(reserved)
    assert sum(c["adjudication"]["strength"] is None for c in data["cases"]) == 7
    assert all(c["source"]["pdf_pages"] for c in data["cases"])
    assert all(c["source"]["verified_excerpt_no_punctuation"] for c in data["cases"])


@pytest.mark.parametrize("change", ["edit", "extra", "missing"])
def test_reference_changes_cannot_silently_rewrite_acceptance(tmp_path, change):
    corpus = tmp_path / "corpus"
    shutil.copytree(audit.CORPUS, corpus)
    if change == "edit":
        path = corpus / "cases.json"
        data = json.loads(path.read_text())
        data[0]["adjudication"]["strength"] = "强"
        path.write_text(json.dumps(data))
    elif change == "extra":
        (corpus / "unreviewed.json").write_text("{}")
    else:
        (corpus / "probes.json").unlink()
    with pytest.raises(ValueError, match="Reference"):
        audit.load_frozen_corpus(corpus)


def test_unknown_source_strength_is_not_a_program_generated_expected_answer():
    data = audit.load_frozen_corpus()
    case = next(c for c in data["cases"] if c["adjudication"]["strength"] is None)
    actual = {
        "elements": {"day_master": {"strength_level": "强"}},
        "monthly_structure": {"label": "正官格"},
    }
    result = audit.compare(case, actual)
    assert result["strength"]["reference"] is None
    assert result["strength"]["status"] == "not_adjudicated_by_source"
    assert result["formation"]["status"] == "unsupported"
    assert result["useful_roles"]["status"] == "different_semantic_object_not_accepted"


def test_incomplete_source_chart_is_rejected_without_filling_hour():
    with pytest.raises(ValueError, match="Unknown or incomplete"):
        audit.observe(["壬申", "丙午", "甲午", None])


def test_actual_audit_retains_disagreement_and_does_not_claim_classical_pass():
    result = audit.audit()
    by_id = {c["id"]: c for c in result["cases"]}
    # Independent book labels remain intact even when the program disagrees.
    assert by_id["ZP37-XIE"]["reference"]["strength"] == "强"
    # Deliberately wrong observation exercises the audit without locking a
    # production defect in place as a desired regression result.
    case = next(c for c in audit.load_frozen_corpus()["cases"] if c["id"] == "ZP37-XIE")
    wrong = {
        "elements": {"day_master": {"strength_level": "弱"}},
        "monthly_structure": {"label": "食神格"},
    }
    assert audit.compare(case, wrong)["strength"]["status"] == "disagreement"
    assert result["summary"]["classical_acceptance_passed"] is False
    assert result["summary"]["strength_unknown_in_source"] == 7
    assert all(not p["production_total_strength_called"] for p in result["probes"])
    variants = by_id["ZP37-LIANG"]["variants"]
    assert len(variants) == 1
    assert variants[0]["source"]["pillars"][-1] == "癸亥"
    assert by_id["ZP37-LIANG"]["reference"]["strength"] == "强"


def test_audit_can_run_through_a_symlinked_script_path(tmp_path):
    alias = tmp_path / "audit_alias.py"
    alias.symlink_to(ROOT / "scripts/audit_bazi_classical.py")
    report = tmp_path / "audit.json"
    result = subprocess.run(
        [sys.executable, str(alias), "--output", str(report)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, result.stderr
    assert json.loads(report.read_text())["summary"]["full_cases"] == 10
