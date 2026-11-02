"""The additive table cannot excuse source drift or arbitrary output changes."""

import json
import shutil
from copy import deepcopy

import pytest

from fatebridge.services.meihua import calculate_meihua_cast
from tests import meihua_candidate_history_reference as history
from tests import meihua_volume5_source_evolution as evolution
from tests.meihua_volume5_source_scope import (
    assert_old_iso_guard_body_preserved,
    assert_only_volume5_comparison_added,
)
from tests.test_meihua_source_evolution import FROZEN, clone_package

ARGS = {
    "casting": {"method": "existing", "hexagram_code": "000000", "moving_line": 1},
    "interpretation_topic": "general",
}


def test_scope_is_127_full_30_named_and_original_raw_failures_stay_visible():
    data = evolution.load()
    assert data["raw_after_guard_passed"] is False
    assert data["raw_original_complete_output_equality_relabelled_passed"] is False
    assert data["raw_complete_output_changes"] == 21991
    assert data["original_weather_output_hashes_unchanged"] == 1936
    from tests.meihua_source_evolution_reference import reviewed_source_guards

    full, named = reviewed_source_guards(FROZEN, history._package_root())
    assert len(full) == 127 and sum(map(len, named.values())) == 30
    assert set(data["after_full_files"]) <= full.keys()


@pytest.mark.parametrize("path", sorted(evolution.NEW | {evolution.SEASONAL}))
def test_every_added_or_modified_production_file_is_still_complete_byte_guarded(
    path, tmp_path
):
    root = clone_package(tmp_path)
    p = root / path
    p.write_bytes(p.read_bytes() + b" ")
    from tests.meihua_source_evolution_reference import reviewed_source_guards

    with pytest.raises(ValueError, match="source file changed"):
        reviewed_source_guards(FROZEN, root)


def test_old_seasonal_logic_cannot_change_even_if_a_hash_were_rebound(tmp_path):
    root = clone_package(tmp_path)
    assert_only_volume5_comparison_added(
        root, evolution.FOLDER / "before-seasonal-reading.py"
    )
    p = root / evolution.SEASONAL
    raw = p.read_text()
    assert '"basis": seasonal["basis"] if seasonal is not None else None' in raw
    p.write_text(
        raw.replace(
            '"basis": seasonal["basis"] if seasonal is not None else None',
            '"basis": "changed"',
            1,
        )
    )
    with pytest.raises(ValueError, match="Existing seasonal AST"):
        assert_only_volume5_comparison_added(
            root, evolution.FOLDER / "before-seasonal-reading.py"
        )


def test_original_125_guard_body_and_other_helpers_are_preserved(tmp_path):
    from tests.meihua_guard_originals import original_helper

    current = original_helper("meihua_iso_clock_source_evolution.py")
    before = evolution.FOLDER / "before-meihua_iso_clock_source_evolution.py"
    assert_old_iso_guard_body_preserved(current, before)
    p = tmp_path / "helper.py"
    raw = current.read_text()
    assert "len(full) == 124" in raw
    p.write_text(raw.replace("len(full) == 124", "len(full) >= 1", 1))
    with pytest.raises(ValueError, match="Original v66 guard body"):
        assert_old_iso_guard_body_preserved(p, before)
    for name in [
        "meihua_candidate_history_reference.py",
        "meihua_clock_evolution_reference.py",
        "meihua_source_evolution_reference.py",
    ]:
        assert (current.parent / name).read_bytes() == (
            evolution.FOLDER / ("before-" + name)
        ).read_bytes()


@pytest.mark.parametrize(
    "name",
    ["binding.json", "added-layer-deduplicated.json.gz", "before-seasonal-reading.py"],
)
def test_reference_bytes_are_checked_after_cache_load(name, tmp_path, monkeypatch):
    evolution.load()
    folder = tmp_path / "reference"
    shutil.copytree(evolution.FOLDER, folder)
    monkeypatch.setattr(evolution, "FOLDER", folder)
    evolution.load()
    p = folder / name
    p.write_bytes(p.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Volume-five reference changed"):
        evolution.load()


def test_repinning_manifest_constant_cannot_relabel_raw_failures(tmp_path, monkeypatch):
    folder = tmp_path / "reference"
    shutil.copytree(evolution.FOLDER, folder)
    p = folder / "binding.json"
    data = json.loads(p.read_bytes())
    data["raw_after_guard_passed"] = True
    p.write_text(json.dumps(data))
    manifest = json.loads((folder / "manifest.json").read_bytes())
    manifest["files"][p.name] = evolution.sha(p.read_bytes())
    (folder / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(evolution, "FOLDER", folder)
    monkeypatch.setattr(
        evolution,
        "MANIFEST_SHA256",
        evolution.sha((folder / "manifest.json").read_bytes()),
    )
    with pytest.raises(ValueError, match="Original failures"):
        evolution.load()


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "unapproved_state",
        "summary",
        "extra",
        "foreign_month",
        "foreign_body",
        "foreign_fact_path",
    ],
)
def test_current_output_addition_must_be_complete_approved_and_bound_to_its_parent(
    mutation,
):
    value = calculate_meihua_cast(**ARGS)
    q = value["interpretation"]["seasonal_qualification"]
    layer = q["volume5_table_comparison"]
    if mutation == "missing":
        del q["volume5_table_comparison"]
    elif mutation == "unapproved_state":
        layer["roles"][0]["table_state"] = "死"
    elif mutation == "summary":
        layer["summary"] += "保证成功"
    elif mutation == "extra":
        layer["unlisted"] = True
    elif mutation == "foreign_month":
        q["month_branch"] = "寅"
    elif mutation == "foreign_body":
        q["roles"][0]["trigram"] = "乾"
    else:
        q["roles"][0]["fact_path"] = "foreign.path"
    with pytest.raises(ValueError, match="Native current output"):
        evolution.reviewed_previous_output_shape(value)


def test_projection_keeps_other_fields_and_old_full_hash_gate_still_checks_them():
    value = calculate_meihua_cast(**ARGS)
    saved = deepcopy(value)
    restored = evolution.reviewed_restore_pre_v58_candidate_summary(
        value, tool="meihua_cast", arguments=ARGS
    )
    assert value == saved
    assert restored == evolution.reviewed_previous_output_shape(value)
    assert history.digest(value) != history.digest(restored)
    assert (
        history.digest(restored)
        == history.binding_for("meihua_cast", ARGS)["current_sha256"]
    )
    value["extra_unrelated"] = True
    assert evolution.reviewed_previous_output_shape(value)["extra_unrelated"] is True
    with pytest.raises(history.HistoryBindingError, match="Native current output"):
        evolution.reviewed_restore_pre_v58_candidate_summary(
            value, tool="meihua_cast", arguments=ARGS
        )
