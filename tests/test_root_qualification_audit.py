"""The isolated v3 kernel cannot silently turn into a different baseline."""

import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_numeric_isolation_keeps_real_downstream_changes_and_unresolved_cases(
    monkeypatch,
):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    audit = importlib.import_module("audit_bazi_root_qualification")
    from fatebridge.core import strength

    evaluate = strength._evaluate
    result = audit.audit(historical_v4_replay=True)
    assert strength._evaluate is evaluate
    assert result["probe_count"] == 485
    assert result["all_numeric_components_unchanged"]
    focus = {r["case_id"]: r for r in result["focus_cases"]}
    changed = focus["published_pair_first_person"]
    assert changed["v3_strength"] == "中和" and changed["v4_strength"] == "强"
    assert changed["v3_vigorous_roots"] == []
    assert changed["v4_vigorous_roots"] == ["month", "hour"]
    assert focus["single_yang_growth_root_source_case"]["v4_strength"] == "弱"
    assert focus["damaged_yang_growth_source_case"]["v4_strength"] == "中和"
    assert focus["body_light_seal_heavy_source_case"]["v4_strength"] == "强"
    assert result["complete_classical_acceptance"] is False
    assert result["real_world_efficacy"] == "not_tested"
    assert result["comparison_mode"] == "historical_v3_to_v4"
    assert result["compared_method_id"] == "season_root_revelation_relations_v4"
    assert result["actual_production_method_id"] == strength.STRENGTH_METHOD_ID


def test_modified_archived_kernel_is_rejected(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    audit = importlib.import_module("audit_bazi_root_qualification")
    altered = tmp_path / "altered.py.txt"
    altered.write_bytes(audit.ARCHIVE.read_bytes() + b"\n")
    monkeypatch.setattr(audit, "ARCHIVE", altered)
    with pytest.raises(ValueError, match="Archived v3 kernel changed"):
        audit.load_v3()


def test_current_extra_changes_cannot_masquerade_as_the_historical_root_only_change(
    monkeypatch,
):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    audit = importlib.import_module("audit_bazi_root_qualification")
    result = audit.audit()
    assert result["comparison_mode"] == "v3_to_current"
    assert not result["all_numeric_components_unchanged"]
    assert result["numeric_differences"]


def test_historical_v4_archive_cannot_be_modified_or_first_report_overwritten(
    monkeypatch, tmp_path
):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    audit = importlib.import_module("audit_bazi_root_qualification")
    changed = tmp_path / "v4.py.txt"
    changed.write_bytes(audit.V4_ARCHIVE.read_bytes() + b"\n")
    monkeypatch.setattr(audit, "V4_ARCHIVE", changed)
    with pytest.raises(ValueError, match="Archived v4 kernel changed"):
        audit.audit(historical_v4_replay=True)
    import sys

    report = ROOT / "docs/validation/bazi-root-qualification-v1.json"
    before = report.read_bytes()
    monkeypatch.setattr(sys, "argv", ["audit", "--output", str(report)])
    with pytest.raises(FileExistsError, match="immutable"):
        audit.main()
    assert report.read_bytes() == before
