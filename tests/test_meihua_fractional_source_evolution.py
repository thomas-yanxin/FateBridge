"""A reviewed parser delta cannot make raw old failure receipts disappear."""

import hashlib
import json
from pathlib import Path

import pytest

from tests import meihua_fractional_source_evolution as fractional
from tests import meihua_source_evolution_reference as evolution
from tests.meihua_fractional_source_scope import (
    PATHS,
    assert_captured_shared_changes,
    assert_prior_guard_body_preserved,
)
from tests.meihua_guard_originals import historical_package_root
from tests.meihua_iso_clock_source_evolution import (
    assert_prior_fractional_scope as assert_only_fractional_parsing_changed,
)
from tests.test_meihua_source_evolution import FROZEN, clone_package


def test_all_original_queues_and_raw_failed_guards_are_preserved():
    data = fractional.load()
    assert not data["raw_v64_source_guard_relabelled_passed"]
    assert data["engineering_receipts_not_new_independent_physical_truth"]
    raw = json.loads((fractional.FOLDER / "raw-v64-source-guards.json").read_bytes())
    assert raw["canonical_v64"]["passed"]
    assert all(
        not raw[k]["passed"]
        for k in [
            "captured_before",
            "after_before_transition",
            "only_v65_production_delta_on_canonical_v64",
        ]
    )
    assert (
        "6 failed, 167 passed"
        in (fractional.FOLDER / "before-three-tests.log").read_text()
    )
    full, named = evolution.reviewed_source_guards(FROZEN, historical_package_root())
    assert len(full) == 127 and sum(map(len, named.values())) == 30
    assert PATHS[2] in full


@pytest.mark.parametrize(
    "name", [*PATHS, "core/meihua_topics.py", "utils/timezones.py"]
)
def test_changed_reviewed_or_unmodified_source_is_rejected(name, tmp_path):
    root = clone_package(tmp_path)
    file = root / name
    file.write_bytes(file.read_bytes() + b"\n# unreviewed\n")
    with pytest.raises(ValueError, match="source file changed"):
        evolution.reviewed_source_guards(FROZEN, root)


def test_exact_scope_passes_before_a_preexisting_predicate_is_changed(tmp_path):
    root = clone_package(tmp_path)
    old = fractional.INPUT_FOLDER / "captured-before" / PATHS[0]
    assert_only_fractional_parsing_changed(root, old)
    file = root / PATHS[0]
    s = file.read_text()
    needle = 'scope["calendar_stability"] != "not_assessed"'
    assert needle in s
    file.write_text(s.replace(needle, "False", 1))
    with pytest.raises(ValueError, match="Preexisting clock binding AST"):
        assert_only_fractional_parsing_changed(root, old)


def test_using_the_old_lossy_parser_is_not_an_allowed_scope_change(tmp_path):
    root = clone_package(tmp_path)
    file = root / PATHS[0]
    s = file.read_text()
    assert "parsed = parse_meihua_clock_label(value)" in s
    file.write_text(
        s.replace(
            "parsed = parse_meihua_clock_label(value)",
            "parsed = datetime.fromisoformat(value)",
            1,
        )
    )
    with pytest.raises(ValueError, match="Fractional parser call changed"):
        assert_only_fractional_parsing_changed(
            root, fractional.INPUT_FOLDER / "captured-before" / PATHS[0]
        )


def test_meihua_request_cannot_change_under_the_canping_review(tmp_path):
    root = clone_package(tmp_path)
    assert_captured_shared_changes(root, fractional.INPUT_FOLDER / "canonical-v64")
    file = root / PATHS[2]
    s = file.read_text()
    needle = "class MeihuaAnalysisRequest"
    assert needle in s
    file.write_text(s.replace(needle, "class ChangedMeihuaAnalysisRequest", 1))
    with pytest.raises(ValueError, match="Shared request AST changed"):
        assert_captured_shared_changes(root, fractional.INPUT_FOLDER / "canonical-v64")


def test_unrelated_clock_helper_cannot_change_under_parser_review(tmp_path):
    root = clone_package(tmp_path)
    file = root / PATHS[1]
    s = file.read_text()
    needle = 'raise ValueError("实际时刻比较必须带时区，不能默认服务器时区")'
    assert needle in s
    file.write_text(s.replace(needle, "return moment", 1))
    with pytest.raises(ValueError, match="Captured civil-clock AST changed"):
        assert_captured_shared_changes(root, fractional.INPUT_FOLDER / "canonical-v64")


def test_prior_guard_body_is_checked_before_and_after_attempted_weakening(tmp_path):
    from tests.meihua_guard_originals import original_helper

    current = original_helper("meihua_source_evolution_reference.py")
    before = fractional.FOLDER / "before-main-helper.py"
    assert_prior_guard_body_preserved(current, before)
    copy = tmp_path / "helper.py"
    s = current.read_text()
    needle = 'require(len(data["rows"]) == 13546, "Original native queue changed")'
    assert needle in s
    copy.write_text(s.replace(needle, "pass", 1))
    with pytest.raises(ValueError, match="Prior v64 source guard body changed"):
        assert_prior_guard_body_preserved(copy, before)


@pytest.mark.parametrize(
    "name",
    [
        "binding.json",
        "before-main-helper.py",
        "before-three-tests.log",
        "before-native23927.json.gz",
    ],
)
def test_frozen_transition_bytes_cannot_be_replaced(name, tmp_path, monkeypatch):
    import shutil

    folder = tmp_path / "evolution"
    shutil.copytree(fractional.FOLDER, folder)
    file = folder / name
    file.write_bytes(file.read_bytes() + b" ")
    monkeypatch.setattr(fractional, "FOLDER", folder)
    with pytest.raises(ValueError, match="Fractional evolution reference changed"):
        fractional.load()
