"""The external-calendar auditor retains failures, gaps and source changes."""

import json
from copy import deepcopy
from datetime import date

import pytest

from scripts.liuyao import audit_liuyao_calendar as audit


def test_naoj_anchor_uses_gregorian_day_distance_and_declared_late_zi():
    _, anchor = audit.reference()
    assert audit.naoj_day(date(2000, 1, 1), late_zi=False, anchor=anchor) == "戊午"
    assert audit.naoj_day(date(2000, 1, 7), late_zi=False, anchor=anchor) == "甲子"
    assert audit.naoj_day(date(2000, 1, 6), late_zi=True, anchor=anchor) == "甲子"
    assert audit.naoj_day(
        date(2000, 2, 28), late_zi=True, anchor=anchor
    ) == audit.naoj_day(date(2000, 2, 29), late_zi=False, anchor=anchor)


def miniature(monkeypatch):
    _, anchor = audit.reference()
    source = {"id": "hko-2000", "kind": "official_calendar", "file": "fixture"}
    row = {
        "date": date(2000, 1, 7),
        "year": 1999,
        "month": 12,
        "day": 1,
        "is_leap_month": False,
    }
    monkeypatch.setattr(audit, "reference", lambda: ({"sources": [source]}, anchor))
    monkeypatch.setattr(audit, "read_source", lambda path: "fixture")
    monkeypatch.setattr(audit, "hko_calendar_rows", lambda text, source: [row])
    return row


def test_audit_does_not_drop_unavailable_lunar_dates_or_wrong_day_pillars(monkeypatch):
    miniature(monkeypatch)
    monkeypatch.setattr(
        audit,
        "build_sixyao_result",
        lambda **kw: {
            "nongli": {"dayGanZi": "错值"},
            "calendar_context": {"lunar_calendar": None},
        },
    )
    result = audit.audit([2000])
    assert result["day_pillar_comparison_count"] == 2
    assert result["mismatch_count"] == 2
    assert result["lunar_unavailable_with_hko_reference"] == 1
    assert result["civil_date_count"] == 1
    assert result["all_performed_comparisons_passed"] is False


def test_audit_rejects_code_mutation_during_an_otherwise_matching_run(monkeypatch):
    row = miniature(monkeypatch)
    changed = False
    original_sha = audit.sha

    def sha(path):
        if changed and str(path).endswith("/sixyao.py"):
            return "mutated"
        return original_sha(path)

    def calculate(**kwargs):
        nonlocal changed
        changed = True
        return {
            "nongli": {
                "dayGanZi": "甲子" if kwargs["time"].startswith("12") else "乙丑"
            },
            "calendar_context": {
                "lunar_calendar": {k: v for k, v in row.items() if k != "date"}
            },
        }

    monkeypatch.setattr(audit, "sha", sha)
    monkeypatch.setattr(audit, "build_sixyao_result", calculate)
    result = audit.audit([2000])
    assert result["mismatch_count"] == 0
    assert result["implementation_unchanged_during_audit"] is False
    assert result["all_performed_comparisons_passed"] is False


def test_independent_reference_hash_cannot_be_regenerated_silently(
    tmp_path, monkeypatch
):
    freeze = json.loads((audit.REFERENCES / "calendar-freeze.json").read_text())
    anchor = json.loads((audit.REFERENCES / "naoj-day-reference.json").read_text())
    changed = deepcopy(anchor)
    changed["day_cycle_offset"] = 50
    (tmp_path / "calendar-freeze.json").write_text(json.dumps(freeze))
    (tmp_path / "naoj-day-reference.json").write_text(json.dumps(changed))
    monkeypatch.setattr(audit, "REFERENCES", tmp_path)
    with pytest.raises(ValueError, match="Frozen independent"):
        audit.reference()


def test_2100_shared_source_segment_is_not_relabelled_as_independent(monkeypatch):
    row = miniature(monkeypatch)
    row["date"] = date(2100, 12, 31)
    _, anchor = audit.reference()
    monkeypatch.setattr(
        audit,
        "reference",
        lambda: (
            {
                "sources": [
                    {"id": "hko-2100", "kind": "official_calendar", "file": "fixture"}
                ]
            },
            anchor,
        ),
    )

    def calculate(**kw):
        return {
            "nongli": {
                "dayGanZi": audit.naoj_day(
                    row["date"], late_zi=kw["time"].startswith("23"), anchor=anchor
                )
            },
            "calendar_context": {
                "lunar_calendar": {k: v for k, v in row.items() if k != "date"}
            },
        }

    # The metadata is intentionally absent. The declared shared-source
    # segment must still be identified by the auditor's fixed date policy.
    monkeypatch.setattr(audit, "build_sixyao_result", calculate)
    result = audit.audit([2100])
    assert result["lunar_engine_source_overlap_count"] == 1
    assert result["lunar_external_reference_other_count"] == 0
    assert result["lunar_comparison_count"] == 1
