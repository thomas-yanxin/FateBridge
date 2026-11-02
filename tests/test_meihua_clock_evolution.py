"""Changed provenance never erases old raw failures or permits unchecked projection."""

import gzip
import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from tests import meihua_clock_evolution_reference as clock
from tests import meihua_clock_integration_reference as integration
from tests import meihua_second_source_evolution as old_seconds
from tests import meihua_source_evolution_reference as evolution
from tests.meihua_fractional_source_evolution import (
    reviewed_clock_source_scope as assert_clock_source_scope,
)
from tests.meihua_guard_originals import historical_package_root
from tests.meihua_volume5_source_evolution import reviewed_restore_clock_before_native
from tests.test_meihua_source_evolution import FROZEN, clone_package


def test_new_guard_keeps_complete_old_scope_and_eight_raw_mismatches_visible():
    data = clock.load()
    binding = data["binding"]
    assert (
        binding["native_cases"] == 23927 and binding["original_native_cases"] == 23595
    )
    assert (
        binding["original_raw_unchanged"] == 23587
        and len(binding["original_raw_changed_indices"]) == 8
    )
    assert not binding["original_full_raw_hash_gate_passed"]
    assert not binding["old_native_receipts_rewritten"]
    assert (
        binding["clock_transition_rows"] == 340
        and binding["new_nullable_minute_admissions"] == 56
    )
    assert binding["new_real_world_observations"] == 0
    full, named = evolution.reviewed_source_guards(FROZEN, historical_package_root())
    assert len(full) == 127 and sum(len(v) for v in named.values()) == 30


def test_original_seconds_semantic_guard_stays_negative_on_new_clock_code():
    root = historical_package_root()
    with pytest.raises(ValueError):
        old_seconds.assert_only_declared_seconds_extensions(root)
    assert_clock_source_scope(root, integration.scope_before_folder())


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
            'default=None,\n        ge=0,\n        le=59,\n        description="Confirmed civil minute',
            'default=0,\n        ge=0,\n        le=59,\n        description="Confirmed civil minute',
        ),
        (
            "transports/mcp.py",
            'if spec.key == "meihua_analysis" else set()',
            "if True else set()",
        ),
        (
            "services/replay_metadata.py",
            'and field == "analysis_minute"',
            'and field.endswith("minute")',
        ),
        (
            "application/execution.py",
            'if spec.key == "meihua_analysis" and request is not None:',
            "if request is not None:",
        ),
    ],
)
def test_semantic_scope_rejects_other_calculations_and_broadened_transport_rules(
    path, before, after, tmp_path
):
    root = clone_package(tmp_path)
    assert_clock_source_scope(root, integration.scope_before_folder())
    p = root / path
    text = p.read_text()
    assert before in text
    p.write_text(text.replace(before, after, 1))
    with pytest.raises(ValueError):
        assert_clock_source_scope(root, integration.scope_before_folder())


@pytest.mark.parametrize(
    "path", ["core/meihua_clock_input.py", "application/meihua_clock_binding.py"]
)
def test_new_complete_source_modules_are_guarded(path, tmp_path):
    root = clone_package(tmp_path)
    p = root / path
    p.write_text(p.read_text() + "\n# changed\n")
    with pytest.raises(ValueError, match="source file changed"):
        evolution.reviewed_source_guards(FROZEN, root)


def test_exact_full_time_receipt_is_checked_before_reversing_only_clock_metadata():
    data = clock.load()
    identity = next(k for k, (_, r) in data["full"].items() if r["index"] < 23595)
    arguments = json.loads(identity)["arguments"]
    from fatebridge.services.divination import calculate_meihua_analysis

    value = calculate_meihua_analysis(**arguments)
    saved = deepcopy(value)
    restored = reviewed_restore_clock_before_native(value, arguments)
    index = data["full"][identity][1]["index"]
    before = next(
        json.loads(line)["before"]
        for line in gzip.open(
            clock.FOLDER / "time-before.jsonl.gz", "rt", encoding="utf-8"
        )
        if json.loads(line)["index"] == index
    )
    assert restored == before and value == saved
    broken = deepcopy(value)
    broken["interpretation"]["comprehensive_judgement"] += "保证成功"
    with pytest.raises(ValueError, match="Native current clock output"):
        reviewed_restore_clock_before_native(broken, arguments)


