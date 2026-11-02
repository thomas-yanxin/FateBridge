"""Reviewed source migration retains old assertions and rejects hash-only edits."""

import ast
import hashlib
import importlib.machinery
import importlib.util
import json
import shutil
import tarfile
from pathlib import Path

import pytest

from fatebridge.core import knowledge_revalidation as binding
from fatebridge.core.classical import determine_monthly_structure
from fatebridge.core.knowledge_store import load_knowledge_bundles
from fatebridge.services.knowledge import calculate_knowledge_read

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_structure_binding_v1"
REVIEW = json.loads((FIXTURE / "review.json").read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def historical_module():
    loader = importlib.machinery.SourceFileLoader(
        "reviewed_month_command_before", str(FIXTURE / "classical-before.py.txt")
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_review_binds_original_archive_current_snapshots_and_unchanged_policy():
    assert digest(binding.BINDING_FILE) == REVIEW["runtime_binding_sha256"]
    for filename, expected in REVIEW["snapshots"].items():
        assert digest(FIXTURE / filename) == expected
    archive = ROOT / REVIEW["original_source_archive"]
    assert digest(archive) == REVIEW["original_archive_sha256"]
    with tarfile.open(archive) as source:
        for name, snapshot in [
            ("src/fatebridge/core/classical.py", "classical-before.py.txt"),
            ("src/fatebridge/core/classical_stages.py", "stages-before.py.txt"),
        ]:
            assert source.extractfile(name).read() == (FIXTURE / snapshot).read_bytes()
        raw = source.extractfile("src/fatebridge/utils/data.py").read()
        assert hashlib.sha256(raw).hexdigest() == digest(
            ROOT / "src/fatebridge/utils/data.py"
        )
    assert (
        digest(FIXTURE / "classical-before.py.txt")
        == REVIEW["previous_ref"]["source_sha256"]
    )
    for name, expected in REVIEW["unchanged_month_function_ast_sha256"].items():
        for filename in ["classical-before.py.txt", "classical-reviewed.py.txt"]:
            assert (
                binding._function_digest((FIXTURE / filename).read_text(), name)
                == expected
            )
    before = ast.parse((FIXTURE / "classical-before.py.txt").read_text())
    after = ast.parse((FIXTURE / "classical-reviewed.py.txt").read_text())
    # Only the independently reviewed metadata import and output may differ.
    for node in after.body:
        if isinstance(node, ast.ImportFrom) and node.module.endswith(
            "classical_stages"
        ):
            node.names = [n for n in node.names if n.name != "STAGE_PROFILE_ID"]
        if isinstance(node, ast.FunctionDef) and node.name == "life_stages_for_pillars":
            result = next(n.value for n in node.body if isinstance(n, ast.Return))
            pairs = [
                (k, v)
                for k, v in zip(result.keys, result.values)
                if not (
                    isinstance(k, ast.Constant) and k.value == "life_stage_profile_id"
                )
            ]
            result.keys, result.values = map(list, zip(*pairs))
    assert ast.dump(before, include_attributes=False) == ast.dump(
        after, include_attributes=False
    )
    old_stages = ast.parse((FIXTURE / "stages-before.py.txt").read_text())
    new_stages = ast.parse((FIXTURE / "stages-reviewed.py.txt").read_text())
    for name in ["LU_SEATS", "YANG_BLADE_SEATS"]:
        values = [
            next(
                n.value
                for n in tree.body
                if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
            )
            for tree in [old_stages, new_stages]
        ]
        assert ast.dump(values[0]) == ast.dump(values[1])


def test_all_month_stems_and_branches_keep_old_selection_in_three_branch_contexts():
    old = historical_module()
    stems = "甲乙丙丁戊己庚辛壬癸"
    count = 0
    for day in stems:
        for month in "子丑寅卯辰巳午未申酉戌亥":
            for year_stem in stems:
                for hour_stem in stems:
                    for branches in [
                        ("子", "午", "酉"),
                        ("申", "辰", "子"),
                        ("亥", "卯", "未"),
                    ]:
                        chart = dict(
                            year=(year_stem, branches[0]),
                            month=("甲", month),
                            day=(day, branches[1]),
                            hour=(hour_stem, branches[2]),
                        )
                        assert determine_monthly_structure(chart, day) == (
                            old.determine_monthly_structure(chart, day)
                        )
                        count += 1
    assert count == 36000


@pytest.mark.parametrize("key", REVIEW["keys"])
def test_only_reviewed_implementation_metadata_changes_and_old_ref_is_retained(key):
    original = load_knowledge_bundles()["bazi"]["categories"]["structures"][key]
    result = calculate_knowledge_read(domain="bazi", key=key)
    curation = result["provenance"]["entry_curation"]
    assert result["tips"] == original["tips"]
    assert curation["source_refs"] == original["curation"]["source_refs"]
    assert curation["entry_revision"] == original["curation"]["entry_revision"]
    assert curation["validation_status"] == original["curation"]["validation_status"]
    assert curation["implementation_ref_history"][-1]["previous_ref"] == (
        original["curation"]["implementation_refs"][0]
    )
    assert curation["implementation_refs"][0]["source_sha256"] == digest(
        ROOT / "src/fatebridge/core/classical.py"
    )
    assert not curation["implementation_revalidation"]["classical_acceptance_changed"]
    curation["implementation_ref_history"][-1]["previous_ref"]["source_sha256"] = "bad"
    again = calculate_knowledge_read(domain="bazi", key=key)
    assert (
        again["provenance"]["entry_curation"]["implementation_ref_history"][-1][
            "previous_ref"
        ]
        == REVIEW["previous_ref"]
    )


@pytest.fixture
def isolated_binding(tmp_path, monkeypatch):
    for relative in REVIEW["current_package_files"]:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(binding.PACKAGE_ROOT / relative, target)
    path = tmp_path / "binding.json"
    shutil.copy2(binding.BINDING_FILE, path)
    monkeypatch.setattr(binding, "PACKAGE_ROOT", tmp_path)
    monkeypatch.setattr(binding, "BINDING_FILE", path)
    return tmp_path, path


def test_changed_dependency_cannot_reuse_an_approved_reference(isolated_binding):
    root, _ = isolated_binding
    path = root / "core/classical_stages.py"
    path.write_text(path.read_text() + "\n# unreviewed edit\n")
    curation = {"implementation_refs": [REVIEW["previous_ref"]]}
    with pytest.raises(RuntimeError, match="bytes need renewed review"):
        binding.revalidate_structure_curation("structures", "正官格", curation)


def test_merely_updating_whole_file_sha_cannot_bless_a_changed_rule(isolated_binding):
    root, path = isolated_binding
    source = root / "core/classical.py"
    source.write_text(source.read_text().replace("chosen = (", "chosen = bool(1) or ("))
    record = json.loads(path.read_text())
    record["current_package_files"]["core/classical.py"] = digest(source)
    path.write_text(json.dumps(record))
    curation = {"implementation_refs": [REVIEW["previous_ref"]]}
    with pytest.raises(RuntimeError, match="policy needs renewed review"):
        binding.revalidate_structure_curation("structures", "正官格", curation)
