"""The new guard keeps the old negative receipts and expands dependency coverage."""

import gzip
import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from tests import meihua_instant_source_evolution as instant
from tests import meihua_source_evolution_reference as evolution
from tests.meihua_guard_originals import historical_package_root
from tests.meihua_iso_clock_source_evolution import (
    assert_prior_fractional_scope as assert_only_fractional_parsing_changed,
)
from tests.test_meihua_source_evolution import FROZEN, clone_package


def test_complete_native_public_and_fault_queues_are_kept_separate_and_intact():
    data = instant.load()
    assert data["native_cases"] == 23927
    assert data["guarded_public_time_contexts"] == 340
    assert data["bound_new_clock_contexts"] == 25
    assert data["standalone_before_guard_false_acceptances"] == 34
    assert data["public_before_false_acceptances"] == 30
    assert data["public_after_false_acceptances"] == 0
    assert data["existing_public_rejections_preserved"] == 4
    assert not data["original_v63_source_guard_relabelled_passed"]
    assert not data["physical_clock_or_prediction_accuracy_certified"]
    full, named = evolution.reviewed_source_guards(FROZEN, historical_package_root())
    assert len(full) == 127 and sum(map(len, named.values())) == 30
    assert instant.DEPENDENCIES <= full.keys()
    assert set(named["utils/places.py"]) == {"DEFAULT_BIRTH_TIMEZONE"}


@pytest.mark.parametrize(
    "path", ["application/meihua_clock_binding.py", *sorted(instant.DEPENDENCIES)]
)
def test_complete_new_validator_and_trusted_clock_dependencies_are_guarded(
    path, tmp_path
):
    root = clone_package(tmp_path)
    p = root / path
    p.write_bytes(p.read_bytes() + b"\n# unreviewed\n")
    with pytest.raises(ValueError, match="source file changed"):
        evolution.reviewed_source_guards(FROZEN, root)


def test_default_timezone_assignment_is_guarded_independently_of_other_place_code(
    tmp_path,
):
    root = clone_package(tmp_path)
    p = root / "utils/places.py"
    s = p.read_text()
    assert 'DEFAULT_BIRTH_TIMEZONE = "Asia/Shanghai"' in s
    p.write_text(
        s.replace(
            'DEFAULT_BIRTH_TIMEZONE = "Asia/Shanghai"',
            'DEFAULT_BIRTH_TIMEZONE = "UTC"',
            1,
        )
    )
    with pytest.raises(ValueError, match="default-timezone AST changed"):
        evolution.reviewed_source_guards(FROZEN, root)


def test_original_minute_binding_cannot_be_weakened_while_adding_the_new_guard(
    tmp_path,
):
    root = clone_package(tmp_path)
    p = root / "application/meihua_clock_binding.py"
    s = p.read_text()
    assert '== "not_assessed"' not in s
    assert_only_fractional_parsing_changed(
        root, instant.FOLDER / "after-clock-binding.py"
    )
    needle = 'scope["calendar_stability"] != "not_assessed"'
    assert needle in s
    p.write_text(s.replace(needle, "False", 1))
    with pytest.raises(ValueError, match="Preexisting clock binding AST"):
        assert_only_fractional_parsing_changed(
            root, instant.FOLDER / "after-clock-binding.py"
        )


def test_cached_new_reference_checks_original_bytes_again(tmp_path, monkeypatch):
    instant.load()
    folder = tmp_path / "reference"
    shutil.copytree(instant.FOLDER, folder)
    monkeypatch.setattr(instant, "FOLDER", folder)
    p = folder / "after-native23927.json.gz"
    p.write_bytes(p.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Instant evolution reference changed"):
        instant.load()


@pytest.mark.parametrize(
    "mutation",
    [
        "drop_original_native",
        "rebind_native",
        "drop_public_time",
        "drop_new_clock",
        "hide_old_failure",
    ],
)
def test_repinning_checksums_does_not_allow_smaller_or_changed_original_gates(
    mutation, tmp_path, monkeypatch
):
    folder = tmp_path / "reference"
    shutil.copytree(instant.FOLDER, folder)
    if mutation in {"drop_original_native", "rebind_native"}:
        names = ["before-native23927.json.gz", "after-native23927.json.gz"]
        for name in names:
            p = folder / name
            data = json.loads(gzip.decompress(p.read_bytes()))
            if mutation == "drop_original_native":
                data.pop()
            else:
                data[0]["expected_sha256"] = data[0]["actual_sha256"] = "0" * 64
            p.write_bytes(
                gzip.compress(json.dumps(data, ensure_ascii=False).encode(), mtime=0)
            )
    elif mutation in {"drop_public_time", "drop_new_clock"}:
        suffix = "public-time340" if mutation == "drop_public_time" else "bound-clock25"
        for stage in ["before", "after"]:
            p = folder / f"{stage}-{suffix}.json.gz"
            data = json.loads(gzip.decompress(p.read_bytes()))
            data.pop()
            p.write_bytes(
                gzip.compress(json.dumps(data, ensure_ascii=False).encode(), mtime=0)
            )
    else:
        p = folder / "binding.json"
        data = json.loads(p.read_bytes())
        data["original_v63_source_guard_relabelled_passed"] = True
        p.write_text(json.dumps(data))
    manifest = json.loads((folder / "manifest.json").read_bytes())
    for name in manifest["files"]:
        manifest["files"][name] = hashlib.sha256(
            (folder / name).read_bytes()
        ).hexdigest()
    (folder / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(instant, "FOLDER", folder)
    monkeypatch.setattr(
        instant,
        "MANIFEST_SHA256",
        hashlib.sha256((folder / "manifest.json").read_bytes()).hexdigest(),
    )
    with pytest.raises(
        ValueError,
        match="queue shrunk|identity or complete output changed|failed gates erased",
    ):
        instant.load()