def test_all_twelve_partial_packets_are_bound_before_historical_projection():
    data = clock.load()
    assert len(data["partial"]) == 12
    for value in data["partial"].values():
        assert clock.restore_clock_before_partial(value["after"]) == value["before"]
    value = deepcopy(next(iter(data["partial"].values()))["after"])
    value["calendar_context"]["lunar_calendar"]["day_ganzhi"] = "wrong"
    with pytest.raises(ValueError, match="intermediate differs"):
        clock.restore_clock_before_partial(value)


def test_cached_clock_reference_is_checked_again_by_bytes(tmp_path, monkeypatch):
    clock.load()
    folder = tmp_path / "reference"
    shutil.copytree(clock.FOLDER, folder)
    monkeypatch.setattr(clock, "FOLDER", folder)
    p = folder / "native-after.json.gz"
    p.write_bytes(p.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Clock evolution reference changed"):
        clock.load()


def test_checksum_only_repin_cannot_shrink_the_current_or_original_queue(
    tmp_path, monkeypatch
):
    folder = tmp_path / "reference"
    shutil.copytree(clock.FOLDER, folder)
    p = folder / "native-after.json.gz"
    rows = json.loads(gzip.decompress(p.read_bytes()))
    rows.pop()
    p.write_bytes(gzip.compress(json.dumps(rows, ensure_ascii=False).encode(), mtime=0))
    manifest = json.loads((folder / "manifest.json").read_bytes())
    manifest["files"][p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    (folder / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    monkeypatch.setattr(clock, "FOLDER", folder)
    monkeypatch.setattr(
        clock,
        "MANIFEST_SHA256",
        hashlib.sha256((folder / "manifest.json").read_bytes()).hexdigest(),
    )
    with pytest.raises(ValueError, match="native queue shrunk"):
        clock.load()


def test_parallel_baseline_keeps_initial_data_and_complete_source_scope():
    original = clock.load()["binding"]
    policy = integration.source_policy(original)
    assert set(policy["seven_modified_module_ast_scope"]) == set(
        original["seven_modified_module_ast_scope"]
    )
    assert policy["changed_named_ast_guards"] == original["changed_named_ast_guards"]
    assert (
        policy["additional_complete_source_guards"]
        == original["additional_complete_source_guards"]
    )
    assert (
        policy["additional_named_ast_guards"]["application/execution.py"]
        != original["additional_named_ast_guards"]["application/execution.py"]
    )


def test_cached_parallel_reference_rechecks_the_original_bytes(tmp_path, monkeypatch):
    original = clock.load()["binding"]
    integration.source_policy(original)
    folder = tmp_path / "integration"
    shutil.copytree(integration.FOLDER, folder)
    monkeypatch.setattr(integration, "FOLDER", folder)
    p = folder / "native-rows.json.gz"
    p.write_bytes(p.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Parallel clock reference changed"):
        integration.source_policy(original)


@pytest.mark.parametrize("mutation", ["drop_row", "change_output", "change_arguments"])
def test_repinning_parallel_rows_cannot_change_the_initial_output_queue(
    mutation, tmp_path, monkeypatch
):
    original = clock.load()["binding"]
    folder = tmp_path / "integration"
    shutil.copytree(integration.FOLDER, folder)
    p = folder / "native-rows.json.gz"
    rows = json.loads(gzip.decompress(p.read_bytes()))
    if mutation == "drop_row":
        rows.pop()
    elif mutation == "change_output":
        rows[0]["actual_sha256"] = rows[0]["expected_sha256"] = "0" * 64
    else:
        rows[0]["arguments"]["question"] = "rebound input"
    p.write_bytes(gzip.compress(json.dumps(rows, ensure_ascii=False).encode(), mtime=0))
    manifest = json.loads((folder / "manifest.json").read_bytes())
    manifest["files"][p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    (folder / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(integration, "FOLDER", folder)
    monkeypatch.setattr(
        integration,
        "MANIFEST_SHA256",
        hashlib.sha256((folder / "manifest.json").read_bytes()).hexdigest(),
    )
    with pytest.raises(ValueError, match="Parallel native clock"):
        integration.source_policy(original)
