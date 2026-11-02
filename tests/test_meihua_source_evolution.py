"""Reviewed source evolution cannot discard old identities or admit other edits."""

import gzip
import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from tests import meihua_candidate_history_reference as history
from tests import meihua_source_evolution_reference as evolution

FROZEN = json.loads(gzip.decompress((history.FOLDER / "bindings.json.gz").read_bytes()))


@pytest.fixture
def reset_cache():
    evolution._load.cache_clear()
    yield
    evolution._load.cache_clear()


def clone_package(tmp_path):
    root = history._package_root()
    target = tmp_path / "package"
    full, named = evolution.reviewed_source_guards(FROZEN, root)
    for name in (
        set(full)
        | set(named)
        | set(FROZEN["source_guards"])
        | evolution.additional_guarded_source_paths()
    ):
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, dest)
    return target


def test_transition_keeps_original_manifest_and_all_18577_native_identities():
    assert (
        history.MANIFEST_SHA256
        == "e2b35f662272a84c7e7bfcdf24d368332a912ef7a0d7074495a41da0d41c5b02"
    )
    policy, rows = evolution._load()
    assert len(rows) == 18577
    assert (
        not policy["old_source_guard_without_transition_passed"]
        and not policy["original_historical_raw_hash_gate_passed"]
    )
    full, named = evolution.reviewed_source_guards(FROZEN, history._package_root())
    assert len(full) == len(FROZEN["source_guards"]) + 13 == 127
    from tests.meihua_second_source_evolution import load as second_transition

    second = second_transition()
    expected_named = deepcopy(FROZEN["named_ast_guards"])
    expected_named["services/divination.py"]["calculate_meihua_analysis"] = second[
        "named_ast_transitions"
    ]["services/divination.py"]["calculate_meihua_analysis"]["after_sha256"]
    expected_named.update(deepcopy(second["new_named_ast_guards"]))
    from tests.meihua_clock_evolution_reference import load as clock_transition
    from tests.meihua_clock_integration_reference import source_policy

    clock = source_policy(clock_transition()["binding"])
    for path, members in clock["changed_named_ast_guards"].items():
        expected_named[path].update(members)
    for path, members in clock["additional_named_ast_guards"].items():
        expected_named.setdefault(path, {}).update(members)
    from tests.meihua_instant_source_evolution import load as instant_transition

    instant = instant_transition()
    for path, members in instant["additional_named_ast_guards"].items():
        expected_named.setdefault(path, {}).update(members)
    assert named == expected_named
    assert set(n for n, h in FROZEN["source_guards"].items() if h != full[n]) == {
        "core/meihua_topics.py",
        "core/requests/meihua.py",
        "core/meihua_clock.py",
        "core/meihua_seasonal_reading.py",
    }


@pytest.mark.parametrize(
    "name",
    [
        "core/meihua_marriage.py",
        "data/meihua/marriage-nlc1925-v1.json",
        "core/meihua_dining.py",
        "data/meihua/dining-nlc1925-v1.json",
        "core/requests/meihua.py",
        "core/meihua_topics.py",
    ],
)
def test_changed_new_or_reviewed_source_is_still_rejected(name, tmp_path, reset_cache):
    root = clone_package(tmp_path)
    p = root / name
    p.write_bytes(p.read_bytes() + b" ")
    with pytest.raises(ValueError, match="source file changed"):
        evolution.reviewed_source_guards(FROZEN, root)


def test_semantic_scope_check_rejects_old_topic_change_independently_of_hashes(
    tmp_path,
):
    root = clone_package(tmp_path)
    p = root / "core/meihua_topics.py"
    text = p.read_text()
    assert "original_static_body_vs_original_moving_use_only" in text
    p.write_text(
        text.replace(
            "original_static_body_vs_original_moving_use_only", "changed_scope", 1
        )
    )
    with pytest.raises(ValueError, match="Old topic AST"):
        evolution.assert_only_declared_topic_extensions(root)


def test_semantic_scope_check_rejects_default_branch_change_independently_of_hashes(
    tmp_path,
):
    root = clone_package(tmp_path)
    p = root / "core/requests/meihua.py"
    text = p.read_text()
    assert 'default="general"' in text
    p.write_text(text.replace('default="general"', 'default="marriage"', 1))
    with pytest.raises(ValueError, match="Old request AST"):
        evolution.assert_only_declared_topic_extensions(root)


