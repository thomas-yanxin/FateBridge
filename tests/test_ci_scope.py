"""Regression coverage for CI routing, full-diff handling and its final gate."""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts import ci_scope


@pytest.mark.parametrize(
    "paths",
    [
        ["README.md", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md"],
        ["docs/development-guide.md", "docs/scenario-routing.md"],
        ["docs/audits/old/report.json", "docs/research/result.log"],
        ["docs/audits/results.xml", "docs/research/numbers.csv", "docs/audits/a.txt"],
        ["docs/a space\nand newline.md"],
    ],
)
def test_documentation_changes_use_the_lightweight_checks(paths):
    assert ci_scope.documentation_only(paths)


@pytest.mark.parametrize(
    "path",
    [
        "src/fatebridge/api.py",
        "tests/test_cli.py",
        "tests/fixtures/example.md",
        "pyproject.toml",
        "uv.lock",
        ".python-version",
        ".github/workflows/ci.yml",
        "scripts/ci_scope.py",
        "skills/onda-shiye/SKILL.md",
        "AGENTS.md",
        "docs/AGENTS.md",
        "docs/examples/fengshui-home.json",
        "docs/examples/README.md",
        "tests/fixtures/bazi_classical_v1/provenance/reference-freeze.json",
        "docs/audits/probe.py",
        "docs/unknown.json",
        "unknown-file",
    ],
)
def test_runtime_inputs_and_unknown_paths_keep_the_full_suite(path):
    assert not ci_scope.documentation_only(["README.md", path])


def test_empty_change_does_not_skip_tests():
    assert not ci_scope.documentation_only([])


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def git(*args):
        return subprocess.check_output(["git", *args], text=True).strip()

    git("init", "-b", "main")
    git("config", "user.email", "ci-test@example.invalid")
    git("config", "user.name", "CI routing test")

    def commit(path, text="content"):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        git("add", "--all")
        git("commit", "-m", "fixture")
        return git("rev-parse", "HEAD")

    return git, commit


def test_multi_commit_push_does_not_hide_an_earlier_code_change(repository):
    _, commit = repository
    base = commit("README.md")
    commit("src/engine.py")
    head = commit("docs/guide.md")
    paths = ci_scope.changed_paths(base, head, "push")
    assert set(paths) == {"src/engine.py", "docs/guide.md"}
    assert not ci_scope.documentation_only(paths)


def test_pr_uses_the_merge_base_instead_of_unrelated_base_branch_changes(repository):
    git, commit = repository
    commit("README.md")
    git("checkout", "-b", "docs")
    head = commit("docs/guide.md")
    git("checkout", "main")
    base = commit("src/engine.py")
    assert ci_scope.changed_paths(base, head, "pull_request") == ["docs/guide.md"]
    assert not ci_scope.documentation_only(ci_scope.changed_paths(base, head, "push"))


def test_renames_include_both_paths_and_deletions_are_classified(repository):
    git, commit = repository
    base = commit("src/engine.py")
    git("mv", "src/engine.py", "guide.md")
    head = commit("README.md")
    paths = ci_scope.changed_paths(base, head, "push")
    assert "src/engine.py" in paths
    assert not ci_scope.documentation_only(paths)
    git("rm", "README.md")
    deleted = commit("docs/new.md")
    assert ci_scope.documentation_only(ci_scope.changed_paths(head, deleted, "push"))


def test_null_separated_names_are_not_split_on_newlines(repository):
    _, commit = repository
    base = commit("README.md")
    head = commit("docs/with a\nnewline.md")
    assert ci_scope.changed_paths(base, head, "push") == ["docs/with a\nnewline.md"]


@pytest.mark.parametrize(
    "base,head,event",
    [
        ("0" * 40, "a" * 40, "push"),
        ("", "a" * 40, "push"),
        ("--invalid", "a" * 40, "push"),
        ("a" * 40, "b" * 40, "workflow_dispatch"),
        ("a" * 40, "b" * 40, "push"),
    ],
)
def test_unavailable_diff_runs_full_suite(repository, base, head, event):
    assert ci_scope.changed_paths(base, head, event) is None


def test_script_writes_a_boolean_output_even_when_diff_is_unknown(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "sys.argv", ["ci_scope", "--event", "push", "--base", "", "--head", ""]
    )
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    assert ci_scope.main() == 0
    assert output.read_text() == "full_tests=true\n"


WORKFLOW = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text()
)


def test_workflow_keeps_the_full_matrix_and_isolates_static_checks():
    jobs = WORKFLOW["jobs"]
    assert jobs["test"]["strategy"]["matrix"]["python-version"] == [
        "3.10",
        "3.11",
        "3.12",
        "3.13",
    ]
    assert jobs["test"]["strategy"]["fail-fast"] is False
    for name in ("test", "floor"):
        assert jobs[name]["needs"] == "scope"
        assert jobs[name]["if"] == "needs.scope.outputs.full_tests == 'true'"
        assert any(
            step.get("run", "").startswith("pytest -q") for step in jobs[name]["steps"]
        )
    for step in jobs["test"]["steps"]:
        if step["name"] in {
            "Check formatting",
            "Check import order",
            "Run type checks",
        }:
            assert step["if"] == "matrix.python-version == '3.12'"
    documentation = [
        name
        for name, job in jobs.items()
        for step in job["steps"]
        if "scripts/check_docs.py" in step.get("run", "")
    ]
    assert documentation == ["locked"]
    assert WORKFLOW["concurrency"]["cancel-in-progress"] is True
    assert "github.workflow" in WORKFLOW["concurrency"]["group"]
    assert "github.ref" in WORKFLOW["concurrency"]["group"]
    assert jobs["ci"]["if"] == "always()"
    assert set(jobs["ci"]["needs"]) == {"scope", "locked", "test", "floor"}


@pytest.mark.parametrize(
    "full_tests,scope,locked,tests,floor,success",
    [
        ("true", "success", "success", "success", "success", True),
        ("false", "success", "success", "skipped", "skipped", True),
        ("true", "success", "success", "failure", "success", False),
        ("true", "success", "success", "success", "failure", False),
        ("true", "success", "success", "skipped", "success", False),
        ("false", "success", "failure", "skipped", "skipped", False),
        ("false", "failure", "success", "skipped", "skipped", False),
        ("false", "success", "success", "failure", "skipped", False),
        ("false", "success", "success", "success", "success", False),
        ("true", "success", "success", "cancelled", "success", False),
        ("", "success", "success", "skipped", "skipped", False),
    ],
)
def test_summary_gate_cannot_hide_failed_or_unexpectedly_skipped_jobs(
    full_tests, scope, locked, tests, floor, success
):
    script = WORKFLOW["jobs"]["ci"]["steps"][0]["run"]
    result = subprocess.run(
        ["bash", "-e", "-c", script],
        env={
            **os.environ,
            "FULL_TESTS": full_tests,
            "SCOPE_RESULT": scope,
            "LOCKED_RESULT": locked,
            "TEST_RESULT": tests,
            "FLOOR_RESULT": floor,
        },
    )
    assert (result.returncode == 0) is success
