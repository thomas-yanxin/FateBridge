"""Models must receive exact declared facts, independently of private rubrics."""

import hashlib
import json

import pytest

import scripts.evaluate_agent as evaluator
from fatebridge.validation.evaluation_assets import (
    copy_case_evidence,
    evidence_source_files,
    evidence_specs,
)


def source_tree(root):
    for name in [
        "AGENTS.md",
        "pyproject.toml",
        "uv.lock",
        "src/fatebridge/__init__.py",
        "docs/README.md",
    ]:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    for name, data in [
        ("one", {"fact": 1}),
        ("two", {"fact": 2}),
        ("rubric", {"hidden_answer": "not model evidence"}),
    ]:
        path = root / f"tests/fixtures/{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))


def case(root, name="one"):
    relative = f"tests/fixtures/{name}.json"
    return {
        "id": name,
        "prompt": "Read evidence/input.json and audit the supplied facts.",
        "evidence_files": [
            {
                "source_path": relative,
                "workspace_path": "evidence/input.json",
                "sha256": hashlib.sha256((root / relative).read_bytes()).hexdigest(),
            }
        ],
    }


def test_explicit_evidence_is_frozen_and_each_workspace_gets_only_its_case(tmp_path):
    source = tmp_path / "source"
    source_tree(source)
    first, second = case(source), case(source, "two")
    extras = evidence_source_files([first, second], source)
    frozen = tmp_path / "frozen"
    manifest = evaluator.freeze_source(frozen, source, extra_files=extras)
    assert set(extras) <= set(manifest)
    assert "tests/fixtures/rubric.json" not in manifest
    assert evaluator.source_manifest(frozen, extra_files=extras) == manifest
    for item in [first, second]:
        workspace = tmp_path / item["id"]
        workspace.mkdir()
        evaluator.prepare_workspace(workspace, frozen)
        proof = copy_case_evidence(workspace, item, frozen)
        assert len(proof) == 1
        expected = source / item["evidence_files"][0]["source_path"]
        assert (workspace / "evidence/input.json").read_bytes() == expected.read_bytes()
        assert not (workspace / "tests").exists()
        assert not (workspace / "scripts/evaluate_agent.py").exists()
        assert not (workspace / "evidence/rubric.json").exists()
        assert not (workspace / "evidence/input.json").is_symlink()


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_path", "../outside.json"),
        ("source_path", "/outside.json"),
        ("source_path", "tests//fixtures/one.json"),
        ("source_path", "tests\\one.json"),
        ("workspace_path", "AGENTS.md"),
        ("workspace_path", "evidence/../AGENTS.md"),
        ("workspace_path", "/evidence/one.json"),
        ("workspace_path", "evidence/input.py"),
        ("sha256", "0" * 63),
        ("sha256", "G" * 64),
    ],
)
def test_paths_cannot_escape_or_overwrite_instructions_or_change_type(
    tmp_path, field, value
):
    source_tree(tmp_path)
    item = case(tmp_path)
    item["evidence_files"][0][field] = value
    with pytest.raises(ValueError):
        evidence_specs(item)


def test_changed_evidence_and_symlink_escapes_fail_before_model_execution(
    tmp_path, monkeypatch
):
    source = tmp_path / "source"
    source_tree(source)
    item = case(source)
    (source / "tests/fixtures/one.json").write_text('{"changed":true}')
    with pytest.raises(ValueError, match="SHA-256"):
        evidence_source_files([item], source)
    output = tmp_path / "output"
    output.mkdir()
    monkeypatch.setattr(evaluator, "prepare_workspace", lambda workspace, frozen: None)

    def no_model(*args, **kwargs):
        pytest.fail("Model process must never start before evidence verification")

    monkeypatch.setattr(evaluator.subprocess, "run", no_model)
    with pytest.raises(ValueError, match="SHA-256"):
        evaluator.run_case("must-not-run", item, output, 1, source=source)
    (source / "tests/fixtures/one.json").unlink()
    external = tmp_path / "external.json"
    external.write_text("{}")
    (source / "tests/fixtures/one.json").symlink_to(external)
    with pytest.raises(ValueError, match="inside"):
        evidence_source_files([item], source)


def test_existing_files_and_duplicate_destinations_are_never_overwritten(tmp_path):
    source = tmp_path / "source"
    source_tree(source)
    item = case(source)
    item["evidence_files"].append(dict(item["evidence_files"][0]))
    with pytest.raises(ValueError, match="collide"):
        evidence_specs(item)
    item = case(source)
    workspace = tmp_path / "workspace"
    (workspace / "evidence").mkdir(parents=True)
    destination = workspace / "evidence/input.json"
    destination.write_text("original")
    with pytest.raises(FileExistsError):
        copy_case_evidence(workspace, item, source)
    assert destination.read_text() == "original"


def test_cases_without_declared_evidence_do_not_gain_files(tmp_path):
    assert evidence_source_files([{}], tmp_path) == ()
    assert copy_case_evidence(tmp_path, {}, tmp_path) == []


def test_evidence_only_workspace_excludes_backend_notes_but_keeps_full_tool_backend(
    tmp_path,
):
    source = tmp_path / "source"
    source_tree(source)
    item = {**case(source), "evidence_only_workspace": True}
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    evaluator.prepare_case_workspace(workspace, source, item)
    copy_case_evidence(workspace, item, source)
    assert {
        p.relative_to(workspace).as_posix() for p in workspace.rglob("*") if p.is_file()
    } == {"AGENTS.md", "evidence/input.json"}
    assert (source / "src/fatebridge/__init__.py").is_file()
    assert (source / "tests/fixtures/rubric.json").is_file()
    with pytest.raises(ValueError, match="backend"):
        evaluator.command_for("codex", workspace, tmp_path, item)
    command = evaluator.command_for(
        "codex", workspace, tmp_path, item, backend_source=source
    )
    assert f'mcp_servers.fatebridge.env.PYTHONPATH="{source}/src"' in command
    assert "--model" not in command