@pytest.mark.parametrize(
    "mutation", ["current_output", "arguments", "drop_original_row"]
)
def test_old_native_queue_cannot_be_rebound_by_a_source_transition(
    mutation, reset_cache
):
    data = deepcopy(FROZEN)
    if mutation == "current_output":
        data["rows"][0]["current_sha256"] = "0" * 64
    elif mutation == "arguments":
        data["rows"][0]["arguments"]["question"] = "unknown"
    else:
        data["rows"].pop()
    with pytest.raises(ValueError, match="Native receipt|Original native queue"):
        evolution.reviewed_source_guards(data, history._package_root())


def test_cached_transition_reference_is_checked_again_after_loading(
    tmp_path, monkeypatch, reset_cache
):
    folder = tmp_path / "evolution"
    shutil.copytree(evolution.FOLDER, folder)
    monkeypatch.setattr(evolution, "FOLDER", folder)
    evolution._load()
    p = folder / "binding.json"
    p.write_bytes(p.read_bytes() + b" ")
    with pytest.raises(ValueError, match="reference changed"):
        evolution.reviewed_source_guards(FROZEN, history._package_root())


def test_checksum_only_repinning_of_native_rows_still_cannot_replace_parent_binding(
    tmp_path, monkeypatch, reset_cache
):
    folder = tmp_path / "evolution"
    shutil.copytree(evolution.FOLDER, folder)
    for name in ["native-before.json.gz", "native-after.json.gz"]:
        data = json.loads(gzip.decompress((folder / name).read_bytes()))
        rows = data["rows"] if isinstance(data, dict) else data
        rows[0]["sha256"] = "0" * 64
        if name == "native-after.json.gz":
            rows[0]["before_sha256"] = "0" * 64
        (folder / name).write_bytes(
            gzip.compress(json.dumps(data, ensure_ascii=False).encode(), mtime=0)
        )
    manifest = json.loads((folder / "manifest.json").read_bytes())
    for name in ["native-before.json.gz", "native-after.json.gz"]:
        manifest["files"][name] = hashlib.sha256(
            (folder / name).read_bytes()
        ).hexdigest()
    (folder / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(evolution, "FOLDER", folder)
    monkeypatch.setattr(
        evolution,
        "MANIFEST_SHA256",
        hashlib.sha256((folder / "manifest.json").read_bytes()).hexdigest(),
    )
    with pytest.raises(ValueError, match="Native receipt"):
        evolution.reviewed_source_guards(FROZEN, history._package_root())


def test_previous_reference_is_rechecked_after_current_transition_cache_load(
    tmp_path, monkeypatch, reset_cache
):
    folder = tmp_path / "previous"
    shutil.copytree(evolution.PREVIOUS_FOLDER, folder)
    monkeypatch.setattr(evolution, "PREVIOUS_FOLDER", folder)
    evolution._load()
    path = folder / "binding.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Previous source evolution reference changed"):
        evolution.reviewed_source_guards(FROZEN, history._package_root())


def test_checksum_repinning_cannot_shrink_the_added_marriage_queue(
    tmp_path, monkeypatch, reset_cache
):
    folder = tmp_path / "current"
    shutil.copytree(evolution.FOLDER, folder)
    for name in ["native-before.json.gz", "native-after.json.gz"]:
        value = json.loads(gzip.decompress((folder / name).read_bytes()))
        rows = value["rows"] if isinstance(value, dict) else value
        rows.pop()
        (folder / name).write_bytes(
            gzip.compress(json.dumps(value, ensure_ascii=False).encode(), mtime=0)
        )
    manifest = json.loads((folder / "manifest.json").read_bytes())
    for name in ["native-before.json.gz", "native-after.json.gz"]:
        manifest["files"][name] = hashlib.sha256(
            (folder / name).read_bytes()
        ).hexdigest()
    (folder / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(evolution, "FOLDER", folder)
    monkeypatch.setattr(
        evolution,
        "MANIFEST_SHA256",
        hashlib.sha256((folder / "manifest.json").read_bytes()).hexdigest(),
    )
    with pytest.raises(ValueError, match="Native queue shrunk"):
        evolution.reviewed_source_guards(FROZEN, history._package_root())
