"""A long calendar audit must reject changes outside its old13-file list."""

import os
from pathlib import Path

import pytest

from fatebridge.validation.meihua_source_guard import (
    capture_package_sources,
    verify_package_sources,
)

PREVIOUSLY_UNTRACKED = [
    "core/calendar.py",
    "core/requests/meihua.py",
    "core/meihua_stage_emphasis.py",
    "data/meihua/stage-emphasis-nlc1925-v1.json",
    "utils/civil_clock.py",
]


@pytest.fixture
def package(tmp_path):
    for name in ["__init__.py", "services/divination.py", *PREVIOUSLY_UNTRACKED]:
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{"value":1}\n' if p.suffix == ".json" else "VALUE = 1\n")
    return tmp_path


@pytest.mark.parametrize("name", PREVIOUSLY_UNTRACKED)
def test_previously_untracked_change_is_detected_despite_same_size_and_time(
    package, name
):
    receipt = capture_package_sources(package)
    path = package / name
    stamp = path.stat()
    original = path.read_bytes()
    changed = original.replace(b"1", b"2")
    assert len(original) == len(changed) and original != changed
    path.write_bytes(changed)
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    with pytest.raises(ValueError, match="changed during audit"):
        verify_package_sources(package, receipt)


def test_added_runtime_policy_is_detected(package):
    receipt = capture_package_sources(package)
    (package / "data/new-runtime-policy.json").write_text('{"value":2}')
    with pytest.raises(ValueError, match="changed during audit"):
        verify_package_sources(package, receipt)


def test_removed_runtime_source_is_detected(package):
    receipt = capture_package_sources(package)
    (package / "core/calendar.py").unlink()
    with pytest.raises(ValueError, match="changed during audit"):
        verify_package_sources(package, receipt)


def test_bytecode_cache_writes_do_not_invalidate_source_receipt(package):
    receipt = capture_package_sources(package)
    cache = package / "core/__pycache__"
    cache.mkdir()
    (cache / "calendar.cpython-312.pyc").write_bytes(b"cache")
    verify_package_sources(package, receipt)
    assert capture_package_sources(package) == receipt


def test_empty_package_cannot_produce_a_passing_empty_receipt(tmp_path):
    with pytest.raises(ValueError, match="source files"):
        capture_package_sources(tmp_path)


@pytest.mark.parametrize("name", ["baseline", "supported", "tam1900", "hko2100"])
def test_all_calendar_audits_capture_package_before_reading_references(
    name, monkeypatch, tmp_path
):
    from fatebridge.validation import meihua, meihua_calendar

    module = meihua if name == "baseline" else meihua_calendar

    def blocked(package):
        assert package.name == "fatebridge"
        raise ValueError("controlled_package_guard_failure")

    monkeypatch.setattr(module, "capture_package_sources", blocked)
    with pytest.raises(ValueError, match="controlled_package_guard_failure"):
        if name == "baseline":
            module.audit_meihua(tmp_path)
        elif name == "supported":
            module.audit_supported_calendar(tmp_path, tmp_path)
        elif name == "tam1900":
            module.audit_tam_1900(tmp_path)
        else:
            module.audit_hko_2100_supplement(tmp_path)


def test_real_package_receipt_covers_indirect_calendar_and_current_rules():
    import fatebridge

    receipt = capture_package_sources(Path(fatebridge.__file__).parent)
    assert all(name in receipt for name in PREVIOUSLY_UNTRACKED)
    assert "validation/meihua_source_guard.py" in receipt
