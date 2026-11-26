"""A follow-up dynamics pass cannot erase civil-time or old minute failures."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "ren_model_tt", ROOT / "scripts/ren/audit_ren_model_tt.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


@pytest.fixture
def matrix(tmp_path):
    source = [
        {
            "year": year,
            "term": term,
            "actual": "2026-01-01T00:00:00+00:00",
            "published_moment": "2026-01-01T00:00:00+00:00",
            "difference_seconds": 30.5,
            "within_original_numeric_criterion": False,
        }
        for year in range(1900, 2026)
        for term in AUDIT.TERMS
    ]
    expected = {(r["year"], r["term"]): {"jd_tt": 2451545.0} for r in source}
    path = tmp_path / "first-matrix.json"
    path.write_text(
        json.dumps(
            {
                "profile": "synthetic",
                "pmo_numeric_comparisons": source,
                "pmo_numeric_failure_count": 3024,
            }
        )
    )
    return path, expected


def test_tt_match_preserves_all_first_minute_failures_and_scope(matrix) -> None:
    path, expected = matrix
    result = AUDIT.compare(
        path, lambda _: SimpleNamespace(jd_tt=2451545.0, method="test"), expected
    )
    assert result["compared_count"] == 3024
    assert result["tt_failure_count"] == 0
    assert result["original_pmo_numeric_failures_retained"] == 3024
    assert result["old_minute_or_opale_failures_reclassified"] is False
    assert result["goal_complete"] is False


@pytest.mark.parametrize("offset_seconds", [1.0001, -1.0001])
def test_one_second_tt_gate_keeps_both_sides_without_rounding(
    matrix, offset_seconds
) -> None:
    path, expected = matrix
    result = AUDIT.compare(
        path,
        lambda _: SimpleNamespace(
            jd_tt=2451545.0 + offset_seconds / 86400, method="test"
        ),
        expected,
    )
    assert result["tt_failure_count"] == 3024


def test_replacing_one_event_with_duplicate_does_not_preserve_the_cohort(
    matrix,
) -> None:
    path, expected = matrix
    record = json.loads(path.read_text())
    record["pmo_numeric_comparisons"][-1] = record["pmo_numeric_comparisons"][0]
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="All original"):
        AUDIT.compare(path, lambda _: None, expected)


@pytest.mark.parametrize("invalid", [None, True, float("nan")])
def test_invalid_clock_rows_remain_errors_in_full_denominator(matrix, invalid) -> None:
    path, expected = matrix
    result = AUDIT.compare(path, lambda _: SimpleNamespace(jd_tt=invalid), expected)
    assert result["expected_count"] == len(result["calculation_errors"]) == 3024
    assert result["compared_count"] == 0
    assert result["all_declared_tt_comparisons_passed"] is False


def test_frozen_independent_de440_references_are_complete() -> None:
    values = AUDIT.reference()
    assert len(values) == 4872
    assert (1899, "小寒") in values and (2101, "冬至") in values


@pytest.mark.parametrize("present", [False, True])
def test_legacy_status_never_claims_missing_or_unverified_provenance(
    present: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(AUDIT, "ROOT", tmp_path)
    target = tmp_path / "tests/data/bazi_all_terms_v1/provenance.json"
    if present:
        target.parent.mkdir(parents=True)
        target.write_text("{}")
    else:
        pass
    status = AUDIT.legacy_source_status()
    assert len(status) == 5
    missing = next(
        row
        for row in status
        if Path(row["source_identifier"]).name == "provenance.json"
    )
    assert missing["current_identity_matches"] is False
    assert missing["current_sha256"] == (AUDIT.sha(target) if present else None)
