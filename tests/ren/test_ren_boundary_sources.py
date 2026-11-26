"""Current local HKO source identity gates run before candidate calculations."""

from pathlib import Path

import pytest

from scripts.ren import audit_ren_boundary_decisions as audit


def test_changed_annual_manifest_is_rejected_before_reading_any_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ref = audit.reference()
    monkeypatch.setattr(audit, "reference", lambda: ref)
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    manifest = tmp_path / "tests/data/ziwei_independent/calendar_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}")
    seen = []

    def observe_source_map():
        seen.append("candidate")
        return {}

    monkeypatch.setattr(audit, "source_map", observe_source_map)
    with pytest.raises(ValueError, match="Original HKO annual manifest changed"):
        audit.audit("empty_auto_de440", tmp_path, None)
    assert seen == []
