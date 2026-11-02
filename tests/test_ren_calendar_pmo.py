"""The complete primary minute cohort retains precision failures and all errors."""

import importlib.util
import shutil
from pathlib import Path

import pytest

from fatebridge.core import almanac

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ren_calendar_pmo", ROOT / "scripts/audit_ren_calendar_pmo.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_all_126_years_keep_both_modern_minutes_and_legacy_notes():
    ref = AUDIT.reference()
    assert len(ref["cases"]) == 3024
    assert ref["years"] == list(range(1900, 2026))
    assert len(ref["historical_term_notes"]) == 5
    values = {(row["year"], row["term"]): row for row in ref["cases"]}
    for note in ref["historical_term_notes"]:
        modern = values[(note["year"], note["term"])]
        assert modern["published_moment"][:10] != note["legacy_date"]
        assert modern["pdf_page"] == note["pdf_page"]
    assert values[(1979, "大寒")]["published_moment"] == "1979-01-21T00:00:00+08:00"


def test_complete_minute_comparisons_keep_declared_threshold_and_full_denominator():
    report = AUDIT.audit()
    assert report["expected_count"] == report["compared_count"] == 3024
    assert report["boundary_pair_count"] == 4536
    assert not report["calculation_errors"] and not report["boundary_pair_failures"]
    assert report["implementation_unchanged_during_audit"]
    assert report["minute_criterion"]["max_absolute_difference_seconds"] == 30
    failures = []
    for row in report["comparisons"]:
        expected = (
            abs(row["difference_seconds"]) <= 30 and row["provider"] == "swisseph"
        )
        assert row["within_printed_minute_criterion"] == expected
        if not expected:
            failures.append(row)
    assert report["minute_failures"] == failures
    assert report["minute_failure_count"] == len(failures)
    assert report["all_performed_comparisons_passed"] == (not failures)
    assert not report["full_supported_calendar_domain_certified"]
    assert not report["goal_complete"]


def test_an_entire_solver_failure_remains_reportable_without_dropping_the_cohort(
    monkeypatch,
):
    monkeypatch.setattr(almanac, "get_solar_terms_for_year", lambda *a, **kw: [])
    report = AUDIT.audit()
    assert report["expected_count"] == 3024
    assert report["compared_count"] == 0
    assert len(report["calculation_errors"]) == 3024
    assert report["max_absolute_difference_seconds"] is None
    assert not report["all_performed_comparisons_passed"]


def test_frozen_source_edit_and_omitted_term_table_are_rejected(tmp_path):
    ref = AUDIT.reference()
    text = (AUDIT.CORPUS / "source.txt").read_text()
    with pytest.raises(ValueError, match="eight terms"):
        AUDIT.extracted_tables(
            text.replace(ref["cases"][0]["extracted_table_token"], "", 1)
        )
    target = tmp_path / "pmo"
    shutil.copytree(AUDIT.CORPUS, target)
    (target / "source.txt").write_text(text + "modified")
    with pytest.raises(ValueError, match="Frozen PMO source changed"):
        AUDIT.reference(target)
