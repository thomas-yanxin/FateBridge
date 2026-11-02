"""The seconds migration must retain every prior guard and output identity."""

import json
from pathlib import Path

import pytest

from tests import meihua_second_source_evolution as second
from tests import meihua_source_evolution_reference as evolution
from tests.test_meihua_source_evolution import FROZEN, clone_package, reset_cache


def test_all_23595_old_outputs_stay_bound_to_the_previous_18577():
    binding = second.load()
    assert binding["native_receipt_rows"] == 23595
    assert binding["retained_previous_rows"] == 18577
    assert not binding["previous_source_guard_passed"]
    assert not binding["original_historical_hash_gate_passed"]
    assert binding["new_independent_prediction_observations"] == 0


@pytest.mark.parametrize(
    "path",
    ["core/meihua_clock.py", "services/divination.py", "core/requests/divination.py"],
)
def test_changed_clock_sources_are_rejected(path, tmp_path, reset_cache):
    root = clone_package(tmp_path)
    p = root / path
    p.write_text(
        p.read_text().replace("analysis_second", "unreviewed_second")
        if "analysis_second" in p.read_text()
        else p.read_text().replace("wall.second", "wall.second + 1")
    )
    with pytest.raises(ValueError):
        evolution.reviewed_source_guards(FROZEN, root)


@pytest.mark.parametrize(
    "path,before,after",
    [
        (
            "services/divination.py",
            "        analysis_hour,\n",
            "        analysis_hour + 1,\n",
        ),
        (
            "core/requests/divination.py",
            'description="Analysis hour (0-23)"',
            'description="Changed old hour contract"',
        ),
        (
            "core/meihua_clock.py",
            '"calendar_zone_replaced_by_offset": False',
            '"calendar_zone_replaced_by_offset": True',
        ),
    ],
)
def test_unrelated_semantics_fail_even_without_hash_checks(
    path, before, after, tmp_path
):
    root = clone_package(tmp_path)
    from tests.meihua_clock_integration_reference import scope_before_folder
    from tests.meihua_fractional_source_evolution import (
        reviewed_clock_source_scope as assert_clock_source_scope,
    )

    assert_clock_source_scope(root, scope_before_folder())
    p = root / path
    text = p.read_text()
    assert before in text
    p.write_text(text.replace(before, after, 1))
    with pytest.raises(ValueError, match="AST changed outside|Old clock facts changed"):
        assert_clock_source_scope(root, scope_before_folder())


def test_cached_second_reference_drift_is_checked_again(tmp_path, monkeypatch):
    second.load()
    import shutil

    shutil.copytree(second.FOLDER, tmp_path / "reference")
    monkeypatch.setattr(second, "FOLDER", tmp_path / "reference")
    p = second.FOLDER / "native-after.json.gz"
    p.write_bytes(p.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Second input reference changed"):
        from tests.meihua_guard_originals import historical_package_root

        evolution.reviewed_source_guards(FROZEN, historical_package_root())
