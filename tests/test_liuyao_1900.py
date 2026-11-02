"""The primary 1900 audit keeps its denominator and every failure."""

from datetime import date

import pytest

from scripts import audit_liuyao_1900 as primary


def test_full_1900_supported_cohort_matches_frozen_primary_cells_and_day_anchor():
    result = primary.audit()
    assert result["primary_printed_date_count"] == 365
    assert result["unique_supported_date_count"] == 365
    assert result["excluded_before_supported_start"] == 0
    assert result["newly_supported_prefix_count"] == 30
    assert result["hko_1901_seam_passed"]
    assert result["selected_checks_passed"]
    assert sum(r["day_checks"] for r in result["reports"]) == 1460
    assert sum(r["lunar_checks"] for r in result["reports"]) == 730


def test_missing_lunar_and_wrong_days_cannot_shrink_the_primary_cohort(monkeypatch):
    monkeypatch.setattr(
        primary,
        "build_sixyao_result",
        lambda **kw: {
            "nongli": {"dayGanZi": "错误"},
            "calendar_context": {"lunar_calendar": None},
        },
    )
    result = primary.audit()
    assert result["unique_supported_date_count"] == 365
    assert sum(len(r["mismatches"]) for r in result["reports"]) == 1460
    assert sum(len(r["lunar_unavailable"]) for r in result["reports"]) == 730
    assert not result["selected_checks_passed"]


def test_reducing_the_production_supported_range_cannot_improve_acceptance(monkeypatch):
    monkeypatch.setattr(
        "fatebridge.core.almanac.LUNAR_SUPPORTED_SOLAR_START", date(1900, 2, 1)
    )
    with pytest.raises(ValueError, match="do not shrink"):
        primary.audit()


def test_primary_comparisons_cannot_pass_after_source_changes(monkeypatch):
    real_hashes = primary.hashes
    calls = 0

    def changed_hashes():
        nonlocal calls
        calls += 1
        values = real_hashes()
        if calls > 1:
            values["src/fatebridge/core/local_techniques/sixyao.py"] = "changed"
        return values

    monkeypatch.setattr(primary, "hashes", changed_hashes)
    report = primary.audit()
    assert all(not r["mismatches"] for r in report["reports"])
    assert not report["implementation_and_manifests_unchanged"]
    assert not report["selected_checks_passed"]
